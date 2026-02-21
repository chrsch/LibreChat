/**
 * Tool: nextcloud_create_folder
 *
 * Creates a new directory, optionally including intermediate parents.
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleCreateFolder(
  client: WebDavClient,
  args: { path: string; create_parents?: boolean },
) {
  const { path, create_parents = true } = args;

  try {
    if (create_parents) {
      const result = await client.createFolderRecursive(path);

      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(
              {
                success: true,
                path,
                folders_created: result.created,
                folders_existed: result.existed,
              },
              null,
              2,
            ),
          },
        ],
      };
    } else {
      const created = await client.createFolder(path);

      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(
              {
                success: true,
                path,
                created,
                note: created ? 'Folder created.' : 'Folder already exists.',
              },
              null,
              2,
            ),
          },
        ],
      };
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: 'text' as const, text: `Error creating folder: ${msg}` }],
      isError: true,
    };
  }
}
