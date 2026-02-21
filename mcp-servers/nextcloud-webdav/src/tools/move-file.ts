/**
 * Tool: nextcloud_move_file
 *
 * Moves a file or folder to a different location.
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleMoveFile(
  client: WebDavClient,
  args: { source_path: string; destination_path: string },
) {
  const { source_path, destination_path } = args;

  try {
    await client.move(source_path, destination_path);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              success: true,
              source_path,
              destination_path,
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
      content: [{ type: 'text' as const, text: `Error moving file: ${msg}` }],
      isError: true,
    };
  }
}
