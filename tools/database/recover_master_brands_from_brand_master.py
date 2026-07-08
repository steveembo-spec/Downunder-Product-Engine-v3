#!/usr/bin/env python
"""
DPE Sprint 11 - Milestone 8: Recover Master Brands from Brand Master

Objective:
- Recover brands into master_products using approved brand_master entries only.

Hard rules enforced by this script:
- Reads from brand_master only (no external dictionaries, no AI, no fuzzy matching).
- Processes only master_products rows where brand is blank.
- Matches only at beginning of title.
- Longest matching brand_master entry wins.
- Never overwrites existing master_products.brand values.
- If no match, brand remains blank.

Output report:
- Products scanned
- Products with existing brand
- Brands recovered
- Remaining blank brands
- Top 100 unmatched title prefixes
- Recovery percentage
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_text(value: str) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def extract_unmatched_prefix(title: str) -> str:
    # Report-friendly prefix bucket for unmatched titles.
    normalized = normalize_text(title)
    if not normalized:
        return "<BLANK_TITLE>"
    token = normalized.split(" ", 1)[0]
    return token or "<BLANK_TITLE>"


def starts_with_brand(title_normalized: str, brand_normalized: str) -> bool:
    if not title_normalized or not brand_normalized:
        return False

    if title_normalized == brand_normalized:
        return True

    # Boundary-safe prefix match only at start.
    return title_normalized.startswith(brand_normalized + " ")


@dataclass
class RecoveryReport:
    products_scanned: int
    products_with_existing_brand: int
    brands_recovered: int
    remaining_blank_brands: int
    recovery_percentage: float
    top_unmatched_prefixes: list[tuple[str, int]]


def load_brand_master_entries(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT brand_name
        FROM brand_master
        WHERE brand_name IS NOT NULL
          AND TRIM(brand_name) != ''
          AND (status IS NULL OR LOWER(TRIM(status)) = 'active')
        """
    )

    rows = []
    seen = set()
    for r in cur.fetchall():
        brand_name = str(r["brand_name"]).strip()
        brand_norm = normalize_text(brand_name)
        if not brand_norm:
            continue
        if brand_norm in seen:
            continue
        seen.add(brand_norm)
        rows.append((brand_name, brand_norm, len(brand_norm)))

    # Longest matching Brand Master entry wins.
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows


def recover_master_product_brands(conn: sqlite3.Connection) -> RecoveryReport:
    cur = conn.cursor()

    cur.execute("SELECT id, title, brand FROM master_products")
    products = cur.fetchall()

    products_scanned = len(products)
    products_with_existing_brand = sum(1 for p in products if not is_blank(p["brand"]))

    brand_master_entries = load_brand_master_entries(conn)
    if not brand_master_entries:
        raise RuntimeError("No active Brand Master entries found in brand_master.")

    updates: list[tuple[str, int]] = []
    unmatched_prefix_counts: Counter[str] = Counter()

    for product in products:
        product_id = int(product["id"])
        title = str(product["title"] or "")
        brand = product["brand"]

        # Never overwrite existing brands.
        if not is_blank(brand):
            continue

        title_norm = normalize_text(title)
        matched_brand = ""

        for brand_name, brand_norm, _length in brand_master_entries:
            if starts_with_brand(title_norm, brand_norm):
                matched_brand = brand_name
                break

        if matched_brand:
            updates.append((matched_brand, product_id))
        else:
            unmatched_prefix_counts[extract_unmatched_prefix(title)] += 1

    if updates:
        cur.executemany(
            """
            UPDATE master_products
            SET brand = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND (brand IS NULL OR TRIM(brand) = '')
            """,
            updates,
        )
    conn.commit()

    brands_recovered = len(updates)

    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM master_products
        WHERE brand IS NULL OR TRIM(brand) = ''
        """
    )
    remaining_blank_brands = int(cur.fetchone()["c"])

    blank_before = products_scanned - products_with_existing_brand
    recovery_percentage = 0.0
    if blank_before > 0:
        recovery_percentage = (brands_recovered / blank_before) * 100.0

    top_unmatched_prefixes = unmatched_prefix_counts.most_common(100)

    return RecoveryReport(
        products_scanned=products_scanned,
        products_with_existing_brand=products_with_existing_brand,
        brands_recovered=brands_recovered,
        remaining_blank_brands=remaining_blank_brands,
        recovery_percentage=recovery_percentage,
        top_unmatched_prefixes=top_unmatched_prefixes,
    )


def run() -> bool:
    print()
    print("=" * 78)
    print("DPE Sprint 11 - Milestone 8: Recover Master Brands from Brand Master")
    print("=" * 78)

    if not DB_FILE.exists():
        print(f"ERROR: Database not found: {DB_FILE}")
        return False

    conn = get_connection()
    try:
        report = recover_master_product_brands(conn)

        print()
        print("Recovery report:")
        print(f"- Products scanned: {report.products_scanned}")
        print(f"- Products with existing brand: {report.products_with_existing_brand}")
        print(f"- Brands recovered: {report.brands_recovered}")
        print(f"- Remaining blank brands: {report.remaining_blank_brands}")
        print(f"- Recovery percentage: {report.recovery_percentage:.2f}%")

        print()
        print("Top 100 unmatched title prefixes:")
        if report.top_unmatched_prefixes:
            for prefix, count in report.top_unmatched_prefixes:
                print(f"  - {prefix}: {count}")
        else:
            print("  - (none)")

        return True
    finally:
        conn.close()


if __name__ == "__main__":
    ok = run()
    raise SystemExit(0 if ok else 1)
