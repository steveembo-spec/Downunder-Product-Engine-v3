from dpe_v3.images.builder import ImageLibraryBuilder
from dpe_v3.suppliers import load_all_suppliers


TEST_LIMIT = 250


def main():
    print("=" * 60)
    print("DPE IMAGE LIBRARY BUILDER v3")
    print("=" * 60)

    products = load_all_suppliers()

    print(f"Products loaded: {len(products):,}")
    print(f"Test limit: {TEST_LIMIT:,}")

    builder = ImageLibraryBuilder()
    records = builder.build(products, limit=TEST_LIMIT)

    print("-" * 60)
    print(f"Image records created : {len(records):,}")
    print("=" * 60)


if __name__ == "__main__":
    main()