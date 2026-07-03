"""
Smoke test for core/product/shopify_export_service.py
Run: python tools/test_shopify_export_service.py
"""
import sys
import os
import csv
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.product.shopify_export_service import ShopifyExportService, SHOPIFY_COLUMNS


def _create_test_database(db_file: Path) -> None:
    """Create a test database matching the production schema and insert sample data."""
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

    # Insert sample products
    cur.executemany(
        """
        INSERT INTO master_products
            (sku, title, brand, category, rrp_avg, rrp_max, stock_total,
             description_status, created_at, updated_at, v4_migrated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        [
            ("SKU001", "Widget Alpha", "BrandX", "Electronics", 19.99, 19.99, 50),
            ("SKU002", "Widget Beta",  "BrandY", "Electronics", 29.99, 29.99, 30),
            ("SKU003", "Widget Gamma", "BrandZ", "Accessories", 39.99, 39.99, 10),
        ],
    )
    conn.commit()
    conn.close()


with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    db_file = tmp_path / "test_catalogue.db"
    _create_test_database(db_file)

    export_dir = tmp_path / "shopify_exports"

    service = ShopifyExportService(db_file=db_file, export_dir=export_dir)
    result = service.export_all_products()

    print("\n--- Shopify Export Result ---")
    print(f"  success        : {result.success}")
    print(f"  output_file    : {result.output_file}")
    print(f"  rows_exported  : {result.rows_exported}")
    print(f"  error_message  : {result.error_message!r}")

    # Assertions
    assert result.success,                          f"Expected success=True, error: {result.error_message}"

    output_path = Path(result.output_file)
    assert output_path.exists(),                    f"Output file not found: {result.output_file}"
    assert result.rows_exported == 3,               f"Expected rows_exported=3, got {result.rows_exported}"

    # Read CSV back and verify
    with output_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        csv_rows = list(reader)
        fieldnames = reader.fieldnames or []

    # All required columns present
    for col in SHOPIFY_COLUMNS:
        assert col in fieldnames, f"Missing Shopify column: {col!r}"

    # Verify fixed field values
    for csv_row in csv_rows:
        assert csv_row["Status"] == "draft",                            f"Expected Status='draft', got {csv_row['Status']!r}"
        assert csv_row["Variant Fulfillment Service"] == "manual",      f"Expected Fulfillment Service='manual'"
        assert csv_row["Variant Inventory Policy"] == "deny",           f"Expected Inventory Policy='deny'"
        assert csv_row["Published"] == "FALSE",                         f"Expected Published='FALSE'"
        assert csv_row["Variant Requires Shipping"] == "TRUE",          f"Expected Requires Shipping='TRUE'"
        assert csv_row["Variant Taxable"] == "TRUE",                    f"Expected Taxable='TRUE'"
        assert csv_row["Option1 Name"] == "Title",                      f"Expected Option1 Name='Title'"
        assert csv_row["Option1 Value"] == "Default Title",             f"Expected Option1 Value='Default Title'"

    print("\n  CSV columns verified.")
    print(f"  First row Handle : {csv_rows[0]['Handle']}")
    print(f"  First row SKU    : {csv_rows[0]['Variant SKU']}")
    print(f"  First row Price  : {csv_rows[0]['Variant Price']}")

print("\nShopify Export Service smoke test passed")
