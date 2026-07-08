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
import concurrent.futures as cf
import csv
import json
import re
import sqlite3
import time
from dataclasses import dataclass, replace
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
FAILURES_CSV_PATH = PROJECT_ROOT / "output" / "image_recovery_failures.csv"
SEARCH_ATTEMPT_TIMEOUT_SECONDS = 10.0
SEARCH_BUDGET_SECONDS = 30.0


FAILURE_NO_SEARCH_RESULTS = "No search results"
FAILURE_HTTP_ERROR = "HTTP error"
FAILURE_SUPPLIER_PAGE_NOT_FOUND = "Supplier page not found"
FAILURE_MULTIPLE_CANDIDATES = "Multiple candidate products"
FAILURE_NO_IMAGE_ON_PAGE = "Product page contains no image"
FAILURE_IMAGE_EXTRACTION_FAILED = "Image extraction failed"
FAILURE_IMAGE_DOWNLOAD_FAILED = "Image download failed"
FAILURE_DATABASE_UPDATE_FAILED = "Database update failed"
FAILURE_OTHER = "Other"

FAILURE_CATEGORIES = [
    FAILURE_NO_SEARCH_RESULTS,
    FAILURE_HTTP_ERROR,
    FAILURE_SUPPLIER_PAGE_NOT_FOUND,
    FAILURE_MULTIPLE_CANDIDATES,
    FAILURE_NO_IMAGE_ON_PAGE,
    FAILURE_IMAGE_EXTRACTION_FAILED,
    FAILURE_IMAGE_DOWNLOAD_FAILED,
    FAILURE_DATABASE_UPDATE_FAILED,
    FAILURE_OTHER,
]


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
    failure_counts: dict[str, int]
    failures_export_path: str
    search_success_counts: dict[str, int]
    slowest_sku: str
    slowest_strategy: str
    slowest_seconds: float
    any_timeout_occurred: bool


@dataclass(frozen=True)
class LookupResult:
    status: str  # found | ambiguous | failed
    image_url: str = ""
    failure_category: str = ""
    failure_details: str = ""
    search_strategy: str = ""
    search_result_count: int = 0
    search_elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class FailureRecord:
    sku: str
    brand: str
    supplier: str
    failure_category: str
    failure_details: str


def failed_lookup(category: str, details: str) -> LookupResult:
    return LookupResult(status="failed", failure_category=category, failure_details=details)


def ambiguous_lookup(details: str) -> LookupResult:
    return LookupResult(
        status="ambiguous",
        failure_category=FAILURE_MULTIPLE_CANDIDATES,
        failure_details=details,
    )


def log_search_attempt(
    *,
    sku: str,
    strategy: str,
    search_term: str,
    elapsed_seconds: float,
    result_count: int,
    skipped_due_to_timeout: bool,
) -> None:
    print(
        "Search attempt: "
        f"SKU={sku} | Strategy={strategy} | Term={search_term} | "
        f"Elapsed={elapsed_seconds:.2f}s | Result count={result_count} | "
        f"Timed out={'yes' if skipped_due_to_timeout else 'no'}",
        flush=True,
    )


def normalize_search_term(value: str) -> str:
    return normalize_space(value)


def result_with_runtime(result: LookupResult, *, search_strategy: str, search_result_count: int, search_elapsed_seconds: float) -> LookupResult:
    return replace(
        result,
        search_strategy=search_strategy,
        search_result_count=search_result_count,
        search_elapsed_seconds=search_elapsed_seconds,
    )


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


def build_significant_title_keywords(title: str, *, max_words: int = 6) -> str:
    stop_words = {
        "A",
        "AN",
        "AND",
        "THE",
        "FOR",
        "WITH",
        "OF",
        "TO",
        "IN",
        "ON",
        "KIT",
        "SET",
        "PACK",
        "ASSY",
        "ASSEMBLY",
        "PART",
    }

    words = re.findall(r"[A-Za-z0-9]+", normalize_space(title).upper())
    filtered = [w for w in words if len(w) >= 3 and w not in stop_words and not w.isdigit()]
    if not filtered:
        return ""
    return " ".join(filtered[:max_words])


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = normalize_space(value)
        if not key:
            continue
        lowered = key.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(key)
    return unique


def table_has_column(cur: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    for row in rows:
        if normalize_space(row[1]).lower() == normalize_space(column_name).lower():
            return True
    return False


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
        return failed_lookup(FAILURE_OTHER, "Empty search query")

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
    except (HTTPError, URLError, TimeoutError) as exc:
        return failed_lookup(FAILURE_HTTP_ERROR, f"Serco suggestion request failed: {type(exc).__name__}")
    except ValueError as exc:
        return failed_lookup(FAILURE_IMAGE_EXTRACTION_FAILED, f"Serco suggestion JSON parse failed: {exc}")
    except Exception as exc:
        return failed_lookup(FAILURE_OTHER, f"Serco suggestion request error: {type(exc).__name__}")

    if not isinstance(suggestions, list) or not suggestions:
        return LookupResult(
            status="failed",
            failure_category=FAILURE_NO_SEARCH_RESULTS,
            failure_details="Serco suggestion endpoint returned no products",
            search_result_count=0,
        )

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
        return LookupResult(
            status="failed",
            failure_category=FAILURE_NO_SEARCH_RESULTS,
            failure_details="No Serco candidate matched query",
            search_result_count=len(suggestions),
        )
    if len(candidate_ids) > 1:
        return LookupResult(
            status="ambiguous",
            failure_category=FAILURE_MULTIPLE_CANDIDATES,
            failure_details="Multiple Serco candidate IDs matched the query",
            search_result_count=len(suggestions),
        )

    try:
        row_html = post_text(
            "https://www.serco.com.au/search/express/result",
            {"id": candidate_ids[0], "quantity": "1"},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.serco.com.au/search/express",
            },
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        return failed_lookup(FAILURE_HTTP_ERROR, f"Serco product row request failed: {type(exc).__name__}")
    except Exception as exc:
        return failed_lookup(FAILURE_OTHER, f"Serco product row request error: {type(exc).__name__}")

    m = re.search(r'href="([^"]*product[^"]*)"', row_html, re.IGNORECASE)
    if not m:
        return failed_lookup(FAILURE_SUPPLIER_PAGE_NOT_FOUND, "Serco product URL not found in row response")

    product_url = normalize_space(m.group(1))
    if product_url.startswith("/"):
        product_url = urljoin("https://www.serco.com.au", product_url)

    try:
        product_html = fetch_text(product_url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return failed_lookup(FAILURE_HTTP_ERROR, f"Serco product page request failed: {type(exc).__name__}")
    except Exception as exc:
        return failed_lookup(FAILURE_OTHER, f"Serco product page request error: {type(exc).__name__}")

    # Serco product pages expose primary image via data-zoom-image.
    zooms = re.findall(r'data-zoom-image="([^"]+)"', product_html, re.IGNORECASE)
    zooms = [normalize_space(z) for z in zooms if normalize_space(z)]
    unique_zooms = sorted(set(zooms))

    if len(unique_zooms) == 1:
        return LookupResult(status="found", image_url=unique_zooms[0], search_result_count=len(suggestions))
    if len(unique_zooms) > 1:
        # Multiple gallery images; use first as primary product image.
        return LookupResult(status="found", image_url=unique_zooms[0], search_result_count=len(suggestions))

    # Fallback to og:image if present.
    og_image = extract_og_image(product_html)
    if og_image:
        return LookupResult(status="found", image_url=og_image, search_result_count=len(suggestions))

    return LookupResult(
        status="failed",
        failure_category=FAILURE_NO_IMAGE_ON_PAGE,
        failure_details="Serco product page contains no usable image markers",
        search_result_count=len(suggestions),
    )


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
        return failed_lookup(FAILURE_OTHER, "Empty search query")

    search_url = f"https://www.cassons.com.au/search?ProductSearch={quote_plus(query)}"

    try:
        html_text = fetch_text(search_url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return failed_lookup(FAILURE_HTTP_ERROR, f"Cassons search request failed: {type(exc).__name__}")
    except Exception as exc:
        return failed_lookup(FAILURE_OTHER, f"Cassons search request error: {type(exc).__name__}")

    tiles = _parse_cassons_tiles(html_text)
    if not tiles:
        return LookupResult(
            status="failed",
            failure_category=FAILURE_NO_SEARCH_RESULTS,
            failure_details="Cassons search returned no product tiles",
            search_result_count=0,
        )

    if exact_code:
        code_norm = normalize_code(exact_code)
        candidates = [t for t in tiles if normalize_code(t["code"]) == code_norm]
    else:
        # Title fallback: strict single result only.
        candidates = tiles

    unique_candidates = {(c["code"], c["link"], c["image_url"]): c for c in candidates}
    candidates = list(unique_candidates.values())

    if len(candidates) == 0:
        return LookupResult(
            status="failed",
            failure_category=FAILURE_NO_SEARCH_RESULTS,
            failure_details="No Cassons candidate matched query",
            search_result_count=len(tiles),
        )
    if len(candidates) > 1:
        return LookupResult(
            status="ambiguous",
            failure_category=FAILURE_MULTIPLE_CANDIDATES,
            failure_details="Multiple Cassons candidates matched the query",
            search_result_count=len(tiles),
        )

    candidate = candidates[0]
    if candidate["image_url"]:
        return LookupResult(status="found", image_url=candidate["image_url"], search_result_count=len(tiles))

    # Fallback: parse product page directly for primary image.
    try:
        product_html = fetch_text(candidate["link"])
    except (HTTPError, URLError, TimeoutError) as exc:
        return failed_lookup(FAILURE_HTTP_ERROR, f"Cassons product page request failed: {type(exc).__name__}")
    except Exception as exc:
        return failed_lookup(FAILURE_OTHER, f"Cassons product page request error: {type(exc).__name__}")

    zoom_m = re.search(r'ZOOM\]\((https?://[^\)]+/images/ProductImages/[^\)]+)\)', product_html, re.IGNORECASE)
    if zoom_m:
        return LookupResult(status="found", image_url=normalize_space(zoom_m.group(1)), search_result_count=len(tiles))

    direct_m = re.search(r'https?://[^"\']+/images/ProductImages/[^"\']+', product_html, re.IGNORECASE)
    if direct_m:
        return LookupResult(status="found", image_url=normalize_space(direct_m.group(0)), search_result_count=len(tiles))

    og_image = extract_og_image(product_html)
    if og_image:
        return LookupResult(status="found", image_url=og_image, search_result_count=len(tiles))

    return LookupResult(
        status="failed",
        failure_category=FAILURE_NO_IMAGE_ON_PAGE,
        failure_details="Cassons product page contains no usable image markers",
        search_result_count=len(tiles),
    )


def lookup_supplier_website_image(
    supplier_name: str,
    supplier_sku: str,
    title: str,
    *,
    brand: str = "",
    manufacturer_part_number: str = "",
    search_executor: Optional[cf.ThreadPoolExecutor] = None,
    search_budget_started_at: Optional[float] = None,
    slowest_search_tracker: Optional[dict[str, object]] = None,
) -> LookupResult:
    supplier_key = normalize_space(supplier_name).lower()

    if supplier_key == "serco":
        sku = normalize_space(supplier_sku)
        clean_no_dash = sku.replace("-", "")
        clean_no_space = re.sub(r"\s+", "", sku)
        clean_no_dash_slash = sku.replace("-", "").replace("/", "")
        upper_sku = sku.upper()
        brand_clean = normalize_space(brand)
        mpn_clean = normalize_space(manufacturer_part_number)
        title_keywords = build_significant_title_keywords(title)

        attempts: list[tuple[str, str, Optional[str]]] = [
            ("Original SKU", sku, sku),
            ("No dashes", clean_no_dash, clean_no_dash),
            ("No spaces", clean_no_space, clean_no_space),
            ("No punctuation", clean_no_dash_slash, clean_no_dash_slash),
            ("Upper-case SKU", upper_sku, upper_sku),
            ("Brand + SKU", normalize_space(f"{brand_clean} {sku}"), sku),
            ("Manufacturer part number", mpn_clean, mpn_clean),
            ("Title keywords", title_keywords, None),
            ("Brand + title keywords", normalize_space(f"{brand_clean} {title_keywords}"), None),
        ]

        best_failure: Optional[LookupResult] = None
        attempted_levels: list[str] = []
        product_started_at = search_budget_started_at or time.monotonic()

        if search_executor is None:
            search_executor = cf.ThreadPoolExecutor(max_workers=1)

        def update_slowest(strategy_name: str, elapsed_seconds: float) -> None:
            if slowest_search_tracker is None:
                return
            current = float(slowest_search_tracker.get("seconds", 0.0) or 0.0)
            if elapsed_seconds > current:
                slowest_search_tracker["sku"] = sku
                slowest_search_tracker["strategy"] = strategy_name
                slowest_search_tracker["seconds"] = elapsed_seconds

        def run_attempt(strategy_name: str, query: str, exact_code: Optional[str]) -> LookupResult:
            search_term = normalize_search_term(query)
            if not search_term:
                return failed_lookup(FAILURE_OTHER, f"Search strategy skipped: {strategy_name}")

            if time.monotonic() - product_started_at >= SEARCH_BUDGET_SECONDS:
                return LookupResult(
                    status="failed",
                    failure_category=FAILURE_OTHER,
                    failure_details="Search budget exceeded",
                    search_strategy=strategy_name,
                    search_result_count=0,
                    search_elapsed_seconds=0.0,
                )

            attempt_started_at = time.monotonic()
            timed_out = False
            result_count = 0
            future = search_executor.submit(lookup_serco_by_sku_or_title, search_term, exact_code)
            try:
                result = future.result(timeout=SEARCH_ATTEMPT_TIMEOUT_SECONDS)
                result_count = int(result.search_result_count or 0)
            except cf.TimeoutError:
                timed_out = True
                future.cancel()
                result = LookupResult(
                    status="failed",
                    failure_category=FAILURE_HTTP_ERROR,
                    failure_details=f"Search strategy timed out: {strategy_name}",
                    search_result_count=0,
                )

            elapsed_seconds = time.monotonic() - attempt_started_at
            update_slowest(strategy_name, elapsed_seconds)
            log_search_attempt(
                sku=sku,
                strategy=strategy_name,
                search_term=search_term,
                elapsed_seconds=elapsed_seconds,
                result_count=result_count,
                skipped_due_to_timeout=timed_out,
            )
            return result_with_runtime(
                result,
                search_strategy=strategy_name,
                search_result_count=result_count,
                search_elapsed_seconds=elapsed_seconds,
            )

        for strategy_name, query, exact_code in attempts:
            query_clean = normalize_space(query)
            if not query_clean:
                continue

            attempted_levels.append(strategy_name)
            if time.monotonic() - product_started_at >= SEARCH_BUDGET_SECONDS:
                best_failure = LookupResult(
                    status="failed",
                    failure_category=FAILURE_OTHER,
                    failure_details="Search budget exceeded",
                    search_strategy=strategy_name,
                    search_result_count=0,
                    search_elapsed_seconds=time.monotonic() - product_started_at,
                )
                break

            result = run_attempt(strategy_name, query_clean, exact_code)
            if result.status == "found" and result.image_url:
                return LookupResult(
                    status="found",
                    image_url=result.image_url,
                    failure_category=result.failure_category,
                    failure_details=result.failure_details,
                    search_strategy=strategy_name,
                    search_result_count=result.search_result_count,
                    search_elapsed_seconds=result.search_elapsed_seconds,
                )

            if best_failure is None:
                best_failure = result
                continue

            # Prefer non-no-search failures over plain no-search outcomes.
            if (
                normalize_failure_category(best_failure.failure_category) == FAILURE_NO_SEARCH_RESULTS
                and normalize_failure_category(result.failure_category) != FAILURE_NO_SEARCH_RESULTS
            ):
                best_failure = result

            if normalize_space(result.failure_details) == "Search budget exceeded":
                best_failure = result
                break

        if best_failure is not None:
            details = normalize_space(best_failure.failure_details)
            if normalize_failure_category(best_failure.failure_category) == FAILURE_NO_SEARCH_RESULTS:
                details = f"No results across search strategies: {', '.join(attempted_levels)}"
            if details == "Search budget exceeded":
                details = "Search budget exceeded"
            return LookupResult(
                status=best_failure.status,
                image_url=best_failure.image_url,
                failure_category=normalize_failure_category(best_failure.failure_category),
                failure_details=details,
                search_strategy=best_failure.search_strategy,
                search_result_count=best_failure.search_result_count,
                search_elapsed_seconds=best_failure.search_elapsed_seconds,
            )

        return failed_lookup(FAILURE_NO_SEARCH_RESULTS, "No valid Serco search strategy candidates were available")

    if supplier_key == "cassons":
        result = lookup_cassons_by_sku_or_title(supplier_sku, exact_code=supplier_sku)
        if result.status == "failed":
            return lookup_cassons_by_sku_or_title(title, exact_code=None)
        return result

    # No safe machine-search adapter implemented yet for this supplier website.
    return failed_lookup(FAILURE_OTHER, f"No supplier image adapter available for supplier: {supplier_name}")


def normalize_failure_category(category: str) -> str:
    normalized = normalize_space(category)
    if normalized in FAILURE_CATEGORIES:
        return normalized
    return FAILURE_OTHER


def export_failure_records(records: list[FailureRecord], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["SKU", "Brand", "Supplier", "Failure category", "Failure details"])
        for record in records:
            writer.writerow(
                [
                    record.sku,
                    record.brand,
                    record.supplier,
                    record.failure_category,
                    record.failure_details,
                ]
            )


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
        SELECT mp.id, mp.sku, mp.title, mp.brand
        FROM master_products mp
                WHERE (mp.image_url IS NULL OR TRIM(mp.image_url) = '')
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
    failure_counts = {category: 0 for category in FAILURE_CATEGORIES}
    search_success_counts = {
        "Original SKU": 0,
        "No dashes": 0,
        "No spaces": 0,
        "No punctuation": 0,
        "Upper-case SKU": 0,
        "Brand + SKU": 0,
        "Manufacturer part number": 0,
        "Title keywords": 0,
        "Brand + title keywords": 0,
    }
    failure_records: list[FailureRecord] = []
    processed_in_batch = 0
    last_supplier_processed = supplier_filter or ""
    started_at = time.time()
    any_timeout_occurred = False
    slowest_search_tracker: dict[str, object] = {"sku": "", "strategy": "", "seconds": 0.0}

    # Cache by (supplier_name, mode, query) to reduce repeated requests.
    lookup_cache: dict[tuple[str, str], LookupResult] = {}
    supplier_products_has_mpn = table_has_column(cur, "supplier_products", "manufacturer_part_number")
    search_executor = cf.ThreadPoolExecutor(max_workers=4)

    try:
        if supplier_products_has_mpn:
            supplier_lookup_sql = """
                SELECT s.supplier_name, s.priority_rank, sp.supplier_sku,
                       COALESCE(sp.manufacturer_part_number, '') AS manufacturer_part_number
                FROM supplier_products sp
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE sp.master_product_id = ?
                  AND s.is_enabled = 1
                  AND (? = '' OR LOWER(TRIM(s.supplier_name)) = LOWER(TRIM(?)))
                ORDER BY s.priority_rank ASC, s.supplier_name ASC
                """
        else:
            supplier_lookup_sql = """
                SELECT s.supplier_name, s.priority_rank, sp.supplier_sku,
                       '' AS manufacturer_part_number
                FROM supplier_products sp
                JOIN suppliers s ON s.id = sp.supplier_id
                WHERE sp.master_product_id = ?
                  AND s.is_enabled = 1
                  AND (? = '' OR LOWER(TRIM(s.supplier_name)) = LOWER(TRIM(?)))
                ORDER BY s.priority_rank ASC, s.supplier_name ASC
                """

        for product in targets:
            product_id = int(product["id"])
            product_sku = normalize_space(product["sku"])
            master_title = normalize_space(product["title"])
            product_brand = normalize_space(product["brand"]) if "brand" in product.keys() else ""
            product_search_started_at = time.monotonic()

            cur.execute(supplier_lookup_sql, (product_id, supplier_filter, supplier_filter))
            supplier_rows = cur.fetchall()

            assigned_this_product = False
            ambiguous_this_product = False
            first_failure_supplier = ""
            first_failure_category = ""
            first_failure_details = ""

            for srow in supplier_rows:
                supplier_name = normalize_space(srow["supplier_name"])
                supplier_sku = normalize_space(srow["supplier_sku"])
                supplier_mpn = normalize_space(srow["manufacturer_part_number"])
                last_supplier_processed = supplier_name or last_supplier_processed

                cache_key = (supplier_name.lower(), f"{supplier_sku}||{supplier_mpn}||{product_brand}||{master_title}")
                result = lookup_cache.get(cache_key)
                if result is None:
                    result = lookup_supplier_website_image(
                        supplier_name=supplier_name,
                        supplier_sku=supplier_sku,
                        title=master_title,
                        brand=product_brand,
                        manufacturer_part_number=supplier_mpn,
                        search_executor=search_executor,
                        search_budget_started_at=product_search_started_at,
                        slowest_search_tracker=slowest_search_tracker,
                    )
                    lookup_cache[cache_key] = result

                if normalize_space(result.failure_details).startswith("Search strategy timed out:"):
                    any_timeout_occurred = True

                if result.status == "ambiguous":
                    ambiguous_this_product = True
                    if not first_failure_category:
                        first_failure_supplier = supplier_name
                        first_failure_category = normalize_failure_category(result.failure_category or FAILURE_MULTIPLE_CANDIDATES)
                        first_failure_details = normalize_space(result.failure_details) or "Multiple candidate products matched"
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
                        strategy_key = normalize_space(result.search_strategy)
                        if strategy_key and strategy_key in search_success_counts:
                            search_success_counts[strategy_key] += 1
                    else:
                        if not first_failure_category:
                            first_failure_supplier = supplier_name
                            first_failure_category = FAILURE_DATABASE_UPDATE_FAILED
                            first_failure_details = "Image was found but database update affected 0 rows"
                    break

                if result.status == "failed" and not first_failure_category:
                    first_failure_supplier = supplier_name
                    first_failure_category = normalize_failure_category(result.failure_category)
                    first_failure_details = normalize_space(result.failure_details) or "Lookup failed without additional details"

            if not assigned_this_product:
                if ambiguous_this_product:
                    ambiguous_matches += 1
                else:
                    failed_lookups += 1

                if not first_failure_category:
                    if not supplier_rows:
                        first_failure_supplier = supplier_filter or "(none)"
                        first_failure_category = FAILURE_OTHER
                        first_failure_details = "No enabled supplier rows matched this product"
                    else:
                        first_failure_supplier = normalize_space(supplier_rows[0]["supplier_name"])
                        first_failure_category = FAILURE_OTHER
                        first_failure_details = "No image was assigned for unknown reason"

                failure_counts[first_failure_category] = failure_counts.get(first_failure_category, 0) + 1
                failure_records.append(
                    FailureRecord(
                        sku=product_sku,
                        brand=product_brand,
                        supplier=first_failure_supplier,
                        failure_category=first_failure_category,
                        failure_details=first_failure_details,
                    )
                )

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

    finally:
        search_executor.shutdown(wait=False, cancel_futures=True)

    conn.commit()

    export_failure_records(failure_records, FAILURES_CSV_PATH)

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

    recovery_rate = 0.0
    if products_scanned > 0:
        recovery_rate = images_saved / products_scanned * 100.0

    print()
    print("Batch diagnostics summary:")
    print(f"Products scanned: {products_scanned}")
    print(f"Images recovered: {images_saved}")
    print(f"Recovery rate: {recovery_rate:.2f}%")
    print()
    print("Search success:")
    print(f"- Original SKU: {search_success_counts['Original SKU']}")
    print(f"- No dashes: {search_success_counts['No dashes']}")
    print(f"- No spaces: {search_success_counts['No spaces']}")
    print(f"- No punctuation: {search_success_counts['No punctuation']}")
    print(f"- Upper-case SKU: {search_success_counts['Upper-case SKU']}")
    print(f"- Brand + SKU: {search_success_counts['Brand + SKU']}")
    print(f"- Manufacturer part number: {search_success_counts['Manufacturer part number']}")
    print(f"- Title keywords: {search_success_counts['Title keywords']}")
    print(f"- Brand + title keywords: {search_success_counts['Brand + title keywords']}")
    print()
    print("Failure summary:")
    print(f"No search results: {failure_counts.get(FAILURE_NO_SEARCH_RESULTS, 0)}")
    print(f"HTTP errors: {failure_counts.get(FAILURE_HTTP_ERROR, 0)}")
    print(f"Supplier page not found: {failure_counts.get(FAILURE_SUPPLIER_PAGE_NOT_FOUND, 0)}")
    print(f"Multiple candidate products: {failure_counts.get(FAILURE_MULTIPLE_CANDIDATES, 0)}")
    print(f"No image on page: {failure_counts.get(FAILURE_NO_IMAGE_ON_PAGE, 0)}")
    print(f"Extraction failures: {failure_counts.get(FAILURE_IMAGE_EXTRACTION_FAILED, 0)}")
    print(f"Download failures: {failure_counts.get(FAILURE_IMAGE_DOWNLOAD_FAILED, 0)}")
    print(f"Database failures: {failure_counts.get(FAILURE_DATABASE_UPDATE_FAILED, 0)}")
    print(f"Other: {failure_counts.get(FAILURE_OTHER, 0)}")
    print(f"Failure CSV: {FAILURES_CSV_PATH}")
    print(f"Slowest SKU: {slowest_search_tracker.get('sku', '')}")
    print(f"Slowest strategy: {slowest_search_tracker.get('strategy', '')}")
    print(f"Any timeout occurred: {'yes' if any_timeout_occurred else 'no'}")

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
        failure_counts=failure_counts,
        failures_export_path=str(FAILURES_CSV_PATH),
        search_success_counts=search_success_counts,
        slowest_sku=str(slowest_search_tracker.get("sku", "") or ""),
        slowest_strategy=str(slowest_search_tracker.get("strategy", "") or ""),
        slowest_seconds=float(slowest_search_tracker.get("seconds", 0.0) or 0.0),
        any_timeout_occurred=any_timeout_occurred,
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
