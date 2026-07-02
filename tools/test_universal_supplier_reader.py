"""
Smoke test for core/product/universal_supplier_reader.py
Run: python tools/test_universal_supplier_reader.py
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.product.universal_supplier_reader import UniversalSupplierReader

SUPPLIER_NAME = "TestSupplier"
CSV_CONTENT = (
    "Item Code,Description,Dealer Price,RRP,Brand,Qty Available\n"
    "SKU001,Widget A,10.00,19.99,BrandX,50\n"
    "SKU002,Widget B,15.00,29.99,BrandY,30\n"
    "SKU003,Widget C,20.00,39.99,BrandZ,10\n"
)

with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    # Write temporary CSV
    csv_file = tmp_path / "test_supplier.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")

    # Use a separate profiles dir (no real profiles present)
    profiles_dir = tmp_path / "profiles"
    reader = UniversalSupplierReader(profiles_dir=profiles_dir)

    result = reader.read_supplier_file(SUPPLIER_NAME, csv_file)

    # Print result summary
    print("\n--- Universal Supplier Reader Result ---")
    print(f"  success       : {result.success}")
    print(f"  encoding      : {result.encoding}")
    print(f"  delimiter     : {result.delimiter!r}")
    print(f"  headers       : {result.headers}")
    print(f"  preview rows  : {len(result.preview_rows)}")
    print(f"  profile_used  : {result.profile_used}")
    print(f"  needs_review  : {result.needs_review}")
    print(f"  error_message : {result.error_message!r}")
    print("\n  Detected mapping:")
    for field_name, match in result.detected_mapping.items():
        if match.detected_header:
            print(f"    {field_name:<30} -> {match.detected_header:<25} [{match.status}, {match.confidence}]")

    # Assertions
    assert result.success,                                          "Expected success=True"
    assert result.encoding != "",                                   "Expected encoding to be detected"
    assert result.delimiter == ",",                                 f"Expected delimiter=',', got {result.delimiter!r}"
    assert result.detected_mapping["sku"].detected_header == "Item Code",     f"sku mismatch: {result.detected_mapping['sku'].detected_header!r}"
    assert result.detected_mapping["title"].detected_header == "Description", f"title mismatch: {result.detected_mapping['title'].detected_header!r}"
    assert result.detected_mapping["cost"].detected_header == "Dealer Price", f"cost mismatch: {result.detected_mapping['cost'].detected_header!r}"
    assert result.detected_mapping["rrp"].detected_header == "RRP",           f"rrp mismatch: {result.detected_mapping['rrp'].detected_header!r}"
    assert len(result.preview_rows) > 0,                            "Expected at least one preview row"
    assert result.needs_review is False,                            f"Expected needs_review=False, got {result.needs_review}"

print("\nUniversal Supplier Reader smoke test passed")
