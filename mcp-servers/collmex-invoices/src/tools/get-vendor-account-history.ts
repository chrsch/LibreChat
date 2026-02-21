/**
 * Tool: collmex_get_vendor_account_history
 *
 * Retrieves historical expense account usage for a specific vendor.
 */

import type { CollmexClient } from '../collmex-client.js';

export const GET_VENDOR_ACCOUNT_HISTORY_TOOL = {
  name: 'collmex_get_vendor_account_history',
  description:
    'Retrieve historical expense account usage for a specific Collmex vendor. Analyses all bookings from the past N years to determine which expense accounts were used most frequently for this vendor. The most-used account is typically the best choice for new invoices (80%+ accuracy). Returns accounts sorted by frequency with usage percentages.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      vendor_number: {
        type: 'string',
        description: 'Collmex vendor number (e.g., "70001")',
      },
      years_back: {
        type: 'number',
        description: 'Number of years of history to analyse (default: 2)',
        default: 2,
      },
    },
    required: ['vendor_number'],
  },
};

export async function handleGetVendorAccountHistory(
  client: CollmexClient,
  args: { vendor_number: string; years_back?: number },
) {
  const history = await client.fetchVendorAccountHistory(
    args.vendor_number,
    args.years_back ?? 2,
  );

  if (history.length === 0) {
    return {
      content: [
        {
          type: 'text' as const,
          text: `No account history found for vendor ${args.vendor_number}. This vendor may be new or have no bookings in the past ${args.years_back ?? 2} years.`,
        },
      ],
    };
  }

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(history, null, 2),
      },
    ],
  };
}
