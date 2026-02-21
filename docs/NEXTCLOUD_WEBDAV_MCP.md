# Nextcloud WebDAV MCP Server — Concept

## Overview

A Model Context Protocol (MCP) server that exposes Nextcloud file operations via the WebDAV protocol as tools for LibreChat agents. Allows agents to browse, download, upload, search, rename, move, and delete files and folders on a Nextcloud instance.

A key use case is invoice processing: an agent can list files in a Nextcloud folder, download PDF invoices, extract text, derive structured data (vendor, amount, date), rename and move files into organised folder structures — creating folders as needed.

---

## Tools

| Tool name | Description |
|---|---|
| `nextcloud_list_files` | List files and folders in a given directory. Returns name, type (file/folder), size, last modified date, and MIME type for each entry. |
| `nextcloud_download_file` | Download a file and return its content. PDFs are parsed to text via `pdf-parse`. Text files are returned as-is. Images are returned as base64. |
| `nextcloud_upload_file` | Upload content (text or base64-encoded binary) as a new file to Nextcloud. |
| `nextcloud_get_file_info` | Get detailed metadata for a single file or folder (size, MIME type, ETag, last modified, permissions). |
| `nextcloud_search_files` | Search for files by name pattern (substring match). Uses WebDAV `SEARCH` or `PROPFIND` with `Depth: infinity` + client-side filtering. |
| `nextcloud_create_folder` | Create a new directory (including intermediate parents if needed). |
| `nextcloud_rename_file` | Rename a file or folder (same directory, new name). |
| `nextcloud_move_file` | Move a file or folder to a different directory (optionally with a new name). |
| `nextcloud_delete_file` | Delete a file or folder (folders are deleted recursively). |

### Tool parameters

**`nextcloud_list_files`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | No | Directory path relative to the user's WebDAV root (e.g. `Documents/Invoices`). Defaults to `/` (root). |

**`nextcloud_download_file`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Path to the file (e.g. `Documents/Invoices/invoice-2025-001.pdf`). |
| `max_pages` | `number` | No | For PDFs: maximum number of pages to extract text from (default: `10`). Guards against huge documents flooding the LLM context. |

Return value:

| Field | Type | Description |
|---|---|---|
| `filename` | `string` | Original filename. |
| `mime_type` | `string` | Detected MIME type (from WebDAV response). |
| `size_bytes` | `number` | File size in bytes. |
| `content` | `string` | File content: extracted text for PDFs, raw text for text files, base64 for images. |
| `content_type` | `string` | One of `text`, `base64`. Indicates how `content` is encoded. |
| `pages_extracted` | `number \| null` | Number of PDF pages processed (null for non-PDFs). |

MIME type handling:

| MIME type | Behavior |
|---|---|
| `application/pdf` | Extract text via `pdf-parse`. If text is empty (scanned PDF), return a warning message. |
| `text/*`, `application/json`, `application/xml` | Return raw text content. |
| `image/*` | Return base64-encoded content (for vision-capable models). |
| Other | Return error: "Unsupported file type". |

**`nextcloud_upload_file`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Destination path including filename (e.g. `Documents/report.txt`). |
| `content` | `string` | Yes | File content: plain text or base64-encoded binary data. |
| `content_type` | `string` | No | One of `text` (default) or `base64`. Indicates how `content` is encoded. |
| `mime_type` | `string` | No | MIME type for the uploaded file (e.g. `application/pdf`). Defaults to `application/octet-stream`. |

**`nextcloud_get_file_info`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Path to the file or folder. |

Return value:

| Field | Type | Description |
|---|---|---|
| `name` | `string` | File or folder name. |
| `path` | `string` | Full path relative to WebDAV root. |
| `type` | `string` | `file` or `folder`. |
| `size_bytes` | `number` | File size (0 for folders). |
| `mime_type` | `string` | MIME type (empty for folders). |
| `last_modified` | `string` | ISO 8601 timestamp. |
| `etag` | `string` | ETag for cache validation. |

**`nextcloud_search_files`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Search term (matched as case-insensitive substring against filenames). |
| `path` | `string` | No | Directory to search within (default: `/` — searches entire user space). |
| `max_results` | `number` | No | Maximum number of results to return (default: `50`). |

**`nextcloud_create_folder`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Path of the folder to create (e.g. `Invoices/2025/January`). |
| `create_parents` | `boolean` | No | If `true` (default), create intermediate directories that don't exist — like `mkdir -p`. |

**`nextcloud_rename_file`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Current path of the file/folder (e.g. `Documents/old-name.pdf`). |
| `new_name` | `string` | Yes | New filename (name only, no path — e.g. `new-name.pdf`). |

**`nextcloud_move_file`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `source_path` | `string` | Yes | Current path of the file/folder. |
| `destination_path` | `string` | Yes | Full destination path including filename (e.g. `Archive/2025/invoice.pdf`). |

**`nextcloud_delete_file`**
| Parameter | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Path of the file/folder to delete. |

---

## Configuration

All configuration is done via environment variables, following the same pattern as the Collmex MCP server.

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `NEXTCLOUD_URL` | **Yes** | — | Base URL of the Nextcloud instance (e.g. `https://cloud.example.com`). |
| `NEXTCLOUD_USERNAME` | **Yes** | — | Nextcloud username for WebDAV authentication. |
| `NEXTCLOUD_PASSWORD` | **Yes** | — | Nextcloud password or app password. |
| `NEXTCLOUD_WEBDAV_PATH` | No | `/remote.php/dav/files/{username}` | WebDAV endpoint path. Auto-populated from username if not set. |
| `NEXTCLOUD_API_TIMEOUT_MS` | No | `30000` | HTTP request timeout in milliseconds. |

### `.env` configuration (LibreChat root)

```env
#=====================================================================#
# Nextcloud WebDAV MCP Server Configuration                           #
#=====================================================================#

# Nextcloud credentials for the Nextcloud-WebDAV MCP server
NEXTCLOUD_URL=https://cloud.example.com
NEXTCLOUD_USERNAME=your-username
NEXTCLOUD_PASSWORD=your-app-password

# Optional defaults
# NEXTCLOUD_WEBDAV_PATH=/remote.php/dav/files/your-username
# NEXTCLOUD_API_TIMEOUT_MS=30000
```

### `librechat.yaml` integration

```yaml
mcpServers:
  Nextcloud-WebDAV:
    type: stdio
    command: node
    args:
      - /app/mcp-servers/nextcloud-webdav/dist/index.js
    env:
      NEXTCLOUD_URL: "${NEXTCLOUD_URL}"
      NEXTCLOUD_USERNAME: "${NEXTCLOUD_USERNAME}"
      NEXTCLOUD_PASSWORD: "${NEXTCLOUD_PASSWORD}"
      NEXTCLOUD_WEBDAV_PATH: "${NEXTCLOUD_WEBDAV_PATH}"
      NEXTCLOUD_API_TIMEOUT_MS: "${NEXTCLOUD_API_TIMEOUT_MS}"
    timeout: 60000
    initTimeout: 15000
```

---

## Project structure

```
mcp-servers/nextcloud-webdav/
├── package.json
├── tsconfig.json
├── .gitignore
└── src/
    ├── index.ts              # MCP server setup, tool registration, loadConfig()
    ├── webdav-client.ts      # Nextcloud WebDAV HTTP client (PROPFIND, GET, PUT, MKCOL, MOVE, DELETE)
    ├── types.ts              # Shared TypeScript interfaces
    ├── tools/
    │   ├── list-files.ts     # Handler for nextcloud_list_files
    │   ├── download-file.ts  # Handler for nextcloud_download_file (PDF text extraction, text, images)
    │   ├── upload-file.ts    # Handler for nextcloud_upload_file
    │   ├── get-file-info.ts  # Handler for nextcloud_get_file_info
    │   ├── search-files.ts   # Handler for nextcloud_search_files
    │   ├── create-folder.ts  # Handler for nextcloud_create_folder
    │   ├── rename-file.ts    # Handler for nextcloud_rename_file
    │   ├── move-file.ts      # Handler for nextcloud_move_file
    │   └── delete-file.ts    # Handler for nextcloud_delete_file
    └── utils/
        ├── xml.ts            # WebDAV XML response parser (PROPFIND multistatus)
        └── content.ts        # Content extraction: PDF→text (pdf-parse), text passthrough, image→base64
```

---

## Technical approach

### WebDAV operations mapping

| Tool | HTTP method | WebDAV details |
|---|---|---|
| List files | `PROPFIND` | `Depth: 1` header on the target collection. Parse `multistatus` XML response. |
| Download file | `GET` | Standard HTTP GET. Response body is the raw file bytes. MIME type from `Content-Type` header. |
| Upload file | `PUT` | Standard HTTP PUT with file bytes as body. Sets `Content-Type` header. |
| Get file info | `PROPFIND` | `Depth: 0` on the specific resource. Returns properties for that single item. |
| Search files | `PROPFIND` | `Depth: infinity` on the search root + client-side filename filtering. (Alternative: Nextcloud `SEARCH` method if available.) |
| Create folder | `MKCOL` | Creates a single collection. For nested paths with `create_parents`, issue `MKCOL` for each missing segment top-down. |
| Rename | `MOVE` | `Destination` header points to same parent directory with new name. |
| Move | `MOVE` | `Destination` header points to the new full path. |
| Delete | `DELETE` | Standard HTTP DELETE on the resource URL. |

### `webdav-client.ts` responsibilities

- Constructs full WebDAV URLs from the base URL + WebDAV path + relative file path.
- Handles Basic auth (`Authorization: Basic base64(user:pass)`).
- `PROPFIND` requests: sends minimal XML body requesting `displayname`, `getcontentlength`, `getlastmodified`, `getcontenttype`, `resourcetype`.
- Parses the `207 Multi-Status` XML response into typed objects.
- `GET` requests: downloads file bytes as `ArrayBuffer`. Returns raw buffer + MIME type from `Content-Type` header.
- `PUT` requests: uploads file bytes with `Content-Type` header. Accepts `Buffer` from either raw text or base64-decoded binary.
- `MKCOL` requests: creates a single directory. For `create_parents` mode, walks the path segments top-down, issuing `MKCOL` for each missing level (ignores 405 "already exists").
- `MOVE` requests: sets `Destination` header with full absolute URL, `Overwrite: F` to prevent silent overwrites.
- `DELETE` requests: standard DELETE, returns success/failure.
- Timeout enforcement via `AbortController`.

### XML parsing

Use a lightweight approach — either a small dependency like `fast-xml-parser` or Node.js built-in string/regex parsing for the well-defined WebDAV `multistatus` schema. No heavy XML library needed.

### PDF text extraction

- Uses `pdf-parse` (pure JS, no native dependencies, ~200 KB).
- Extracts text content from digital (text-layer) PDFs — works perfectly for typical invoices.
- `max_pages` parameter limits extraction to avoid flooding the LLM context window (default: 10 pages).
- **Scanned PDFs** (image-only, no text layer) will return empty or near-empty text. In this case, the tool returns a warning: `"This PDF appears to be scanned/image-based. Text extraction returned no content."` — a future enhancement could render pages as images for vision models.
- Typical invoice text output: 1–5 KB, well within LLM context limits.

### Error handling

- Missing/invalid credentials → fail fast at startup (same as Collmex pattern).
- HTTP 404 → "File or folder not found" user-friendly message.
- HTTP 401/403 → "Authentication failed" message.
- HTTP 409 (conflict, e.g. destination parent doesn't exist) → descriptive error.
- HTTP 405 (method not allowed, e.g. `MKCOL` on existing folder) → silently ignored in `create_parents` mode; error otherwise.
- HTTP 412 (precondition failed, `Overwrite: F` and target exists) → "Destination already exists" error.
- Timeout → "Request timed out" error.

### Dependencies

```json
{
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.1",
    "fast-xml-parser": "^5.0.0",
    "pdf-parse": "^1.1.1",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "tsx": "^4.7.0",
    "typescript": "^5.7.0"
  }
}
```

Build uses `bun build` (same as Collmex MCP):
```
bun build src/index.ts --outfile dist/index.js --target node --format esm
```

---

## Security considerations

- Credentials are stored in `.env` and passed at runtime — never committed.
- Use **app passwords** (Nextcloud settings → Security → App passwords) rather than the main account password.
- All paths are sanitized to prevent directory traversal outside the WebDAV root (reject paths containing `..`).
- `Overwrite: F` on MOVE operations prevents accidental data loss.

---

## Limitations (v1)

- **Scanned PDFs** — `pdf-parse` only extracts text layers. Image-only PDFs return a warning with no content.
- **Large files** — File content is returned in the MCP response (LLM context window). Practical limit ~100 KB of extracted text. The `max_pages` parameter mitigates this for PDFs.
- **Binary files** — Only PDFs, text files, and images are supported for download/content extraction. Other binary formats (DOCX, XLSX, etc.) return an "unsupported" error.
- **Search** — Filename-only substring matching. No full-text content search.
- **Upload size** — Limited by what fits in an MCP tool call parameter (practical limit ~1 MB base64).

---

## Example agent workflow: Invoice processing

This demonstrates the full invoice processing workflow that an agent can execute:

```
Step 1: nextcloud_list_files(path: "Invoices/Incoming")
  → Returns: [{name: "inv-001.pdf", type: "file", ...}, {name: "inv-002.pdf", type: "file", ...}]

Step 2: nextcloud_download_file(path: "Invoices/Incoming/inv-001.pdf")
  → Returns: {filename: "inv-001.pdf", content: "Invoice\nVendor: Acme Corp\nDate: 2025-01-15\nAmount: €1,234.56\n...", ...}

Step 3: (LLM reasoning — no tool call)
  → Parses: vendor="Acme Corp", date="2025-01-15", amount=1234.56, currency="EUR"
  → Decides target folder: "Invoices/2025/Acme Corp/"
  → Decides new filename: "2025-01-15_Acme-Corp_1234.56EUR.pdf"

Step 4: nextcloud_create_folder(path: "Invoices/2025/Acme Corp", create_parents: true)
  → Creates "Invoices/2025/" and "Invoices/2025/Acme Corp/" as needed

Step 5: nextcloud_rename_file(path: "Invoices/Incoming/inv-001.pdf", new_name: "2025-01-15_Acme-Corp_1234.56EUR.pdf")
  → File is now "Invoices/Incoming/2025-01-15_Acme-Corp_1234.56EUR.pdf"

Step 6: nextcloud_move_file(source_path: "Invoices/Incoming/2025-01-15_Acme-Corp_1234.56EUR.pdf",
                            destination_path: "Invoices/2025/Acme Corp/2025-01-15_Acme-Corp_1234.56EUR.pdf")
  → File moved to final location

(Repeat steps 2–6 for each file)
```

Note: Steps 5 + 6 (rename then move) can be combined into a single `nextcloud_move_file` call since `destination_path` includes the new filename:

```
Step 5+6: nextcloud_move_file(source_path: "Invoices/Incoming/inv-001.pdf",
                              destination_path: "Invoices/2025/Acme Corp/2025-01-15_Acme-Corp_1234.56EUR.pdf")
```

---

## Future extensions (out of scope for v1)

- Scanned PDF support — render PDF pages as images for vision models (requires `pdfjs-dist` + `canvas`).
- DOCX/XLSX extraction — parse Office documents (requires additional dependencies).
- Full-text content search (depends on Nextcloud server-side search/indexing).
- Share management (public links, user shares).
- File versioning (list/restore previous versions).
