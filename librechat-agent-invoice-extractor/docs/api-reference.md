# Python API for Invoice Extraction with LibreChat Agents

This guide shows how to use LibreChat's agent API to extract invoice information from PDF files using Python.

## Overview

The workflow:
1. Authenticate with LibreChat
2. Upload PDF file (similar to "Upload as Text" in UI)
3. Create or continue a conversation with the invoice extraction agent
4. Send extraction prompt with vendor mappings
5. Receive structured JSON response

## Prerequisites

```bash
pip install requests
```

## Complete Working Example

```python
#!/usr/bin/env python3
"""
LibreChat Invoice Extraction Client

Uploads a PDF invoice and extracts structured data using the
qwen2.5-3b-instruct-invoice-extractor-gtx1650 model.
"""

import requests
import json
from pathlib import Path
from typing import Dict, List, Optional

class LibreChatInvoiceExtractor:
    """Client for LibreChat invoice extraction API."""
    
    def __init__(self, base_url: str = "http://localhost:3080"):
        """
        Initialize the client.
        
        Args:
            base_url: LibreChat server URL (default: http://localhost:3080)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.conversation_id = None
        self.parent_message_id = None
        
    def login(self, email: str, password: str) -> bool:
        """
        Authenticate with LibreChat.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            True if login successful
        """
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            # Session cookie is automatically stored in self.session
            print("✓ Login successful")
            return True
        else:
            print(f"✗ Login failed: {response.status_code}")
            print(response.text)
            return False
    
    def upload_file(self, file_path: str) -> Optional[Dict]:
        """
        Upload a file to LibreChat (similar to "Upload as Text").
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            File metadata dict or None if failed
        """
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"✗ File not found: {file_path}")
            return None
        
        with open(file_path, 'rb') as f:
            files = {
                'file': (file_path.name, f, 'application/pdf')
            }
            # Set endpoint to 'agents' for agent conversations
            data = {
                'endpoint': 'agents'
            }
            
            response = self.session.post(
                f"{self.base_url}/api/files/upload",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            file_data = response.json()
            print(f"✓ File uploaded: {file_data.get('filename')}")
            return file_data
        else:
            print(f"✗ File upload failed: {response.status_code}")
            print(response.text)
            return None
    
    def extract_invoice(
        self,
        file_data: Dict,
        vendor_mappings: Dict[str, str],
        model: str = "qwen2.5-3b-instruct-invoice-extractor-gtx1650",
        conversation_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract invoice data from uploaded file.
        
        Args:
            file_data: File metadata from upload_file()
            vendor_mappings: Dict mapping vendor names to vendor numbers
            model: Model name to use
            conversation_id: Optional conversation ID to continue
            
        Returns:
            Extracted invoice data as dict or None if failed
        """
        # Build vendor list for prompt
        vendor_list = "\n".join([
            f"- {name}: {number}" 
            for name, number in vendor_mappings.items()
        ])
        
        # Construct the extraction prompt
        prompt = f"""Extract all invoice information from the provided text and return a JSON object with the following structure. Follow these rules strictly:

1. Extract ONLY from the provided context - never guess or infer missing data
2. Return null for any field not explicitly present in the text
3. Follow the exact schema below
4. Use ISO 8601 dates (YYYY-MM-DD)
5. Use ISO 4217 currency codes (e.g., "EUR", "USD")
6. Use dot as decimal separator for all numbers (e.g., 1234.56)
7. Do not add explanations, prose, or additional fields
8. Output JSON only

JSON Schema:
{{
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
    {{
      "description": null,
      "quantity": null,
      "unit_price": null,
      "amount": null
    }}
  ]
}}

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
{vendor_list}

If you identify the vendor name, use the corresponding vendor_number from the list above."""

        # Prepare the message payload
        payload = {
            "endpoint": "agents",
            "model": model,
            "text": prompt,
            "conversationId": conversation_id or "new",
            "parentMessageId": self.parent_message_id or "00000000-0000-0000-0000-000000000000",
            "files": [
                {
                    "file_id": file_data.get("file_id"),
                    "filepath": file_data.get("filepath"),
                    "filename": file_data.get("filename"),
                    "type": file_data.get("type"),
                    "height": file_data.get("height"),
                    "width": file_data.get("width")
                }
            ]
        }
        
        print(f"✓ Sending extraction request with model: {model}")
        
        # Send the message
        response = self.session.post(
            f"{self.base_url}/api/ask/agents",
            json=payload,
            stream=True
        )
        
        if response.status_code != 200:
            print(f"✗ Extraction failed: {response.status_code}")
            print(response.text)
            return None
        
        # Parse streaming response
        full_response = ""
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_str = line_text[6:]  # Remove 'data: ' prefix
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        # Accumulate text from streaming response
                        if 'text' in data:
                            full_response = data['text']
                        # Store conversation metadata
                        if 'conversationId' in data:
                            self.conversation_id = data['conversationId']
                        if 'messageId' in data:
                            self.parent_message_id = data['messageId']
                    except json.JSONDecodeError:
                        continue
        
        print("✓ Extraction complete")
        
        # Parse the JSON response from the model
        try:
            # The model should return pure JSON, but handle markdown code blocks just in case
            json_text = full_response.strip()
            if json_text.startswith('```'):
                # Extract JSON from markdown code block
                lines = json_text.split('\n')
                json_text = '\n'.join(lines[1:-1])
            
            invoice_data = json.loads(json_text)
            return invoice_data
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse JSON response: {e}")
            print(f"Raw response: {full_response}")
            return None


def main():
    """Example usage of the LibreChat invoice extractor."""
    
    # Configuration
    LIBRECHAT_URL = "http://localhost:3080"
    EMAIL = "your-email@example.com"
    PASSWORD = "your-password"
    PDF_PATH = "path/to/invoice.pdf"
    
    # Vendor mappings (update this with your vendors)
    VENDOR_MAPPINGS = {
        "ACME Corp": "V12345",
        "Global Supplies GmbH": "V67890",
        "Tech Solutions Ltd": "V24680",
        "Office Depot": "V13579",
        "Staples Inc": "V98765"
    }
    
    # Initialize client
    client = LibreChatInvoiceExtractor(base_url=LIBRECHAT_URL)
    
    # Step 1: Login
    if not client.login(EMAIL, PASSWORD):
        return
    
    # Step 2: Upload PDF
    file_data = client.upload_file(PDF_PATH)
    if not file_data:
        return
    
    # Step 3: Extract invoice data
    invoice_data = client.extract_invoice(
        file_data=file_data,
        vendor_mappings=VENDOR_MAPPINGS
    )
    
    if invoice_data:
        # Step 4: Process the results
        print("\n" + "="*60)
        print("EXTRACTED INVOICE DATA")
        print("="*60)
        print(json.dumps(invoice_data, indent=2, ensure_ascii=False))
        print("="*60)
        
        # Example: Access specific fields
        print(f"\nVendor: {invoice_data.get('vendor')}")
        print(f"Vendor Number: {invoice_data.get('vendor_number')}")
        print(f"Invoice #: {invoice_data.get('invoice_number')}")
        print(f"Total: {invoice_data.get('total_amount')} {invoice_data.get('currency')}")
        print(f"Summary: {invoice_data.get('item_summary')}")
        
        # Example: Save to file
        output_path = Path(PDF_PATH).with_suffix('.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(invoice_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to: {output_path}")


if __name__ == "__main__":
    main()
```

## Usage

### 1. Basic Usage

```python
from invoice_extractor import LibreChatInvoiceExtractor

# Initialize
client = LibreChatInvoiceExtractor("http://localhost:3080")

# Login
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

### 2. Batch Processing

```python
from pathlib import Path

client = LibreChatInvoiceExtractor()
client.login("user@example.com", "password")

# Load vendor mappings from database/file
vendors = load_vendor_mappings()  # Your function

# Process all PDFs in a folder
invoice_dir = Path("./invoices")
for pdf_path in invoice_dir.glob("*.pdf"):
    print(f"\nProcessing: {pdf_path.name}")
    
    file_data = client.upload_file(str(pdf_path))
    if file_data:
        result = client.extract_invoice(file_data, vendors)
        if result:
            # Save or process result
            save_to_database(result)
```

### 3. With Updated Vendor List

```python
def get_latest_vendor_mappings(db_connection):
    """Fetch current vendor mappings from database."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT vendor_name, vendor_number FROM vendors WHERE active = 1")
    return dict(cursor.fetchall())

# Use fresh vendor data for each extraction
client = LibreChatInvoiceExtractor()
client.login("user@example.com", "password")

file_data = client.upload_file("invoice.pdf")
vendors = get_latest_vendor_mappings(db_conn)  # Always current
result = client.extract_invoice(file_data, vendors)
```

### 4. Error Handling

```python
client = LibreChatInvoiceExtractor()

try:
    if not client.login(email, password):
        raise Exception("Login failed")
    
    file_data = client.upload_file(pdf_path)
    if not file_data:
        raise Exception("File upload failed")
    
    result = client.extract_invoice(file_data, vendor_mappings)
    if not result:
        raise Exception("Extraction failed")
    
    # Validate result
    required_fields = ['vendor', 'invoice_number', 'total_amount']
    missing = [f for f in required_fields if result.get(f) is None]
    if missing:
        print(f"Warning: Missing fields: {missing}")
    
    return result
    
except Exception as e:
    print(f"Error: {e}")
    return None
```

## Expected Response Format

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

## Configuration Options

### Environment Variables

```bash
# .env file or export
export LIBRECHAT_URL="http://localhost:3080"
export LIBRECHAT_EMAIL="user@example.com"
export LIBRECHAT_PASSWORD="your-password"
export LIBRECHAT_MODEL="qwen2.5-3b-instruct-invoice-extractor-gtx1650"
```

Load in Python:
```python
import os
from dotenv import load_dotenv

load_dotenv()

client = LibreChatInvoiceExtractor(
    base_url=os.getenv("LIBRECHAT_URL")
)
client.login(
    email=os.getenv("LIBRECHAT_EMAIL"),
    password=os.getenv("LIBRECHAT_PASSWORD")
)
```

## Tips

1. **Vendor Mappings**: Always fetch the latest vendor list before extraction to ensure up-to-date mappings
2. **Session Reuse**: The client maintains session cookies automatically - no need to login for each request
3. **Conversation Context**: The client tracks `conversation_id` and `parent_message_id` - you can continue conversations if needed
4. **File Size**: Large PDFs (>10MB) may need chunking or RAG processing for best results
5. **Validation**: Always validate extracted data before saving to your database
6. **Error Handling**: Check for `None` returns and handle null values in the JSON response
7. **Rate Limiting**: Add delays between requests if processing many invoices

## Troubleshooting

### Login Fails
- Check username/password
- Verify LibreChat is running: `curl http://localhost:3080`
- Check if registration is required first

### File Upload Fails
- Ensure file exists and is readable
- Check file size limits in LibreChat config
- Verify endpoint is set to 'agents'

### Extraction Returns Null
- Check model name matches exactly
- Verify PDF text is extractable (not scanned image)
- Review LibreChat logs: `docker logs -f LibreChat`

### JSON Parse Error
- Model may have returned explanation text instead of pure JSON
- Check temperature setting (should be 0.15)
- Verify you're using `qwen2.5-3b-instruct-invoice-extractor-gtx1650`

### Missing Vendor Numbers
- Ensure vendor names in invoice match your mapping keys exactly
- Consider fuzzy matching if vendor names vary
- Add more vendor mappings to cover all suppliers

## Integration Examples

### Django/Flask Web App

```python
from flask import Flask, request, jsonify
from invoice_extractor import LibreChatInvoiceExtractor

app = Flask(__name__)
client = LibreChatInvoiceExtractor()

@app.route('/extract-invoice', methods=['POST'])
def extract_invoice():
    # Get uploaded file
    file = request.files['invoice']
    temp_path = f"/tmp/{file.filename}"
    file.save(temp_path)
    
    # Login (cache session or use API key)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    # Upload and extract
    file_data = client.upload_file(temp_path)
    vendors = get_vendors_from_db()
    result = client.extract_invoice(file_data, vendors)
    
    return jsonify(result)
```

### Celery Background Task

```python
from celery import Celery
from invoice_extractor import LibreChatInvoiceExtractor

app = Celery('tasks', broker='redis://localhost:6379')

@app.task
def process_invoice(pdf_path, user_id):
    client = LibreChatInvoiceExtractor()
    client.login(WORKER_EMAIL, WORKER_PASSWORD)
    
    file_data = client.upload_file(pdf_path)
    vendors = fetch_user_vendors(user_id)
    result = client.extract_invoice(file_data, vendors)
    
    save_to_database(user_id, result)
    notify_user(user_id, "Invoice processed")
    
    return result
```

## See Also

- [Invoice Extraction Prompt Guide](invoice-extraction-prompt.md)
- [LibreChat API Documentation](https://www.librechat.ai/docs/api)
- [Ollama Models README](../README-Ollama-Extension.md)
