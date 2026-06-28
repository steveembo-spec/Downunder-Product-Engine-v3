import csv

from dpe_v3.config import A1_FILE
from dpe_v3.csv_utils import clean, money


SUPPLIER_NAME = "A1"


def normalise_row(row):
    if len(row) < 5:
        return None

    sku = clean(row[0]).upper()

    if not sku:
        return None

    return {
        "sku": sku,
        "title": clean(row[1]) or sku,
        "brand": "",
        "category": "",
        "cost": money(row[3]),
        "rrp": money(row[4]),
        "stock": clean(row[2]),
        "barcode": "",
        "supplier": SUPPLIER_NAME,
    }


def load():
    if not A1_FILE.exists():
        raise FileNotFoundError(f"Missing supplier file: {A1_FILE}")

    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
    last_error = None

    for encoding in encodings:
        try:
            products = []

            with open(A1_FILE, newline="", encoding=encoding) as f:
                reader = csv.reader(f)

                for row in reader:
                    product = normalise_row(row)

                    if product:
                        products.append(product)

            print(f"{SUPPLIER_NAME}: {len(products)} products loaded ({encoding})")
            return products

        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise last_error