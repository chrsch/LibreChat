/**
 * Tool: collmex_upload_invoice
 *
 * Uploads one or more supplier invoices to Collmex via CMXLRN format.
 */

import type { CollmexClient } from '../collmex-client.js';
import type { InvoiceUpload } from '../types.js';

export const UPLOAD_INVOICE_TOOL = {
  name: 'collmex_upload_invoice',
  description:
    'Upload one or more supplier invoices to Collmex. Creates CMXLRN (Lieferantenrechnung) booking records. IMPORTANT: Always confirm with the user before calling this tool — uploads cannot be easily undone. Requires: vendor_number, invoice_date (YYYY-MM-DD), invoice_number, net_amount, vat_amount, and expense_account.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      invoices: {
        type: 'array',
        description: 'Array of invoice objects to upload',
        items: {
          type: 'object',
          properties: {
            vendor_number: {
              type: 'string',
              description: 'Collmex vendor number (e.g., "70001")',
            },
            invoice_date: {
              type: 'string',
              description: 'Invoice date in YYYY-MM-DD format',
            },
            invoice_number: {
              type: 'string',
              description: 'Invoice number as shown on the invoice',
            },
            net_amount: {
              type: 'number',
              description: 'Net amount (excluding VAT) in EUR',
            },
            vat_amount: {
              type: 'number',
              description: 'VAT amount in EUR',
            },
            expense_account: {
              type: 'string',
              description: 'Expense account number (e.g., "4616")',
            },
            booking_text: {
              type: 'string',
              description:
                'Booking text / description. If omitted, defaults to "Rechnung {invoice_number}"',
            },
            currency: {
              type: 'string',
              description: 'Currency code (default: "EUR")',
              default: 'EUR',
            },
          },
          required: [
            'vendor_number',
            'invoice_date',
            'invoice_number',
            'net_amount',
            'vat_amount',
            'expense_account',
          ],
        },
      },
    },
    required: ['invoices'],
  },
};

export async function handleUploadInvoice(
  client: CollmexClient,
  args: { invoices: InvoiceUpload[] },
) {
  if (!args.invoices || args.invoices.length === 0) {
    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            { success: false, message: 'No invoices provided', recordsUploaded: 0 },
            null,
            2,
          ),
        },
      ],
    };
  }

  // Validate required fields
  for (const inv of args.invoices) {
    const missing: string[] = [];
    if (!inv.vendor_number) missing.push('vendor_number');
    if (!inv.invoice_date) missing.push('invoice_date');
    if (!inv.invoice_number) missing.push('invoice_number');
    if (inv.net_amount == null) missing.push('net_amount');
    if (inv.vat_amount == null) missing.push('vat_amount');
    if (!inv.expense_account) missing.push('expense_account');

    if (missing.length > 0) {
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(
              {
                success: false,
                message: `Invoice ${inv.invoice_number ?? '(unknown)'} missing required fields: ${missing.join(', ')}`,
                recordsUploaded: 0,
              },
              null,
              2,
            ),
          },
        ],
      };
    }
  }

  const result = await client.uploadInvoices(args.invoices);

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(result, null, 2),
      },
    ],
  };
}
