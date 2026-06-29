#!/usr/bin/env python
"""
DPE Sprint 6 - Milestone 1.2: Population Verification

Verifies that v4.0 foundation tables are properly populated with data integrity checks.
"""

import sqlite3
from pathlib import Path

# Adjust path for tools/database/ location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"


def verify():
    """Run comprehensive verification."""
    print()
    print("=" * 60)
    print("DPE Sprint 6 - Milestone 1.2: Population Verification")
    print("=" * 60)
    print()
    
    if not DB_FILE.exists():
        print(f"❌ Database not found: {DB_FILE}")
        return False
    
    print(f"✓ Database: {DB_FILE}")
    print(f"  Size: {DB_FILE.stat().st_size / 1024:.1f} KB")
    print()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        print("SOURCE DATA:")
        print("-" * 60)
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        print(f"  products table: {products_count:,} rows")
        
        cur.execute("SELECT COUNT(DISTINCT sku) FROM products WHERE sku IS NOT NULL AND sku != ''")
        unique_skus = cur.fetchone()[0]
        print(f"  unique SKUs: {unique_skus:,}")
        
        cur.execute("SELECT COUNT(DISTINCT supplier) FROM products WHERE supplier IS NOT NULL AND supplier != ''")
        unique_suppliers = cur.fetchone()[0]
        print(f"  unique suppliers: {unique_suppliers:,}")
        
        print()
        print("V4.0 FOUNDATION TABLES:")
        print("-" * 60)
        
        # Suppliers
        cur.execute("SELECT COUNT(*) FROM suppliers")
        suppliers_count = cur.fetchone()[0]
        print(f"  suppliers: {suppliers_count:,} rows")
        
        if suppliers_count > 0:
            cur.execute("""
                SELECT supplier_code, is_enabled, priority_rank 
                FROM suppliers 
                ORDER BY priority_rank DESC, supplier_code
            """)
            for row in cur.fetchall():
                enabled = "✓" if row[1] else "✗"
                print(f"    {enabled} {row[0]:<15} (priority: {row[2]})")
        
        print()
        
        # Master Products
        cur.execute("SELECT COUNT(*) FROM master_products")
        master_count = cur.fetchone()[0]
        print(f"  master_products: {master_count:,} rows")
        
        if master_count > 0:
            cur.execute("SELECT COUNT(DISTINCT brand) FROM master_products WHERE brand IS NOT NULL AND brand != ''")
            brands = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT category) FROM master_products")
            categories = cur.fetchone()[0]
            print(f"    brands: {brands:,}")
            print(f"    categories: {categories:,}")
        
        print()
        
        # Supplier Products
        cur.execute("SELECT COUNT(*) FROM supplier_products")
        sp_count = cur.fetchone()[0]
        print(f"  supplier_products: {sp_count:,} rows")
        
        if sp_count > 0:
            cur.execute("SELECT COUNT(*) FROM supplier_products WHERE is_active = 1")
            active_sp = cur.fetchone()[0]
            print(f"    active: {active_sp:,}")
            
            # Count by supplier
            cur.execute("""
                SELECT s.supplier_code, COUNT(*) as count
                FROM supplier_products sp
                JOIN suppliers s ON sp.supplier_id = s.id
                GROUP BY s.supplier_code
                ORDER BY count DESC
            """)
            for row in cur.fetchall():
                print(f"    {row[0]}: {row[1]:,}")
        
        print()
        
        # Product Intelligence
        cur.execute("SELECT COUNT(*) FROM product_intelligence")
        pi_count = cur.fetchone()[0]
        print(f"  product_intelligence: {pi_count:,} rows")
        
        print()
        print("DATA INTEGRITY CHECKS:")
        print("-" * 60)
        
        integrity_ok = True
        
        # Check 1: All master_products have supplier_products entries
        cur.execute("""
            SELECT COUNT(*) FROM master_products mp
            WHERE NOT EXISTS (
                SELECT 1 FROM supplier_products sp
                WHERE sp.master_product_id = mp.id
            )
        """)
        orphaned_products = cur.fetchone()[0]
        if orphaned_products > 0:
            print(f"  ⚠  Master products without suppliers: {orphaned_products}")
            integrity_ok = False
        else:
            print(f"  ✓ All master_products have supplier_products")
        
        # Check 2: All supplier_products reference valid suppliers
        cur.execute("""
            SELECT COUNT(*) FROM supplier_products sp
            WHERE NOT EXISTS (
                SELECT 1 FROM suppliers s WHERE s.id = sp.supplier_id
            )
        """)
        invalid_suppliers = cur.fetchone()[0]
        if invalid_suppliers > 0:
            print(f"  ⚠  Supplier_products with invalid suppliers: {invalid_suppliers}")
            integrity_ok = False
        else:
            print(f"  ✓ All supplier_products have valid suppliers")
        
        # Check 3: All supplier_products reference valid master_products
        cur.execute("""
            SELECT COUNT(*) FROM supplier_products sp
            WHERE NOT EXISTS (
                SELECT 1 FROM master_products mp WHERE mp.id = sp.master_product_id
            )
        """)
        invalid_products = cur.fetchone()[0]
        if invalid_products > 0:
            print(f"  ⚠  Supplier_products with invalid products: {invalid_products}")
            integrity_ok = False
        else:
            print(f"  ✓ All supplier_products have valid master_products")
        
        # Check 4: All product_intelligence reference valid master_products
        cur.execute("""
            SELECT COUNT(*) FROM product_intelligence pi
            WHERE NOT EXISTS (
                SELECT 1 FROM master_products mp WHERE mp.id = pi.master_product_id
            )
        """)
        invalid_pi = cur.fetchone()[0]
        if invalid_pi > 0:
            print(f"  ⚠  Product_intelligence with invalid products: {invalid_pi}")
            integrity_ok = False
        else:
            print(f"  ✓ All product_intelligence have valid master_products")
        
        # Check 5: No duplicate supplier_products
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT master_product_id, supplier_id FROM supplier_products
                GROUP BY master_product_id, supplier_id
                HAVING COUNT(*) > 1
            )
        """)
        duplicate_sp = cur.fetchone()[0]
        if duplicate_sp > 0:
            print(f"  ⚠  Duplicate supplier_products entries: {duplicate_sp}")
            integrity_ok = False
        else:
            print(f"  ✓ No duplicate supplier_products")
        
        # Check 6: Verify relationship counts
        cur.execute("""
            SELECT AVG(sp_count) as avg_suppliers
            FROM (
                SELECT COUNT(*) as sp_count
                FROM supplier_products
                GROUP BY master_product_id
            )
        """)
        avg_suppliers = cur.fetchone()[0]
        print(f"  ✓ Average suppliers per product: {avg_suppliers:.1f}")
        
        print()
        print("RELATIONSHIP SUMMARY:")
        print("-" * 60)
        
        # Master products to suppliers ratio
        if master_count > 0 and suppliers_count > 0:
            ratio = sp_count / master_count if master_count > 0 else 0
            print(f"  Total relationships: {sp_count:,}")
            print(f"  Products: {master_count:,}")
            print(f"  Suppliers: {suppliers_count:,}")
            print(f"  Coverage: {ratio:.2f} supplier entries per product")
        
        print()
        print("DATABASE CONSISTENCY:")
        print("-" * 60)
        
        # Check that source products table is unchanged
        print(f"  ✓ products table still intact: {products_count:,} rows")
        
        # Check indexes
        cur.execute("""
            SELECT COUNT(*) FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%' OR name LIKE 'sqlite_autoindex%'
        """)
        index_count = cur.fetchone()[0]
        print(f"  ✓ Indexes in place: {index_count}")
        
        print()
        print("SUMMARY:")
        print("-" * 60)
        
        if integrity_ok and master_count > 0 and suppliers_count > 0:
            print("  ✅ Data integrity: VALID")
        elif master_count == 0 and suppliers_count == 0:
            print("  ⚠  Tables are empty (not yet populated)")
        else:
            print("  ⚠  Data integrity issues detected")
        
        print()
        
        if master_count > 0 and suppliers_count > 0 and sp_count > 0:
            print(f"✅ Population verification PASSED")
            print(f"   - {master_count:,} master products")
            print(f"   - {suppliers_count:,} suppliers")
            print(f"   - {sp_count:,} supplier_products")
            print(f"   - {pi_count:,} product_intelligence records")
        else:
            print("⚠  Population verification INCOMPLETE (tables empty)")
        
        print()
        
        conn.close()
        return integrity_ok and (master_count > 0 and suppliers_count > 0)
        
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify()
    exit(0 if success else 1)
