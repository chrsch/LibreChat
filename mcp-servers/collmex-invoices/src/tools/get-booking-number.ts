/**
 * Tool: collmex_get_booking_number
 *
 * Retrieves the Collmex-assigned booking number for a recently uploaded invoice.
 */

import type { CollmexClient } from '../collmex-client.js';

export const GET_BOOKING_NUMBER_TOOL = {
  name: 'collmex_get_booking_number',
  description:
    'Retrieve the Collmex-assigned booking number (Buchungsnummer) for a recently uploaded invoice. IMPORTANT: Wait at least 2-3 seconds after uploading before calling this, as Collmex needs time to process the booking.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      vendor_number: {
        type: 'string',
        description: 'Collmex vendor number (e.g., "70001")',
      },
      invoice_number: {
        type: 'string',
        description: 'Invoice number exactly as uploaded',
      },
      invoice_date: {
        type: 'string',
        description: 'Invoice date in YYYY-MM-DD format',
      },
    },
    required: ['vendor_number', 'invoice_number', 'invoice_date'],
  },
};

export async function handleGetBookingNumber(
  client: CollmexClient,
  args: { vendor_number: string; invoice_number: string; invoice_date: string },
) {
  const result = await client.getBookingNumber(
    args.vendor_number,
    args.invoice_number,
    args.invoice_date,
  );

  if (result.bookingNumber) {
    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            { booking_number: result.bookingNumber, found: true },
            null,
            2,
          ),
        },
      ],
    };
  }

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            booking_number: null,
            found: false,
            hint: 'Booking number not found. The invoice may not have been processed yet. Try again after a few seconds.',
          },
          null,
          2,
        ),
      },
    ],
  };
}
