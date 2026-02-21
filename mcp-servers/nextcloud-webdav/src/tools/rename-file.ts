/**
 * Tool: nextcloud_rename_file
 *
 * Renames a file or folder (same directory, new name).
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleRenameFile(
  client: WebDavClient,
  args: { path: string; new_name: string },
) {
  const { path, new_name } = args;

  // Validate new_name doesn't contain path separators
  if (new_name.includes('/') || new_name.includes('\\')) {
    return {
      content: [
        {
          type: 'text' as const,
          text: 'Error: new_name must be a filename only, not a path. Use nextcloud_move_file to move files.',
        },
      ],
      isError: true,
    };
  }

  try {
    // Build destination: same parent directory + new name
    const segments = path.replace(/\/+$/, '').split('/');
    segments.pop();
    const parentDir = segments.join('/');
    const destinationPath = parentDir ? `${parentDir}/${new_name}` : new_name;

    await client.move(path, destinationPath);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              success: true,
              old_path: path,
              new_path: destinationPath,
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
      content: [{ type: 'text' as const, text: `Error renaming file: ${msg}` }],
      isError: true,
    };
  }
}
