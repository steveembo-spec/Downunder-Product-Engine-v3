from dataclasses import dataclass
from datetime import datetime


@dataclass
class ImageRecord:
    sku: str
    title: str
    brand: str
    supplier: str
    provider: str
    image_url: str
    filename: str
    status: str
    last_checked: str

    @classmethod
    def found(cls, product, provider, image_url):
        sku = str(product.get("sku", "")).strip()
        title = str(product.get("title", "")).strip()
        brand = str(product.get("brand", "")).strip()
        supplier = str(product.get("supplier", "")).strip()

        filename = image_url.rstrip("/").split("/")[-1]

        return cls(
            sku=sku,
            title=title,
            brand=brand,
            supplier=supplier,
            provider=provider,
            image_url=image_url,
            filename=filename,
            status="FOUND",
            last_checked=datetime.now().isoformat(timespec="seconds"),
        )