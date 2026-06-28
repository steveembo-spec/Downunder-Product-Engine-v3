import json
from datetime import datetime
from pathlib import Path

from dpe_v3.config import PROJECT_ROOT
from dpe_v3.suppliers import load_all_suppliers
from dpe_v3.merge_engine import merge_duplicate_skus
from dpe_v3.pricing_engine import apply_business_rules
from dpe_v3.image_engine import load_image_library, attach_images
from dpe_v3.content_engine import load_legacy_descriptions, attach_descriptions
from dpe_v3.shopify_builder import build_shopify_csv


def image_library_record_count(image_library):
    if isinstance(image_library, dict):
        return int(image_library.get("records", 0) or 0)

    try:
        return len(image_library)
    except TypeError:
        return 0


def write_build_report(stats):
    report_file = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"

    lines = [
        "=" * 60,
        "DOWNUNDER PRODUCT ENGINE v3",
        "BUILD REPORT",
        "=" * 60,
        "",
        f"Run date: {stats['run_date']}",
        f"Status: {stats['status']}",
        "",
        "-" * 60,
        "SUPPLIERS",
        "-" * 60,
        f"Supplier rows loaded: {stats['supplier_rows']}",
        f"Unique SKUs exported: {stats['unique_skus']}",
        f"Duplicate SKUs merged: {stats['duplicates_merged']}",
        f"Suppliers active: {', '.join(stats['suppliers'])}",
        "",
        "-" * 60,
        "IMAGES",
        "-" * 60,
        f"Image library records: {stats['image_library']}",
        f"Images matched: {stats['images_matched']}",
        f"Images missing: {stats['images_missing']}",
        "",
        "-" * 60,
        "DESCRIPTIONS",
        "-" * 60,
        f"Legacy descriptions loaded: {stats['legacy_descriptions']}",
        f"Descriptions matched: {stats['descriptions_matched']}",
        f"Default descriptions used: {stats['default_descriptions']}",
        "",
        "-" * 60,
        "PRICING",
        "-" * 60,
        f"Products missing cost: {stats['missing_cost']}",
        f"Products missing RRP: {stats['missing_rrp']}",
        "",
        "-" * 60,
        "OUTPUT",
        "-" * 60,
        f"Shopify CSV: {stats['output_file']}",
        f"Build manifest: {stats['manifest_file']}",
        "",
        "=" * 60,
    ]

    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Build report created: {report_file}")


def write_build_manifest(stats):
    manifest_file = PROJECT_ROOT / "output" / "build_manifest.json"
    history_dir = PROJECT_ROOT / "output" / "build_history"
    history_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "status": stats["status"],
        "run_date": stats["run_date"],
        "build_time_iso": stats["build_time_iso"],
        "supplier_rows": stats["supplier_rows"],
        "products": stats["unique_skus"],
        "duplicates_merged": stats["duplicates_merged"],
        "suppliers": stats["suppliers"],
        "supplier_count": len(stats["suppliers"]),
        "image_library_records": stats["image_library"],
        "images": stats["images_matched"],
        "missing_images": stats["images_missing"],
        "legacy_descriptions": stats["legacy_descriptions"],
        "descriptions": stats["descriptions_matched"],
        "default_descriptions": stats["default_descriptions"],
        "missing_cost": stats["missing_cost"],
        "missing_rrp": stats["missing_rrp"],
        "shopify_file": stats["output_file"],
    }

    manifest_file.write_text(
        json.dumps(manifest, indent=4),
        encoding="utf-8",
    )

    history_file = history_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    history_file.write_text(
        json.dumps(manifest, indent=4),
        encoding="utf-8",
    )

    stats["manifest_file"] = str(manifest_file)

    print(f"Build manifest created: {manifest_file}")
    print(f"Build history saved: {history_file}")


def main():
    print("=" * 60)
    print("DPE v3 - CLEAN PRODUCTION PIPELINE")
    print("=" * 60)

    now = datetime.now()

    stats = {
        "run_date": now.strftime("%d/%m/%Y %H:%M:%S"),
        "build_time_iso": now.isoformat(),
        "status": "SUCCESS",
        "manifest_file": "",
    }

    products = load_all_suppliers()
    stats["supplier_rows"] = len(products)
    stats["suppliers"] = sorted(
        {p.get("supplier", "") for p in products if p.get("supplier")}
    )

    print(f"Supplier rows loaded: {len(products)}")

    merged = merge_duplicate_skus(products)
    stats["unique_skus"] = len(merged)
    stats["duplicates_merged"] = len(products) - len(merged)

    print(f"Unique SKUs merged: {len(merged)}")

    ruled = apply_business_rules(merged)
    print("Business rules applied")

    stats["missing_cost"] = sum(1 for p in ruled if not p.get("cost"))
    stats["missing_rrp"] = sum(1 for p in ruled if not p.get("rrp"))

    image_library = load_image_library()
    stats["image_library"] = image_library_record_count(image_library)

    with_images = attach_images(ruled, image_library)
    stats["images_matched"] = sum(1 for p in with_images if p.get("image_url"))
    stats["images_missing"] = len(with_images) - stats["images_matched"]

    print("Images attached")

    descriptions = load_legacy_descriptions()
    stats["legacy_descriptions"] = len(descriptions)

    print(f"Legacy descriptions loaded: {len(descriptions)}")

    with_content = attach_descriptions(with_images, descriptions)
    stats["descriptions_matched"] = sum(
        1 for p in with_content if p.get("sku") in descriptions
    )
    stats["default_descriptions"] = len(with_content) - stats["descriptions_matched"]

    print("Descriptions attached")

    output_file = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
    build_shopify_csv(with_content, output_file)

    stats["output_file"] = str(output_file)

    write_build_manifest(stats)
    write_build_report(stats)

    print("=" * 60)
    print("DPE v3 COMPLETE")
    print(f"Shopify CSV created: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()