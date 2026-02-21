/**
 * Tool: collmex_select_account
 *
 * Applies the 5-level account selection logic server-side.
 */

import type { AccountSelection } from '../types.js';

/** Static vendor keyword → account mapping (fallback level 4) */
const STATIC_RULES: Record<string, string> = {
  apple: '4616',
  jetbrains: '4616',
  github: '4616',
  openai: '4616',
  udemy: '4616',
  leetcode: '4616',
  hetzner: '4640',
  manitu: '4640',
  uptimerobot: '4640',
  signal: '4640',
  posteo: '4640',
  collmex: '4964',
  nzz: '4940',
  congstar: '4920',
  drillisch: '4920',
};

const DEFAULT_ACCOUNT = '4900';

export const SELECT_ACCOUNT_TOOL = {
  name: 'collmex_select_account',
  description:
    'Apply the 5-level account selection logic to determine the best expense account for an invoice. Priority: 1) Historical usage (most reliable), 2) Vendor preferred account from master data, 3) AI/LLM suggestion, 4) Static keyword rules, 5) Default account 4900. Provide as many inputs as available for best results.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      vendor_name: {
        type: 'string',
        description: 'Vendor/company name (for static rule matching)',
      },
      vendor_preferred_account: {
        type: 'string',
        description:
          'Preferred expense account from vendor master data (from collmex_get_vendors)',
      },
      account_history: {
        type: 'array',
        description:
          'Historical account entries from collmex_get_vendor_account_history',
        items: {
          type: 'object',
          properties: {
            account: { type: 'string' },
            frequency: { type: 'number' },
            percentage: { type: 'number' },
          },
          required: ['account', 'frequency'],
        },
      },
      ai_suggestion: {
        type: 'string',
        description:
          'Account number suggested by your own analysis of the invoice content',
      },
    },
    required: ['vendor_name'],
  },
};

export async function handleSelectAccount(args: {
  vendor_name: string;
  vendor_preferred_account?: string;
  account_history?: Array<{ account: string; frequency: number; percentage?: number }>;
  ai_suggestion?: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  let selection: AccountSelection;

  // 1. Historical (highest priority)
  if (args.account_history && args.account_history.length > 0) {
    const best = args.account_history.reduce((a, b) =>
      a.frequency >= b.frequency ? a : b,
    );
    selection = {
      account: best.account,
      reason: `Used ${best.frequency}x historically (${best.percentage ?? '?'}% of bookings)`,
      source: 'historical',
    };
  }
  // 2. Vendor preferred
  else if (args.vendor_preferred_account) {
    selection = {
      account: args.vendor_preferred_account,
      reason: 'Vendor master data preferred account (Aufwandskonto)',
      source: 'vendor_preferred',
    };
  }
  // 3. AI suggestion
  else if (args.ai_suggestion) {
    selection = {
      account: args.ai_suggestion,
      reason: 'LLM analysis of invoice content',
      source: 'ai',
    };
  }
  // 4. Static rules
  else {
    const nameLower = args.vendor_name.toLowerCase();
    let matched = false;
    for (const [keyword, account] of Object.entries(STATIC_RULES)) {
      if (nameLower.includes(keyword)) {
        selection = {
          account,
          reason: `Static rule match for keyword "${keyword}"`,
          source: 'static',
        };
        matched = true;
        break;
      }
    }
    // 5. Default
    if (!matched!) {
      selection = {
        account: DEFAULT_ACCOUNT,
        reason: 'No match found — using default general expense account',
        source: 'default',
      };
    }
  }

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(selection!, null, 2),
      },
    ],
  };
}
