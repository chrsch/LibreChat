/**
 * Tool: nextcloud_download_file
 *
 * Downloads a file and returns its content.
 * PDF → text extraction, text → raw, image → base64.
 */

import type { WebDavClient } from '../webdav-client.js';
import { extractContent } from '../utils/content.js';

export async function handleDownloadFile(
  client: WebDavClient,
  args: { path: string; max_pages?: number },
) {
  const { path, max_pages = 10 } = args;
  const filename = path.split('/').pop() || path;

  try {
    const { buffer, mimeType, size } = await client.downloadFile(path);
    const result = await extractContent(buffer, mimeType, filename, max_pages);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: 'text' as const, text: `Error downloading file: ${msg}` }],
      isError: true,
    };
  }
}
