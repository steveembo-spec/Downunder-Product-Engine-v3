#!/usr/bin/env python
"""
CLI test script for large supplier import (e.g., Whites CSV).

Usage:
  python tools/test_import_whites_cli.py <supplier_name> <csv_file_path>

Example:
  python tools/test_import_whites_cli.py "Whites" "input/Whites/Whites.csv"

This script imports a CSV file outside the UI with full diagnostic logging
to identify where large imports stall or perform poorly.
"""

import sys
import logging
from pathlib import Path

# Setup logging to console with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.product.universal_master_product_importer import UniversalMasterProductImporter

def main():
    """Main entry point for CLI test."""
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    supplier_name = sys.argv[1]
    csv_file_path = Path(sys.argv[2])
    
    if not csv_file_path.exists():
        print(f"ERROR: File not found: {csv_file_path}")
        sys.exit(1)
    
    print("=" * 100)
    print("SUPPLIER IMPORT - CLI TEST")
    print("=" * 100)
    print(f"\nSupplier:  {supplier_name}")
    print(f"File:      {csv_file_path}")
    print(f"File Size: {csv_file_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("\n" + "=" * 100)
    print("RUNNING IMPORT (with diagnostic logging)...")
    print("=" * 100 + "\n")
    
    # Run import with diagnostics
    importer = UniversalMasterProductImporter()
    result = importer.import_supplier_file(supplier_name, csv_file_path)
    
    # Print results
    print("\n" + "=" * 100)
    print("IMPORT RESULT")
    print("=" * 100)
    
    print(f"\nSuccess:           {result.success}")
    print(f"Supplier:          {result.supplier_name}")
    print(f"File:              {Path(result.file_path).name}")
    print(f"\nRows Read:         {result.rows_read}")
    print(f"Rows Imported:     {result.rows_imported}")
    print(f"Rows Skipped:      {result.rows_skipped}")
    print(f"Products Created:  {result.products_created}")
    print(f"Products Updated:  {result.products_updated}")
    
    if result.error_message:
        print(f"\nError Message:\n{result.error_message}")
    
    if result.errors:
        print(f"\nRow Errors ({len(result.errors)} total):")
        for i, error in enumerate(result.errors[:10], 1):  # Show first 10
            print(f"  {i}. {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")
    
    print("\n" + "=" * 100)
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
