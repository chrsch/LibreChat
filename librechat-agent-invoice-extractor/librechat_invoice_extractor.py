#!/usr/bin/env python3
"""
LibreChat Invoice Extraction Client

Uploads a PDF invoice and extracts structured data using the
qwen2.5-3b-instruct-invoice-extractor-gtx1650 model.

Usage:
    python librechat_invoice_extractor.py --pdf invoice.pdf --email user@example.com --password secret

Requirements:
    pip install requests
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests


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


def load_vendor_mappings(vendors_file: Optional[str] = None) -> Dict[str, str]:
    """
    Load vendor mappings from file or return defaults.
    
    Args:
        vendors_file: Optional path to JSON file with vendor mappings
        
    Returns:
        Dict mapping vendor names to vendor numbers
    """
    if vendors_file and Path(vendors_file).exists():
        with open(vendors_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Default vendor mappings
    return {
        "ACME Corp": "V12345",
        "Global Supplies GmbH": "V67890",
        "Tech Solutions Ltd": "V24680",
        "Office Depot": "V13579",
        "Staples Inc": "V98765"
    }


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Extract invoice data from PDF using LibreChat agents"
    )
    parser.add_argument(
        '--pdf', 
        required=True,
        help='Path to PDF invoice file'
    )
    parser.add_argument(
        '--email',
        default=os.getenv('LIBRECHAT_EMAIL'),
        help='LibreChat email (or set LIBRECHAT_EMAIL env var)'
    )
    parser.add_argument(
        '--password',
        default=os.getenv('LIBRECHAT_PASSWORD'),
        help='LibreChat password (or set LIBRECHAT_PASSWORD env var)'
    )
    parser.add_argument(
        '--url',
        default=os.getenv('LIBRECHAT_URL', 'http://localhost:3080'),
        help='LibreChat URL (default: http://localhost:3080)'
    )
    parser.add_argument(
        '--model',
        default='qwen2.5-3b-instruct-invoice-extractor-gtx1650',
        help='Model to use for extraction'
    )
    parser.add_argument(
        '--vendors',
        help='Path to JSON file with vendor mappings (name: number)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file path (default: <pdf_name>.json)'
    )
    
    args = parser.parse_args()
    
    # Validate required args
    if not args.email or not args.password:
        parser.error("Email and password required (via args or env vars)")
    
    # Initialize client
    client = LibreChatInvoiceExtractor(base_url=args.url)
    
    # Login
    if not client.login(args.email, args.password):
        return 1
    
    # Load vendor mappings
    vendor_mappings = load_vendor_mappings(args.vendors)
    print(f"✓ Loaded {len(vendor_mappings)} vendor mappings")
    
    # Upload PDF
    file_data = client.upload_file(args.pdf)
    if not file_data:
        return 1
    
    # Extract invoice data
    invoice_data = client.extract_invoice(
        file_data=file_data,
        vendor_mappings=vendor_mappings,
        model=args.model
    )
    
    if not invoice_data:
        return 1
    
    # Display results
    print("\n" + "="*60)
    print("EXTRACTED INVOICE DATA")
    print("="*60)
    print(json.dumps(invoice_data, indent=2, ensure_ascii=False))
    print("="*60)
    
    # Summary
    print(f"\nVendor: {invoice_data.get('vendor')}")
    print(f"Vendor Number: {invoice_data.get('vendor_number')}")
    print(f"Invoice #: {invoice_data.get('invoice_number')}")
    print(f"Date: {invoice_data.get('invoice_date')}")
    print(f"Total: {invoice_data.get('total_amount')} {invoice_data.get('currency')}")
    print(f"Summary: {invoice_data.get('item_summary')}")
    
    # Save to file
    output_path = args.output or str(Path(args.pdf).with_suffix('.json'))
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(invoice_data, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
