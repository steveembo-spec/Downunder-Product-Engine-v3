from __future__ import annotations

import re
import string
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Field lists
# ---------------------------------------------------------------------------

REQUIRED_MASTER_FIELDS: list[str] = ["sku", "title", "cost", "rrp"]

OPTIONAL_MASTER_FIELDS: list[str] = [
    "brand",
    "category",
    "stock",
    "description",
    "barcode",
    "image_url",
    "supplier_sku",
    "manufacturer_part_number",
    "weight",
]

# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

HEADER_ALIASES: dict[str, list[str]] = {
    "sku": [
        "sku",
        "item id",
        "item code",
        "part number",
        "part no",
        "product code",
        "product id",
        "code",
        "stock code",
        "supplier code",
        "vendor sku",
        "supplier sku",
    ],
    "title": [
        "title",
        "name",
        "product name",
        "product title",
        "description",
        "item description",
        "product description",
        "desc",
    ],
    "cost": [
        "cost",
        "unit cost",
        "buy price",
        "buying price",
        "wholesale",
        "wholesale price",
        "wsp",
        "dealer price",
        "trade price",
        "net price",
        "nett price",
    ],
    "rrp": [
        "rrp",
        "retail",
        "retail price",
        "recommended retail",
        "recommended retail price",
        "sell price",
        "selling price",
        "price",
        "list price",
    ],
    "brand": [
        "brand",
        "manufacturer",
        "make",
        "vendor",
        "supplier brand",
    ],
    "category": [
        "category",
        "product category",
        "group",
        "product group",
        "department",
        "class",
        "type",
    ],
    "stock": [
        "stock",
        "qty",
        "quantity",
        "quantity available",
        "available",
        "availability",
        "on hand",
        "stock on hand",
        "soh",
    ],
    "description": [
        "long description",
        "web description",
        "shopify description",
        "body html",
        "body",
        "details",
    ],
    "barcode": [
        "barcode",
        "ean",
        "ean13",
        "upc",
        "gtin",
    ],
    "image_url": [
        "image",
        "image url",
        "image link",
        "photo",
        "photo url",
        "picture",
        "picture url",
        "main image",
    ],
    "supplier_sku": [
        "supplier sku",
        "supplier part number",
        "supplier product code",
        "vendor part number",
        "vendor sku",
    ],
    "manufacturer_part_number": [
        "manufacturer part number",
        "manufacturer part no",
        "mpn",
        "mfr part number",
        "mfr part no",
    ],
    "weight": [
        "weight",
        "product weight",
        "shipping weight",
        "kg",
        "grams",
    ],
}

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_MATCHED = "MATCHED"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_MISSING = "MISSING"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HeaderMatch:
    master_field: str
    detected_header: str | None
    confidence: int
    status: str
    reason: str

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_STRIP_PATTERN = re.compile(r"[\s_\-" + re.escape(string.punctuation) + r"]+")


def normalise_header(value: str) -> str:
    """Lowercase, strip spaces/underscores/hyphens/punctuation."""
    return _STRIP_PATTERN.sub("", value.lower())


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _score_header(raw_header: str, aliases: list[str]) -> int:
    """Return the best confidence score for a raw header against a set of aliases."""
    norm_header = normalise_header(raw_header)
    best = 0

    for alias in aliases:
        norm_alias = normalise_header(alias)

        # Exact match
        if norm_header == norm_alias:
            return 100

        # Strong prefix / suffix match
        if norm_header.startswith(norm_alias) or norm_header.endswith(norm_alias):
            best = max(best, 85)
        elif norm_alias.startswith(norm_header) or norm_alias.endswith(norm_header):
            best = max(best, 85)

        # Alias contained in header
        elif norm_alias in norm_header:
            best = max(best, 75)

        # Header contained in alias
        elif norm_header in norm_alias:
            best = max(best, 65)

    return best


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_header_mapping(headers: list[str]) -> dict[str, HeaderMatch]:
    """
    Map Master Product fields to the best matching supplier CSV/Excel header.

    Returns a dict keyed by master field name, values are HeaderMatch instances.
    Each supplier header is assigned to at most one master field (highest score wins).
    """
    all_fields = REQUIRED_MASTER_FIELDS + OPTIONAL_MASTER_FIELDS

    # Step 1: Score every (field, header) pair.
    # scores[field][header] = confidence
    scores: dict[str, dict[str, int]] = {}
    for field in all_fields:
        aliases = HEADER_ALIASES.get(field, [])
        scores[field] = {}
        for header in headers:
            scores[field][header] = _score_header(header, aliases)

    # Step 2: Greedy assignment – highest score wins, each header used once.
    # Build a flat list of (confidence, field, header) sorted descending.
    candidates: list[tuple[int, str, str]] = []
    for field in all_fields:
        for header, conf in scores[field].items():
            if conf > 0:
                candidates.append((conf, field, header))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))

    assigned_headers: set[str] = set()
    # best_for_field[field] = (confidence, header)
    best_for_field: dict[str, tuple[int, str]] = {}
    # Track tied headers per field to detect AMBIGUOUS
    tied_for_field: dict[str, list[str]] = {}

    for conf, field, header in candidates:
        if header in assigned_headers:
            continue
        if field not in best_for_field:
            best_for_field[field] = (conf, header)
            tied_for_field[field] = [header]
            assigned_headers.add(header)
        else:
            existing_conf, _ = best_for_field[field]
            if conf == existing_conf:
                # Tie – record but don't reassign header (header not yet assigned)
                tied_for_field[field].append(header)
                assigned_headers.add(header)

    # Step 3: Build result dict.
    result: dict[str, HeaderMatch] = {}

    for field in all_fields:
        if field not in best_for_field:
            result[field] = HeaderMatch(
                master_field=field,
                detected_header=None,
                confidence=0,
                status=STATUS_MISSING,
                reason="No matching header found",
            )
        else:
            conf, header = best_for_field[field]
            ties = tied_for_field.get(field, [])
            if len(ties) > 1:
                result[field] = HeaderMatch(
                    master_field=field,
                    detected_header=header,
                    confidence=conf,
                    status=STATUS_AMBIGUOUS,
                    reason=f"Multiple headers tied at confidence {conf}: {ties}",
                )
            else:
                result[field] = HeaderMatch(
                    master_field=field,
                    detected_header=header,
                    confidence=conf,
                    status=STATUS_MATCHED,
                    reason=f"Matched via alias at confidence {conf}",
                )

    return result


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def required_fields_missing(mapping: dict[str, HeaderMatch]) -> list[str]:
    """Return a list of required master fields that were not matched."""
    return [
        field
        for field in REQUIRED_MASTER_FIELDS
        if mapping.get(field, HeaderMatch(field, None, 0, STATUS_MISSING, "")).status == STATUS_MISSING
    ]


def mapping_needs_review(
    mapping: dict[str, HeaderMatch],
    confidence_threshold: int = 80,
) -> bool:
    """
    Return True if any required field is MISSING, AMBIGUOUS, or below the
    confidence threshold.
    """
    for field in REQUIRED_MASTER_FIELDS:
        match = mapping.get(field)
        if match is None:
            return True
        if match.status in (STATUS_MISSING, STATUS_AMBIGUOUS):
            return True
        if match.confidence < confidence_threshold:
            return True
    return False
