# Sprint 6 Milestone 1.2 - Build Pipeline Inspection Report
## Findings on Supplier Data Loading Architecture

**Date:** 29 June 2026  
**Status:** Inspection Complete - Ready for Architecture Decision  
**Finding:** Current population script uses wrong data source; needs revision to reuse existing build pipeline

---

## Executive Summary

The build pipeline successfully processes **96,140 supplier rows** across three suppliers (A1: 38,637, Cassons: 24,131, Serco: 33,371), but the current Milestone 1.2 population script only loaded **24,130 products** (Cassons only).

**Root Cause:** The populate script reads CSVs directly without using the existing supplier plugin system, which means:
- It bypasses supplier-specific field normalization
- It cannot handle the different CSV formats (A1/Serco use arrays; Cassons uses dict with headers)
- It only successfully processes Cassons data

**Solution:** Reuse the existing supplier loader (`dpe_v3.supplier_plugins.loader.load_all_suppliers()`) which is the production source of truth and handles all three suppliers correctly.

---

## 1. Build Pipeline Architecture

### 1.1 Entry Point: `run_dpe_v3.py`

The main build orchestrator calls `load_all_suppliers()` and processes through a pipeline:

```
run_dpe_v3.py
  ↓
load_all_suppliers()  [96,140 rows]
  ↓
merge_duplicate_skus()  [95,759 unique SKUs]
  ↓
apply_business_rules()  [pricing/stock logic]
  ↓
load_image_library() + attach_images()
  ↓
load_legacy_descriptions() + attach_descriptions()
  ↓
build_shopify_csv()  [final export]
```

### 1.2 Supplier Loader System

**File:** `dpe_v3/supplier_plugins/loader.py`

**Key Function:** `load_all_suppliers()`
```python
def load_all_suppliers():
    suppliers = discover_plugins()  # Load enabled plugins from config
    print(f"Supplier plugins enabled: {len(suppliers)}")
    products = []
    for supplier in suppliers:
        print(f"Loading {supplier.SUPPLIER_NAME}...")
        products.extend(supplier.load())  # Each plugin reads its CSV
    return products
```

**Flow:**
1. Reads `config/suppliers.json` to determine enabled suppliers
2. Discovers plugin modules from `dpe_v3/supplier_plugins/`
3. Each plugin loads its CSV file and normalizes rows
4. Returns list of normalized product dictionaries

### 1.3 Supplier Plugins: Format & Fields

Each plugin normalizes CSV rows into this structure:
```python
{
    'sku': str,              # Upper-cased product SKU
    'title': str,            # Product title/description
    'brand': str,            # Brand name (empty for some suppliers)
    'category': str,         # Product category (empty for some)
    'cost': float,           # Trade/wholesale cost
    'rrp': float,           # Recommended retail price
    'stock': str or int,    # Stock quantity (as string initially)
    'barcode': str,         # UPC/Barcode (usually empty)
    'supplier': str,        # e.g., "A1", "Cassons", "Serco"
}
```

---

## 2. Supplier-Specific Details

### 2.1 A1 Plugin - `dpe_v3/supplier_plugins/a1.py`

**CSV File:** `input/A1/A1 pricefile.csv`  
**Rows:** 38,637 products  
**Format:** Array-based (positional columns)

**Field Mapping:**
```python
# Using array indices, not column names
sku = row[0].upper()              # Column 0
title = row[1]                    # Column 1
stock = row[2]                    # Column 2
cost = row[3]  (money format)     # Column 3
rrp = row[4]   (money format)     # Column 4
brand = ""                         # Not available
category = ""                      # Not available
barcode = ""                       # Not available
```

**Encoding:** Tries multiple (utf-8-sig, utf-8, cp1252, latin1)

**Row Validation:** Length check (`len(row) < 5` = skip)

### 2.2 Cassons Plugin - `dpe_v3/supplier_plugins/cassons.py`

**CSV File:** `input/Cassons/Cassons.csv`  
**Rows:** 24,131 products  
**Format:** Dictionary-based (named columns via csv.DictReader)

**Field Mapping:**
```python
# Using first_field() for flexible column lookup
sku = first_field(row, ["Part No."]).upper()
title = first_field(row, ["Description"]) or sku
brand = first_field(row, ["Brand"])
category = first_field(row, ["Category", "Product Group", "Classification"])
cost = money(first_field(row, ["Cassons Standard Price", "Sell Price"]))
rrp = money(first_field(row, ["Special RRP", "RRP"]))
stock = first_field(row, ["Stock Available"])
barcode = first_field(row, ["UPC Code"])
```

**Encoding:** Uses csv_utils.read_csv() with fallback encoding trials

**Row Validation:** SKU required (returns None if missing)

**Special Logic:** Tracks skipped rows separately

### 2.3 Serco Plugin - `dpe_v3/supplier_plugins/serco.py`

**CSV File:** `input/Serco/serco.csv`  
**Rows:** 33,371 products  
**Format:** Array-based (positional columns)

**Field Mapping:**
```python
# Using array indices, like A1
sku = row[0].upper()              # Column 0
title = row[1]                    # Column 1
stock = row[2]                    # Column 2
cost = row[3]  (money format)     # Column 3
rrp = row[4]   (money format)     # Column 4
brand = ""                         # Not available
category = ""                      # Not available
barcode = ""                       # Not available
```

**Encoding:** Tries multiple (utf-8-sig, utf-8, cp1252, latin1)

**Row Validation:** Length check + SKU header skip

---

## 3. Merge Engine: Deduplication Logic

**File:** `dpe_v3/merge_engine.py`

**Process:** `merge_duplicate_skus(products)` combines products with same SKU

**Decision Logic - choosing best supplier when SKU appears multiple times:**
```python
1. Choose supplier with HIGHEST stock (stock_score())
2. If stock is equal, choose by SUPPLIER PRIORITY:
   - A1: priority 1 (highest)
   - Cassons: priority 2
   - Serco: priority 3 (lowest)
3. If stock and priority tied, choose LOWEST COST
4. Returns merged product dict with 'supplier_options' list
```

**Stock Scoring:**
```python
"In Stock" / "Available" / "Yes" / "True" → 100
"Out of Stock" / "Unavailable" / "No" / "False" / "N/A" → 0
Numeric values → int(value)
```

**Result:**
- Input: 96,140 rows (some SKUs from multiple suppliers)
- Output: 95,759 unique SKUs (381 duplicates merged)

---

## 4. CSV Utilities & Helper Functions

**File:** `dpe_v3/csv_utils.py`

### 4.1 `first_field(row, names)`
Used by Cassons to find column by multiple possible names:
```python
# Case-insensitive lookup
first_field(row, ["Part No.", "SKU", "Product Code"])
# Returns first matching value or ""
```

### 4.2 `money(value)`
Converts money strings to float:
```python
"$12.95" → 12.95
"1,234.56" → 1234.56
"12.95 AUD" → 12.95
"" → 0.0
```

### 4.3 `clean(value)`
Safely handles None and whitespace:
```python
None → ""
"  text  " → "text"
```

### 4.4 `read_csv(path)`
Reads CSV with fallback encoding:
```python
Tries: utf-8-sig, utf-8, cp1252, latin1
Returns: list of dicts via csv.DictReader
```

---

## 5. Why Current Population Script Failed

### 5.1 Problem: Only 24,130 supplier_products (Cassons only)

**Expected:** 96,139 rows from CSVs → ~95,759 master products with all three suppliers

**Got:** 24,130 rows (only Cassons)

### 5.2 Root Causes

**Issue 1: Direct CSV Reading Without Plugins**
```python
# Current populate script does:
with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f)  # Assumes dict format
    # ... generic field extraction
```

**Problem:** CSV formats vary by supplier:
- A1/Serco: array-based (no headers, positional columns)
- Cassons: dict-based (with named columns)
- Direct DictReader fails silently on A1/Serco

**Issue 2: Generic Field Name Matching**
```python
# Script tries this:
if k_lower in ['sku', 'part no.', 'variant sku']:
    sku = row[key]
```

**Problem:** A1/Serco plugins use array indices, not column names:
- `row[0]` not `row['sku']`
- Script can't extract data from positional arrays

**Issue 3: Bypassing Plugin Configuration**
- Plugins use `config/suppliers.json` to determine enabled suppliers
- Script reads files directly without this control
- No mechanism to respect enabled/disabled suppliers

**Issue 4: Missing Field Extraction Logic**
- Plugins have supplier-specific normalise_row() with field precedence
- Script uses generic extraction that doesn't handle:
  - Alternative column names ("Cassons Standard Price" vs "Sell Price")
  - Money formatting ($, commas, currency codes)
  - Stock string parsing ("In Stock" → 100)

---

## 6. Data Structure Available Before Build Pipeline

### 6.1 Fields Available in load_all_suppliers() Output

**Always Present:**
✓ sku (extracted and normalized by each plugin)  
✓ title (fallback to SKU if empty)  
✓ cost (float, 0.0 if missing)  
✓ rrp (float, 0.0 if missing)  
✓ stock (string from CSV)  
✓ supplier (plugin name: "A1", "Cassons", "Serco")  

**Sometimes Present (depends on supplier):**
✓ brand (Cassons has; A1/Serco empty)  
✓ category (Cassons has; A1/Serco empty)  
✓ barcode (usually empty, only Cassons may have)  

**NOT Available at this stage:**
✗ image_url (added later by image_engine.attach_images())  
✗ description (added later by content_engine.attach_descriptions())  

### 6.2 What Gets Added Later in Build Pipeline

**Image Engine:** `dpe_v3/image_engine.py`
- Loads image library from `output/image_urls.csv`
- Attaches images to products by SKU matching
- Only ~8,320 images available for ~95,759 products

**Content Engine:** `dpe_v3/content_engine.py`
- Loads legacy descriptions from `output/shopify_import_smart.csv`
- Only ~1,207 descriptions available
- Uses defaults for ~95,751 products

---

## 7. Reusability Analysis

### 7.1 Can We Reuse the Supplier Loader?

**YES - HIGHLY RECOMMENDED**

**Advantages:**
1. ✓ Already tested and production-proven (builds run daily)
2. ✓ Handles all three suppliers (A1, Cassons, Serco)
3. ✓ Correctly normalizes different CSV formats
4. ✓ Respects config/suppliers.json enabled/disabled setting
5. ✓ Gets all 96,139 rows with correct fields
6. ✓ Deduplicates to 95,759 unique SKUs
7. ✓ No duplicate code to maintain
8. ✓ Changes to plugins auto-apply to population

**How to Use:**
```python
from dpe_v3.supplier_plugins.loader import load_all_suppliers

# Get 96,139 normalized products
products = load_all_suppliers()

# Each product dict has:
# {
#   'sku': 'ABC123',
#   'title': 'Product Name',
#   'brand': 'Brand',
#   'category': 'Category',
#   'cost': 12.95,
#   'rrp': 24.95,
#   'stock': '100',
#   'barcode': '',
#   'supplier': 'Cassons',
# }

# Then populate tables from this data
```

### 7.2 Alternative: Replicate Plugin Logic

**NOT RECOMMENDED**

Would need to:
1. Duplicate A1 plugin's array-based CSV reading
2. Duplicate Cassons plugin's dict-based CSV reading with first_field()
3. Duplicate Serco plugin's array-based CSV reading
4. Duplicate money(), clean() utilities
5. Duplicate merge_duplicate_skus() logic

**Problems:**
- High maintenance cost (changes to plugins forgotten)
- Easy to introduce subtle bugs
- Violates DRY principle
- Code review difficulty

---

## 8. Files That Load Supplier Rows

### Build Centre Pipeline
| File | Purpose | Rows Processed |
|------|---------|-----------------|
| `run_dpe_v3.py` | Main orchestrator | 96,140 |
| `dpe_v3/suppliers.py` | Re-exports loader | Passthrough |
| `dpe_v3/supplier_plugins/loader.py` | Discovers & loads plugins | 96,140 |
| `dpe_v3/supplier_plugins/a1.py` | A1 CSV loader | 38,637 |
| `dpe_v3/supplier_plugins/cassons.py` | Cassons CSV loader | 24,131 |
| `dpe_v3/supplier_plugins/serco.py` | Serco CSV loader | 33,371 |
| `dpe_v3/merge_engine.py` | Deduplicates by SKU | 95,759 (output) |

### Build Centre UI
| File | Purpose |
|------|---------|
| `desktop/catalogue.py` | Calls run_dpe_v3.py subprocess |
| `desktop/pages/catalogue_page.py` | UI for build trigger |

---

## 9. Recommended Revised Milestone 1.2 Approach

### Phase 1: Core Population (Use Supplier Loader)

**Revised populate_v4_foundation.py:**

```python
from dpe_v3.supplier_plugins.loader import load_all_suppliers

# 1. Load all suppliers (96,139 rows)
products = load_all_suppliers()

# 2. Populate suppliers (from config/suppliers.json) ✓ Keep current
#    - a1, cassons, serco with priority ranking

# 3. Populate master_products (from unique SKUs) ✓ Keep current
#    - 95,759 records after deduplication
#    - Use products list to get title, brand, category

# 4. Populate supplier_products (from products list) ← CHANGE
#    - 96,139 records (before dedup) or 95,759+ (after?)
#    - Map each product to supplier_products junction table
#    - Extract: supplier_sku, cost, rrp, stock
#    - Leave image_url, description NULL (added in Phase 2)

# 5. Populate product_intelligence ✓ Keep current
#    - 95,759 empty skeleton records
```

### Phase 2: Enhancement (Optional - Future Milestone)

```python
# After Phase 1, optionally populate:
# - image_url (from image_library during build)
# - description_text (from legacy descriptions during build)
# 
# But this requires running full build pipeline
# OR keeping images/descriptions separate in product_intelligence
```

### Design Decision

**Question for Architecture Review:**
Should supplier_products table have:

**Option A (Recommended for Milestone 1.2):**
- supplier_sku, cost, rrp, stock ✓
- image_url NULL, description NULL
- (Images/descriptions added during build pipeline)

**Option B (Future enhancement):**
- All fields populated from build output
- Requires running full build pipeline before population
- More data duplication but cleaner separation

---

## 10. Action Items

### Immediate (For Milestone 1.2 Revision)

- [ ] Update populate_v4_foundation.py to use load_all_suppliers()
- [ ] Verify it loads all 96,139 products (not just Cassons)
- [ ] Update supplier_products to store cost, rrp, stock from all suppliers
- [ ] Re-run populate script and verify 96,139 rows
- [ ] Run verify_population.py to confirm all relationships valid
- [ ] Test application still functional

### Future Considerations

- [ ] Decision on image_url/description storage in supplier_products
- [ ] Possible Phase 2 to populate images/descriptions during build
- [ ] Possible caching of load_all_suppliers() output for reuse

---

## Appendix: Configuration Reference

### config/suppliers.json
```json
{
  "enabled_suppliers": ["a1", "cassons", "serco"]
}
```

### dpe_v3/config.py (Supplier Priority)
```python
SUPPLIER_PRIORITY = {
    "A1": 1,          # Highest priority
    "Cassons": 2,
    "Serco": 3,       # Lowest priority
}
```

### CSV File Locations
```
input/
  A1/
    A1 pricefile.csv (38,637 rows)
  Cassons/
    Cassons.csv (24,131 rows)
  Serco/
    serco.csv (33,371 rows)
```

---

**Report Completed:** 29 June 2026  
**Prepared by:** Build Pipeline Inspection  
**Status:** Ready for Architecture Decision
