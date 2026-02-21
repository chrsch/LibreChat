/**
 * Tool: nextcloud_upload_file
 *
 * Uploads content as a file to Nextcloud.
 */

import type { WebDavClient } from '../webdav-client.js';

export async function handleUploadFile(
  client: WebDavClient,
  args: {
    path: string;
    content: string;
    content_type?: string;
    mime_type?: string;
  },
) {
  const { path, content, content_type = 'text', mime_type = 'application/octet-stream' } = args;

  try {
    let buffer: Buffer;
    if (content_type === 'base64') {
      buffer = Buffer.from(content, 'base64');
    } else {
      buffer = Buffer.from(content, 'utf-8');
    }

    const result = await client.uploadFile(path, buffer, mime_type);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              success: true,
              path,
              size_bytes: result.size,
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
      content: [{ type: 'text' as const, text: `Error uploading file: ${msg}` }],
      isError: true,
    };
  }
}
