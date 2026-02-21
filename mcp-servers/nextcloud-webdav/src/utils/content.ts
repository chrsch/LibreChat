/**
 * Content extraction utilities.
 *
 * Handles conversion of raw file bytes to text/base64 based on MIME type.
 * PDF → extracted text (pdf-parse)
 * text/* → raw string
 * image/* → base64
 */

// @ts-expect-error pdf-parse has no type declarations
import pdf from 'pdf-parse';
import type { DownloadResult } from '../types.js';

/**
 * Determine if a MIME type is a text type that should be returned as raw text.
 */
function isTextMime(mime: string): boolean {
  if (mime.startsWith('text/')) return true;
  if (mime === 'application/json') return true;
  if (mime === 'application/xml') return true;
  if (mime === 'application/xhtml+xml') return true;
  if (mime === 'application/javascript') return true;
  if (mime === 'application/typescript') return true;
  return false;
}

/**
 * Extract content from a downloaded file based on MIME type.
 */
export async function extractContent(
  buffer: Buffer,
  mimeType: string,
  filename: string,
  maxPages: number = 10,
): Promise<DownloadResult> {
  const sizeBytes = buffer.length;

  // PDF: extract text
  if (mimeType === 'application/pdf') {
    return extractPdf(buffer, filename, sizeBytes, maxPages);
  }

  // Text-based: return raw string
  if (isTextMime(mimeType)) {
    return {
      filename,
      mime_type: mimeType,
      size_bytes: sizeBytes,
      content: buffer.toString('utf-8'),
      content_type: 'text',
      pages_extracted: null,
    };
  }

  // Images: return base64
  if (mimeType.startsWith('image/')) {
    return {
      filename,
      mime_type: mimeType,
      size_bytes: sizeBytes,
      content: buffer.toString('base64'),
      content_type: 'base64',
      pages_extracted: null,
    };
  }

  // Unsupported type
  throw new Error(
    `Unsupported file type: ${mimeType}. Supported types: PDF, text/*, image/*, application/json, application/xml.`,
  );
}

/**
 * Extract text from a PDF buffer.
 */
async function extractPdf(
  buffer: Buffer,
  filename: string,
  sizeBytes: number,
  maxPages: number,
): Promise<DownloadResult> {
  try {
    const data = await pdf(buffer, {
      max: maxPages,
    });

    const text = data.text?.trim() ?? '';
    const pagesExtracted = Math.min(data.numpages, maxPages);

    if (!text) {
      return {
        filename,
        mime_type: 'application/pdf',
        size_bytes: sizeBytes,
        content:
          'This PDF appears to be scanned/image-based. Text extraction returned no content. ' +
          `Total pages: ${data.numpages}.`,
        content_type: 'text',
        pages_extracted: pagesExtracted,
      };
    }

    return {
      filename,
      mime_type: 'application/pdf',
      size_bytes: sizeBytes,
      content: text,
      content_type: 'text',
      pages_extracted: pagesExtracted,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(`Failed to parse PDF "${filename}": ${msg}`);
  }
}
