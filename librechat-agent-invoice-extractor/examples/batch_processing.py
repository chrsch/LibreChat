#!/usr/bin/env python3
"""
Batch Invoice Processing Example

Process all PDF invoices in a folder and save extracted data.

Usage:
    python batch_processing.py --folder ./invoices --vendors vendors.json
"""

import argparse
import json
import sys
from pathlib import Path

# Import from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from librechat_invoice_extractor import LibreChatInvoiceExtractor


def process_invoice_folder(
    folder_path: str,
    vendors_file: str,
    librechat_url: str,
    email: str,
    password: str,
    output_folder: str = None
):
    """
    Process all PDF invoices in a folder.
    
    Args:
        folder_path: Path to folder containing PDF invoices
        vendors_file: Path to JSON file with vendor mappings
        librechat_url: LibreChat server URL
        email: Login email
        password: Login password
        output_folder: Optional output folder (defaults to same as input)
    """
    # Initialize client
    client = LibreChatInvoiceExtractor(librechat_url)
    
    # Login
    print(f"Logging in to {librechat_url}...")
    if not client.login(email, password):
        print("❌ Login failed")
        return
    
    # Load vendor mappings
    with open(vendors_file, 'r', encoding='utf-8') as f:
        vendors = json.load(f)
    print(f"✓ Loaded {len(vendors)} vendor mappings")
    
    # Find all PDFs
    folder = Path(folder_path)
    pdfs = list(folder.glob("*.pdf"))
    print(f"✓ Found {len(pdfs)} PDF files")
    
    if not pdfs:
        print("No PDF files found in folder")
        return
    
    # Determine output folder
    output_dir = Path(output_folder) if output_folder else folder
    output_dir.mkdir(exist_ok=True)
    
    # Process each PDF
    results = []
    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
        
        try:
            # Upload PDF
            file_data = client.upload_file(str(pdf_path))
            if not file_data:
                print(f"  ❌ Upload failed")
                continue
            
            # Extract data
            invoice_data = client.extract_invoice(file_data, vendors)
            if not invoice_data:
                print(f"  ❌ Extraction failed")
                continue
            
            # Save result
            output_path = output_dir / pdf_path.with_suffix('.json').name
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(invoice_data, f, indent=2, ensure_ascii=False)
            
            print(f"  ✓ Saved: {output_path}")
            print(f"  - Vendor: {invoice_data.get('vendor')}")
            print(f"  - Invoice: {invoice_data.get('invoice_number')}")
            print(f"  - Total: {invoice_data.get('total_amount')} {invoice_data.get('currency')}")
            
            results.append({
                'file': pdf_path.name,
                'status': 'success',
                'data': invoice_data
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                'file': pdf_path.name,
                'status': 'error',
                'error': str(e)
            })
    
    # Summary
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - successful
    
    print("\n" + "="*60)
    print("BATCH PROCESSING COMPLETE")
    print("="*60)
    print(f"Total: {len(results)}")
    print(f"Success: {successful}")
    print(f"Failed: {failed}")
    print("="*60)
    
    # Save summary
    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Summary saved: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch process PDF invoices"
    )
    parser.add_argument(
        '--folder',
        required=True,
        help='Folder containing PDF invoices'
    )
    parser.add_argument(
        '--vendors',
        required=True,
        help='Path to vendors.json file'
    )
    parser.add_argument(
        '--email',
        required=True,
        help='LibreChat email'
    )
    parser.add_argument(
        '--password',
        required=True,
        help='LibreChat password'
    )
    parser.add_argument(
        '--url',
        default='http://localhost:3080',
        help='LibreChat URL (default: http://localhost:3080)'
    )
    parser.add_argument(
        '--output',
        help='Output folder (default: same as input folder)'
    )
    
    args = parser.parse_args()
    
    process_invoice_folder(
        folder_path=args.folder,
        vendors_file=args.vendors,
        librechat_url=args.url,
        email=args.email,
        password=args.password,
        output_folder=args.output
    )


if __name__ == "__main__":
    main()
