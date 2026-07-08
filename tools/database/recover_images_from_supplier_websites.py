#!/usr/bin/env python
"""
DPE Sprint 12 - Supplier Website Image Engine

Scope and safety:
- Updates master_products.image_url only when currently blank.
- Uses supplier priority order from suppliers.priority_rank.
- Uses supplier websites only (no Google, no manufacturer websites).
- Never overwrites existing image_url.
- Skips ambiguous matches.
- Stores image URLs only; does not download images.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urljoin
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = PROJECT_ROOT / "output" / "dpe_catalogue.db"

REQUEST_DELAY_SECONDS = 0.05
BATCH_SIZE_DEFAULT = 1000
COMMIT_INTERVAL = 100


@dataclass(frozen=True)
class SupplierImageRecoveryReport:
    batch_size: int
    products_scanned: int
    already_had_images: int
    images_found_from_supplier_websites: int
    images_saved: int
    failed_lookups: int
    ambiguous_matches: int
    image_coverage_before: float
    image_coverage_after: float


@dataclass(frozen=True)
class LookupResult:
    status: str  # found | ambiguous | failed
    image_url: str = ""


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes:d}m {secs:02d}s"
    return f"{secs:d}s"


def print_progress(
    *,
    current_supplier: str,
    processed_in_batch: int,
    total_in_batch: int,
    images_found: int,
    images_saved: int,
    failed_lookups: int,
    ambiguous_matches: int,
    elapsed_seconds: float,
) -> None:
    remaining = max(0, total_in_batch - processed_in_batch)
    eta_seconds: Optional[float] = None
    if processed_in_batch > 0:
        eta_seconds = elapsed_seconds / processed_in_batch * remaining

    print()
    print(f"Progress checkpoint: {processed_in_batch}/{total_in_batch} products")
    print(f"- Supplier currently being processed: {current_supplier or '(none)'}")
    print(f"- Products processed in this batch: {processed_in_batch}")
    print(f"- Images found: {images_found}")
    print(f"- Images saved: {images_saved}")
    print(f"- Failed lookups: {failed_lookups}")
    print(f"- Ambiguous matches: {ambiguous_matches}")
    print(f"- Elapsed time: {format_duration(elapsed_seconds)}")
    print(
        "- Estimated remaining time: "
        + (format_duration(eta_seconds) if eta_seconds is not None else "n/a")
    )


def get_image_coverage_percent(cur: sqlite3.Cursor) -> float:
    cur.execute("SELECT COUNT(*) FROM master_products")
    total_products = int(cur.fetchone()[0])
    if total_products == 0:
        return 0.0

    cur.execute("SELECT COUNT(*) FROM master_products WHERE image_url IS NOT NULL AND TRIM(image_url) != ''")
    products_with_images = int(cur.fetchone()[0])
    return products_with_images / total_products * 100.0


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def fetch_text(url: str, *, timeout: int = 30, headers: Optional[dict[str, str]] = None) -> str:
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-AU,en;q=0.9",
    }
    if headers:
        req_headers.update(headers)

    req = Request(url, headers=req_headers)
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def post_text(url: str, payload: dict[str, str], *, timeout: int = 30, headers: Optional[dict[str, str]] = None) -> str:
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept-Language": "en-AU,en;q=0.9",
    }
    if headers:
        req_headers.update(headers)

    data = urlencode(payload).encode("utf-8")
    req = Request(url, data=data, headers=req_headers)
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_og_image(html_text: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            return normalize_space(m.group(1))
    return ""


def lookup_serco_by_sku_or_title(query: str, exact_code: Optional[str] = None) -> LookupResult:
    """
    Serco website adapter.

    Flow:
    1) POST /search/express/results with keywords
    2) Resolve candidate id(s)
    3) POST /search/express/result with id to get product URL
    4) Fetch product page and extract primary image URL from data-zoom-image
    """
    query = normalize_space(query)
    if not query:
        return LookupResult(status="failed")

    try:
        suggestions_raw = post_text(
            "https://www.serco.com.au/search/express/results",
            {"keywords": query},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.serco.com.au/search/express",
            },
        )
        suggestions = json.loads(suggestions_raw)
    except (HTTPError, URLError, TimeoutError, ValueError, Exception):
        return LookupResult(status="failed")

    if not isinstance(suggestions, list) or not suggestions:
        return LookupResult(status="failed")

    exact_norm = normalize_code(exact_code) if exact_code else ""

    candidate_ids: list[str] = []
    for item in suggestions:
        sid = str(item.get("id") or "").strip()
        label = str(item.get("label") or "")
        if not sid:
            continue

        if exact_norm:
            label_code = normalize_code(label.split(" - ", 1)[0])
            if label_code == exact_norm:
                candidate_ids.append(sid)
        else:
            candidate_ids.append(sid)

    # Title fallback must still be strict single candidate.
    candidate_ids = sorted(set(candidate_ids))
    if len(candidate_ids) == 0:
        return LookupResult(status="failed")
    if len(candidate_ids) > 1:
        return LookupResult(status="ambiguous")

    try:
        row_html = post_text(
            "https://www.serco.com.au/search/express/result",
            {"id": candidate_ids[0], "quantity": "1"},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.serco.com.au/search/express",
            },
        )
    except (HTTPError, URLError, TimeoutError, Exception):
        return LookupResult(status="failed")

    m = re.search(r'href="([^"]*product[^"]*)"', row_html, re.IGNORECASE)
    if not m:
        return LookupResult(status="failed")

    product_url = normalize_space(m.group(1))
    if product_url.startswith("/"):
        product_url = urljoin("https://www.serco.com.au", product_url)

    try:
        product_html = fetch_text(product_url)
    except (HTTPError, URLError, TimeoutError, Exception):
        return LookupResult(status="failed")

    # Serco product pages expose primary image via data-zoom-image.
    zooms = re.findall(r'data-zoom-image="([^"]+)"', product_html, re.IGNORECASE)
    zooms = [normalize_space(z) for z in zooms if normalize_space(z)]
    unique_zooms = sorted(set(zooms))

    if len(unique_zooms) == 1:
        return LookupResult(status="found", image_url=unique_zooms[0])
    if len(unique_zooms) > 1:
        # Multiple gallery images; use first as primary product image.
        return LookupResult(status="found", image_url=unique_zooms[0])

    # Fallback to og:image if present.
    og_image = extract_og_image(product_html)
    if og_image:
        return LookupResult(status="found", image_url=og_image)

    return LookupResult(status="failed")


def _parse_cassons_tiles(html_text: str) -> list[dict[str, str]]:
    tiles: list[dict[str, str]] = []

    # Parse each product block in the results grid.
    for block in re.findall(r'<div class="product "[\s\S]*?</span>\s*</div>\s*</div>', html_text, re.IGNORECASE):
        code_m = re.search(r'data-product-code="([^"]+)"', block, re.IGNORECASE)
        link_m = re.search(r'href\s*=\s*"(/[^"?]+)(?:\?[^"]*)?"[^>]*data-product-link=', block, re.IGNORECASE)
        img_m = re.search(r'data-src="(/Images/ProductImages/[^"]+)"', block, re.IGNORECASE)
        title_m = re.search(r'widget-productlist-title[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)

        if not code_m or not link_m:
            continue

        title = ""
        if title_m:
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", title_m.group(1))).strip()

        image_url = ""
        if img_m:
            image_url = urljoin("https://www.cassons.com.au", normalize_space(img_m.group(1)))

        tiles.append(
            {
                "code": normalize_space(code_m.group(1)),
                "link": urljoin("https://www.cassons.com.au", normalize_space(link_m.group(1))),
                "title": title,
                "image_url": image_url,
            }
        )

    return tiles


def lookup_cassons_by_sku_or_title(query: str, exact_code: Optional[str] = None) -> LookupResult:
    query = normalize_space(query)
    if not query:
        return LookupResult(status="failed")

    search_url = f"https://www.cassons.com.au/search?ProductSearch={quote_plus(query)}"

    try:
        html_text = fetch_text(search_url)
    except (HTTPError, URLError, TimeoutError, Exception):
        return LookupResult(status="failed")

    tiles = _parse_cassons_tiles(html_text)
    if not tiles:
        return LookupResult(status="failed")

    if exact_code:
        code_norm = normalize_code(exact_code)
        candidates = [t for t in tiles if normalize_code(t["code"]) == code_norm]
    else:
        # Title fallback: strict single result only.
        candidates = tiles

    unique_candidates = {(c["code"], c["link"], c["image_url"]): c for c in candidates}
    candidates = list(unique_candidates.values())

    if len(candidates) == 0:
        return LookupResult(status="failed")
    if len(candidates) > 1:
        return LookupResult(status="ambiguous")

    candidate = candidates[0]
    if candidate["image_url"]:
        return LookupResult(status="found", image_url=candidate["image_url"])

    # Fallback: parse product page directly for primary image.
    try:
        product_html = fetch_text(candidate["link"])
    except (HTTPError, URLError, TimeoutError, Exception):
        return LookupResult(status="failed")

    zoom_m = re.search(r'ZOOM\]\((https?://[^\)]+/images/ProductImages/[^\)]+)\)', product_html, re.IGNORECASE)
    if zoom_m:
        return LookupResult(status="found", image_url=normalize_space(zoom_m.group(1)))

    direct_m = re.search(r'https?://[^"\']+/images/ProductImages/[^"\']+', product_html, re.IGNORECASE)
    if direct_m:
        return LookupResult(status="found", image_url=normalize_space(direct_m.group(0)))

    og_image = extract_og_image(product_html)
    if og_image:
        return LookupResult(status="found", image_url=og_image)

    return LookupResult(status="failed")


def lookup_supplier_website_image(supplier_name: str, supplier_sku: str, title: str) -> LookupResult:
    supplier_key = normalize_space(supplier_name).lower()

    if supplier_key == "serco":
        result = lookup_serco_by_sku_or_title(supplier_sku, exact_code=supplier_sku)
        if result.status == "failed":
            return lookup_serco_by_sku_or_title(title, exact_code=None)
        return result

    if supplier_key == "cassons":
        result = lookup_cassons_by_sku_or_title(supplier_sku, exact_code=supplier_sku)
        if result.status == "failed":
            return lookup_cassons_by_sku_or_title(title, exact_code=None)
        return result

    # No safe machine-search adapter implemented yet for this supplier website.
    return LookupResult(status="failed")


def recover_images_from_supplier_websites(
    conn: sqlite3.Connection,
    *,
    batch_size: int = BATCH_SIZE_DEFAULT,
    limit: Optional[int] = None,
    supplier: Optional[str] = None,
) -> SupplierImageRecoveryReport:
    cur = conn.cursor()

    effective_batch_size = int(batch_size) if batch_size and batch_size > 0 else BATCH_SIZE_DEFAULT
    if limit is not None and limit > 0:
        effective_batch_size = min(effective_batch_size, int(limit))

    already_had_images = 0
    image_coverage_before = get_image_coverage_percent(cur)

    target_sql = """
        SELECT mp.id, mp.sku, mp.title
        FROM master_products mp
        WHERE mp.image_url IS NULL OR TRIM(mp.image_url) = ''
    """
    params: list[object] = []
    supplier_filter = normalize_space(supplier)
    if supplier_filter:
        target_sql += """
          AND EXISTS (
              SELECT 1
              FROM supplier_products sp
              JOIN suppliers s ON s.id = sp.supplier_id
              WHERE sp.master_product_id = mp.id
                AND s.is_enabled = 1
                AND LOWER(TRIM(s.supplier_name)) = LOWER(TRIM(?))
          )
        """
        params.append(supplier_filter)

    target_sql += " ORDER BY mp.id LIMIT ?"
    params.append(effective_batch_size)

    cur.execute(target_sql, tuple(params))
    targets = cur.fetchall()

    products_scanned = len(targets)

    images_found_from_supplier_websites = 0
    images_saved = 0
    failed_lookups = 0
    ambiguous_matches = 0
    processed_in_batch = 0
    last_supplier_processed = supplier_filter or ""
    started_at = time.time()

    # Cache by (supplier_name, mode, query) to reduce repeated requests.
    lookup_cache: dict[tuple[str, str], LookupResult] = {}

    for product in targets:
        product_id = int(product["id"])
        master_title = normalize_space(product["title"])

        cur.execute(
            """
            SELECT s.supplier_name, s.priority_rank, sp.supplier_sku
            FROM supplier_products sp
            JOIN suppliers s ON s.id = sp.supplier_id
            WHERE sp.master_product_id = ?
              AND s.is_enabled = 1
                            AND (? = '' OR LOWER(TRIM(s.supplier_name)) = LOWER(TRIM(?)))
            ORDER BY s.priority_rank ASC, s.supplier_name ASC
            """,
                        (product_id, supplier_filter, supplier_filter),
        )
        supplier_rows = cur.fetchall()

        assigned_this_product = False
        ambiguous_this_product = False

        for srow in supplier_rows:
            supplier_name = normalize_space(srow["supplier_name"])
            supplier_sku = normalize_space(srow["supplier_sku"])
            last_supplier_processed = supplier_name or last_supplier_processed

            cache_key = (supplier_name.lower(), f"{supplier_sku}||{master_title}")
            result = lookup_cache.get(cache_key)
            if result is None:
                result = lookup_supplier_website_image(
                    supplier_name=supplier_name,
                    supplier_sku=supplier_sku,
                    title=master_title,
                )
                lookup_cache[cache_key] = result

            if result.status == "ambiguous":
                ambiguous_this_product = True
                # Continue to next supplier in priority order.
                continue

            if result.status == "found" and result.image_url:
                images_found_from_supplier_websites += 1
                cur.execute(
                    """
                    UPDATE master_products
                    SET image_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                      AND (image_url IS NULL OR TRIM(image_url) = '')
                    """,
                    (result.image_url, product_id),
                )
                if cur.rowcount:
                    images_saved += 1
                    assigned_this_product = True
                break

        if not assigned_this_product:
            if ambiguous_this_product:
                ambiguous_matches += 1
            else:
                failed_lookups += 1

        processed_in_batch += 1

        if processed_in_batch % COMMIT_INTERVAL == 0:
            conn.commit()
            print_progress(
                current_supplier=last_supplier_processed,
                processed_in_batch=processed_in_batch,
                total_in_batch=products_scanned,
                images_found=images_found_from_supplier_websites,
                images_saved=images_saved,
                failed_lookups=failed_lookups,
                ambiguous_matches=ambiguous_matches,
                elapsed_seconds=time.time() - started_at,
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    conn.commit()

    if processed_in_batch and processed_in_batch % COMMIT_INTERVAL != 0:
        print_progress(
            current_supplier=last_supplier_processed,
            processed_in_batch=processed_in_batch,
            total_in_batch=products_scanned,
            images_found=images_found_from_supplier_websites,
            images_saved=images_saved,
            failed_lookups=failed_lookups,
            ambiguous_matches=ambiguous_matches,
            elapsed_seconds=time.time() - started_at,
        )

    image_coverage_after = get_image_coverage_percent(cur)

    return SupplierImageRecoveryReport(
        batch_size=effective_batch_size,
        products_scanned=products_scanned,
        already_had_images=already_had_images,
        images_found_from_supplier_websites=images_found_from_supplier_websites,
        images_saved=images_saved,
        failed_lookups=failed_lookups,
        ambiguous_matches=ambiguous_matches,
        image_coverage_before=image_coverage_before,
        image_coverage_after=image_coverage_after,
    )


def run(*, batch_size: int = BATCH_SIZE_DEFAULT, limit: Optional[int] = None, supplier: Optional[str] = None) -> bool:
    print()
    print("=" * 78)
    print("DPE Sprint 12 - Supplier Website Image Engine")
    print("=" * 78)

    if not DB_FILE.exists():
        print(f"ERROR: Database not found: {DB_FILE}")
        return False

    conn = get_connection()
    try:
        report = recover_images_from_supplier_websites(
            conn,
            batch_size=batch_size,
            limit=limit,
            supplier=supplier,
        )

        print()
        print("Batch report:")
        print(f"- Batch size: {report.batch_size}")
        print(f"- Products scanned: {report.products_scanned}")
        print(f"- Already had images: {report.already_had_images}")
        print(f"- Images found from supplier websites: {report.images_found_from_supplier_websites}")
        print(f"- Images saved: {report.images_saved}")
        print(f"- Failed lookups: {report.failed_lookups}")
        print(f"- Ambiguous matches: {report.ambiguous_matches}")
        print(f"- Image coverage before: {report.image_coverage_before:.2f}%")
        print(f"- Image coverage after: {report.image_coverage_after:.2f}%")

        if supplier:
            print(f"- Supplier filter: {normalize_space(supplier)}")
        if limit is not None and limit > 0:
            print(f"- Run limit applied: {int(limit)} blank-image products")

        return True
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE_DEFAULT,
        help="Number of blank-image master products to process in this batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on blank-image master products processed.",
    )
    parser.add_argument(
        "--supplier",
        type=str,
        default=None,
        help="Optional supplier filter for target selection and lookups.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ok = run(batch_size=args.batch_size, limit=args.limit, supplier=args.supplier)
    raise SystemExit(0 if ok else 1)
