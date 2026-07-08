#!/usr/bin/env python
"""
DPE Sprint 11 - Milestone 9: Improve Brand Master from unmatched prefixes.

Scope:
- Updates brand_master only.
- Does not modify supplier import, Shopify export, UI, products page, or recovery script.

This script adds only validated manufacturer brands approved for Milestone 9.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def canonical_key(value: str) -> str:
    s = normalize_space(value).upper()
    s = s.replace("&", " AND ")
    s = s.replace("-", " ")
    s = re.sub(r"[^A-Z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def row_exists_by_key(conn: sqlite3.Connection, key: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM brand_master WHERE canonical_key = ? LIMIT 1", (key,))
    return cur.fetchone() is not None


def approved_brands() -> list[dict]:
    return [
        {
            "brand_name": "Wiseco",
            "aliases": ["WISECO"],
            "manufacturer_website": "https://www.wiseco.com",
        },
        {
            "brand_name": "Newfren",
            "aliases": ["NEWFREN", "NewFren"],
            "manufacturer_website": "https://www.newfren.com",
        },
        {
            "brand_name": "Motorex",
            "aliases": ["MOTOREX"],
            "manufacturer_website": "https://www.motorex.com",
        },
        {
            "brand_name": "Yoshimura",
            "aliases": ["YOSHIMURA"],
            "manufacturer_website": "https://www.yoshimura-rd.com",
        },
        {
            "brand_name": "Maxxis",
            "aliases": ["MAXXIS"],
            "manufacturer_website": "https://www.maxxis.com",
        },
        {
            "brand_name": "SKF",
            "aliases": ["SKF", "S.K.F."],
            "manufacturer_website": "https://www.skf.com",
        },
        {
            "brand_name": "VHM",
            "aliases": ["VHM", "V.H.M."],
            "manufacturer_website": "https://www.vhm.nl",
        },
        {
            "brand_name": "Crosspro",
            "aliases": ["CROSSPRO", "CrossPro"],
            "manufacturer_website": "https://crosspro.pt",
        },
        {
            "brand_name": "Guts Racing",
            "aliases": ["GUTS", "GUTS RACING", "Guts"],
            "manufacturer_website": "https://www.gutsracing.com",
        },
        {
            "brand_name": "EK",
            "aliases": ["EK", "E.K.", "EK Chain"],
            "manufacturer_website": "https://www.ekchain.com",
        },
        {
            "brand_name": "GET",
            "aliases": ["GET"],
            "manufacturer_website": "https://www.getdata.it",
        },
        {
            "brand_name": "Armega",
            "aliases": ["ARMEGA"],
            "manufacturer_website": "https://www.ride100percent.com",
        },
        {
            "brand_name": "Accuri",
            "aliases": ["ACCURI", "ACCURI 2"],
            "manufacturer_website": "https://www.ride100percent.com",
        },
    ]


def apply_brand_master_updates(conn: sqlite3.Connection) -> tuple[int, int]:
    cur = conn.cursor()

    inserted = 0
    updated = 0

    for item in approved_brands():
        brand_name = item["brand_name"].strip()
        aliases = sorted({a.strip() for a in item.get("aliases", []) if a and a.strip()})
        website = item.get("manufacturer_website")
        key = canonical_key(brand_name)

        existed_before = row_exists_by_key(conn, key)

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
            ) VALUES (?, ?, ?, NULL, 'manufacturer', 'manufacturer', 'active', ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
                brand_name = excluded.brand_name,
                aliases = excluded.aliases,
                manufacturer_website = excluded.manufacturer_website,
                image_strategy = excluded.image_strategy,
                description_strategy = excluded.description_strategy,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                brand_name,
                json.dumps(aliases),
                website,
                key,
            ),
        )

        if existed_before:
            updated += 1
        else:
            inserted += 1

    conn.commit()
    return inserted, updated


def run() -> bool:
    print("\n" + "=" * 78)
    print("DPE Sprint 11 - Milestone 9: Improve Brand Master from unmatched prefixes")
    print("=" * 78)

    if not DB_FILE.exists():
        print(f"ERROR: Database not found: {DB_FILE}")
        return False

    conn = get_connection()
    try:
        inserted, updated = apply_brand_master_updates(conn)
        print(f"- Brands added: {inserted}")
        print(f"- Existing brands updated: {updated}")
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    ok = run()
    raise SystemExit(0 if ok else 1)
