# Invoice Extraction Prompt for qwen2.5-3b-instruct-invoice-extractor-gtx1650

## System Prompt (Already in Modelfile)

The Modelfile already includes the base system prompt. Use the instructions below in your agent or chat.

## User Instructions for Agent / Chat

Use this prompt when extracting invoice data with `qwen2.5-3b-instruct-invoice-extractor-gtx1650`:

```
Extract all invoice information from the provided text and return a JSON object with the following structure. Follow these rules strictly:

1. Extract ONLY from the provided context - never guess or infer missing data
2. Return null for any field not explicitly present in the text
3. Follow the exact schema below
4. Use ISO 8601 dates (YYYY-MM-DD)
5. Use ISO 4217 currency codes (e.g., "EUR", "USD")
6. Use dot as decimal separator for all numbers (e.g., 1234.56)
7. Do not add explanations, prose, or additional fields
8. Output JSON only

JSON Schema:
{
  "vendor": null,
  "vendor_number": null,
  "invoice_number": null,
  "invoice_date": null,
  "due_date": null,
  "currency": null,
  "total_amount": null,
  "vat_amount": null,
  "vat_rate": null,
  "item_summary": null,
  "line_items": [
    {
      "description": null,
      "quantity": null,
      "unit_price": null,
      "amount": null
    }
  ]
}

Field Definitions:
- vendor: The name of the company/person issuing the invoice
- vendor_number: The supplier/vendor number (Lieferantennummer) if present
- invoice_number: The invoice reference/number
- invoice_date: The date the invoice was issued (YYYY-MM-DD)
- due_date: The payment due date (YYYY-MM-DD)
- currency: ISO 4217 currency code (e.g., "EUR", "USD", "GBP")
- total_amount: Total invoice amount including VAT (number with dot decimal)
- vat_amount: Total VAT/tax amount (number with dot decimal)
- vat_rate: VAT/tax rate as a percentage (e.g., 19 for 19%, 7 for 7%)
- item_summary: Brief summary of all line items (max 15 words, e.g., "Office chairs, desks, and supplies")
- line_items: Array of invoice line items, each with:
  - description: Item/service description
  - quantity: Number of units (number)
  - unit_price: Price per unit (number with dot decimal)
  - amount: Total for this line (number with dot decimal)

Return ONLY the JSON object. Do not include any markdown code blocks, explanations, or additional text.

If vendor numbers are not on invoices, provide them in the prompt:

Known vendor numbers:
- ACME Corp: V12345
- Global Supplies GmbH: V67890
- Tech Solutions Ltd: V24680

If you identify the vendor name, use the corresponding vendor_number from the list above.
```

## Example Usage in LibreChat Agent

1. **Select Model**: `qwen2.5-3b-instruct-invoice-extractor-gtx1650`
2. **Upload Invoice**: Use "Upload as Text" for short invoices (< 2 pages) or use RAG for longer documents
3. **Paste Prompt**: Copy the user instructions above (including your known vendor numbers)
4. **Send**: The model will return pure JSON

## Example Output

```json
{
  "vendor": "Global Supplies GmbH",
  "vendor_number": "V67890",
  "invoice_number": "INV-2024-001234",
  "invoice_date": "2024-10-15",
  "due_date": "2024-11-14",
  "currency": "EUR",
  "total_amount": 1190.00,
  "vat_amount": 190.00,
  "vat_rate": 19,
  "item_summary": "Office chairs and furniture",
  "line_items": [
    {
      "description": "Office Chairs - Model XYZ",
      "quantity": 10,
      "unit_price": 100.00,
      "amount": 1000.00
    }
  ]
}
```

## Tips for Best Results

1. **Keep Temperature Low**: The Modelfile is set to 0.15 - keep it there for consistent output
2. **Use RAG for Multi-Page**: For invoices > 2 pages, prefer RAG to retrieve only relevant chunks
3. **Validate Output**: Always validate the JSON structure in your application
4. **Handle Nulls**: Check for null values and handle missing data appropriately
5. **Date Normalization**: The model will attempt ISO format, but validate dates in your app
6. **Vendor Lookup**: For production, maintain a vendor master database and do post-extraction matching
7. **OCR Quality**: Ensure clean text extraction from PDFs (use tools like Unstructured, PyMuPDF, or Marker)

## Common Issues

### Model Returns Explanation Text Instead of JSON

- Ensure you're using `qwen2.5-3b-instruct-invoice-extractor-gtx1650`
- The Modelfile includes format hints, but if issues persist, add: "Return ONLY the JSON object with no markdown formatting."

### Missing Fields

- Check if the field exists in the source document
- OCR quality issues can cause missing text
- The model correctly returns null for absent fields

### Wrong Date Format

- Add explicit example: "invoice_date must be YYYY-MM-DD, e.g., 2024-11-02"

### Vendor Number Not Found

- Provide known vendor mappings in the prompt (see example above)
- The model will match vendor names to the provided vendor_number list

---

**Note**: This prompt is optimized for `qwen2.5-3b-instruct-invoice-extractor-gtx1650` with low temperature (0.15) for deterministic JSON output.
