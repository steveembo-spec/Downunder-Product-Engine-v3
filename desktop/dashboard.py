import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)

from widgets import (
    StatCard,
    HealthRow,
    PageTitle,
    PageSubtitle,
    PrimaryButton,
    SecondaryButton,
)

from dashboard_data import load_dashboard


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
REPORT = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"


class DashboardPage(QWidget):

    def __init__(self):
        super().__init__()
        self.build_ui()
        self.refresh()

    def build_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(24)

        layout.addWidget(PageTitle("Dashboard"))
        layout.addWidget(PageSubtitle("Downunder Product Engine"))

        cards = QHBoxLayout()
        cards.setSpacing(18)

        self.products = StatCard("Master Products", "0", "Live DB total", "📦")
        self.suppliers = StatCard("Suppliers", "0", "Active in master DB", "🏭")
        self.missing_price = StatCard("Missing Price", "0", "No RRP aggregate", "💲")
        self.missing_image = StatCard("Missing Image", "0", "No product image", "🖼")

        cards.addWidget(self.products)
        cards.addWidget(self.suppliers)
        cards.addWidget(self.missing_price)
        cards.addWidget(self.missing_image)

        layout.addLayout(cards)

        content = QHBoxLayout()
        content.setSpacing(20)

        health_col = QVBoxLayout()
        health_col.setSpacing(10)

        health_title = QLabel("Catalogue Health")
        health_title.setStyleSheet("font-size:18px; font-weight:800;")

        health_col.addWidget(health_title)
        self.health_rows = QVBoxLayout()
        self.health_rows.setSpacing(10)
        health_col.addLayout(self.health_rows)
        health_col.addStretch()

        actions_col = QVBoxLayout()
        actions_col.setSpacing(10)

        actions_title = QLabel("Quick Actions")
        actions_title.setStyleSheet("font-size:18px; font-weight:800;")

        self.build_button = PrimaryButton("BUILD SHOPIFY CATALOGUE")
        self.open_report = SecondaryButton("Open Build Report")
        self.open_csv = SecondaryButton("Open Shopify CSV")
        self.open_output = SecondaryButton("Open Output Folder")

        self.build_button.clicked.connect(self.go_to_catalogue)
        self.open_report.clicked.connect(self.open_build_report)
        self.open_csv.clicked.connect(self.open_shopify_csv)
        self.open_output.clicked.connect(self.open_output_folder)

        actions_col.addWidget(actions_title)
        actions_col.addWidget(self.build_button)
        actions_col.addWidget(self.open_report)
        actions_col.addWidget(self.open_csv)
        actions_col.addWidget(self.open_output)
        actions_col.addStretch()

        content.addLayout(health_col, 2)
        content.addLayout(actions_col, 1)

        layout.addLayout(content)

        self.last_build = QLabel()
        self.last_build.setStyleSheet("font-size:14px; color:#9CA3AF;")

        layout.addWidget(self.last_build)
        layout.addStretch()

    def refresh(self):
        stats = load_dashboard()

        self.products.set_value(stats["products"])
        self.suppliers.set_value(stats["suppliers"])
        self.missing_price.set_value(stats["missing_price"])
        self.missing_image.set_value(stats["missing_image"])

        self._refresh_health_rows(stats)
        self.last_build.setText(f"Last Sync: {stats['run_date']}  |  Source: {stats['status']}")

    def _refresh_health_rows(self, stats):
        while self.health_rows.count():
            item = self.health_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        missing_desc = int(stats.get("missing_description", "0"))
        desc_colour = "#22C55E" if missing_desc == 0 else "#F59E0B"
        self.health_rows.addWidget(
            HealthRow("Missing Description", str(missing_desc), desc_colour)
        )

        by_supplier = stats.get("products_by_supplier", [])
        if by_supplier:
            for row in by_supplier[:3]:
                self.health_rows.addWidget(
                    HealthRow(
                        f"Supplier: {row['supplier_name']}",
                        f"{row['product_count']:,} products",
                        "#22C55E",
                    )
                )
        else:
            self.health_rows.addWidget(
                HealthRow("Products By Supplier", "No data", "#9CA3AF")
            )

        latest = stats.get("latest_suppliers", [])
        if latest:
            for row in latest[:2]:
                self.health_rows.addWidget(
                    HealthRow(
                        f"Latest Import: {row['supplier_name']}",
                        f"{row['product_count']:,} products",
                        "#22C55E",
                    )
                )
        else:
            self.health_rows.addWidget(
                HealthRow("Latest Supplier Import", "Unavailable", "#9CA3AF")
            )

    def go_to_catalogue(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, "setCurrentIndex"):
                parent.setCurrentIndex(1)
                return
            parent = parent.parent()

    def open_build_report(self):
        if REPORT.exists():
            os.startfile(REPORT)
        else:
            QMessageBox.warning(self, "Missing Report", "Run a catalogue build first.")

    def open_shopify_csv(self):
        if OUTPUT.exists():
            os.startfile(OUTPUT)
        else:
            QMessageBox.warning(self, "Missing CSV", "Run a catalogue build first.")

    def open_output_folder(self):
        os.startfile(PROJECT_ROOT / "output")