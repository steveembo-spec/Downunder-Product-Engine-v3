"""
Smoke test for core/product/supplier_profile_manager.py
Run: python tools/test_supplier_profile_manager.py
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.product.supplier_profile_manager import SupplierProfile, SupplierProfileManager

# Use a temporary directory so the test never writes to the real config folder
with tempfile.TemporaryDirectory() as tmp_dir:
    manager = SupplierProfileManager(profiles_dir=Path(tmp_dir))

    SUPPLIER_NAME = "TestSupplier"

    # 1. Create a test profile
    profile = SupplierProfile(
        supplier_name=SUPPLIER_NAME,
        file_type="csv",
        encoding="utf-8",
        delimiter=",",
        header_row=0,
        column_mapping={
            "sku": "Item Code",
            "title": "Description",
            "cost": "Dealer Price",
            "rrp": "RRP",
            "brand": "Brand",
            "stock": "Qty Available",
        },
        last_verified="2026-07-02T00:00:00",
    )

    # 2. Save it
    manager.save_profile(profile)

    # 3. Load it
    loaded = manager.load_profile(SUPPLIER_NAME)
    assert loaded is not None, "load_profile() returned None unexpectedly"

    # 4. Verify all fields match
    assert loaded.supplier_name == profile.supplier_name,   f"supplier_name mismatch: {loaded.supplier_name!r}"
    assert loaded.file_type == profile.file_type,           f"file_type mismatch: {loaded.file_type!r}"
    assert loaded.encoding == profile.encoding,             f"encoding mismatch: {loaded.encoding!r}"
    assert loaded.delimiter == profile.delimiter,           f"delimiter mismatch: {loaded.delimiter!r}"
    assert loaded.header_row == profile.header_row,         f"header_row mismatch: {loaded.header_row!r}"
    assert loaded.last_verified == profile.last_verified,   f"last_verified mismatch: {loaded.last_verified!r}"
    assert loaded.column_mapping == profile.column_mapping, f"column_mapping mismatch: {loaded.column_mapping!r}"

    # 5. profile_exists() returns True
    assert manager.profile_exists(SUPPLIER_NAME), "profile_exists() returned False after save"

    # 6. list_profiles() contains the supplier
    profiles = manager.list_profiles()
    assert SUPPLIER_NAME in profiles, f"{SUPPLIER_NAME!r} not found in list_profiles(): {profiles}"

    # 7. Delete the profile
    deleted = manager.delete_profile(SUPPLIER_NAME)
    assert deleted, "delete_profile() returned False unexpectedly"

    # 8. profile_exists() returns False
    assert not manager.profile_exists(SUPPLIER_NAME), "profile_exists() returned True after delete"

print("Supplier Profile Manager smoke test passed")
