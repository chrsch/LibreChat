# Quick Start: Python Invoice Extraction

This guide shows how to quickly extract invoice data from PDFs using Python.

## Prerequisites

```bash
pip install requests
```

## Method 1: CLI Script (Easiest)

### Basic Usage

```bash
# Set credentials (recommended)
export LIBRECHAT_EMAIL="your-email@example.com"
export LIBRECHAT_PASSWORD="your-password"

# Extract invoice
python librechat_invoice_extractor.py --pdf invoice.pdf
```

### With Custom Vendor Mappings

```bash
# Create vendors.json with your vendor mappings
cat > vendors.json << 'EOF'
{
  "ACME Corp": "V12345",
  "Global Supplies GmbH": "V67890",
  "Tech Solutions Ltd": "V24680"
}
EOF

# Extract with custom vendors
python librechat_invoice_extractor.py \
  --pdf invoice.pdf \
  --vendors vendors.json \
  --output result.json
```

### All Options

```bash
python librechat_invoice_extractor.py \
  --pdf path/to/invoice.pdf \
  --email user@example.com \
  --password secret \
  --url http://localhost:3080 \
  --model qwen2.5-3b-instruct-invoice-extractor-gtx1650 \
  --vendors vendors.json \
  --output extracted_data.json
```

## Method 2: Python Script

Create `extract_my_invoice.py`:

```python
#!/usr/bin/env python3
import json
from librechat_invoice_extractor import LibreChatInvoiceExtractor

# Configuration
LIBRECHAT_URL = "http://localhost:3080"
EMAIL = "your-email@example.com"
PASSWORD = "your-password"
PDF_PATH = "invoice.pdf"

# Your vendor mappings
VENDORS = {
    "ACME Corp": "V12345",
    "Global Supplies GmbH": "V67890",
    "Tech Solutions Ltd": "V24680"
}

# Initialize and login
client = LibreChatInvoiceExtractor(LIBRECHAT_URL)
client.login(EMAIL, PASSWORD)

# Upload PDF
file_data = client.upload_file(PDF_PATH)

# Extract invoice data
invoice_data = client.extract_invoice(file_data, VENDORS)

# Print results
print(json.dumps(invoice_data, indent=2))

# Save to file
with open("extracted_invoice.json", "w") as f:
    json.dump(invoice_data, f, indent=2)
```

Run it:
```bash
python extract_my_invoice.py
```

## Method 3: Batch Processing

Process multiple invoices:

```python
#!/usr/bin/env python3
from pathlib import Path
import json
from librechat_invoice_extractor import LibreChatInvoiceExtractor

# Setup
client = LibreChatInvoiceExtractor()
client.login("user@example.com", "password")

# Load vendors from file
with open("vendors.json") as f:
    vendors = json.load(f)

# Process all PDFs
invoice_dir = Path("./invoices")
for pdf in invoice_dir.glob("*.pdf"):
    print(f"\n Processing: {pdf.name}")
    
    # Upload and extract
    file_data = client.upload_file(str(pdf))
    if file_data:
        result = client.extract_invoice(file_data, vendors)
        
        # Save result
        output = pdf.with_suffix('.json')
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ Saved: {output}")
```

## Expected Output

```json
{
  "vendor": "Global Supplies GmbH",
  "vendor_number": "V67890",
  "invoice_number": "INV-2024-001234",
  "invoice_date": "2024-10-15",
  "due_date": "2024-11-14",
  "currency": "EUR",
  "total_amount": 1190.0,
  "vat_amount": 190.0,
  "vat_rate": 19,
  "item_summary": "Office chairs and furniture",
  "line_items": [
    {
      "description": "Office Chairs - Model XYZ",
      "quantity": 10,
      "unit_price": 100.0,
      "amount": 1000.0
    }
  ]
}
```

## Tips

1. **Always update vendor mappings** before processing invoices
2. **Use environment variables** for credentials (never hardcode passwords)
3. **Validate extracted data** before saving to database
4. **Handle null values** - the model returns null for missing fields
5. **Check OCR quality** - ensure PDFs have extractable text

## Troubleshooting

### "Login failed"
- Check email/password
- Verify LibreChat is running: `curl http://localhost:3080`

### "File upload failed"
- Check file exists and is readable
- Verify file is a valid PDF

### "Extraction failed" or returns null
- Check model name is correct
- Verify PDF contains extractable text (not just scanned images)
- Review LibreChat logs: `docker logs LibreChat`

### Vendor number not matched
- Ensure vendor name in invoice matches your mapping exactly
- Try adding more variations to your vendors.json

## Next Steps

- See full documentation: [`docs/python-invoice-extraction-api.md`](docs/python-invoice-extraction-api.md)
- Customize extraction prompt: [`docs/invoice-extraction-prompt.md`](docs/invoice-extraction-prompt.md)
- Optimize models: [`README-Ollama-Extension.md`](README-Ollama-Extension.md#optimizing-ollama-model-performance)
