/**
 * CSV parsing and formatting utilities for Collmex API communication.
 */

/**
 * Parse a semicolon-delimited CSV response into rows of string arrays.
 */
export function parseCsvResponse(text: string): string[][] {
  const rows: string[][] = [];
  const lines = text.trim().split('\n');

  for (const line of lines) {
    if (!line.trim()) continue;
    // Simple semicolon split — Collmex rarely quotes fields
    // but handle basic quoted fields just in case
    rows.push(parseCsvLine(line));
  }

  return rows;
}

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ';') {
        fields.push(current);
        current = '';
      } else {
        current += ch;
      }
    }
  }
  fields.push(current);
  return fields;
}

/**
 * Build a semicolon-delimited CSV line from an array of values.
 */
export function buildCsvLine(fields: (string | number)[]): string {
  return fields
    .map((f) => {
      const s = String(f);
      // Quote if contains semicolon or quotes
      if (s.includes(';') || s.includes('"')) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    })
    .join(';');
}
