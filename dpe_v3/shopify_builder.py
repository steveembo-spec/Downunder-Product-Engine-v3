import csv
import re
from pathlib import Path

from dpe_v3.config import DEFAULT_VENDOR, SHOPIFY_STATUS


SHOPIFY_COLUMNS = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Product Category",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Variant SKU",
    "Variant Grams",
    "Variant Inventory Tracker",
    "Variant Inventory Qty",
    "Variant Inventory Policy",
    "Variant Fulfillment Service",
    "Variant Price",
    "Variant Compare At Price",
    "Cost per item",
    "Variant Requires Shipping",
    "Variant Taxable",
    "Variant Barcode",
    "Image Src",
    "Image Position",
    "Status",
]


def make_handle(title, sku):
    base = title or sku
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = base.strip("-")

    if not base:
        base = sku.lower()

    return base


def build_tags(product):
    tags = []

    if product.get("brand"):
        tags.append(product["brand"])

    if product.get("category"):
        tags.append(product["category"])

    if product.get("supplier"):
        tags.append(f"Supplier: {product['supplier']}")

    return ", ".join(tags)


def build_shopify_row(product):
    title = product.get("title", "")
    sku = product.get("sku", "")

    vendor = product.get("brand") or DEFAULT_VENDOR

    cost = product.get("cost", 0) or 0
    rrp = product.get("rrp", 0) or 0
    sell_price = product.get("shopify_price", 0) or 0

    return {
        "Handle": make_handle(title, sku),
        "Title": title,
        "Body (HTML)": product.get("body_html", ""),
        "Vendor": vendor,
        "Product Category": "",
        "Type": product.get("category", ""),
        "Tags": build_tags(product),
        "Published": "FALSE",
        "Option1 Name": "Title",
        "Option1 Value": "Default Title",
        "Variant SKU": sku,
        "Variant Grams": "0",
        "Variant Inventory Tracker": "shopify",
        "Variant Inventory Qty": product.get("inventory_quantity", 0),
        "Variant Inventory Policy": "deny",
        "Variant Fulfillment Service": "manual",
        "Variant Price": f"{sell_price:.2f}",
        "Variant Compare At Price": "",
        "Cost per item": f"{cost:.2f}" if cost else "",
        "Variant Requires Shipping": "TRUE",
        "Variant Taxable": "TRUE",
        "Variant Barcode": product.get("barcode", ""),
        "Image Src": product.get("image_url", ""),
        "Image Position": "1" if product.get("image_url") else "",
        "Status": SHOPIFY_STATUS,
    }


def build_shopify_csv(products, output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    rows = [build_shopify_row(product) for product in products]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Rows written: {len(rows)}")