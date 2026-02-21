/**
 * Collmex API client — handles all HTTP communication with the Collmex CSV API.
 *
 * Protocol: POST semicolon-delimited CSV over HTTPS.
 * Auth: LOGIN line prepended to every request body.
 *
 * See docs/COLLMEX-API-SPEC.md for full specification.
 */

import type {
  CollmexConfig,
  Vendor,
  Account,
  AccountHistoryEntry,
  InvoiceUpload,
  UploadResult,
  BookingNumberResult,
} from './types.js';
import { parseCsvResponse, buildCsvLine } from './utils/csv.js';
import {
  toCommaFloat,
  toCollmexUploadDate,
  toCollmexQueryDate,
  todayYYYYMMDD,
  yearsAgoYYYYMMDD,
  cleanText,
} from './utils/formatting.js';

export class CollmexClient {
  private baseUrl: string;
  private loginLine: string;

  constructor(private config: CollmexConfig) {
    this.baseUrl = `https://www.collmex.de/c.cmx?${config.customerId},0,data_exchange`;
    this.loginLine = `LOGIN;${config.username};${config.password}`;
  }

  // ─── Low-level request ──────────────────────────────────────────

  private async request(csvBody: string): Promise<string> {
    const body = `${this.loginLine}\n${csvBody}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.apiTimeoutMs);

    try {
      const res = await fetch(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'text/csv',
          Accept: 'text/csv',
        },
        body: Buffer.from(body, 'utf-8'),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      return await res.text();
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Parse MESSAGE records from a response and determine success/failure.
   */
  private parseMessages(rows: string[][]): { success: boolean; errors: string[]; info: string[] } {
    const errors: string[] = [];
    const info: string[] = [];
    let success = true;

    for (const row of rows) {
      if (row[0] !== 'MESSAGE') continue;
      const type = row[1]; // S, W, E
      const text = row[3] ?? row[2] ?? '';
      if (type === 'E') {
        success = false;
        errors.push(text);
      } else {
        info.push(text);
      }
    }

    return { success, errors, info };
  }

  // ─── VENDOR_GET ─────────────────────────────────────────────────

  async fetchVendors(): Promise<Vendor[]> {
    const csv = `VENDOR_GET;;${this.config.companyNr}\n`;
    const text = await this.request(csv);
    const rows = parseCsvResponse(text);
    const vendors: Vendor[] = [];

    for (const row of rows) {
      if (row[0] !== 'CMXLIF' || row.length <= 8) continue;

      const number = row[1];
      const name = row[7];
      if (!number || !name) continue;

      // Field 36 (index 35): Aufwandskonto — may be "4920" or "4920 Telefon"
      let preferredAccount: string | null = null;
      const aufwandskonto = (row[35] ?? '').trim();
      if (aufwandskonto) {
        const parts = aufwandskonto.split(/\s+/);
        if (parts[0] && /^\d+$/.test(parts[0]) && parts[0].startsWith('4')) {
          preferredAccount = parts[0];
        }
      }

      vendors.push({ number, name, preferredAccount });
    }

    return vendors;
  }

  // ─── ACCDOC_GET: Chart of accounts ─────────────────────────────

  async fetchAccountChart(): Promise<Account[]> {
    const startDate = yearsAgoYYYYMMDD(this.config.accountHistoryYears);
    const endDate = todayYYYYMMDD();
    const csv = `ACCDOC_GET;${this.config.companyNr};;;;;;;;;;;;;${startDate};${endDate}\n`;

    const text = await this.request(csv);
    const rows = parseCsvResponse(text);

    const seen = new Map<string, string>();
    for (const row of rows) {
      if (row[0] !== 'ACCDOC' || row.length <= 10) continue;
      const accountNumber = row[8];
      const accountName = row[9];
      if (accountNumber && accountName && !seen.has(accountNumber)) {
        seen.set(accountNumber, accountName);
      }
    }

    return Array.from(seen.entries()).map(([number, name]) => ({ number, name }));
  }

  // ─── ACCDOC_GET: Vendor account history ────────────────────────

  async fetchVendorAccountHistory(
    vendorNumber: string,
    yearsBack: number = 2,
  ): Promise<AccountHistoryEntry[]> {
    const dateFrom = yearsAgoYYYYMMDD(yearsBack);
    const dateTo = todayYYYYMMDD();
    const csv = `ACCDOC_GET;${this.config.companyNr};;;;;;;;;;;${dateFrom};${dateTo}\n`;

    const text = await this.request(csv);
    const rows = parseCsvResponse(text);

    // Group rows by booking number (index 3)
    const bookingMap = new Map<string, string[][]>();
    for (const row of rows) {
      if (row[0] !== 'ACCDOC' || row.length <= 15) continue;
      const bookingNo = (row[3] ?? '').trim();
      if (!bookingNo) continue;
      if (!bookingMap.has(bookingNo)) bookingMap.set(bookingNo, []);
      bookingMap.get(bookingNo)!.push(row);
    }

    // Count expense accounts for this vendor
    const accountCounts = new Map<string, number>();
    let totalBookings = 0;

    for (const [, records] of bookingMap) {
      let vendorFound = false;
      const expenseAccounts: string[] = [];

      for (const row of records) {
        const vNum = (row[14] ?? '').trim();
        const account = (row[8] ?? '').trim();

        if (vNum === vendorNumber) vendorFound = true;
        if (account && /^\d+$/.test(account) && account.startsWith('4')) {
          expenseAccounts.push(account);
        }
      }

      if (vendorFound && expenseAccounts.length > 0) {
        totalBookings++;
        for (const acc of expenseAccounts) {
          accountCounts.set(acc, (accountCounts.get(acc) ?? 0) + 1);
        }
      }
    }

    if (totalBookings === 0) return [];

    // Sort by frequency descending
    const entries: AccountHistoryEntry[] = Array.from(accountCounts.entries())
      .map(([account, frequency]) => ({
        account,
        frequency,
        percentage: Math.round((frequency / totalBookings) * 100 * 10) / 10,
      }))
      .sort((a, b) => b.frequency - a.frequency);

    return entries;
  }

  // ─── CMXLRN: Upload supplier invoices ──────────────────────────

  async uploadInvoices(invoices: InvoiceUpload[]): Promise<UploadResult> {
    if (invoices.length === 0) {
      return { success: false, message: 'No invoices to upload', recordsUploaded: 0 };
    }

    const lines: string[] = [];

    for (const inv of invoices) {
      const dateStr = toCollmexUploadDate(inv.invoice_date);
      const bookingText = cleanText(inv.booking_text ?? `Rechnung ${inv.invoice_number}`);

      const record = buildCsvLine([
        'CMXLRN',
        inv.vendor_number,
        this.config.companyNr,
        dateStr,
        cleanText(inv.invoice_number),
        toCommaFloat(inv.net_amount),
        toCommaFloat(inv.vat_amount),
        '', '', '', '', // Fields 8-11 empty
        inv.currency ?? this.config.defaultCurrency,
        inv.tax_code ?? this.config.defaultTaxCode,
        0, // Payment target
        bookingText,
        '', // Field 16 empty
        inv.expense_account,
        '', '', '', // Fields 18-20 empty
        'Importiert via MCP',
      ]);

      lines.push(record);
    }

    const text = await this.request(lines.join('\n') + '\n');
    const rows = parseCsvResponse(text);
    const { success, errors } = this.parseMessages(rows);

    if (success) {
      return {
        success: true,
        message: `Successfully uploaded ${invoices.length} invoice(s)`,
        recordsUploaded: invoices.length,
      };
    } else {
      return {
        success: false,
        message: `Upload failed: ${errors.join('; ')}`,
        recordsUploaded: 0,
      };
    }
  }

  // ─── ACCDOC_GET: Get booking number ────────────────────────────

  async getBookingNumber(
    vendorNumber: string,
    invoiceNumber: string,
    invoiceDate: string, // YYYY-MM-DD
  ): Promise<BookingNumberResult> {
    const dateStr = toCollmexQueryDate(invoiceDate);
    const csv = `ACCDOC_GET;${this.config.companyNr};;;;;;;;${invoiceNumber};;;;${dateStr};${dateStr}\n`;

    const text = await this.request(csv);
    const rows = parseCsvResponse(text);

    const currentYear = new Date().getFullYear();
    let bestMatch: string | null = null;
    let bestYear = 0;

    for (const row of rows) {
      if (row[0] !== 'ACCDOC' || row.length <= 15) continue;

      const yearStr = (row[2] ?? '').trim();
      const bookingNo = (row[3] ?? '').trim();
      const vNum = (row[14] ?? '').trim();

      if (!bookingNo || !/^\d+$/.test(bookingNo)) continue;

      const year = parseInt(yearStr, 10) || 0;

      // Prefer current year + matching vendor (exact match)
      if (year === currentYear && vNum === vendorNumber) {
        return { bookingNumber: bookingNo };
      }

      // Track best fallback
      if (year > bestYear) {
        bestYear = year;
        bestMatch = bookingNo;
      }
    }

    return { bookingNumber: bestMatch };
  }
}
