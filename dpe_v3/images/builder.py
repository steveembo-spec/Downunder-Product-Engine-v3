import csv

from dpe_v3.config import IMAGE_LIBRARY_DIR
from dpe_v3.images.library import write_image_library
from dpe_v3.images.models import ImageRecord
from dpe_v3.images.providers.mcas import MCASImageProvider


MISSING_IMAGE_REPORT = IMAGE_LIBRARY_DIR / "missing_image_library_v3.csv"


class ImageLibraryBuilder:
    def __init__(self):
        self.providers = [
            MCASImageProvider(),
        ]

    def build(self, products, limit=None):
        records = []
        missing = []

        products_to_process = products[:limit] if limit else products

        for product in products_to_process:
            found = False

            for provider in self.providers:
                image_url = provider.search(product)

                if image_url:
                    records.append(
                        ImageRecord.found(
                            product=product,
                            provider=provider.name,
                            image_url=image_url,
                        )
                    )
                    found = True
                    break

            if not found:
                missing.append({
                    "sku": product.get("sku", ""),
                    "title": product.get("title", ""),
                    "brand": product.get("brand", ""),
                    "supplier": product.get("supplier", ""),
                    "reason": "not_found",
                })

        output_file = write_image_library(records)
        self.write_missing_report(missing)

        print(f"Image Library v3 products checked: {len(products_to_process)}")
        print(f"Image Library v3 records written: {len(records)}")
        print(f"Image Library v3 missing: {len(missing)}")
        print(f"Image Library v3 file created: {output_file}")
        print(f"Image Library v3 missing report: {MISSING_IMAGE_REPORT}")

        return records

    def write_missing_report(self, rows):
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