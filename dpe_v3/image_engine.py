import csv
import re
from pathlib import Path

from dpe_v3.config import IMAGE_LIBRARY_FILE, PROJECT_ROOT
from dpe_v3.csv_utils import read_csv, first_field


MISSING_IMAGE_REPORT = PROJECT_ROOT / "output" / "missing_images_report.csv"


def normalise_sku(value):
    value = str(value or "").upper().strip()
    value = re.sub(r"[^A-Z0-9]", "", value)
    return value


def normalise_loose(value):
    value = str(value or "").upper().strip()
    value = value.replace("\\", "/")
    value = Path(value).stem
    value = re.sub(r"[^A-Z0-9]", "", value)
    return value


def _first_present(row, fields):
    return first_field(row, fields).strip()


def load_image_library():
    if not IMAGE_LIBRARY_FILE.exists():
        print(f"WARNING: image library missing: {IMAGE_LIBRARY_FILE}")
        return {
            "exact": {},
            "normalised": {},
            "loose": {},
            "records": 0,
        }

    rows = read_csv(IMAGE_LIBRARY_FILE)

    exact = {}
    normalised = {}
    loose = {}

    for row in rows:
        sku = _first_present(row, [
            "sku",
            "SKU",
            "Variant SKU",
            "variant sku",
            "sku_guess",
            "SKU Guess",
            "Sku",
        ]).upper()

        image_url = _first_present(row, [
            "image_url",
            "Image URL",
            "Image Src",
            "image src",
            "src",
            "Src",
            "image",
            "Image",
            "url",
            "URL",
        ])

        filename = _first_present(row, [
            "filename",
            "Filename",
            "file",
            "File",
            "path",
            "Path",
            "image_path",
            "Image Path",
        ])

        if not image_url:
            continue

        if sku:
            exact[sku] = image_url

            normalised_key = normalise_sku(sku)
            if normalised_key:
                normalised.setdefault(normalised_key, image_url)

        if filename:
            loose_key = normalise_loose(filename)
            if loose_key:
                loose.setdefault(loose_key, image_url)

    print(f"Image library loaded: {len(rows)}")

    return {
        "exact": exact,
        "normalised": normalised,
        "loose": loose,
        "records": len(rows),
    }


def find_image_for_product(product, image_library):
    sku = str(product.get("sku", "")).upper().strip()
    title = str(product.get("title", "")).upper().strip()

    if not sku:
        return "", "missing_sku"

    exact = image_library.get("exact", {})
    normalised = image_library.get("normalised", {})
    loose = image_library.get("loose", {})

    if sku in exact:
        return exact[sku], "exact_sku"

    normalised_sku = normalise_sku(sku)

    if normalised_sku in normalised:
        return normalised[normalised_sku], "normalised_sku"

    if normalised_sku in loose:
        return loose[normalised_sku], "filename_sku"

    title_key = normalise_loose(title)

    if title_key in loose:
        return loose[title_key], "filename_title"

    return "", "not_found"


def attach_images(products, image_library):
    matched = 0
    missing_rows = []
    match_methods = {}

    for product in products:
        image_url, method = find_image_for_product(product, image_library)

        product["image_url"] = image_url
        product["image_match_method"] = method

        match_methods[method] = match_methods.get(method, 0) + 1

        if image_url:
            matched += 1
        else:
            missing_rows.append({
                "sku": product.get("sku", ""),
                "title": product.get("title", ""),
                "brand": product.get("brand", ""),
                "supplier": product.get("supplier", ""),
                "reason": method,
            })

    write_missing_image_report(missing_rows)

    print(f"Image matches: {matched}")
    print(f"Missing images: {len(products) - matched}")

    for method, count in sorted(match_methods.items()):
        print(f"Image match method - {method}: {count}")

    return products


def write_missing_image_report(rows):
    MISSING_IMAGE_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with open(MISSING_IMAGE_REPORT, "w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "sku",
            "title",
            "brand",
            "supplier",
            "reason",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)