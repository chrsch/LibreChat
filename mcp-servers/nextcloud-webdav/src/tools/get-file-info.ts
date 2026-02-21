/**
 * Tool: nextcloud_get_file_info
 *
 * Gets detailed metadata for a single file or folder.
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleGetFileInfo(client: WebDavClient, args: { path: string }) {
  const { path } = args;

  try {
    const entry = await client.getFileInfo(path);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(entry, null, 2),
        },
      ],
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: 'text' as const, text: `Error getting file info: ${msg}` }],
      isError: true,
    };
  }
}
