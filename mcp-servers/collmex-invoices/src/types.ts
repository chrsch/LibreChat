/**
 * Shared TypeScript interfaces for the Collmex-Invoices MCP server.
 */

export interface Vendor {
  number: string;
  name: string;
  preferredAccount: string | null;
}

export interface Account {
  number: string;
  name: string;
}

export interface AccountHistoryEntry {
  account: string;
  frequency: number;
  percentage: number;
}

export interface InvoiceUpload {
  vendor_number: string;
  invoice_date: string; // YYYY-MM-DD
  invoice_number: string;
  net_amount: number;
  vat_amount: number;
  expense_account: string;
  booking_text?: string;
  currency?: string;
  tax_code?: number;
}

export interface AccountSelection {
  account: string;
  reason: string;
  source: 'historical' | 'vendor_preferred' | 'ai' | 'static' | 'default';
}

export interface UploadResult {
  success: boolean;
  message: string;
  recordsUploaded: number;
}

export interface BookingNumberResult {
  bookingNumber: string | null;
}

export interface CollmexConfig {
  customerId: string;
  username: string;
  password: string;
  companyNr: number;
  defaultTaxCode: number;
  defaultCurrency: string;
  unknownVendorNumber: string;
  accountHistoryYears: number;
  apiTimeoutMs: number;
}
