/**
 * Number and date formatting utilities for Collmex API.
 */

/**
 * Convert a number to German comma-decimal format: 100.00 → "100,00"
 */
export function toCommaFloat(value: number): string {
  return value.toFixed(2).replace('.', ',');
}

/**
 * Parse a date string (YYYY-MM-DD) to DD.MM.YYYY for CMXLRN upload.
 */
export function toCollmexUploadDate(isoDate: string): string {
  const parts = isoDate.split('-');
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

/**
 * Parse a date string (YYYY-MM-DD) to YYYYMMDD for ACCDOC_GET queries.
 */
export function toCollmexQueryDate(isoDate: string): string {
  return isoDate.replace(/-/g, '');
}

/**
 * Get today's date in YYYYMMDD format.
 */
export function todayYYYYMMDD(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

/**
 * Get a date N years ago in YYYYMMDD format.
 */
export function yearsAgoYYYYMMDD(n: number): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

/**
 * Clean text: remove backslashes, normalize whitespace.
 */
export function cleanText(text: string): string {
  return text
    .replace(/\\/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}
