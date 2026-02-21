/**
 * Nextcloud-WebDAV MCP Server
 *
 * A Model Context Protocol server that exposes Nextcloud file operations
 * via WebDAV as tools for LibreChat agents.
 *
 * Tools:
 *   - nextcloud_list_files        — List files and folders in a directory
 *   - nextcloud_download_file     — Download a file (PDF→text, text, image→base64)
 *   - nextcloud_upload_file       — Upload content as a file
 *   - nextcloud_get_file_info     — Get metadata for a single file/folder
 *   - nextcloud_search_files      — Search files by name pattern
 *   - nextcloud_create_folder     — Create directories (with mkdir -p support)
 *   - nextcloud_rename_file       — Rename a file or folder
 *   - nextcloud_move_file         — Move a file or folder
 *   - nextcloud_delete_file       — Delete a file or folder
 *
 * Configuration via environment variables:
 *   NEXTCLOUD_URL          — Base URL of the Nextcloud instance
 *   NEXTCLOUD_USERNAME     — WebDAV username
 *   NEXTCLOUD_PASSWORD     — WebDAV password or app password
 *   NEXTCLOUD_WEBDAV_PATH  — WebDAV endpoint path (optional)
 *   NEXTCLOUD_API_TIMEOUT_MS — Request timeout (optional)
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { WebDavClient } from './webdav-client.js';
import type { NextcloudConfig } from './types.js';

import { handleListFiles } from './tools/list-files.js';
import { handleDownloadFile } from './tools/download-file.js';
import { handleUploadFile } from './tools/upload-file.js';
import { handleGetFileInfo } from './tools/get-file-info.js';
import { handleSearchFiles } from './tools/search-files.js';
import { handleCreateFolder } from './tools/create-folder.js';
import { handleRenameFile } from './tools/rename-file.js';
import { handleMoveFile } from './tools/move-file.js';
import { handleDeleteFile } from './tools/delete-file.js';

// ─── Configuration ────────────────────────────────────────────────

function loadConfig(): NextcloudConfig {
  const url = process.env.NEXTCLOUD_URL;
  const username = process.env.NEXTCLOUD_USERNAME;
  const password = process.env.NEXTCLOUD_PASSWORD;

  if (!url || !username || !password) {
    console.error(
      'Missing required environment variables: NEXTCLOUD_URL, NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD',
    );
    process.exit(1);
  }

  const webdavPath =
    process.env.NEXTCLOUD_WEBDAV_PATH || `/remote.php/dav/files/${username}`;

  return {
    url,
    username,
    password,
    webdavPath,
    apiTimeoutMs: parseInt(process.env.NEXTCLOUD_API_TIMEOUT_MS ?? '30000', 10),
  };
}

// ─── Server setup ─────────────────────────────────────────────────

async function main() {
  const config = loadConfig();
  const client = new WebDavClient(config);

  const server = new McpServer({
    name: 'Nextcloud-WebDAV',
    version: '1.0.0',
  });

  // --- nextcloud_list_files ---
  server.tool(
    'nextcloud_list_files',
    'List files and folders in a directory on Nextcloud. Returns name, type (file/folder), size, last modified date, and MIME type for each entry.',
    {
      path: z
        .string()
        .optional()
        .default('')
        .describe(
          'Directory path relative to the WebDAV root (e.g. "Documents/Invoices"). Defaults to root.',
        ),
    },
    async (args) => handleListFiles(client, args),
  );

  // --- nextcloud_download_file ---
  server.tool(
    'nextcloud_download_file',
    'Download a file from Nextcloud and return its content. PDFs are parsed to extracted text (ideal for invoices). Text files are returned as-is. Images are returned as base64.',
    {
      path: z.string().describe('Path to the file (e.g. "Documents/Invoices/invoice-001.pdf").'),
      max_pages: z
        .number()
        .optional()
        .default(10)
        .describe('For PDFs: max pages to extract text from (default: 10). Guards against huge documents.'),
    },
    async (args) => handleDownloadFile(client, args),
  );

  // --- nextcloud_upload_file ---
  server.tool(
    'nextcloud_upload_file',
    'Upload content as a file to Nextcloud. Provide text content directly or base64-encoded binary.',
    {
      path: z.string().describe('Destination path including filename (e.g. "Documents/report.txt").'),
      content: z.string().describe('File content: plain text or base64-encoded binary.'),
      content_type: z
        .string()
        .optional()
        .default('text')
        .describe('How content is encoded: "text" (default) or "base64".'),
      mime_type: z
        .string()
        .optional()
        .default('application/octet-stream')
        .describe('MIME type for the file (e.g. "text/plain", "application/pdf").'),
    },
    async (args) => handleUploadFile(client, args),
  );

  // --- nextcloud_get_file_info ---
  server.tool(
    'nextcloud_get_file_info',
    'Get detailed metadata for a single file or folder on Nextcloud (size, MIME type, ETag, last modified).',
    {
      path: z.string().describe('Path to the file or folder.'),
    },
    async (args) => handleGetFileInfo(client, args),
  );

  // --- nextcloud_search_files ---
  server.tool(
    'nextcloud_search_files',
    'Search for files by name on Nextcloud. Performs case-insensitive substring matching against filenames.',
    {
      query: z.string().describe('Search term (matched as case-insensitive substring against filenames).'),
      path: z
        .string()
        .optional()
        .default('')
        .describe('Directory to search within (default: root — searches entire user space).'),
      max_results: z
        .number()
        .optional()
        .default(50)
        .describe('Maximum number of results to return (default: 50).'),
    },
    async (args) => handleSearchFiles(client, args),
  );

  // --- nextcloud_create_folder ---
  server.tool(
    'nextcloud_create_folder',
    'Create a new directory on Nextcloud. By default creates intermediate parent directories (mkdir -p).',
    {
      path: z.string().describe('Path of the folder to create (e.g. "Invoices/2025/January").'),
      create_parents: z
        .boolean()
        .optional()
        .default(true)
        .describe('If true (default), create intermediate directories that don\'t exist.'),
    },
    async (args) => handleCreateFolder(client, args),
  );

  // --- nextcloud_rename_file ---
  server.tool(
    'nextcloud_rename_file',
    'Rename a file or folder on Nextcloud (same directory, new name only). Use nextcloud_move_file to move to a different directory.',
    {
      path: z.string().describe('Current path of the file/folder (e.g. "Documents/old-name.pdf").'),
      new_name: z.string().describe('New filename (name only, no path — e.g. "new-name.pdf").'),
    },
    async (args) => handleRenameFile(client, args),
  );

  // --- nextcloud_move_file ---
  server.tool(
    'nextcloud_move_file',
    'Move a file or folder to a different location on Nextcloud. Can also rename in the same operation by using a different filename in the destination path.',
    {
      source_path: z.string().describe('Current path of the file/folder.'),
      destination_path: z
        .string()
        .describe('Full destination path including filename (e.g. "Archive/2025/invoice.pdf").'),
    },
    async (args) => handleMoveFile(client, args),
  );

  // --- nextcloud_delete_file ---
  server.tool(
    'nextcloud_delete_file',
    'Delete a file or folder on Nextcloud. Folders are deleted recursively. IMPORTANT: This action cannot be undone (except via Nextcloud trash).',
    {
      path: z.string().describe('Path of the file/folder to delete.'),
    },
    async (args) => handleDeleteFile(client, args),
  );

  // Connect via stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('Nextcloud-WebDAV MCP server started (stdio)');
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
