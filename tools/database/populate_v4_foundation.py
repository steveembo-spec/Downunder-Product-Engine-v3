#!/usr/bin/env python
"""
DPE Sprint 6 - Milestone 1.2: Populate v4.0 Foundation Tables

Idempotent data migration that populates v4.0 tables using the existing
supplier plugin pipeline as the single source of truth.

Uses: dpe_v3.supplier_plugins.loader.load_all_suppliers()

Tables populated:
1. suppliers - from config/suppliers.json + enabled supplier plugins
2. master_products - unique SKUs from all supplier products
3. supplier_products - junction table from supplier products
4. product_intelligence - empty records for future scoring

Idempotent: Safe to run multiple times.
"""

import sys
import sqlite3
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Add project root to path so we can import dpe_v3
sys.path.insert(0, str(PROJECT_ROOT))

from dpe_v3.supplier_plugins.loader import load_all_suppliers

DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"
CONFIG_FILE = PROJECT_ROOT / "config" / "suppliers.json"


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def load_supplier_config():
    """Load supplier configuration from config file."""
    if not CONFIG_FILE.exists():
        return []
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get("enabled_suppliers", [])
    except Exception as e:
        print(f"⚠  Failed to load config: {e}")
        return []


def populate_suppliers(conn, supplier_config):
    """Populate suppliers table from config."""
    if not _table_empty(conn, "suppliers"):
        print("  ✓ suppliers already populated (skipping)")
        return
    
    print("  → Populating suppliers...")
    cur = conn.cursor()
    
    supplier_metadata = {
        "a1": ("A1", 100),
        "cassons": ("Cassons", 90),
        "link": ("Link", 80),
        "serco": ("Serco", 70),
    }
    
    suppliers_to_add = []
    for code in supplier_config:
        code_lower = code.lower()
        name, priority = supplier_metadata.get(code_lower, (code, 50))
        suppliers_to_add.append((code_lower, name, priority))
    
    for code, name, priority in suppliers_to_add:
        cur.execute("""
            INSERT INTO suppliers (
                supplier_code, supplier_name, is_enabled, priority_rank, created_at
            ) VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
        """, (code, name, priority))
    
    conn.commit()
    print(f"    Inserted {len(suppliers_to_add)} suppliers")


def populate_master_products(conn, products):
    """Populate master_products from unique SKUs in supplier products."""
    if not _table_empty(conn, "master_products"):
        print("  ✓ master_products already populated (skipping)")
        return
    
    print("  → Populating master_products...")
    cur = conn.cursor()
    
    # Extract unique SKUs from supplier products
    unique_skus = {}
    for product in products:
        sku = product.get('sku')
        if sku and sku not in unique_skus:
            unique_skus[sku] = {
                'sku': sku,
                'title': product.get('title') or sku,
                'brand': product.get('brand') or '',
                'category': product.get('category') or 'General',
            }
    
    # Insert master products
    inserted = 0
    for sku_data in unique_skus.values():
        cur.execute("""
            INSERT INTO master_products (
                sku, title, brand, category, description_status, created_at, v4_migrated_at
            ) VALUES (?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (sku_data['sku'], sku_data['title'], sku_data['brand'], sku_data['category']))
        inserted += 1
    
    conn.commit()
    print(f"    Inserted {inserted} master products")


def populate_supplier_products(conn, products):
    """Populate supplier_products from supplier products."""
    if not _table_empty(conn, "supplier_products"):
        print("  ✓ supplier_products already populated (skipping)")
        return
    
    print("  → Populating supplier_products...")
    cur = conn.cursor()
    
    # Build lookups
    cur.execute("SELECT id, supplier_code FROM suppliers")
    suppliers_map = {row[1].lower(): row[0] for row in cur.fetchall()}
    
    cur.execute("SELECT id, sku FROM master_products")
    products_map = {row[1]: row[0] for row in cur.fetchall()}
    
    inserted = 0
    
    for product in products:
        sku = product.get('sku')
        supplier_name = product.get('supplier', '').lower()
        
        master_id = products_map.get(sku)
        supplier_id = suppliers_map.get(supplier_name)
        
        if not master_id or not supplier_id:
            continue
        
        # Check if exists
        cur.execute("""
            SELECT 1 FROM supplier_products
            WHERE master_product_id = ? AND supplier_id = ?
        """, (master_id, supplier_id))
        if cur.fetchone():
            continue
        
        # Extract fields from product dict
        supplier_sku = sku
        cost = product.get('cost')
        rrp = product.get('rrp')
        stock = product.get('stock')
        
        # Convert stock string to int if needed
        if isinstance(stock, str):
            try:
                stock = int(stock)
            except (ValueError, TypeError):
                stock = 1
        
        if stock is None:
            stock = 1
        
        cur.execute("""
            INSERT INTO supplier_products (
                master_product_id, supplier_id, supplier_sku, supplier_cost, 
                supplier_rrp, supplier_stock, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        """, (master_id, supplier_id, supplier_sku, cost, rrp, stock))
        
        inserted += 1
    
    conn.commit()
    print(f"    Inserted {inserted} supplier_products")


def populate_product_intelligence(conn):
    """Populate product_intelligence records."""
    if not _table_empty(conn, "product_intelligence"):
        print("  ✓ product_intelligence already populated (skipping)")
        return
    
    print("  → Populating product_intelligence...")
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM master_products")
    master_ids = [row[0] for row in cur.fetchall()]
    
    for master_id in master_ids:
        cur.execute("""
            INSERT INTO product_intelligence (
                master_product_id, recommendation_score, created_at
            ) VALUES (?, 0, CURRENT_TIMESTAMP)
        """, (master_id,))
    
    conn.commit()
    print(f"    Inserted {len(master_ids)} product_intelligence records")


def _table_empty(conn, table_name):
    """Check if table is empty."""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cur.fetchone()[0] == 0


def _get_count(conn, table_name):
    """Get row count."""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cur.fetchone()[0]


def populate():
    """Run population migration."""
    print()
    print("=" * 60)
    print("DPE Sprint 6 - Milestone 1.2: Populate v4.0 Foundation")
    print("=" * 60)
    print()
    
    if not DB_FILE.exists():
        print(f"❌ Database not found: {DB_FILE}")
        return False
    
    print(f"Database: {DB_FILE}")
    print()
    
    # Load source data using supplier plugin pipeline
    print("Loading source data:")
    try:
        supplier_config = load_supplier_config()
        print(f"  ✓ Config suppliers: {len(supplier_config)}")
        
        print(f"  Loading supplier plugins...")
        products = load_all_suppliers()
        print(f"  ✓ Supplier rows loaded: {len(products):,}")
    except Exception as e:
        print(f"❌ Failed to load suppliers: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    conn = get_connection()
    
    try:
        print("Source data:")
        products_count = _get_count(conn, "products")
        print(f"  ✓ products: {products_count:,} rows (legacy)")
        print()
        
        print("Populating v4.0 tables:")
        populate_suppliers(conn, supplier_config)
        populate_master_products(conn, products)
        populate_supplier_products(conn, products)
        populate_product_intelligence(conn)
        
        print()
        print("Final counts:")
        s_count = _get_count(conn, "suppliers")
        m_count = _get_count(conn, "master_products")
        sp_count = _get_count(conn, "supplier_products")
        pi_count = _get_count(conn, "product_intelligence")
        
        print(f"  ✓ suppliers: {s_count:,}")
        print(f"  ✓ master_products: {m_count:,}")
        print(f"  ✓ supplier_products: {sp_count:,}")
        print(f"  ✓ product_intelligence: {pi_count:,}")
        print()
        print("✅ Population complete!")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = populate()
    exit(0 if success else 1)
