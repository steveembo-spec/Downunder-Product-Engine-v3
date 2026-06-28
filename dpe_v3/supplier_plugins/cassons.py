from dpe_v3.config import CASSONS_FILE
from dpe_v3.csv_utils import read_csv, money, first_field


SUPPLIER_NAME = "Cassons"


def normalise_row(row):
    sku = first_field(row, ["Part No."]).upper()

    if not sku:
        return None

    return {
        "sku": sku,
        "title": first_field(row, ["Description"]) or sku,
        "brand": first_field(row, ["Brand"]),
        "category": first_field(row, ["Category", "Product Group", "Classification"]),
        "cost": money(first_field(row, ["Cassons Standard Price", "Sell Price"])),
        "rrp": money(first_field(row, ["Special RRP", "RRP"])),
        "stock": first_field(row, ["Stock Available"]),
        "barcode": first_field(row, ["UPC Code"]),
        "supplier": SUPPLIER_NAME,
    }


def load():
    if not CASSONS_FILE.exists():
        raise FileNotFoundError(f"Missing supplier file: {CASSONS_FILE}")

    rows = read_csv(CASSONS_FILE)

    products = []
    skipped = 0

    for row in rows:
        product = normalise_row(row)

        if product:
            products.append(product)
        else:
            skipped += 1

    print(f"{SUPPLIER_NAME}: {len(products)} products loaded, {skipped} skipped")

    return products