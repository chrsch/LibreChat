/**
 * Tool: nextcloud_search_files
 *
 * Searches for files by name pattern (case-insensitive substring match).
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleSearchFiles(
  client: WebDavClient,
  args: { query: string; path?: string; max_results?: number },
) {
  const { query, path = '', max_results = 50 } = args;

  try {
    const matches = await client.searchFiles(query, path, max_results);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              query,
              search_path: path || '/',
              total_matches: matches.length,
              results: matches,
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
      content: [{ type: 'text' as const, text: `Error searching files: ${msg}` }],
      isError: true,
    };
  }
}
