/**
 * Tool: nextcloud_delete_file
 *
 * Deletes a file or folder (folders are deleted recursively).
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleDeleteFile(client: WebDavClient, args: { path: string }) {
  const { path } = args;

  try {
    await client.delete(path);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              success: true,
              path,
              note: 'File or folder deleted.',
            },
            null,
            2,
          ),
        },
      ],
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: 'text' as const, text: `Error deleting file: ${msg}` }],
      isError: true,
    };
  }
}
