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

with tempfile.TemporaryDirectory() as tmp_dir:
    manager = SupplierProfileManager(profiles_dir=Path(tmp_dir))

    # ------------------------------------------------------------------ #
    # 1. Generic profile: create, save, load, verify, delete              #
    # ------------------------------------------------------------------ #
    GENERIC_NAME = "TestGenericSupplier"

    generic = SupplierProfile(
        supplier_name=GENERIC_NAME,
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
        supplier_type="generic",
    )

    manager.save_profile(generic)
    loaded = manager.load_profile(GENERIC_NAME)
    assert loaded is not None,                              "Generic: load_profile() returned None"
    assert loaded.supplier_name == GENERIC_NAME,            f"Generic: supplier_name mismatch"
    assert loaded.file_type == "csv",                       f"Generic: file_type mismatch"
    assert loaded.encoding == "utf-8",                      f"Generic: encoding mismatch"
    assert loaded.delimiter == ",",                         f"Generic: delimiter mismatch"
    assert loaded.header_row == 0,                          f"Generic: header_row mismatch"
    assert loaded.last_verified == "2026-07-02T00:00:00",   f"Generic: last_verified mismatch"
    assert loaded.column_mapping == generic.column_mapping, f"Generic: column_mapping mismatch"
    assert loaded.supplier_type == "generic",               f"Generic: supplier_type should be 'generic', got {loaded.supplier_type!r}"
    assert loaded.plugin_name is None,                      f"Generic: plugin_name should be None"
    assert loaded.input_file_path is None,                  f"Generic: input_file_path should be None"

    assert manager.profile_exists(GENERIC_NAME), "Generic: profile_exists() returned False"
    assert GENERIC_NAME in manager.list_profiles(), "Generic: not in list_profiles()"

    deleted = manager.delete_profile(GENERIC_NAME)
    assert deleted,                                "Generic: delete_profile() returned False"
    assert not manager.profile_exists(GENERIC_NAME), "Generic: profile_exists() True after delete"

    # ------------------------------------------------------------------ #
    # 2. Managed profile: create_managed_profile()                        #
    # ------------------------------------------------------------------ #
    MANAGED_NAME = "TestManagedSupplier"

    managed = manager.create_managed_profile(
        supplier_name=MANAGED_NAME,
        plugin_name="test_plugin",
        input_file_path="input/Test/test.csv",
    )
    assert managed.supplier_type == "managed",              f"Managed: supplier_type should be 'managed', got {managed.supplier_type!r}"
    assert managed.plugin_name == "test_plugin",            f"Managed: plugin_name mismatch"
    assert managed.input_file_path == "input/Test/test.csv", f"Managed: input_file_path mismatch"

    # Reload from disk to confirm persistence
    reloaded = manager.load_profile(MANAGED_NAME)
    assert reloaded is not None,                            "Managed: load_profile() returned None"
    assert reloaded.supplier_type == "managed",             f"Managed: supplier_type mismatch on reload"
    assert reloaded.plugin_name == "test_plugin",           f"Managed: plugin_name mismatch on reload"
    assert reloaded.input_file_path == "input/Test/test.csv", f"Managed: input_file_path mismatch on reload"

    # ------------------------------------------------------------------ #
    # 3. Existing profile must NOT be overwritten                         #
    # ------------------------------------------------------------------ #
    # Manually tweak the saved profile, then call create_managed_profile again
    original_mapping = {"sku": "Code"}
    managed.column_mapping.update(original_mapping)
    manager.save_profile(managed)  # write a custom column_mapping

    # Calling create_managed_profile again should return the existing profile unchanged
    returned = manager.create_managed_profile(MANAGED_NAME, plugin_name="other_plugin")
    assert returned.plugin_name == "test_plugin",           "Existing profile should NOT be overwritten by create_managed_profile()"

    manager.delete_profile(MANAGED_NAME)

    # ------------------------------------------------------------------ #
    # 4. ensure_default_profiles_exist() baseline + non-overwrite         #
    # ------------------------------------------------------------------ #
    # Seed existing profiles to verify bootstrap never overwrites them
    existing_mcs = SupplierProfile(
        supplier_name="MCS",
        file_type="csv",
        encoding="utf-8-sig",
        delimiter=",",
        header_row=0,
        column_mapping={
            "sku": "Product Code",
            "title": "Description",
            "cost": "Price",
            "rrp": "RRP",
        },
        last_verified="2026-07-03T11:42:23.268168",
        supplier_type="generic",
        plugin_name=None,
        input_file_path="input/MCS/MCS Price List.csv",
    )
    existing_whites = SupplierProfile(
        supplier_name="Whites",
        file_type="csv",
        encoding="utf-8-sig",
        delimiter=",",
        header_row=0,
        column_mapping={
            "sku": "Part Number",
            "title": "Description",
            "cost": "Cost",
            "rrp": "RRP",
        },
        last_verified="2026-07-03T14:00:00",
        supplier_type="generic",
        plugin_name=None,
        input_file_path="input/Whites/whites030726.csv",
    )
    manager.save_profile(existing_mcs)
    manager.save_profile(existing_whites)

    created = manager.ensure_default_profiles_exist()
    assert set(created) == {"A1", "Cassons", "Serco"},      f"ensure_default_profiles_exist() created: {created}"

    # Existing MCS/Whites profiles must remain unchanged
    mcs_after = manager.load_profile("MCS")
    whites_after = manager.load_profile("Whites")
    assert mcs_after is not None and mcs_after.column_mapping == existing_mcs.column_mapping, "MCS mapping was overwritten"
    assert whites_after is not None and whites_after.column_mapping == existing_whites.column_mapping, "Whites mapping was overwritten"

    for name in ("A1", "Cassons", "Serco", "MCS", "Whites"):
        p = manager.load_profile(name)
        assert p is not None,                               f"{name} profile not found after ensure"
        assert p.file_type in ("csv", "xlsx"),            f"{name}: file_type should be set"
        assert p.encoding != "",                           f"{name}: encoding should be set"
        assert p.delimiter != "",                          f"{name}: delimiter should be set"
        assert isinstance(p.header_row, int),               f"{name}: header_row should be int"
        assert isinstance(p.column_mapping, dict),          f"{name}: column_mapping should be dict"
        if name in ("A1", "Cassons", "Serco"):
            assert p.supplier_type == "managed",            f"{name}: supplier_type should be 'managed'"
            assert p.plugin_name is not None,               f"{name}: plugin_name should not be None"
        else:
            assert p.supplier_type == "generic",            f"{name}: supplier_type should be 'generic'"
            assert p.plugin_name is None,                   f"{name}: plugin_name should be None"
        assert p.input_file_path is not None,               f"{name}: input_file_path should be set"

    # 5. Calling again must NOT recreate any defaults
    created_again = manager.ensure_default_profiles_exist()
    assert created_again == [],                             f"Expected [] on second call, got {created_again}"

    # ------------------------------------------------------------------ #
    # 5. create_generic_profile() helper                                  #
    # ------------------------------------------------------------------ #
    gen2 = manager.create_generic_profile(
        "GenericViaHelper",
        encoding="cp1252",
        delimiter=";",
        input_file_path="input/Generic/generic.csv",
    )
    assert gen2.supplier_type == "generic",                 f"create_generic_profile: wrong type"
    assert gen2.encoding == "cp1252",                       f"create_generic_profile: encoding mismatch"
    assert gen2.delimiter == ";",                           f"create_generic_profile: delimiter mismatch"
    assert gen2.plugin_name is None,                        f"create_generic_profile: plugin_name should be None"
    assert gen2.input_file_path == "input/Generic/generic.csv", f"create_generic_profile: input_file_path mismatch"

print("Supplier Profile Manager smoke test passed")
