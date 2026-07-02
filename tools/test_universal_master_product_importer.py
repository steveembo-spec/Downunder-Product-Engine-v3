"""
Smoke test for core/product/universal_master_product_importer.py
Run: python tools/test_universal_master_product_importer.py
"""
import sys
import os
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.product.universal_master_product_importer import UniversalMasterProductImporter

SUPPLIER_NAME = "TestSupplier"
CSV_CONTENT = (
    "Item Code,Description,Dealer Price,RRP,Brand,Qty Available\n"
    "SKU001,Widget Alpha,10.00,19.99,BrandX,50\n"
    "SKU002,Widget Beta,15.00,29.99,BrandY,30\n"
    "SKU003,Widget Gamma,20.00,39.99,BrandZ,10\n"
)


def _create_test_database(db_file: Path) -> None:
    """Create a temporary SQLite database matching the production schema."""
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE master_products (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sku                 TEXT    NOT NULL UNIQUE,
            title               TEXT,
            brand               TEXT,
            category            TEXT,
            cost_avg            REAL,
            cost_min            REAL,
            cost_max            REAL,
            rrp_avg             REAL,
            rrp_min             REAL,
            rrp_max             REAL,
            stock_total         INTEGER,
            stock_suppliers     INTEGER,
            image_count         INTEGER,
            description_status  TEXT    DEFAULT 'Pending',
            created_at          TEXT,
            updated_at          TEXT,
            v4_migrated_at      TEXT
        );

        CREATE TABLE suppliers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code   TEXT    NOT NULL UNIQUE,
            supplier_name   TEXT,
            is_enabled      INTEGER DEFAULT 1,
            priority_rank   INTEGER DEFAULT 50,
            contact_email   TEXT,
            contact_phone   TEXT,
            product_count   INTEGER,
            avg_cost        REAL,
            avg_rrp         REAL,
            created_at      TEXT,
            updated_at      TEXT,
            last_import_at  TEXT
        );

        CREATE TABLE supplier_products (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            master_product_id   INTEGER NOT NULL,
            supplier_id         INTEGER NOT NULL,
            supplier_sku        TEXT,
            supplier_cost       REAL,
            supplier_rrp        REAL,
            supplier_stock      INTEGER,
            image_url           TEXT,
            description_text    TEXT,
            is_active           INTEGER DEFAULT 1,
            last_updated        TEXT,
            created_at          TEXT,
            synced_at           TEXT,
            UNIQUE(master_product_id, supplier_id)
        );
    """)
    conn.commit()
    conn.close()


with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    # Create temp CSV
    csv_file = tmp_path / "test_supplier.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")

    # Create temp database with production-matching schema
    db_file = tmp_path / "test_catalogue.db"
    _create_test_database(db_file)

    profiles_dir = tmp_path / "profiles"

    importer = UniversalMasterProductImporter(db_file=db_file, profiles_dir=profiles_dir)
    result = importer.import_supplier_file(SUPPLIER_NAME, csv_file)

    print("\n--- Universal Master Product Importer Result ---")
    print(f"  success          : {result.success}")
    print(f"  rows_read        : {result.rows_read}")
    print(f"  rows_imported    : {result.rows_imported}")
    print(f"  rows_skipped     : {result.rows_skipped}")
    print(f"  products_created : {result.products_created}")
    print(f"  products_updated : {result.products_updated}")
    print(f"  errors           : {result.errors}")
    print(f"  error_message    : {result.error_message!r}")

    # Assertions
    assert result.success,           f"Expected success=True, error: {result.error_message}"
    assert result.rows_read == 3,    f"Expected rows_read=3, got {result.rows_read}"
    assert result.rows_imported == 3, f"Expected rows_imported=3, got {result.rows_imported}"

    # Verify products are in the database
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT sku, title, cost_avg, rrp_avg, stock_total FROM master_products ORDER BY sku")
    db_products = cur.fetchall()
    conn.close()

    print("\n  Products in database:")
    for p in db_products:
        print(f"    sku={p[0]}, title={p[1]}, cost_avg={p[2]}, rrp_avg={p[3]}, stock_total={p[4]}")

    db_skus = {p[0] for p in db_products}
    assert "SKU001" in db_skus, "SKU001 not found in database"
    assert "SKU002" in db_skus, "SKU002 not found in database"
    assert "SKU003" in db_skus, "SKU003 not found in database"

    # Verify aggregates were calculated
    for p in db_products:
        sku, title, cost_avg, rrp_avg, stock_total = p
        assert cost_avg is not None,    f"{sku}: cost_avg should not be None"
        assert rrp_avg is not None,     f"{sku}: rrp_avg should not be None"
        assert stock_total is not None, f"{sku}: stock_total should not be None"

print("\nUniversal Master Product Importer smoke test passed")
