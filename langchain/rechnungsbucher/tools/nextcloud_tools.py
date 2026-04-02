"""
LangChain tool wrappers for Nextcloud WebDAV file operations.

Each tool mirrors the corresponding MCP tool from the Nextcloud-WebDAV MCP server.
"""

from __future__ import annotations

import base64
import json
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from clients.nextcloud import NextcloudClient
from config import NextcloudConfig

# Module-level client — initialised by init_nextcloud_tools()
_client: NextcloudClient | None = None


def init_nextcloud_tools(config: NextcloudConfig) -> None:
    """Initialise the module-level Nextcloud client."""
    global _client
    _client = NextcloudClient(config)


def _get_client() -> NextcloudClient:
    if _client is None:
        raise RuntimeError("Nextcloud tools not initialised. Call init_nextcloud_tools() first.")
    return _client


def _extract_pdf_text(raw: bytes, max_pages: int = 10) -> tuple[str, int]:
    """Extract text from a PDF buffer using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=raw, filetype="pdf")
    pages_to_read = min(len(doc), max_pages)
    texts: list[str] = []
    for i in range(pages_to_read):
        page = doc[i]
        texts.append(page.get_text())
    doc.close()
    combined = "\n".join(texts).strip()
    return combined, pages_to_read


def _is_text_mime(mime: str) -> bool:
    if mime.startswith("text/"):
        return True
    return mime in ("application/json", "application/xml", "application/xhtml+xml", "application/javascript")


# ─── Tools ─────────────────────────────────────────────────────────


class ListFilesInput(BaseModel):
    path: str = Field(default="", description='Directory path relative to WebDAV root (default: root)')


@tool(args_schema=ListFilesInput)
def nextcloud_list_files(path: str = "") -> str:
    """List files and folders in a directory on Nextcloud.

    Returns name, type (file/folder), size, last modified date, and MIME type for each entry.
    """
    client = _get_client()
    try:
        entries = client.list_files(path)
        result = {
            "path": path or "/",
            "total_entries": len(entries),
            "entries": [
                {
                    "name": e.name,
                    "path": e.path,
                    "type": e.type,
                    "size_bytes": e.size_bytes,
                    "mime_type": e.mime_type,
                    "last_modified": e.last_modified,
                }
                for e in entries
            ],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Error listing files: {exc}"


class DownloadFileInput(BaseModel):
    path: str = Field(description='Path to the file (e.g. "Documents/Invoices/invoice.pdf")')
    max_pages: int = Field(default=10, description="For PDFs: max pages to extract text from (default: 10)")


@tool(args_schema=DownloadFileInput)
def nextcloud_download_file(path: str, max_pages: int = 10) -> str:
    """Download a file from Nextcloud and return its content.

    PDFs are parsed to extracted text (ideal for invoices).
    Text files are returned as-is. Images are returned as base64.
    """
    client = _get_client()
    filename = path.split("/")[-1] or path
    try:
        raw, mime, size = client.download_file(path)

        if mime == "application/pdf":
            text, pages = _extract_pdf_text(raw, max_pages)
            if not text:
                text = (
                    "This PDF appears to be scanned/image-based. Text extraction returned no content. "
                    f"Total size: {size} bytes."
                )
            return json.dumps(
                {"filename": filename, "mime_type": mime, "size_bytes": size, "content": text, "content_type": "text", "pages_extracted": pages},
                indent=2,
                ensure_ascii=False,
            )

        if _is_text_mime(mime):
            return json.dumps(
                {"filename": filename, "mime_type": mime, "size_bytes": size, "content": raw.decode("utf-8", errors="replace"), "content_type": "text", "pages_extracted": None},
                indent=2,
                ensure_ascii=False,
            )

        if mime.startswith("image/"):
            return json.dumps(
                {"filename": filename, "mime_type": mime, "size_bytes": size, "content": base64.b64encode(raw).decode(), "content_type": "base64", "pages_extracted": None},
                indent=2,
            )

        return f"Unsupported file type: {mime}. Supported: PDF, text/*, image/*."
    except Exception as exc:
        return f"Error downloading file: {exc}"


class UploadFileInput(BaseModel):
    path: str = Field(description='Destination path including filename (e.g. "Documents/report.txt")')
    content: str = Field(description="File content: plain text or base64-encoded binary")
    content_type: str = Field(default="text", description='How content is encoded: "text" or "base64"')
    mime_type: str = Field(default="application/octet-stream", description="MIME type for the file")


@tool(args_schema=UploadFileInput)
def nextcloud_upload_file(path: str, content: str, content_type: str = "text", mime_type: str = "application/octet-stream") -> str:
    """Upload content as a file to Nextcloud. Provide text content directly or base64-encoded binary."""
    client = _get_client()
    try:
        if content_type == "base64":
            buf = base64.b64decode(content)
        else:
            buf = content.encode("utf-8")
        size = client.upload_file(path, buf, mime_type)
        return json.dumps({"success": True, "path": path, "size_bytes": size}, indent=2)
    except Exception as exc:
        return f"Error uploading file: {exc}"


class GetFileInfoInput(BaseModel):
    path: str = Field(description="Path to the file or folder")


@tool(args_schema=GetFileInfoInput)
def nextcloud_get_file_info(path: str) -> str:
    """Get detailed metadata for a single file or folder on Nextcloud (size, MIME type, ETag, last modified)."""
    client = _get_client()
    try:
        entry = client.get_file_info(path)
        return json.dumps(
            {"name": entry.name, "path": entry.path, "type": entry.type, "size_bytes": entry.size_bytes, "mime_type": entry.mime_type, "last_modified": entry.last_modified, "etag": entry.etag},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as exc:
        return f"Error getting file info: {exc}"


class SearchFilesInput(BaseModel):
    query: str = Field(description="Search term (case-insensitive substring match against filenames)")
    path: str = Field(default="", description="Directory to search within (default: root)")
    max_results: int = Field(default=50, description="Maximum number of results (default: 50)")


@tool(args_schema=SearchFilesInput)
def nextcloud_search_files(query: str, path: str = "", max_results: int = 50) -> str:
    """Search for files by name on Nextcloud. Performs case-insensitive substring matching."""
    client = _get_client()
    try:
        matches = client.search_files(query, path, max_results)
        result = {
            "query": query,
            "search_path": path or "/",
            "total_matches": len(matches),
            "results": [
                {"name": m.name, "path": m.path, "type": m.type, "size_bytes": m.size_bytes, "mime_type": m.mime_type}
                for m in matches
            ],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Error searching files: {exc}"


class CreateFolderInput(BaseModel):
    path: str = Field(description='Path of the folder to create (e.g. "Invoices/2025/January")')
    create_parents: bool = Field(default=True, description="Create intermediate directories (mkdir -p)")


@tool(args_schema=CreateFolderInput)
def nextcloud_create_folder(path: str, create_parents: bool = True) -> str:
    """Create a new directory on Nextcloud. By default creates intermediate parent directories."""
    client = _get_client()
    try:
        if create_parents:
            result = client.create_folder_recursive(path)
            return json.dumps({"success": True, "path": path, "folders_created": result["created"], "folders_existed": result["existed"]}, indent=2)
        created = client.create_folder(path)
        return json.dumps({"success": True, "path": path, "created": created}, indent=2)
    except Exception as exc:
        return f"Error creating folder: {exc}"


class RenameFileInput(BaseModel):
    path: str = Field(description='Current path of the file/folder (e.g. "Documents/old-name.pdf")')
    new_name: str = Field(description='New filename (name only, not a path — e.g. "new-name.pdf")')


@tool(args_schema=RenameFileInput)
def nextcloud_rename_file(path: str, new_name: str) -> str:
    """Rename a file or folder on Nextcloud (same directory, new name only). Use nextcloud_move_file to move."""
    if "/" in new_name or "\\" in new_name:
        return "Error: new_name must be a filename only, not a path. Use nextcloud_move_file to move files."
    client = _get_client()
    try:
        segments = path.rstrip("/").split("/")
        segments.pop()
        parent = "/".join(segments)
        dest = f"{parent}/{new_name}" if parent else new_name
        client.move(path, dest)
        return json.dumps({"success": True, "old_path": path, "new_path": dest}, indent=2)
    except Exception as exc:
        return f"Error renaming file: {exc}"


class MoveFileInput(BaseModel):
    source_path: str = Field(description="Current path of the file/folder")
    destination_path: str = Field(description='Full destination path including filename (e.g. "Archive/2025/invoice.pdf")')


@tool(args_schema=MoveFileInput)
def nextcloud_move_file(source_path: str, destination_path: str) -> str:
    """Move a file or folder to a different location on Nextcloud. Can also rename in the same operation."""
    client = _get_client()
    try:
        client.move(source_path, destination_path)
        return json.dumps({"success": True, "source_path": source_path, "destination_path": destination_path}, indent=2)
    except Exception as exc:
        return f"Error moving file: {exc}"


class DeleteFileInput(BaseModel):
    path: str = Field(description="Path of the file/folder to delete")


@tool(args_schema=DeleteFileInput)
def nextcloud_delete_file(path: str) -> str:
    """Delete a file or folder on Nextcloud. Folders are deleted recursively. IRREVERSIBLE (except via Nextcloud trash)."""
    client = _get_client()
    try:
        client.delete(path)
        return json.dumps({"success": True, "path": path, "note": "File or folder deleted."}, indent=2)
    except Exception as exc:
        return f"Error deleting file: {exc}"


# ─── Export all tools ──────────────────────────────────────────────

ALL_NEXTCLOUD_TOOLS = [
    nextcloud_list_files,
    nextcloud_download_file,
    nextcloud_upload_file,
    nextcloud_get_file_info,
    nextcloud_search_files,
    nextcloud_create_folder,
    nextcloud_rename_file,
    nextcloud_move_file,
    nextcloud_delete_file,
]
