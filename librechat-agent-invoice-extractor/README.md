# LibreChat Agent Invoice Extractor

A complete solution for extracting structured invoice data from PDF files using LibreChat agents and the `qwen2.5-3b-instruct-invoice-extractor-gtx1650` model.

## Features

- ✅ **PDF Upload** - Upload invoices directly to LibreChat (like "Upload as Text" in UI)
- ✅ **Structured JSON Output** - Extract all invoice fields in a consistent schema
- ✅ **Dynamic Vendor Mapping** - Provide updated vendor numbers with each request
- ✅ **CLI & Python API** - Use as command-line tool or import as library
- ✅ **Batch Processing** - Process multiple invoices efficiently
- ✅ **Session Management** - Automatic authentication and cookie handling

## Quick Start

### Prerequisites

```bash
pip install requests
```

### Basic Usage

```bash
# Set credentials
export LIBRECHAT_EMAIL="your-email@example.com"
export LIBRECHAT_PASSWORD="your-password"

# Extract invoice
./librechat_invoice_extractor.py --pdf invoice.pdf
```

### With Custom Vendor Mappings

```bash
# Create vendors.json
cp vendors.example.json vendors.json
# Edit vendors.json with your actual vendors

# Extract with custom vendors
./librechat_invoice_extractor.py \
  --pdf invoice.pdf \
  --vendors vendors.json \
  --output result.json
```

## Extracted Data Schema

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

## Documentation

- **[Model Configuration](MODEL-CONFIGURATION.md)** - Setup the Ollama model in LibreChat
- **[Quick Start Guide](docs/quickstart.md)** - Get started in 5 minutes
- **[API Reference](docs/api-reference.md)** - Complete Python API documentation
- **[Prompt Template](docs/prompt-template.md)** - Extraction prompt guide and customization

## Files

- **`librechat_invoice_extractor.py`** - Main CLI script and Python library
- **`vendors.example.json`** - Example vendor mappings template
- **`docs/quickstart.md`** - Quick start examples
- **`docs/api-reference.md`** - Full API documentation with integration examples
- **`docs/prompt-template.md`** - Prompt customization and vendor lookup options
- **`examples/`** - Example scripts (batch processing, Flask/Django integration)

## Python API Example

```python
from librechat_invoice_extractor import LibreChatInvoiceExtractor

# Initialize
client = LibreChatInvoiceExtractor("http://localhost:3080")
client.login("user@example.com", "password")

# Upload PDF
file_data = client.upload_file("invoice.pdf")

# Extract with vendor mappings
vendors = {
    "ACME Corp": "V12345",
    "Global Supplies GmbH": "V67890"
}
result = client.extract_invoice(file_data, vendors)

print(result)
```

## CLI Usage

```bash
# Basic extraction
./librechat_invoice_extractor.py --pdf invoice.pdf

# With all options
./librechat_invoice_extractor.py \
  --pdf path/to/invoice.pdf \
  --email user@example.com \
  --password secret \
  --url http://localhost:3080 \
  --model qwen2.5-3b-instruct-invoice-extractor-gtx1650 \
  --vendors vendors.json \
  --output extracted_data.json
```

## Configuration

### Environment Variables

```bash
export LIBRECHAT_URL="http://localhost:3080"
export LIBRECHAT_EMAIL="user@example.com"
export LIBRECHAT_PASSWORD="your-password"
export LIBRECHAT_MODEL="qwen2.5-3b-instruct-invoice-extractor-gtx1650"
```

### Vendor Mappings

Edit `vendors.json` with your vendor database:

```json
{
  "ACME Corp": "V12345",
  "Global Supplies GmbH": "V67890",
  "Tech Solutions Ltd": "V24680"
}
```

Update this file before processing invoices to ensure accurate vendor number mapping.

## Model Configuration

The extractor uses the `qwen2.5-3b-instruct-invoice-extractor-gtx1650` model, which is optimized for:

- **Context Size**: 4096 tokens
- **Temperature**: 0.15 (low for deterministic output)
- **JSON Output**: Strict schema enforcement
- **Hardware**: GTX 1650 4GB VRAM

For setup instructions, see **[MODEL-CONFIGURATION.md](MODEL-CONFIGURATION.md)**

Modelfile location: [`../ollama/Modelfiles/qwen2.5-3b-instruct-invoice-extractor-gtx1650/`](../ollama/Modelfiles/qwen2.5-3b-instruct-invoice-extractor-gtx1650/)

## Integration Examples

### Batch Processing

```python
from pathlib import Path
from librechat_invoice_extractor import LibreChatInvoiceExtractor

client = LibreChatInvoiceExtractor()
client.login("user@example.com", "password")

vendors = load_vendors()  # Your function

for pdf in Path("./invoices").glob("*.pdf"):
    file_data = client.upload_file(str(pdf))
    result = client.extract_invoice(file_data, vendors)
    save_to_database(result)
```

### Flask API Endpoint

```python
from flask import Flask, request, jsonify
from librechat_invoice_extractor import LibreChatInvoiceExtractor

app = Flask(__name__)
client = LibreChatInvoiceExtractor()

@app.route('/extract', methods=['POST'])
def extract():
    file = request.files['invoice']
    vendors = get_vendors_from_db()
    
    file_data = client.upload_file(file)
    result = client.extract_invoice(file_data, vendors)
    
    return jsonify(result)
```

See [`docs/api-reference.md`](docs/api-reference.md) for more integration examples.

## Troubleshooting

### Login Failed
- Check email/password
- Verify LibreChat is running: `curl http://localhost:3080`

### File Upload Failed
- Ensure file exists and is readable
- Check file size limits in LibreChat config

### Extraction Returns Null
- Verify PDF has extractable text (not scanned image)
- Check model name is correct
- Review LibreChat logs: `docker logs LibreChat`

### Vendor Number Not Found
- Ensure vendor name matches your mapping exactly
- Add more variations to `vendors.json`

## Requirements

- Python 3.7+
- `requests` library
- LibreChat instance running with the invoice extraction model
- PDF files with extractable text (OCR if needed)

## Related Documentation

- [Ollama Models Setup](../README-Ollama-Extension.md) - Model configuration and optimization
- [LibreChat Configuration](../librechat.yaml) - Main LibreChat setup
- [Docker Setup](../docker-compose.override.yml) - Container configuration

## License

Part of the LibreChat project. See main repository for license details.

## Support

For issues and questions:
- Check [docs/api-reference.md](docs/api-reference.md) for detailed troubleshooting
- Review LibreChat logs: `docker logs LibreChat`
- Check Ollama logs: `docker logs Ollama`
