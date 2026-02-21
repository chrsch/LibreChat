/**
 * Nextcloud WebDAV client — handles all HTTP communication with Nextcloud's WebDAV endpoint.
 *
 * Supported operations: PROPFIND, GET, PUT, MKCOL, MOVE, DELETE.
 * Auth: Basic authentication via Authorization header.
 */

import type { NextcloudConfig, WebDavResponse, FileEntry } from './types.js';
import { parseMultiStatus } from './utils/xml.js';

/** PROPFIND XML body requesting common file properties */
const PROPFIND_BODY = `<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:prop>
    <d:displayname/>
    <d:getcontentlength/>
    <d:getlastmodified/>
    <d:getcontenttype/>
    <d:resourcetype/>
    <d:getetag/>
  </d:prop>
</d:propfind>`;

export class WebDavClient {
  private baseUrl: string;
  private authHeader: string;
  private webdavRoot: string;

  constructor(private config: NextcloudConfig) {
    // Remove trailing slash from URL
    const url = config.url.replace(/\/+$/, '');
    const webdavPath = config.webdavPath.replace(/\/+$/, '');
    this.webdavRoot = `${url}${webdavPath}`;
    this.baseUrl = url;
    this.authHeader =
      'Basic ' + Buffer.from(`${config.username}:${config.password}`).toString('base64');
  }

  // ─── Helpers ────────────────────────────────────────────────────

  /**
   * Build the full WebDAV URL for a given relative path.
   */
  private buildUrl(relativePath: string): string {
    const clean = sanitizePath(relativePath);
    // Encode each path segment individually to handle special chars
    const encoded = clean
      .split('/')
      .map((segment) => encodeURIComponent(segment))
      .join('/');
    return `${this.webdavRoot}/${encoded}`;
  }

  /**
   * Create an AbortController with the configured timeout.
   */
  private createAbort(): { controller: AbortController; timer: ReturnType<typeof setTimeout> } {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.apiTimeoutMs);
    return { controller, timer };
  }

  /**
   * Convert a WebDavResponse href into a path relative to the WebDAV root.
   */
  private hrefToRelativePath(href: string): string {
    // href is typically /remote.php/dav/files/username/path/to/file
    const webdavPathNormalized = this.config.webdavPath.replace(/\/+$/, '');
    const idx = href.indexOf(webdavPathNormalized);
    if (idx === -1) return href;
    const rel = href.slice(idx + webdavPathNormalized.length);
    return rel.replace(/^\/+/, '').replace(/\/+$/, '');
  }

  /**
   * Convert WebDavResponse to FileEntry.
   */
  private toFileEntry(resp: WebDavResponse): FileEntry {
    const relativePath = this.hrefToRelativePath(resp.href);
    const name = resp.displayname || relativePath.split('/').pop() || '';
    return {
      name,
      path: relativePath,
      type: resp.resourcetype,
      size_bytes: resp.contentlength,
      mime_type: resp.contenttype,
      last_modified: resp.lastmodified ? new Date(resp.lastmodified).toISOString() : '',
      etag: resp.etag,
    };
  }

  /**
   * Handle HTTP error responses with user-friendly messages.
   */
  private handleHttpError(status: number, statusText: string, url: string): Error {
    const path = decodeURIComponent(url.replace(this.webdavRoot, ''));
    switch (status) {
      case 401:
      case 403:
        return new Error('Authentication failed. Check NEXTCLOUD_USERNAME and NEXTCLOUD_PASSWORD.');
      case 404:
        return new Error(`File or folder not found: ${path}`);
      case 405:
        return new Error(`Method not allowed on: ${path}`);
      case 409:
        return new Error(
          `Conflict: parent directory may not exist. Path: ${path}`,
        );
      case 412:
        return new Error('Destination already exists (overwrite is disabled).');
      default:
        return new Error(`HTTP ${status} ${statusText}`);
    }
  }

  /**
   * Extract a meaningful error message from a fetch error, including the `cause` property.
   */
  private handleFetchError(err: unknown, method: string, url: string): Error {
    const e = err as Error;
    if (e.name === 'AbortError') {
      return new Error(`Request timed out after ${this.config.apiTimeoutMs}ms`);
    }

    // Node.js fetch wraps the real error in a `cause` property
    const cause = (e as Error & { cause?: Error }).cause;
    const causeMsg = cause ? `: ${cause.message || cause}` : '';
    const fullMsg = `${method} ${decodeURIComponent(url.replace(this.webdavRoot, ''))} failed: ${e.message}${causeMsg}`;
    console.error(`[Nextcloud-WebDAV] ${fullMsg}`);
    return new Error(fullMsg);
  }

  // ─── PROPFIND (list / info) ─────────────────────────────────────

  /**
   * List files and folders in a directory (Depth: 1).
   * Returns entries excluding the directory itself.
   */
  async listFiles(path: string): Promise<FileEntry[]> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'PROPFIND',
        headers: {
          Authorization: this.authHeader,
          'Content-Type': 'application/xml; charset=utf-8',
          Depth: '1',
        },
        body: PROPFIND_BODY,
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 207) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }

      const xml = await res.text();
      const responses = parseMultiStatus(xml);

      // First entry is the directory itself — skip it
      return responses.slice(1).map((r) => this.toFileEntry(r));
    } catch (err) {
      throw this.handleFetchError(err, 'PROPFIND', url);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Get metadata for a single file or folder (Depth: 0).
   */
  async getFileInfo(path: string): Promise<FileEntry> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'PROPFIND',
        headers: {
          Authorization: this.authHeader,
          'Content-Type': 'application/xml; charset=utf-8',
          Depth: '0',
        },
        body: PROPFIND_BODY,
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 207) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }

      const xml = await res.text();
      const responses = parseMultiStatus(xml);

      if (responses.length === 0) {
        throw new Error(`No response from server for path: ${path}`);
      }

      return this.toFileEntry(responses[0]);
    } catch (err) {
      throw this.handleFetchError(err, 'PROPFIND', url);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Search files by name (PROPFIND Depth: infinity + client-side filtering).
   */
  async searchFiles(query: string, path: string, maxResults: number): Promise<FileEntry[]> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'PROPFIND',
        headers: {
          Authorization: this.authHeader,
          'Content-Type': 'application/xml; charset=utf-8',
          Depth: 'infinity',
        },
        body: PROPFIND_BODY,
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 207) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }

      const xml = await res.text();
      const responses = parseMultiStatus(xml);

      // Skip the root directory itself (first entry), then filter by name
      const lowerQuery = query.toLowerCase();
      const matches: FileEntry[] = [];

      for (let i = 1; i < responses.length && matches.length < maxResults; i++) {
        const entry = this.toFileEntry(responses[i]);
        if (entry.name.toLowerCase().includes(lowerQuery)) {
          matches.push(entry);
        }
      }

      return matches;
    } catch (err) {
      throw this.handleFetchError(err, 'PROPFIND(search)', url);
    } finally {
      clearTimeout(timer);
    }
  }

  // ─── GET (download) ─────────────────────────────────────────────

  /**
   * Download a file. Returns the raw bytes and detected MIME type.
   */
  async downloadFile(path: string): Promise<{ buffer: Buffer; mimeType: string; size: number }> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: this.authHeader,
        },
        signal: controller.signal,
      });

      if (!res.ok) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }

      const arrayBuffer = await res.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);
      const mimeType = res.headers.get('Content-Type') || 'application/octet-stream';

      return {
        buffer,
        mimeType: mimeType.split(';')[0].trim(), // strip charset
        size: buffer.length,
      };
    } catch (err) {
      throw this.handleFetchError(err, 'GET', url);
    } finally {
      clearTimeout(timer);
    }
  }

  // ─── PUT (upload) ───────────────────────────────────────────────

  /**
   * Upload a file. Creates or overwrites.
   */
  async uploadFile(path: string, content: Buffer, mimeType: string): Promise<{ size: number }> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'PUT',
        headers: {
          Authorization: this.authHeader,
          'Content-Type': mimeType,
        },
        body: new Uint8Array(content),
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 201 && res.status !== 204) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }

      return { size: content.length };
    } catch (err) {
      throw this.handleFetchError(err, 'PUT', url);
    } finally {
      clearTimeout(timer);
    }
  }

  // ─── MKCOL (create folder) ─────────────────────────────────────

  /**
   * Create a single directory.
   * @returns true if created, false if it already existed.
   */
  async createFolder(path: string): Promise<boolean> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'MKCOL',
        headers: {
          Authorization: this.authHeader,
        },
        signal: controller.signal,
      });

      if (res.status === 201) return true;
      if (res.status === 405) return false; // Already exists
      if (!res.ok) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }
      return true;
    } catch (err) {
      throw this.handleFetchError(err, 'MKCOL', url);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Create a directory including all intermediate parents (mkdir -p).
   */
  async createFolderRecursive(path: string): Promise<{ created: string[]; existed: string[] }> {
    const clean = sanitizePath(path);
    const segments = clean.split('/').filter(Boolean);
    const created: string[] = [];
    const existed: string[] = [];

    let current = '';
    for (const segment of segments) {
      current = current ? `${current}/${segment}` : segment;
      const wasCreated = await this.createFolder(current);
      if (wasCreated) {
        created.push(current);
      } else {
        existed.push(current);
      }
    }

    return { created, existed };
  }

  // ─── MOVE (rename / move) ──────────────────────────────────────

  /**
   * Move or rename a file/folder.
   */
  async move(sourcePath: string, destinationPath: string): Promise<void> {
    const sourceUrl = this.buildUrl(sourcePath);
    const destUrl = this.buildUrl(destinationPath);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(sourceUrl, {
        method: 'MOVE',
        headers: {
          Authorization: this.authHeader,
          Destination: destUrl,
          Overwrite: 'F',
        },
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 201 && res.status !== 204) {
        throw this.handleHttpError(res.status, res.statusText, sourceUrl);
      }
    } catch (err) {
      throw this.handleFetchError(err, 'MOVE', sourceUrl);
    } finally {
      clearTimeout(timer);
    }
  }

  // ─── DELETE ─────────────────────────────────────────────────────

  /**
   * Delete a file or folder (folders are deleted recursively).
   */
  async delete(path: string): Promise<void> {
    const url = this.buildUrl(path);
    const { controller, timer } = this.createAbort();

    try {
      const res = await fetch(url, {
        method: 'DELETE',
        headers: {
          Authorization: this.authHeader,
        },
        signal: controller.signal,
      });

      if (!res.ok && res.status !== 204) {
        throw this.handleHttpError(res.status, res.statusText, url);
      }
    } catch (err) {
      throw this.handleFetchError(err, 'DELETE', url);
    } finally {
      clearTimeout(timer);
    }
  }
}

// ─── Path utilities ───────────────────────────────────────────────

/**
 * Sanitize a path to prevent directory traversal attacks.
 * Strips leading/trailing slashes, rejects `..` segments.
 */
function sanitizePath(path: string): string {
  // Remove leading/trailing slashes and whitespace
  const cleaned = path.replace(/^\/+|\/+$/g, '').trim();

  // Reject path traversal
  const segments = cleaned.split('/');
  for (const seg of segments) {
    if (seg === '..' || seg === '.') {
      throw new Error(
        `Invalid path: "${path}" — path traversal (.. or .) is not allowed.`,
      );
    }
  }

  return cleaned;
}
