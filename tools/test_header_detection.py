"""
Smoke test for core/product/header_detection.py
Run: python tools/test_header_detection.py
"""
import sys
import os

# Allow running from project root or tools/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.product.header_detection import detect_header_mapping, mapping_needs_review

headers = ["Item Code", "Description", "Dealer Price", "RRP", "Brand", "Qty Available"]

mapping = detect_header_mapping(headers)

print("\n--- Header Detection Results ---")
for field, match in mapping.items():
    if match.detected_header:
        print(f"  {match.master_field:<30} -> {match.detected_header:<25} [{match.status}, {match.confidence}]")
    else:
        print(f"  {match.master_field:<30} -> (no match)              [{match.status}]")

# Assertions
assert mapping["sku"].detected_header == "Item Code",    f"sku: expected 'Item Code', got {mapping['sku'].detected_header!r}"
assert mapping["title"].detected_header == "Description", f"title: expected 'Description', got {mapping['title'].detected_header!r}"
assert mapping["cost"].detected_header == "Dealer Price", f"cost: expected 'Dealer Price', got {mapping['cost'].detected_header!r}"
assert mapping["rrp"].detected_header == "RRP",           f"rrp: expected 'RRP', got {mapping['rrp'].detected_header!r}"
assert mapping["brand"].detected_header == "Brand",       f"brand: expected 'Brand', got {mapping['brand'].detected_header!r}"
assert mapping["stock"].detected_header == "Qty Available", f"stock: expected 'Qty Available', got {mapping['stock'].detected_header!r}"

print("\nHeader detection smoke test passed")
