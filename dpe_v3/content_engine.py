from dpe_v3.config import LEGACY_DESCRIPTION_FILES
from dpe_v3.csv_utils import read_csv, first_field


def load_legacy_descriptions():
    descriptions = {}

    for file in LEGACY_DESCRIPTION_FILES:
        if not file.exists():
            print(f"WARNING: legacy description file missing: {file}")
            continue

        rows = read_csv(file)

        for row in rows:
            sku = first_field(row, [
                "Variant SKU",
                "variant sku",
                "SKU",
                "sku",
            ]).upper()

            body = first_field(row, [
                "Body (HTML)",
                "body html",
                "Body",
                "body",
                "Description",
                "description",
            ])

            if sku and body and sku not in descriptions:
                descriptions[sku] = body

    return descriptions


def default_description(product):
    title = product.get("title", "")
    brand = product.get("brand", "")
    sku = product.get("sku", "")

    html = f"<p>{title}</p>"

    if brand:
        html += f"<p><strong>Brand:</strong> {brand}</p>"

    html += f"<p><strong>SKU:</strong> {sku}</p>"

    return html


def attach_descriptions(products, descriptions):
    matched = 0

    for product in products:
        sku = product["sku"]
        body = descriptions.get(sku, "")

        if body:
            matched += 1
        else:
            body = default_description(product)

        product["body_html"] = body

    print(f"Description matches: {matched}")
    print(f"Default descriptions used: {len(products) - matched}")

    return products