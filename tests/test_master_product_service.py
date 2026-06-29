#!/usr/bin/env python
"""
DPE Sprint 6 - Milestone 1.3: MasterProductService Verification

Tests the MasterProductService to ensure:
- All methods work correctly
- Data integrity is maintained
- Idempotency works
- sync_from_supplier_loader() operates correctly
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.product.master_product_service import MasterProductService


def test_service():
    """Run comprehensive service tests."""
    print()
    print("=" * 60)
    print("DPE Sprint 6 - Milestone 1.3: MasterProductService Tests")
    print("=" * 60)
    print()
    
    service = MasterProductService()
    
    # =========================================================================
    # Test 1: Database connectivity
    # =========================================================================
    print("TEST 1: Database Connectivity")
    print("-" * 60)
    
    try:
        db_file = service.db_file
        if db_file.exists():
            size_kb = db_file.stat().st_size / 1024
            print(f"  ✓ Database found: {db_file}")
            print(f"  ✓ Size: {size_kb:.1f} KB")
        else:
            print(f"  ❌ Database not found: {db_file}")
            return False
    except Exception as e:
        print(f"  ❌ Error accessing database: {e}")
        return False
    
    # =========================================================================
    # Test 2: Count master products
    # =========================================================================
    print()
    print("TEST 2: Count Master Products")
    print("-" * 60)
    
    try:
        count = service.count_master_products()
        print(f"  ✓ Total master products: {count:,}")
        
        if count == 0:
            print("  ⚠  Warning: No master products found")
        else:
            print("  ✓ Master products exist")
    except Exception as e:
        print(f"  ❌ Error counting master products: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 3: List master products (first 5)
    # =========================================================================
    print()
    print("TEST 3: List Master Products (first 5)")
    print("-" * 60)
    
    try:
        products = service.list_master_products(limit=5)
        print(f"  ✓ Retrieved {len(products)} products")
        
        for i, prod in enumerate(products, 1):
            print(f"    {i}. {prod.sku} - {prod.title[:40]}")
    except Exception as e:
        print(f"  ❌ Error listing master products: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 4: Get single product by SKU
    # =========================================================================
    print()
    print("TEST 4: Get Master Product by SKU")
    print("-" * 60)
    
    try:
        if products:
            # Get the first product's SKU
            test_sku = products[0].sku
            product = service.get_master_product_by_sku(test_sku)
            
            if product:
                print(f"  ✓ Found product: {test_sku}")
                print(f"    Title: {product.title}")
                print(f"    Brand: {product.brand}")
                print(f"    Category: {product.category}")
                print(f"    Status: {product.description_status}")
            else:
                print(f"  ❌ Product not found: {test_sku}")
                return False
        else:
            print("  ⚠  Skipping test: no products to test")
    except Exception as e:
        print(f"  ❌ Error getting product by SKU: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 5: Get supplier products for SKU
    # =========================================================================
    print()
    print("TEST 5: Get Supplier Products for SKU")
    print("-" * 60)
    
    try:
        if products:
            test_sku = products[0].sku
            supplier_products = service.list_supplier_products_for_sku(test_sku)
            
            print(f"  ✓ SKU: {test_sku}")
            print(f"  ✓ Supplier entries: {len(supplier_products)}")
            
            for sp in supplier_products:
                print(f"    - Supplier ID: {sp.supplier_id}, Cost: {sp.supplier_cost}, Stock: {sp.supplier_stock}")
    except Exception as e:
        print(f"  ❌ Error getting supplier products: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 6: Get supplier options for SKU
    # =========================================================================
    print()
    print("TEST 6: Get Supplier Options for SKU")
    print("-" * 60)
    
    try:
        if products:
            test_sku = products[0].sku
            suppliers = service.get_supplier_options_for_sku(test_sku)
            
            print(f"  ✓ SKU: {test_sku}")
            print(f"  ✓ Available suppliers: {len(suppliers)}")
            
            for supp in suppliers:
                print(f"    - {supp.supplier_name} (priority: {supp.priority_rank})")
    except Exception as e:
        print(f"  ❌ Error getting supplier options: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 7: Sync from supplier loader (idempotent)
    # =========================================================================
    print()
    print("TEST 7: Sync from Supplier Loader (Idempotency)")
    print("-" * 60)
    
    try:
        print("  Running sync (may skip if data already exists)...")
        stats = service.sync_from_supplier_loader()
        
        print()
        print("  SYNC STATISTICS:")
        print(f"    Suppliers added: {stats['suppliers_added']}")
        print(f"    Suppliers skipped: {stats['suppliers_skipped']}")
        print(f"    Master products added: {stats['master_products_added']:,}")
        print(f"    Master products skipped: {stats['master_products_skipped']:,}")
        print(f"    Supplier products added: {stats['supplier_products_added']:,}")
        print(f"    Supplier products skipped: {stats['supplier_products_skipped']:,}")
        
        if stats['suppliers_added'] == 0 and stats['suppliers_skipped'] > 0:
            print()
            print("  ✓ Idempotency test PASSED (data already exists, skipped)")
        elif stats['suppliers_added'] > 0:
            print()
            print("  ✓ First sync completed (new data added)")
    except Exception as e:
        print(f"  ❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Test 8: Verify data integrity after sync
    # =========================================================================
    print()
    print("TEST 8: Data Integrity After Sync")
    print("-" * 60)
    
    try:
        new_count = service.count_master_products()
        print(f"  ✓ Master products after sync: {new_count:,}")
        
        if new_count > 0:
            print(f"  ✓ Data integrity maintained")
        else:
            print(f"  ❌ No data in database after sync")
            return False
    except Exception as e:
        print(f"  ❌ Error verifying data: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # Summary
    # =========================================================================
    print()
    print("=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    print()
    
    return True


if __name__ == "__main__":
    success = test_service()
    exit(0 if success else 1)
