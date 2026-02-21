/**
 * Tool: collmex_get_account_chart
 *
 * Retrieves the chart of accounts (SKR03) from Collmex.
 */

import type { CollmexClient } from '../collmex-client.js';

export const GET_ACCOUNT_CHART_TOOL = {
  name: 'collmex_get_account_chart',
  description:
    'Retrieve all expense and asset accounts (SKR03 chart of accounts) from Collmex. Returns account numbers and names. Use this to validate account numbers and display human-readable account names. Common expense accounts: 4616 (Software), 4640 (Internet/Hosting), 4800 (Marketing), 4900 (General expenses), 4920 (Telephone), 4940 (Books).',
  inputSchema: {
    type: 'object' as const,
    properties: {},
    required: [] as string[],
  },
};

export async function handleGetAccountChart(client: CollmexClient) {
  const accounts = await client.fetchAccountChart();
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(accounts, null, 2),
      },
    ],
  };
}
