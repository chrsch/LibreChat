/**
 * Tool: collmex_get_vendors
 *
 * Retrieves all vendor (supplier) master data from Collmex.
 */

import type { CollmexClient } from '../collmex-client.js';
import type { CollmexConfig } from '../types.js';

export const GET_VENDORS_TOOL = {
  name: 'collmex_get_vendors',
  description:
    'Retrieve all vendor (supplier) master data from Collmex. Returns vendor numbers, company names, and preferred expense accounts. Call this first to identify which vendor number belongs to an invoice vendor name.',
  inputSchema: {
    type: 'object' as const,
    properties: {},
    required: [] as string[],
  },
};

export async function handleGetVendors(client: CollmexClient, config: CollmexConfig) {
  const vendors = await client.fetchVendors();
  const result = {
    vendors,
    unknown_vendor_number: config.unknownVendorNumber,
    note: `Use vendor number "${config.unknownVendorNumber}" for vendors not found in the list. Warn the user when using the unknown vendor.`,
  };
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(result, null, 2),
      },
    ],
  };
}
