from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.paths import get_project_root
from dpe_v3.image_engine import find_image_for_product, load_image_library


@dataclass(frozen=True)
class ImageEnrichmentReport:
    products_scanned: int
    already_had_image: int
    images_found_in_image_library: int
    images_assigned: int
    require_website_lookup: int
    errors: int


class ImageEnrichmentService:
    """Incremental image enrichment framework for master products."""

    def __init__(self, db_file: Optional[Path] = None) -> None:
        if db_file is None:
            project_root = Path(get_project_root(__file__))
            db_file = project_root / "output" / "dpe_catalogue.db"
        self._db_file = Path(db_file)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_master_image_field(self, conn: sqlite3.Connection) -> None:
        """Add master_products.image_url if missing."""
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(master_products)")
        columns = {row[1] for row in cur.fetchall()}
        if "image_url" not in columns:
            cur.execute("ALTER TABLE master_products ADD COLUMN image_url TEXT")
            conn.commit()

    def run_incremental(self) -> ImageEnrichmentReport:
        """Compatibility entry point for the Cassons image enrichment pass."""
        return self.run_for_supplier("Cassons")

    def run_for_supplier(self, supplier_name: str) -> ImageEnrichmentReport:
        errors = 0
        conn = self._get_connection()

        try:
            self._ensure_master_image_field(conn)
            image_library = load_image_library()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT COUNT(*)
                FROM master_products mp
                JOIN supplier_products sp ON sp.master_product_id = mp.id
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE s.supplier_name = ?
                  AND mp.sku IS NOT NULL AND TRIM(mp.sku) != ''
                """,
                (supplier_name,),
            )
            products_scanned = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*)
                FROM master_products mp
                JOIN supplier_products sp ON sp.master_product_id = mp.id
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE s.supplier_name = ?
                  AND mp.sku IS NOT NULL AND TRIM(mp.sku) != ''
                  AND mp.image_url IS NOT NULL AND TRIM(mp.image_url) != ''
                """,
                (supplier_name,),
            )
            already_had_image = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT mp.id, mp.sku, mp.title, mp.image_url
                FROM master_products mp
                JOIN supplier_products sp ON sp.master_product_id = mp.id
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE s.supplier_name = ?
                  AND mp.sku IS NOT NULL AND TRIM(mp.sku) != ''
                GROUP BY mp.id, mp.sku, mp.title, mp.image_url
                ORDER BY mp.sku
                """,
                (supplier_name,),
            )
            products = cur.fetchall()

            images_found_in_image_library = 0
            images_assigned = 0

            for product in products:
                sku = (product["sku"] or "").strip()
                title = (product["title"] or "").strip()
                has_master_image = bool((product["image_url"] or "").strip())

                image_url, _ = find_image_for_product({"sku": sku, "title": title}, image_library)
                if image_url:
                    images_found_in_image_library += 1

                if has_master_image or not image_url:
                    continue

                cur.execute(
                    """
                    UPDATE master_products
                    SET image_url = ?
                    WHERE id = ?
                      AND (image_url IS NULL OR TRIM(image_url) = '')
                    """,
                    (image_url, product["id"]),
                )
                if cur.rowcount:
                    images_assigned += 1

            conn.commit()

            cur.execute(
                """
                SELECT COUNT(*)
                FROM master_products mp
                JOIN supplier_products sp ON sp.master_product_id = mp.id
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE s.supplier_name = ?
                  AND mp.sku IS NOT NULL AND TRIM(mp.sku) != ''
                  AND (mp.image_url IS NULL OR TRIM(mp.image_url) = '')
                """,
                (supplier_name,),
            )
            require_website_lookup = int(cur.fetchone()[0])

            return ImageEnrichmentReport(
                products_scanned=products_scanned,
                already_had_image=already_had_image,
                images_found_in_image_library=images_found_in_image_library,
                images_assigned=images_assigned,
                require_website_lookup=require_website_lookup,
                errors=errors,
            )
        except Exception:
            errors += 1
            return ImageEnrichmentReport(
                products_scanned=0,
                already_had_image=0,
                images_found_in_image_library=0,
                images_assigned=0,
                require_website_lookup=0,
                errors=errors,
            )
        finally:
            conn.close()
