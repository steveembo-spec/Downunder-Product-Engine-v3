#!/usr/bin/env python
"""
DPE Sprint 6 - Milestone 1.1: Database Verification

Verifies that:
- Database exists and is accessible
- Old Sprint 4 products table is preserved
- New v4.0 foundation tables exist
- Indexes are in place
- Data integrity is maintained
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Adjust path for new location in tools/database/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"


def verify():
    """Run complete database verification."""
    print()
    print("=" * 60)
    print("DPE Sprint 6 - Milestone 1.1: Database Verification")
    print("=" * 60)
    print()
    
    # Check database exists
    if not DB_FILE.exists():
        print(f"❌ Database not found: {DB_FILE}")
        return False
    
    file_size_kb = DB_FILE.stat().st_size / 1024
    print(f"✓ Database found")
    print(f"  Path: {DB_FILE}")
    print(f"  Size: {file_size_kb:.1f} KB")
    print()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        all_tables = {row[0]: row[0] for row in cur.fetchall()}
        
        # Get all indexes
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
        all_indexes = {row[0]: row[0] for row in cur.fetchall()}
        
        print("SPRINT 4 TABLES (MUST EXIST):")
        print("-" * 60)
        
        required_sprint4_tables = ["products"]
        sprint4_ok = True
        
        for table in required_sprint4_tables:
            if table in all_tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  ✓ {table:<30} {count:>8,} rows")
            else:
                print(f"  ❌ {table:<30} MISSING!")
                sprint4_ok = False
        
        print()
        print("V4.0 FOUNDATION TABLES (SHOULD EXIST):")
        print("-" * 60)
        
        v4_tables = [
            "master_products",
            "product_families",
            "suppliers",
            "supplier_products",
            "product_intelligence",
        ]
        v4_ok = True
        
        for table in v4_tables:
            if table in all_tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                status = "✓" if count == 0 else "✓"
                print(f"  {status} {table:<30} {count:>8,} rows")
            else:
                print(f"  ❌ {table:<30} MISSING!")
                v4_ok = False
        
        print()
        print("INDEXES:")
        print("-" * 60)
        
        required_indexes = {
            "Sprint 4 (Products)": [
                "idx_products_sku",
                "idx_products_brand",
                "idx_products_supplier",
                "idx_products_title",
            ],
            "v4.0 (Master Products)": [
                "idx_master_sku",
                "idx_master_brand",
                "idx_master_category",
            ],
            "v4.0 (Product Families)": [
                "idx_family_code",
                "idx_family_parent",
            ],
            "v4.0 (Suppliers)": [
                "idx_supplier_code",
                "idx_supplier_enabled",
                "idx_supplier_priority",
            ],
            "v4.0 (Supplier Products)": [
                "idx_sp_master",
                "idx_sp_supplier",
                "idx_sp_active",
            ],
            "v4.0 (Product Intelligence)": [
                "idx_pi_master",
                "idx_pi_recommended",
                "idx_pi_score",
            ],
        }
        
        indexes_ok = True
        for category, indexes in required_indexes.items():
            print(f"{category}:")
            for idx in indexes:
                if idx in all_indexes:
                    print(f"    ✓ {idx}")
                else:
                    print(f"    ❌ {idx} MISSING!")
                    indexes_ok = False
        
        print()
        print("DATA INTEGRITY:")
        print("-" * 60)
        
        integrity_ok = True
        
        # Check for orphaned data
        cur.execute("SELECT COUNT(*) FROM products WHERE sku IS NULL OR sku = ''")
        null_skus = cur.fetchone()[0]
        if null_skus > 0:
            print(f"  ⚠  Products with NULL/empty SKU: {null_skus}")
            integrity_ok = False
        else:
            print(f"  ✓ No NULL/empty SKUs in products table")
        
        # Check for duplicate SKUs in products
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT sku FROM products
                WHERE sku IS NOT NULL AND sku != ''
                GROUP BY sku HAVING COUNT(*) > 1
            )
        """)
        dup_skus = cur.fetchone()[0]
        if dup_skus > 0:
            print(f"  ⚠  Duplicate SKUs in products table: {dup_skus}")
            integrity_ok = False
        else:
            print(f"  ✓ No duplicate SKUs in products table")
        
        # Check for missing supplier references (if supplier_products has data)
        cur.execute("SELECT COUNT(*) FROM supplier_products")
        sp_count = cur.fetchone()[0]
        if sp_count > 0:
            cur.execute("""
                SELECT COUNT(*) FROM supplier_products sp
                WHERE NOT EXISTS (
                    SELECT 1 FROM suppliers s WHERE s.id = sp.supplier_id
                )
            """)
            missing_suppliers = cur.fetchone()[0]
            if missing_suppliers > 0:
                print(f"  ⚠  Orphaned supplier references: {missing_suppliers}")
                integrity_ok = False
            else:
                print(f"  ✓ All supplier_products have valid supplier references")
        
        print()
        print("SUMMARY:")
        print("-" * 60)
        
        all_ok = sprint4_ok and v4_ok and indexes_ok and integrity_ok
        
        if sprint4_ok:
            print("  ✓ Sprint 4 tables and data preserved")
        else:
            print("  ❌ Sprint 4 tables or data corrupted")
        
        if v4_ok:
            print("  ✓ v4.0 foundation tables created")
        else:
            print("  ❌ v4.0 foundation tables incomplete")
        
        if indexes_ok:
            print("  ✓ All required indexes exist")
        else:
            print("  ❌ Some required indexes missing")
        
        if integrity_ok:
            print("  ✓ Data integrity validated")
        else:
            print("  ⚠  Some data integrity issues detected")
        
        print()
        
        if all_ok:
            print("✅ Database verification PASSED")
        else:
            print("⚠  Database verification PARTIAL or FAILED")
        
        print()
        
        conn.close()
        return all_ok
        
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify()
    exit(0 if success else 1)
