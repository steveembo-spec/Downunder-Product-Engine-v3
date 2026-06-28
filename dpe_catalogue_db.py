import csv
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"

SUPPLIER_CATALOGUE_FILE = OUTPUT_DIR / "dpe_supplier_catalogue.csv"
SHOPIFY_READY_FILE = OUTPUT_DIR / "dpe_v3_shopify_ready.csv"
DB_FILE = OUTPUT_DIR / "dpe_catalogue.db"


def first_value(row, possible_names):
    for name in possible_names:
        if name in row and row[name] not in (None, ""):
            return str(row[name]).strip()
    return ""


def normalise_money(value):
    if value is None:
        return ""
    text = str(value).replace("$", "").replace(",", "").strip()
    return text


def get_source_file():
    if SUPPLIER_CATALOGUE_FILE.exists():
        return SUPPLIER_CATALOGUE_FILE

    if SHOPIFY_READY_FILE.exists():
        return SHOPIFY_READY_FILE

    raise FileNotFoundError(
        "No catalogue CSV found. Run the Build Centre first so output files exist."
    )


def create_schema(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS products")

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            title TEXT,
            brand TEXT,
            supplier TEXT,
            cost TEXT,
            rrp TEXT,
            stock TEXT,
            image_url TEXT,
            description TEXT,
            raw_json TEXT
        )
    """)

    cur.execute("CREATE INDEX idx_products_sku ON products (sku)")
    cur.execute("CREATE INDEX idx_products_brand ON products (brand)")
    cur.execute("CREATE INDEX idx_products_supplier ON products (supplier)")
    cur.execute("CREATE INDEX idx_products_title ON products (title)")

    conn.commit()


def build_database():
    source_file = get_source_file()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    create_schema(conn)

    inserted = 0

    with open(source_file, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)

        for row in reader:
            sku = first_value(row, ["SKU", "sku", "Variant SKU", "Supplier SKU", "Part Number", "part_number"])
            title = first_value(row, ["Title", "title", "Product Title", "Name", "name", "Description", "description"])
            brand = first_value(row, ["Brand", "brand", "Vendor", "vendor", "Manufacturer", "manufacturer"])
            supplier = first_value(row, ["Supplier", "supplier", "Source", "source"])
            cost = normalise_money(first_value(row, ["Cost", "cost", "WSP", "wsp", "Wholesale", "wholesale", "Variant Cost"]))
            rrp = normalise_money(first_value(row, ["RRP", "rrp", "Price", "price", "Variant Price", "Sell Price"]))
            stock = first_value(row, ["Stock", "stock", "Qty", "Quantity", "Available", "availability"])
            image_url = first_value(row, ["Image Src", "Image", "image", "Image URL", "image_url", "Variant Image"])
            description = first_value(row, ["Body (HTML)", "Description", "description", "Body", "Product Description"])

            conn.execute("""
                INSERT INTO products (
                    sku, title, brand, supplier, cost, rrp, stock, image_url, description, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sku,
                title,
                brand,
                supplier,
                cost,
                rrp,
                stock,
                image_url,
                description,
                str(row),
            ))

            inserted += 1

            if inserted % 5000 == 0:
                conn.commit()
                print(f"Inserted {inserted:,} products...")

    conn.commit()
    conn.close()

    print("")
    print("============================================================")
    print("DPE SQLITE CATALOGUE BUILD COMPLETE")
    print("============================================================")
    print(f"Source file: {source_file}")
    print(f"Database:    {DB_FILE}")
    print(f"Rows:        {inserted:,}")
    print("")


def search_catalogue(query, limit=50):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    q = f"%{query.strip()}%"

    rows = conn.execute("""
        SELECT sku, title, brand, supplier, cost, rrp, stock,
               CASE WHEN image_url != '' THEN 'Yes' ELSE 'Missing' END AS image,
               CASE WHEN description != '' THEN 'Yes' ELSE 'Missing' END AS description
        FROM products
        WHERE sku LIKE ?
           OR title LIKE ?
           OR brand LIKE ?
           OR supplier LIKE ?
        ORDER BY
            CASE
                WHEN sku = ? THEN 0
                WHEN sku LIKE ? THEN 1
                WHEN title LIKE ? THEN 2
                ELSE 3
            END,
            title
        LIMIT ?
    """, (
        q, q, q, q,
        query.strip(),
        f"{query.strip()}%",
        f"{query.strip()}%",
        limit,
    )).fetchall()

    conn.close()
    return rows


def supplier_matches_for_sku(sku):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT sku, title, brand, supplier, cost, rrp, stock,
               CASE WHEN image_url != '' THEN 'Yes' ELSE 'Missing' END AS image,
               CASE WHEN description != '' THEN 'Yes' ELSE 'Missing' END AS description
        FROM products
        WHERE lower(sku) = lower(?)
        ORDER BY supplier
    """, (sku.strip(),)).fetchall()

    conn.close()
    return rows


if __name__ == "__main__":
    build_database()
