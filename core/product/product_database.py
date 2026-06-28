from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class ProductRecord:
    sku: str
    title: str
    supplier: str
    cost: str
    rrp: str
    stock: str
    brand: str
    category: str
    image_status: str
    description_status: str
    margin: str
    raw: dict


class ProductDatabase:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.products = []
        self.source_file = None

    def load(self):
        self.products = []

        candidates = [
            self.project_root / "output" / "dpe_supplier_catalogue.csv",
            self.project_root / "output" / "dpe_v3_shopify_ready.csv",
            self.project_root / "output" / "dpe_ready_for_shopify.csv",
            self.project_root / "output" / "dpe_merged_catalogue.csv",
        ]

        self.source_file = None

        for candidate in candidates:
            if candidate.exists():
                self.source_file = candidate
                break

        if self.source_file is None:
            return []

        with self.source_file.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                sku = self.pick(row, "sku", "SKU", "Variant SKU", "Supplier SKU")
                title = self.pick(row, "title", "Title", "name", "Name", "Product Title")
                supplier = self.clean_supplier(self.pick(row, "supplier", "Supplier", "Tags"))
                cost = self.pick(row, "cost", "Cost", "WSP", "wsp", "Wholesale", "Cost per item")
                rrp = self.pick(row, "rrp", "RRP", "price", "Price", "Variant Price")
                stock = self.pick(row, "stock", "Stock", "qty", "Qty", "quantity", "Quantity", "Variant Inventory Qty")
                brand = self.pick(row, "brand", "Brand", "Vendor")
                category = self.pick(row, "category", "Category", "Product Category", "Product Type", "product_type", "Type")

                product = ProductRecord(
                    sku=sku,
                    title=title,
                    supplier=supplier,
                    cost=cost,
                    rrp=rrp,
                    stock=stock,
                    brand=brand,
                    category=category,
                    image_status="Found" if self.pick(row, "image", "Image", "Image Src", "image_url", "Image URL") else "Missing",
                    description_status="Found" if self.pick(row, "description", "Description", "Body (HTML)", "body_html") else "Missing",
                    margin=self.calculate_margin(cost, rrp),
                    raw=row,
                )

                if product.sku or product.title:
                    self.products.append(product)

        return self.products

    def search(self, query):
        query = query.strip().lower()

        if not query:
            return self.products

        results = []

        for product in self.products:
            raw_text = " ".join(str(value or "") for value in product.raw.values())

            searchable = " ".join([
                product.sku,
                product.title,
                product.brand,
                product.supplier,
                product.category,
                raw_text,
            ]).lower()

            if query in searchable:
                results.append(product)

        return results

    @staticmethod
    def pick(row, *keys):
        lower = {str(k).lower(): str(v or "").strip() for k, v in row.items()}

        for key in keys:
            value = lower.get(key.lower())
            if value:
                return value

        return ""

    @staticmethod
    def clean_supplier(value):
        value = str(value or "").strip()

        if not value:
            return ""

        parts = [part.strip() for part in value.split(",")]

        for part in parts:
            if part.lower().startswith("supplier:"):
                return part.split(":", 1)[1].strip()

        return value

    @staticmethod
    def calculate_margin(cost, rrp):
        try:
            cost_value = float(str(cost).replace("$", "").replace(",", "").strip())
            rrp_value = float(str(rrp).replace("$", "").replace(",", "").strip())

            if rrp_value <= 0:
                return ""

            margin = ((rrp_value - cost_value) / rrp_value) * 100
            return f"{margin:.1f}%"

        except (TypeError, ValueError):
            return ""