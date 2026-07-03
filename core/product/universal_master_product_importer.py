from __future__ import annotations

import csv
import io
import sqlite3
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.product.universal_supplier_reader import UniversalSupplierReader
from core.product.header_detection import STATUS_MISSING, REQUIRED_MASTER_FIELDS

# Setup logging for diagnostics
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class UniversalImportResult:
    success: bool
    supplier_name: str
    file_path: str
    rows_read: int
    rows_imported: int
    rows_skipped: int
    products_created: int
    products_updated: int
    errors: list[str]
    error_message: str


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------

class UniversalMasterProductImporter:
    """
    Import a supplier CSV file into the Master Product database using the
    Universal Supplier Reader for header detection/profile lookup.

    Accepts an optional db_file path for testing; defaults to the standard
    output/dpe_catalogue.db location relative to the project root.
    """

    def __init__(
        self,
        db_file: Optional[Path] = None,
        profiles_dir: Optional[Path] = None,
    ) -> None:
        if db_file is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            db_file = project_root / "output" / "dpe_catalogue.db"
        self._db_file = Path(db_file)
        self._reader = UniversalSupplierReader(profiles_dir=profiles_dir)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def import_supplier_file(
        self,
        supplier_name: str,
        csv_file_path: str | Path,
    ) -> UniversalImportResult:
        """
        Read and import a supplier CSV into the master product database.
        Never raises – all errors captured in the result.
        """
        csv_file_path = Path(csv_file_path)

        # 1. Use the universal reader to detect headers/mapping
        read_result = self._reader.read_supplier_file(supplier_name, csv_file_path)

        if not read_result.success:
            return self._error(supplier_name, csv_file_path, read_result.error_message)

        if read_result.needs_review:
            missing = [
                f
                for f in REQUIRED_MASTER_FIELDS
                if read_result.detected_mapping.get(f) is None
                or read_result.detected_mapping[f].status == STATUS_MISSING
            ]
            return self._error(
                supplier_name,
                csv_file_path,
                f"Column mapping needs review before import. "
                f"Missing or ambiguous required fields: {missing or 'check confidence scores'}",
            )

        # Build header→field lookup from the mapping
        # field_to_header: master_field -> raw_header (or None)
        field_to_header: dict[str, Optional[str]] = {
            master_field: match.detected_header
            for master_field, match in read_result.detected_mapping.items()
            if match.detected_header is not None
        }

        # 2. Open the database
        if not self._db_file.exists():
            return self._error(
                supplier_name,
                csv_file_path,
                f"Database not found: {self._db_file}",
            )

        # 3. Ensure supplier record exists
        try:
            supplier_id = self._ensure_supplier(supplier_name)
        except Exception as exc:
            return self._error(supplier_name, csv_file_path, f"Supplier setup failed: {exc}")

        # 4. Read all CSV rows using detected encoding/delimiter
        try:
            raw_text = csv_file_path.read_text(
                encoding=read_result.encoding, errors="replace"
            )
            all_rows = list(
                csv.DictReader(io.StringIO(raw_text), delimiter=read_result.delimiter)
            )
        except Exception as exc:
            return self._error(supplier_name, csv_file_path, f"Could not read CSV rows: {exc}")
        
        # Log import start
        logger.info(f"[IMPORT START] Supplier: {supplier_name}, File: {csv_file_path.name}, CSV Row Count: {len(all_rows)}")

        # 5. Import rows
        rows_read = 0
        rows_imported = 0
        rows_skipped = 0
        products_created = 0
        products_updated = 0
        row_errors: list[str] = []

        conn = sqlite3.connect(self._db_file)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()

            # Pre-fetch existing SKUs for this file to track created vs updated
            logger.info("[IMPORT] Pre-fetching existing SKUs...")
            cur.execute("SELECT sku FROM master_products")
            existing_skus: set[str] = {row[0] for row in cur.fetchall()}
            logger.info(f"[IMPORT] Found {len(existing_skus)} existing SKUs")

            touched_skus: set[str] = set()
            batch_size = 1000
            import_start_time = time.time()

            for row_num, row in enumerate(all_rows, start=2):  # 2 = first data row
                rows_read += 1
                try:
                    # Extract required fields
                    sku = self._get_field(row, field_to_header, "sku")
                    title = self._get_field(row, field_to_header, "title")

                    if not sku or not sku.strip():
                        rows_skipped += 1
                        continue

                    sku = sku.strip()

                    # Extract optional fields
                    cost_raw = self._get_field(row, field_to_header, "cost")
                    rrp_raw = self._get_field(row, field_to_header, "rrp")
                    brand = self._get_field(row, field_to_header, "brand") or ""
                    category = self._get_field(row, field_to_header, "category") or "General"
                    stock_raw = self._get_field(row, field_to_header, "stock")
                    description = self._get_field(row, field_to_header, "description") or ""
                    image_url = self._get_field(row, field_to_header, "image_url") or ""
                    supplier_sku_val = self._get_field(row, field_to_header, "supplier_sku") or sku

                    cost = _parse_float(cost_raw)
                    rrp = _parse_float(rrp_raw)
                    stock = _parse_int(stock_raw)

                    # Upsert master_product (INSERT OR IGNORE – do not overwrite)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO master_products
                            (sku, title, brand, category, description_status,
                             created_at, updated_at, v4_migrated_at)
                        VALUES (?, ?, ?, ?, 'Pending',
                                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (sku, (title or sku).strip(), brand.strip(), category.strip()),
                    )
                    was_created = cur.rowcount == 1

                    # Fetch master_product id
                    cur.execute("SELECT id FROM master_products WHERE sku = ?", (sku,))
                    mp_row = cur.fetchone()
                    if mp_row is None:
                        rows_skipped += 1
                        row_errors.append(f"Row {row_num}: could not find master product id for SKU {sku!r}")
                        continue
                    master_id = mp_row[0]

                    # Upsert supplier_product
                    cur.execute(
                        """
                        INSERT INTO supplier_products
                            (master_product_id, supplier_id, supplier_sku,
                             supplier_cost, supplier_rrp, supplier_stock,
                             image_url, description_text, is_active,
                             created_at, last_updated, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1,
                                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(master_product_id, supplier_id) DO UPDATE SET
                            supplier_sku       = excluded.supplier_sku,
                            supplier_cost      = excluded.supplier_cost,
                            supplier_rrp       = excluded.supplier_rrp,
                            supplier_stock     = excluded.supplier_stock,
                            image_url          = excluded.image_url,
                            description_text   = excluded.description_text,
                            is_active          = 1,
                            last_updated       = CURRENT_TIMESTAMP,
                            synced_at          = CURRENT_TIMESTAMP
                        """,
                        (
                            master_id, supplier_id, supplier_sku_val,
                            cost, rrp, stock,
                            image_url, description,
                        ),
                    )

                    touched_skus.add(sku)
                    rows_imported += 1

                    if was_created or sku not in existing_skus:
                        products_created += 1
                        existing_skus.add(sku)
                    else:
                        products_updated += 1
                    
                    # Progress logging and batch commits every 1000 rows
                    if rows_read % batch_size == 0:
                        logger.info(f"[IMPORT PROGRESS] Row {rows_read}/{len(all_rows)}, SKU: {sku}, Imported: {rows_imported}, Created: {products_created}, Updated: {products_updated}")
                        conn.commit()  # Batch commit to prevent long transaction
                        logger.info(f"[IMPORT BATCH] Committed {batch_size} rows at position {rows_read}")

                except Exception as exc:
                    rows_skipped += 1
                    row_errors.append(f"Row {row_num}: {exc}")

            # 6. Recalculate aggregates for all touched master products
            if touched_skus:
                logger.info(f"[IMPORT AGGREGATES] Starting aggregate recalculation for {len(touched_skus)} touched products...")
                aggregate_start = time.time()
                touched_sku_list = sorted(touched_skus)
                aggregate_chunk_size = 5000
                aggregate_sql_statements = 0
                uses_correlated_subqueries = False
                loops_per_touched_sku = False

                for start_idx in range(0, len(touched_sku_list), aggregate_chunk_size):
                    sku_batch = touched_sku_list[start_idx:start_idx + aggregate_chunk_size]
                    placeholders = ",".join("?" * len(sku_batch))

                    cur.execute(
                        f"""
                        WITH touched AS (
                            SELECT id
                            FROM master_products
                            WHERE sku IN ({placeholders})
                        ),
                        aggregated AS (
                            SELECT
                                t.id AS master_id,
                                AVG(sp.supplier_cost) AS cost_avg,
                                MIN(sp.supplier_cost) AS cost_min,
                                MAX(sp.supplier_cost) AS cost_max,
                                AVG(sp.supplier_rrp) AS rrp_avg,
                                MIN(sp.supplier_rrp) AS rrp_min,
                                MAX(sp.supplier_rrp) AS rrp_max,
                                COALESCE(SUM(sp.supplier_stock), 0) AS stock_total,
                                COALESCE(SUM(CASE WHEN sp.is_active = 1 THEN 1 ELSE 0 END), 0) AS stock_suppliers
                            FROM touched t
                            LEFT JOIN supplier_products sp
                                ON sp.master_product_id = t.id
                            GROUP BY t.id
                        )
                        UPDATE master_products
                        SET
                            cost_avg = aggregated.cost_avg,
                            cost_min = aggregated.cost_min,
                            cost_max = aggregated.cost_max,
                            rrp_avg = aggregated.rrp_avg,
                            rrp_min = aggregated.rrp_min,
                            rrp_max = aggregated.rrp_max,
                            stock_total = aggregated.stock_total,
                            stock_suppliers = aggregated.stock_suppliers,
                            updated_at = CURRENT_TIMESTAMP
                        FROM aggregated
                        WHERE master_products.id = aggregated.master_id
                        """,
                        sku_batch,
                    )
                    aggregate_sql_statements += 1
                
                aggregate_time = time.time() - aggregate_start
                logger.info(
                    "[IMPORT AGGREGATES] Diagnostics: SQL statements=%s, correlated_subqueries=%s, per_sku_loop=%s, chunk_size=%s",
                    aggregate_sql_statements,
                    uses_correlated_subqueries,
                    loops_per_touched_sku,
                    aggregate_chunk_size,
                )
                logger.info(f"[IMPORT AGGREGATES] Completed in {aggregate_time:.2f} seconds")

            conn.commit()
            
            import_total_time = time.time() - import_start_time
            logger.info(f"[IMPORT COMPLETE] Total time: {import_total_time:.2f}s, Rows: {rows_read}, Imported: {rows_imported}, Created: {products_created}, Updated: {products_updated}")

        except Exception as exc:
            conn.rollback()
            logger.error(f"[IMPORT ERROR] {exc}", exc_info=True)
            return self._error(supplier_name, csv_file_path, f"Database error: {exc}")
        finally:
            conn.close()

        return UniversalImportResult(
            success=True,
            supplier_name=supplier_name,
            file_path=str(csv_file_path),
            rows_read=rows_read,
            rows_imported=rows_imported,
            rows_skipped=rows_skipped,
            products_created=products_created,
            products_updated=products_updated,
            errors=row_errors,
            error_message="",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_supplier(self, supplier_name: str) -> int:
        """Insert supplier if missing and return its id."""
        supplier_code = supplier_name.lower().strip()
        conn = sqlite3.connect(self._db_file)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO suppliers
                    (supplier_code, supplier_name, is_enabled, priority_rank,
                     created_at, updated_at)
                VALUES (?, ?, 1, 50, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (supplier_code, supplier_name),
            )
            conn.commit()
            cur.execute("SELECT id FROM suppliers WHERE supplier_code = ?", (supplier_code,))
            return cur.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def _get_field(
        row: dict,
        field_to_header: dict[str, Optional[str]],
        master_field: str,
    ) -> Optional[str]:
        """Extract a value from a CSV row using the detected header mapping."""
        header = field_to_header.get(master_field)
        if not header:
            return None
        return row.get(header) or None

    @staticmethod
    def _error(
        supplier_name: str,
        file_path: Path,
        message: str,
    ) -> UniversalImportResult:
        return UniversalImportResult(
            success=False,
            supplier_name=supplier_name,
            file_path=str(file_path),
            rows_read=0,
            rows_imported=0,
            rows_skipped=0,
            products_created=0,
            products_updated=0,
            errors=[],
            error_message=message,
        )


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None
