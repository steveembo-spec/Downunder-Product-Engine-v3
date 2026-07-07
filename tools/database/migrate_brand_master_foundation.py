#!/usr/bin/env python
"""
DPE Sprint 11 - Milestone 7: Brand Master Foundation

Creates and seeds a global brand_master table.

Scope:
- Infrastructure only
- No import/export/UI changes
- No title-derived brand guesses

Seed sources:
1) Existing non-blank master_products.brand values
2) Existing supplier brand fields from source files (currently Cassons)

Idempotent:
- Safe to run repeatedly
- Table create is guarded
- Seed uses canonical_key uniqueness and upsert
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"
CASSONS_FILE = PROJECT_ROOT / "input" / "Cassons" / "Cassons.csv"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return cur.fetchone() is not None


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def canonical_key(value: str) -> str:
    """Canonical key for duplicate detection and merge safety."""
    s = normalize_space(value).upper()
    s = s.replace("&", " AND ")
    s = s.replace("-", " ")
    s = re.sub(r"[^A-Z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_brand_name(value: str) -> str:
    s = normalize_space(value)
    if not s:
        return ""
    if s.isupper():
        return s.title()
    return s


def create_brand_master_table(conn: sqlite3.Connection) -> None:
    if table_exists(conn, "brand_master"):
        print("  ✓ brand_master already exists (skipping create)")
        return

    print("  → Creating brand_master table...")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE brand_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT NOT NULL,
            aliases TEXT,
            manufacturer_website TEXT,
            default_shopify_category TEXT,
            image_strategy TEXT,
            description_strategy TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            canonical_key TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    if not index_exists(conn, "idx_brand_master_name"):
        cur.execute("CREATE INDEX idx_brand_master_name ON brand_master (brand_name)")

    if not index_exists(conn, "idx_brand_master_status"):
        cur.execute("CREATE INDEX idx_brand_master_status ON brand_master (status)")

    conn.commit()
    print("  ✓ brand_master created")


def load_db_brands(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT TRIM(brand) AS brand_name, COUNT(*) AS c
        FROM master_products
        WHERE brand IS NOT NULL AND TRIM(brand) != ''
        GROUP BY TRIM(brand)
        """
    )
    return {normalize_brand_name(r["brand_name"]): int(r["c"]) for r in cur.fetchall()}


def load_supplier_file_brands() -> dict[str, int]:
    counts: dict[str, int] = {}

    if not CASSONS_FILE.exists():
        return counts

    with CASSONS_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = normalize_brand_name(row.get("Brand", ""))
            if not brand:
                continue
            counts[brand] = counts.get(brand, 0) + 1

    return counts


def seed_brand_master(conn: sqlite3.Connection) -> dict:
    db_brands = load_db_brands(conn)
    supplier_brands = load_supplier_file_brands()

    source_rows = []
    for name, c in db_brands.items():
        source_rows.append((name, c, "Existing DB brand"))
    for name, c in supplier_brands.items():
        source_rows.append((name, c, "Supplier brand field"))

    merged: dict[str, dict] = {}
    skipped = 0

    for raw_name, count, source in source_rows:
        name = normalize_brand_name(raw_name)
        key = canonical_key(name)

        if not name or not key:
            skipped += 1
            continue

        if key not in merged:
            merged[key] = {
                "brand_name": name,
                "canonical_key": key,
                "aliases": set(),
                "sources": set(),
            }
        else:
            if merged[key]["brand_name"] != name:
                merged[key]["aliases"].add(name)

        merged[key]["sources"].add(source)

    duplicate_merged = max(0, len(source_rows) - skipped - len(merged))

    cur = conn.cursor()
    upserted = 0
    for key, payload in merged.items():
        aliases_json = json.dumps(sorted(payload["aliases"])) if payload["aliases"] else json.dumps([])

        # Keep strategy fields explicit but neutral for infrastructure phase.
        cur.execute(
            """
            INSERT INTO brand_master (
                brand_name,
                aliases,
                manufacturer_website,
                default_shopify_category,
                image_strategy,
                description_strategy,
                status,
                canonical_key
            ) VALUES (?, ?, NULL, NULL, ?, ?, 'active', ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
                brand_name = excluded.brand_name,
                aliases = excluded.aliases,
                image_strategy = excluded.image_strategy,
                description_strategy = excluded.description_strategy,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload["brand_name"],
                aliases_json,
                "pending",
                "pending",
                key,
            ),
        )
        upserted += 1

    conn.commit()

    cur.execute(
        """
        SELECT id, brand_name, aliases, manufacturer_website,
               default_shopify_category, image_strategy, description_strategy, status
        FROM brand_master
        ORDER BY brand_name
        LIMIT 10
        """
    )
    example_rows = [dict(r) for r in cur.fetchall()]

    return {
        "source_rows": len(source_rows),
        "brands_imported": upserted,
        "duplicate_brands_merged": duplicate_merged,
        "brands_skipped": skipped,
        "example_rows": example_rows,
    }


def migrate_brand_master() -> bool:
    print()
    print("=" * 72)
    print("DPE Sprint 11 - Milestone 7: Brand Master Foundation")
    print("=" * 72)

    if not DB_FILE.exists():
        print(f"❌ Database not found: {DB_FILE}")
        return False

    conn = get_connection()
    try:
        print("Creating table:")
        create_brand_master_table(conn)

        print()
        print("Seeding table:")
        report = seed_brand_master(conn)

        print(f"  ✓ Brands imported: {report['brands_imported']}")
        print(f"  ✓ Duplicate brands merged: {report['duplicate_brands_merged']}")
        print(f"  ✓ Brands skipped: {report['brands_skipped']}")

        print()
        print("Example rows:")
        for row in report["example_rows"]:
            print(f"  - {row}")

        return True
    finally:
        conn.close()


if __name__ == "__main__":
    ok = migrate_brand_master()
    raise SystemExit(0 if ok else 1)
