/**
 * Tool: nextcloud_list_files
 *
 * Lists files and folders in a given directory.
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleListFiles(client: WebDavClient, args: { path?: string }) {
  const path = args.path ?? '';

  try {
    const entries = await client.listFiles(path);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              path: path || '/',
              total_entries: entries.length,
              entries,
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
      content: [{ type: 'text' as const, text: `Error listing files: ${msg}` }],
      isError: true,
    };
  }
}
