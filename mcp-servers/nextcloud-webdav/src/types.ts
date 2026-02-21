/**
 * Shared TypeScript interfaces for the Nextcloud-WebDAV MCP server.
 */

export interface NextcloudConfig {
  url: string;
  username: string;
  password: string;
  webdavPath: string;
  apiTimeoutMs: number;
}

export interface FileEntry {
  name: string;
  path: string;
  type: 'file' | 'folder';
  size_bytes: number;
  mime_type: string;
  last_modified: string;
  etag: string;
}

export interface DownloadResult {
  filename: string;
  mime_type: string;
  size_bytes: number;
  content: string;
  content_type: 'text' | 'base64';
  pages_extracted: number | null;
}

export interface UploadResult {
  success: boolean;
  path: string;
  size_bytes: number;
}

export interface FileInfoResult {
  name: string;
  path: string;
  type: 'file' | 'folder';
  size_bytes: number;
  mime_type: string;
  last_modified: string;
  etag: string;
}

export interface SearchResult {
  results: FileEntry[];
  total_matches: number;
  query: string;
  search_path: string;
}

export interface WebDavResponse {
  href: string;
  displayname: string;
  contentlength: number;
  lastmodified: string;
  contenttype: string;
  resourcetype: 'file' | 'folder';
  etag: string;
}
