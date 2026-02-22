/**
 * Collmex-Invoices MCP Server
 *
 * A Model Context Protocol server that exposes Collmex accounting API
 * operations as tools for LibreChat agents.
 *
 * Tools:
 *   - collmex_get_vendors           — Fetch all vendor master data
 *   - collmex_get_account_chart     — Fetch chart of accounts (SKR03)
 *   - collmex_get_vendor_account_history — Historical expense account usage per vendor
 *   - collmex_select_account        — 5-level account selection logic
 *   - collmex_upload_invoice        — Upload supplier invoices (CMXLRN)
 *   - collmex_get_booking_number    — Retrieve booking number after upload
 *
 * Configuration via environment variables:
 *   COLLMEX_CUSTOMER_ID  — Collmex customer/company ID
 *   COLLMEX_USERNAME     — API username
 *   COLLMEX_PASSWORD     — API password
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { CollmexClient } from './collmex-client.js';
import type { CollmexConfig, InvoiceUpload } from './types.js';

import { handleGetVendors } from './tools/get-vendors.js';
import { handleGetAccountChart } from './tools/get-account-chart.js';
import { handleGetVendorAccountHistory } from './tools/get-vendor-account-history.js';
import { handleSelectAccount } from './tools/select-account.js';
import { handleUploadInvoice } from './tools/upload-invoice.js';
import { handleGetBookingNumber } from './tools/get-booking-number.js';

// ─── Configuration ────────────────────────────────────────────────

function loadConfig(): CollmexConfig {
  const customerId = process.env.COLLMEX_CUSTOMER_ID;
  const username = process.env.COLLMEX_USERNAME;
  const password = process.env.COLLMEX_PASSWORD;

  if (!customerId || !username || !password) {
    console.error(
      'Missing required environment variables: COLLMEX_CUSTOMER_ID, COLLMEX_USERNAME, COLLMEX_PASSWORD',
    );
    process.exit(1);
  }

  return {
    customerId,
    username,
    password,
    companyNr: parseInt(process.env.COLLMEX_COMPANY_NR ?? '1', 10),
    defaultTaxCode: parseInt(process.env.COLLMEX_DEFAULT_TAX_CODE ?? '1600', 10),
    defaultCurrency: process.env.COLLMEX_DEFAULT_CURRENCY ?? 'EUR',
    unknownVendorNumber: process.env.COLLMEX_UNKNOWN_VENDOR ?? '9999',
    accountHistoryYears: parseInt(process.env.COLLMEX_ACCOUNT_HISTORY_YEARS ?? '2', 10),
    apiTimeoutMs: parseInt(process.env.COLLMEX_API_TIMEOUT_MS ?? '30000', 10),
  };
}

// ─── Server setup ─────────────────────────────────────────────────

async function main() {
  const config = loadConfig();
  const client = new CollmexClient(config);

  const server = new McpServer({
    name: 'Collmex-Invoices',
    version: '1.0.0',
  });

  // --- collmex_get_vendors ---
  server.tool(
    'collmex_get_vendors',
    `Retrieve all vendor (supplier) master data from Collmex. Returns vendor numbers, company names, preferred expense accounts, and the unknown-vendor fallback number (${config.unknownVendorNumber}). Call this first to identify which vendor number belongs to an invoice vendor name.`,
    {},
    async () => handleGetVendors(client, config),
  );

  // --- collmex_get_account_chart ---
  server.tool(
    'collmex_get_account_chart',
    'Retrieve all expense and asset accounts (SKR03 chart of accounts) from Collmex. Returns account numbers and names. Use this to validate account numbers and display human-readable account names.',
    {},
    async () => handleGetAccountChart(client),
  );

  // --- collmex_get_vendor_account_history ---
  server.tool(
    'collmex_get_vendor_account_history',
    `Retrieve historical expense account usage for a specific Collmex vendor. Analyses past bookings to determine which expense accounts were used most frequently. The most-used account is typically the best choice (80%+ accuracy). Returns accounts sorted by frequency. Default lookback: ${config.accountHistoryYears} years.`,
    {
      vendor_number: z.string().describe('Collmex vendor number (e.g., "70001")'),
      years_back: z.number().nullish().default(config.accountHistoryYears).describe(`Number of years of history to analyse (default: ${config.accountHistoryYears})`),
    },
    async (args) => handleGetVendorAccountHistory(client, args),
  );

  // --- collmex_select_account ---
  server.tool(
    'collmex_select_account',
    'Apply the 5-level account selection logic to determine the best expense account for an invoice. Priority: 1) Historical usage, 2) Vendor preferred account, 3) AI/LLM suggestion, 4) Static keyword rules, 5) Default 4900. Provide as many inputs as available.',
    {
      vendor_name: z.string().describe('Vendor/company name (for static rule matching)'),
      vendor_preferred_account: z.string().nullish().describe('Preferred expense account from vendor master data'),
      account_history: z
        .array(
          z.object({
            account: z.string(),
            frequency: z.number(),
            percentage: z.number().nullish(),
          }),
        )
        .nullish()
        .describe('Historical account entries from collmex_get_vendor_account_history'),
      ai_suggestion: z.string().nullish().describe('Account number suggested by your analysis of the invoice content'),
    },
    async (args) => handleSelectAccount(args),
  );

  // --- collmex_upload_invoice ---
  server.tool(
    'collmex_upload_invoice',
    `Upload one or more supplier invoices to Collmex. Creates CMXLRN booking records. Defaults: currency=${config.defaultCurrency}, tax_code=${config.defaultTaxCode} (19% VAT), company=${config.companyNr}. IMPORTANT: Always confirm with the user before calling this — uploads cannot be easily undone.`,
    {
      invoices: z
        .array(
          z.object({
            vendor_number: z.string().describe('Collmex vendor number (e.g., "70001")'),
            invoice_date: z.string().describe('Invoice date in YYYY-MM-DD format'),
            invoice_number: z.string().describe('Invoice number as shown on the invoice'),
            net_amount: z.number().describe('Net amount (excluding VAT) in EUR'),
            vat_amount: z.number().describe('VAT amount in EUR'),
            expense_account: z.string().describe('Expense account number (e.g., "4616")'),
            booking_text: z.string().nullish().describe('Booking text / description'),
            currency: z.string().nullish().describe(`Currency code (default: ${config.defaultCurrency})`),
            tax_code: z.number().nullish().describe(`Collmex tax code / Steuerschlüssel (default: ${config.defaultTaxCode} = 19% VAT). Use 0 for tax-free, 8 for 7% VAT.`),
          }),
        )
        .describe('Array of invoice objects to upload'),
    },
    async (args) => handleUploadInvoice(client, args as { invoices: InvoiceUpload[] }),
  );

  // --- collmex_get_booking_number ---
  server.tool(
    'collmex_get_booking_number',
    'Retrieve the Collmex-assigned booking number for a recently uploaded invoice. Wait at least 2-3 seconds after uploading before calling this.',
    {
      vendor_number: z.string().describe('Collmex vendor number (e.g., "70001")'),
      invoice_number: z.string().describe('Invoice number exactly as uploaded'),
      invoice_date: z.string().describe('Invoice date in YYYY-MM-DD format'),
    },
    async (args) => handleGetBookingNumber(client, args),
  );

  // Connect via stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('Collmex-Invoices MCP server started (stdio)');
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
