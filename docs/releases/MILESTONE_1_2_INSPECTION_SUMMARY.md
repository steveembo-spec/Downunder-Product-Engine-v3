# Milestone 1.2 Inspection - Quick Summary

## The Problem
Current populate script loaded only **24,130 supplier_products** (Cassons only)  
Should load: **96,139 supplier rows** from all three suppliers

## Root Cause
Population script reads CSVs directly without using supplier plugins.  
This fails because:
- A1 & Serco CSVs use **array format** (positional columns)
- Cassons CSV uses **dict format** (named columns)
- Generic field extraction can't handle both formats
- Result: Only Cassons is parsed successfully

## The Source of Truth
Build pipeline **correctly processes all 96,140 rows** by using:
```
dpe_v3/supplier_plugins/loader.load_all_suppliers()
  ↓
Discovers enabled plugins: a1.py, cassons.py, serco.py
  ↓
Each plugin.load() reads its CSV with custom normalization
  ↓
Returns list of normalized product dicts (96,139 rows)
  ↓
merge_duplicate_skus() deduplicates by SKU (95,759 unique)
```

## CSV Distribution
- **A1:** 38,637 products
- **Cassons:** 24,131 products
- **Serco:** 33,371 products
- **Total:** 96,139 supplier rows
- **After dedup by SKU:** 95,759 unique products

## Fields Available at Each Stage

**From load_all_suppliers():**
- ✓ sku, title, brand, category, cost, rrp, stock, barcode, supplier

**Added later in build pipeline:**
- image_url (from image_library during build)
- description (from legacy descriptions during build)

## The Solution
**Reuse the supplier loader** instead of reading CSVs directly:

```python
from dpe_v3.supplier_plugins.loader import load_all_suppliers

# Gets all 96,139 rows with proper normalization
products = load_all_suppliers()

# Then populate:
# - suppliers (from config)
# - master_products (unique SKUs)
# - supplier_products (junction table from products list)
# - product_intelligence (empty records)
```

## Why This Works
1. ✓ Tested and production-proven (daily builds)
2. ✓ Handles all three suppliers
3. ✓ Correctly normalizes different CSV formats
4. ✓ Respects enabled/disabled config
5. ✓ No duplicate code to maintain
6. ✓ Single source of truth

## Files to Examine
- **Build entry:** `run_dpe_v3.py`
- **Loader:** `dpe_v3/supplier_plugins/loader.py`
- **Plugins:** `dpe_v3/supplier_plugins/{a1,cassons,serco}.py`
- **Merge:** `dpe_v3/merge_engine.py`
- **Utilities:** `dpe_v3/csv_utils.py`

## Recommended Revision
Update `tools/database/populate_v4_foundation.py` to:
1. Import `load_all_suppliers()`
2. Call `products = load_all_suppliers()` to get all 96,139 rows
3. Populate supplier_products from this products list
4. Keep everything else the same

This will:
- Load all 96,139 supplier rows (not just 24,130)
- Match the build pipeline's data source
- Create ~95,759+ supplier_product relationships
- Maintain data integrity and auditability
