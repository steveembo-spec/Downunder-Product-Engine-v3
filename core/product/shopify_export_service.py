from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Shopify column spec (order matters – Shopify expects this column order)
# Matches dpe_v3_shopify_ready.csv format exactly
# ---------------------------------------------------------------------------

SHOPIFY_COLUMNS = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Product Category",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Variant SKU",
    "Variant Grams",
    "Variant Inventory Tracker",
    "Variant Inventory Qty",
    "Variant Inventory Policy",
    "Variant Fulfillment Service",
    "Variant Price",
    "Variant Compare At Price",
    "Cost per item",
    "Variant Requires Shipping",
    "Variant Taxable",
    "Variant Barcode",
    "Image Src",
    "Image Position",
    "Status",
]

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ShopifyExportResult:
    success: bool
    output_file: str
    rows_exported: int
    error_message: str

# ---------------------------------------------------------------------------
# Handle generation
# ---------------------------------------------------------------------------

_HANDLE_STRIP = re.compile(r"[^\w\s-]")
_HANDLE_SPACE = re.compile(r"[\s_]+")


def _make_handle(title: str, sku: str) -> str:
    """Generate a URL-safe Shopify handle from title, falling back to SKU."""
    source = (title or sku or "product").strip()
    handle = source.lower()
    handle = _HANDLE_STRIP.sub("", handle)
    handle = _HANDLE_SPACE.sub("-", handle)
    handle = handle.strip("-")
    return handle or sku.lower().strip() or "product"

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ShopifyExportService:
    """
    Export Master Product Database records to a Shopify-compatible CSV.

    Reads from the existing SQLite database; performs no writes to it.
    Writes export files under output/shopify_exports/.
    """

    def __init__(
        self,
        db_file: Optional[Path] = None,
        export_dir: Optional[Path] = None,
    ) -> None:
        if db_file is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            db_file = project_root / "output" / "dpe_catalogue.db"
        if export_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            export_dir = project_root / "output" / "shopify_exports"

        self._db_file = Path(db_file)
        self._export_dir = Path(export_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_all_products(self) -> ShopifyExportResult:
        """Export all master products to a Shopify CSV."""
        return self._run_export(limit=None)

    def export_products(self, limit: Optional[int] = None) -> ShopifyExportResult:
        """Export master products with an optional row limit."""
        return self._run_export(limit=limit)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_export(self, limit: Optional[int]) -> ShopifyExportResult:
        if not self._db_file.exists():
            return ShopifyExportResult(
                success=False,
                output_file="",
                rows_exported=0,
                error_message=f"Database not found: {self._db_file}",
            )

        try:
            self._export_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ShopifyExportResult(
                success=False,
                output_file="",
                rows_exported=0,
                error_message=f"Could not create export directory: {exc}",
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self._export_dir / f"shopify_upload_{timestamp}.csv"

        try:
            rows = self._fetch_products(limit)
        except Exception as exc:
            return ShopifyExportResult(
                success=False,
                output_file="",
                rows_exported=0,
                error_message=f"Database query failed: {exc}",
            )

        try:
            rows_exported = self._write_csv(output_file, rows)
        except Exception as exc:
            return ShopifyExportResult(
                success=False,
                output_file="",
                rows_exported=0,
                error_message=f"CSV write failed: {exc}",
            )

        return ShopifyExportResult(
            success=True,
            output_file=str(output_file),
            rows_exported=rows_exported,
            error_message="",
        )

    def _fetch_products(self, limit: Optional[int]) -> list[dict]:
        """
        Query master_products joined to best available supplier_product data.
        Returns all fields needed for Shopify export with proper fallback rules.
        """
        conn = sqlite3.connect(self._db_file)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            sql = """
                SELECT
                    mp.sku,
                    mp.title,
                    mp.brand,
                    mp.category,
                    mp.rrp_avg,
                    mp.rrp_max,
                    mp.stock_total,
                    (
                        SELECT sp.supplier_rrp
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                          AND sp.supplier_rrp IS NOT NULL
                          AND sp.supplier_rrp > 0
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS supplier_rrp,
                    (
                        SELECT sp.supplier_stock
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                          AND sp.supplier_stock IS NOT NULL
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS supplier_stock,
                    (
                        SELECT sp.supplier_cost
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                          AND sp.supplier_cost IS NOT NULL
                          AND sp.supplier_cost > 0
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS supplier_cost,
                    (
                        SELECT s.supplier_name
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS supplier_name,
                    (
                        SELECT sp.image_url
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                          AND sp.image_url IS NOT NULL
                          AND sp.image_url != ''
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS image_url,
                    (
                        SELECT sp.description_text
                        FROM supplier_products sp
                        JOIN suppliers s ON sp.supplier_id = s.id
                        WHERE sp.master_product_id = mp.id
                          AND sp.description_text IS NOT NULL
                          AND sp.description_text != ''
                        ORDER BY s.priority_rank DESC
                        LIMIT 1
                    ) AS description_text
                FROM master_products mp
                WHERE mp.sku IS NOT NULL AND mp.sku != ''
                ORDER BY mp.sku
            """
            if limit is not None:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _write_csv(output_file: Path, rows: list[dict]) -> int:
        """Write Shopify CSV. Returns number of product rows written."""
        rows_exported = 0
        with output_file.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=SHOPIFY_COLUMNS)
            writer.writeheader()

            for row in rows:
                sku = (row.get("sku") or "").strip()
                if not sku:
                    continue

                # Extract and apply business rules for each field
                title = (row.get("title") or sku).strip()
                
                # Vendor: brand > supplier_name > blank
                brand = (row.get("brand") or "").strip()
                supplier_name = (row.get("supplier_name") or "").strip()
                vendor = brand if brand else supplier_name
                
                # Category and Type: use category if present, else "General"
                category = (row.get("category") or "").strip()
                if not category:
                    category = "General"
                
                # Helper to safely convert to float
                def to_float(val):
                    if val is None:
                        return None
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return None
                
                # Cost per item: supplier_cost > blank
                cost_per_item = ""
                supplier_cost = to_float(row.get("supplier_cost"))
                if supplier_cost and supplier_cost > 0:
                    cost_per_item = str(supplier_cost)
                
                # Variant Price: rrp_avg > rrp_max > supplier_rrp > (cost * 1.5) > blank
                variant_price = ""
                rrp_avg = to_float(row.get("rrp_avg"))
                rrp_max = to_float(row.get("rrp_max"))
                supplier_rrp = to_float(row.get("supplier_rrp"))
                
                if rrp_avg and rrp_avg > 0:
                    variant_price = str(rrp_avg)
                elif rrp_max and rrp_max > 0:
                    variant_price = str(rrp_max)
                elif supplier_rrp and supplier_rrp > 0:
                    variant_price = str(supplier_rrp)
                elif supplier_cost and supplier_cost > 0:
                    # Calculate price from cost: cost * 1.5, rounded to 2 decimals
                    calculated_price = round(supplier_cost * 1.5, 2)
                    variant_price = str(calculated_price)
                
                # Variant Inventory Qty: stock_total > supplier_stock > 0
                inventory_qty = 0
                stock_total = row.get("stock_total")
                supplier_stock = row.get("supplier_stock")
                
                try:
                    if stock_total and int(stock_total) > 0:
                        inventory_qty = int(stock_total)
                    elif supplier_stock and int(supplier_stock) > 0:
                        inventory_qty = int(supplier_stock)
                except (ValueError, TypeError):
                    inventory_qty = 0
                
                # Body (HTML) and Image Src: use supplier data if present
                image_src = (row.get("image_url") or "").strip()
                body_html = (row.get("description_text") or "").strip()
                
                # Tags: supplier name, brand, category
                tags = []
                if supplier_name:
                    tags.append(f"supplier:{supplier_name}")
                if brand:
                    tags.append(f"brand:{brand}")
                if category and category != "General":
                    tags.append(f"category:{category}")
                tags_str = ", ".join(tags)

                writer.writerow({
                    "Handle":                       _make_handle(title, sku),
                    "Title":                        title,
                    "Body (HTML)":                  body_html,
                    "Vendor":                       vendor,
                    "Product Category":             category,
                    "Type":                         category,
                    "Tags":                         tags_str,
                    "Published":                    "FALSE",
                    "Option1 Name":                 "Title",
                    "Option1 Value":                "Default Title",
                    "Variant SKU":                  sku,
                    "Variant Grams":                "0",
                    "Variant Inventory Tracker":    "shopify",
                    "Variant Inventory Qty":        str(inventory_qty),
                    "Variant Inventory Policy":     "deny",
                    "Variant Fulfillment Service":  "manual",
                    "Variant Price":                variant_price,
                    "Variant Compare At Price":     "",
                    "Cost per item":                cost_per_item,
                    "Variant Requires Shipping":    "TRUE",
                    "Variant Taxable":              "TRUE",
                    "Variant Barcode":              "",
                    "Image Src":                    image_src,
                    "Image Position":               "",
                    "Status":                       "draft",
                })
                rows_exported += 1

        return rows_exported
