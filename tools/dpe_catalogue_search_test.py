from pathlib import Path
from dpe_catalogue_db import DB_FILE, search_catalogue, supplier_matches_for_sku


def print_rows(rows):
    if not rows:
        print("No results.")
        return

    for row in rows:
        print("-" * 80)
        print(f"SKU:         {row['sku']}")
        print(f"Title:       {row['title']}")
        print(f"Brand:       {row['brand']}")
        print(f"Supplier:    {row['supplier']}")
        print(f"Cost:        {row['cost']}")
        print(f"RRP:         {row['rrp']}")
        print(f"Stock:       {row['stock']}")
        print(f"Image:       {row['image']}")
        print(f"Description: {row['description']}")


def main():
    if not DB_FILE.exists():
        print("Database not found.")
        print("Run this first:")
        print("python dpe_catalogue_db.py")
        return

    print("")
    print("DPE Catalogue Search Test")
    print("Type a SKU, brand, or keyword. Type EXIT to close.")
    print("")

    while True:
        query = input("Search: ").strip()

        if query.lower() in ("exit", "quit", "q"):
            break

        if not query:
            continue

        rows = search_catalogue(query, limit=20)
        print_rows(rows)

        if rows:
            exact_sku = rows[0]["sku"]
            matches = supplier_matches_for_sku(exact_sku)

            if len(matches) > 1:
                print("")
                print(f"Supplier comparison available for SKU {exact_sku}: {len(matches)} supplier rows")
                for match in matches:
                    print(f"  - {match['supplier']} | Cost: {match['cost']} | RRP: {match['rrp']} | Image: {match['image']}")


if __name__ == "__main__":
    main()
