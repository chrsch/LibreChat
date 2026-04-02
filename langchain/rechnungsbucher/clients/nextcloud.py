"""
Nextcloud WebDAV client — handles all HTTP communication with Nextcloud's WebDAV endpoint.

Supported operations: PROPFIND, GET, PUT, MKCOL, MOVE, DELETE.
Auth: Basic authentication via Authorization header.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote as url_quote

import httpx
from lxml import etree

from config import NextcloudConfig


# ─── Data classes ──────────────────────────────────────────────────

@dataclass
class FileEntry:
    name: str
    path: str
    type: str  # "file" | "folder"
    size_bytes: int
    mime_type: str
    last_modified: str
    etag: str


@dataclass
class DownloadResult:
    filename: str
    mime_type: str
    size_bytes: int
    content: str
    content_type: str  # "text" | "base64"
    pages_extracted: int | None


# ─── Client ───────────────────────────────────────────────────────

PROPFIND_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:prop>
    <d:displayname/>
    <d:getcontentlength/>
    <d:getlastmodified/>
    <d:getcontenttype/>
    <d:resourcetype/>
    <d:getetag/>
  </d:prop>
</d:propfind>"""


class NextcloudClient:
    def __init__(self, config: NextcloudConfig) -> None:
        self.config = config
        url = config.url.rstrip("/")
        webdav_path = config.webdav_path.rstrip("/")
        self.webdav_root = f"{url}{webdav_path}"
        self._client = httpx.Client(
            timeout=config.api_timeout_ms / 1000,
            auth=(config.username, config.password),
        )

    # ── helpers ────────────────────────────────────────────────────

    def _build_url(self, relative_path: str) -> str:
        clean = _sanitize_path(relative_path)
        encoded = "/".join(url_quote(seg, safe="") for seg in clean.split("/"))
        return f"{self.webdav_root}/{encoded}"

    def _href_to_relative(self, href: str) -> str:
        webdav_path = self.config.webdav_path.rstrip("/")
        idx = href.find(webdav_path)
        if idx == -1:
            return href
        rel = href[idx + len(webdav_path) :]
        return rel.strip("/")

    def _parse_multistatus(self, xml_bytes: bytes) -> list[dict]:
        """Parse a WebDAV 207 Multi-Status XML response."""
        root = etree.fromstring(xml_bytes)
        ns = {"d": "DAV:"}
        entries: list[dict] = []
        for resp in root.findall("d:response", ns):
            href_el = resp.find("d:href", ns)
            href = href_el.text if href_el is not None else ""
            propstat = resp.find("d:propstat", ns)
            if propstat is None:
                continue
            prop = propstat.find("d:prop", ns)
            if prop is None:
                continue

            displayname_el = prop.find("d:displayname", ns)
            length_el = prop.find("d:getcontentlength", ns)
            modified_el = prop.find("d:getlastmodified", ns)
            ctype_el = prop.find("d:getcontenttype", ns)
            rtype_el = prop.find("d:resourcetype", ns)
            etag_el = prop.find("d:getetag", ns)

            is_folder = rtype_el is not None and rtype_el.find("d:collection", ns) is not None

            from urllib.parse import unquote
            rel_path = self._href_to_relative(unquote(href or ""))
            name = (displayname_el.text if displayname_el is not None and displayname_el.text else "") or rel_path.split("/")[-1] if rel_path else ""

            entries.append(
                {
                    "name": name,
                    "path": rel_path,
                    "type": "folder" if is_folder else "file",
                    "size_bytes": int(length_el.text) if length_el is not None and length_el.text else 0,
                    "mime_type": ctype_el.text if ctype_el is not None and ctype_el.text else "",
                    "last_modified": modified_el.text if modified_el is not None and modified_el.text else "",
                    "etag": (etag_el.text or "").strip('"') if etag_el is not None else "",
                }
            )
        return entries

    @staticmethod
    def _handle_http_error(resp: httpx.Response, path: str) -> Exception:
        status = resp.status_code
        if status in (401, 403):
            return Exception("Authentication failed. Check NEXTCLOUD_USERNAME and NEXTCLOUD_PASSWORD.")
        if status == 404:
            return Exception(f"File or folder not found: {path}")
        if status == 409:
            return Exception(f"Conflict: parent directory may not exist. Path: {path}")
        if status == 412:
            return Exception("Destination already exists (overwrite is disabled).")
        return Exception(f"HTTP {status} {resp.reason_phrase}")

    # ── PROPFIND (list / info) ─────────────────────────────────────

    def list_files(self, path: str = "") -> list[FileEntry]:
        url = self._build_url(path)
        resp = self._client.request(
            "PROPFIND",
            url,
            content=PROPFIND_BODY,
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
        )
        if resp.status_code not in (200, 207):
            raise self._handle_http_error(resp, path)

        entries = self._parse_multistatus(resp.content)
        # First entry is the directory itself — skip it
        return [FileEntry(**e) for e in entries[1:]]

    def get_file_info(self, path: str) -> FileEntry:
        url = self._build_url(path)
        resp = self._client.request(
            "PROPFIND",
            url,
            content=PROPFIND_BODY,
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "0"},
        )
        if resp.status_code not in (200, 207):
            raise self._handle_http_error(resp, path)

        entries = self._parse_multistatus(resp.content)
        if not entries:
            raise Exception(f"No response from server for path: {path}")
        return FileEntry(**entries[0])

    def search_files(self, query: str, path: str = "", max_results: int = 50) -> list[FileEntry]:
        url = self._build_url(path)
        resp = self._client.request(
            "PROPFIND",
            url,
            content=PROPFIND_BODY,
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "infinity"},
        )
        if resp.status_code not in (200, 207):
            raise self._handle_http_error(resp, path)

        entries = self._parse_multistatus(resp.content)
        lower_q = query.lower()
        matches: list[FileEntry] = []
        for e in entries[1:]:
            if lower_q in e["name"].lower():
                matches.append(FileEntry(**e))
                if len(matches) >= max_results:
                    break
        return matches

    # ── GET (download) ─────────────────────────────────────────────

    def download_file(self, path: str) -> tuple[bytes, str, int]:
        """Download a file. Returns (raw_bytes, mime_type, size)."""
        url = self._build_url(path)
        resp = self._client.get(url)
        if not resp.is_success:
            raise self._handle_http_error(resp, path)

        mime = (resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
        return resp.content, mime, len(resp.content)

    # ── PUT (upload) ───────────────────────────────────────────────

    def upload_file(self, path: str, content: bytes, mime_type: str) -> int:
        url = self._build_url(path)
        resp = self._client.put(url, content=content, headers={"Content-Type": mime_type})
        if resp.status_code not in (200, 201, 204):
            raise self._handle_http_error(resp, path)
        return len(content)

    # ── MKCOL (create folder) ─────────────────────────────────────

    def create_folder(self, path: str) -> bool:
        """Create a single directory. Returns True if created, False if existed."""
        url = self._build_url(path)
        resp = self._client.request("MKCOL", url)
        if resp.status_code == 201:
            return True
        if resp.status_code == 405:
            return False  # already exists
        if not resp.is_success:
            raise self._handle_http_error(resp, path)
        return True

    def create_folder_recursive(self, path: str) -> dict:
        """Create a directory including all intermediate parents (mkdir -p)."""
        clean = _sanitize_path(path)
        segments = [s for s in clean.split("/") if s]
        created: list[str] = []
        existed: list[str] = []
        current = ""
        for segment in segments:
            current = f"{current}/{segment}" if current else segment
            if self.create_folder(current):
                created.append(current)
            else:
                existed.append(current)
        return {"created": created, "existed": existed}

    # ── MOVE (rename / move) ──────────────────────────────────────

    def move(self, source_path: str, destination_path: str) -> None:
        source_url = self._build_url(source_path)
        dest_url = self._build_url(destination_path)
        resp = self._client.request(
            "MOVE",
            source_url,
            headers={"Destination": dest_url, "Overwrite": "F"},
        )
        if resp.status_code not in (200, 201, 204):
            raise self._handle_http_error(resp, source_path)

    # ── DELETE ─────────────────────────────────────────────────────

    def delete(self, path: str) -> None:
        url = self._build_url(path)
        resp = self._client.delete(url)
        if resp.status_code not in (200, 204):
            raise self._handle_http_error(resp, path)


# ─── Path utilities ───────────────────────────────────────────────

def _sanitize_path(path: str) -> str:
    """Sanitize a path to prevent directory traversal attacks."""
    cleaned = path.strip().strip("/")
    for seg in cleaned.split("/"):
        if seg in ("..", "."):
            raise ValueError(f'Invalid path: "{path}" — path traversal (.. or .) is not allowed.')
    return cleaned
