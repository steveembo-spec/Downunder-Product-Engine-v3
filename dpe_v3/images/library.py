import csv

from dpe_v3.config import IMAGE_LIBRARY_V3_FILE


FIELDNAMES = [
    "sku",
    "title",
    "brand",
    "supplier",
    "provider",
    "image_url",
    "filename",
    "status",
    "last_checked",
]


def write_image_library(records, output_file=IMAGE_LIBRARY_V3_FILE):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()

        for record in records:
            writer.writerow({
                "sku": record.sku,
                "title": record.title,
                "brand": record.brand,
                "supplier": record.supplier,
                "provider": record.provider,
                "image_url": record.image_url,
                "filename": record.filename,
                "status": record.status,
                "last_checked": record.last_checked,
            })

    return output_file