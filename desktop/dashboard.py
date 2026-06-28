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

        self.products = StatCard("Products", "0", "Shopify draft rows", "📦")
        self.images = StatCard("Images", "0", "Matched product images", "🖼")
        self.descriptions = StatCard("Descriptions", "0", "Real descriptions matched", "📝")
        self.status = StatCard("Status", "UNKNOWN", "Last catalogue build", "✅")

        cards.addWidget(self.products)
        cards.addWidget(self.images)
        cards.addWidget(self.descriptions)
        cards.addWidget(self.status)

        layout.addLayout(cards)

        content = QHBoxLayout()
        content.setSpacing(20)

        health_col = QVBoxLayout()
        health_col.setSpacing(10)

        health_title = QLabel("Catalogue Health")
        health_title.setStyleSheet("font-size:18px; font-weight:800;")

        health_col.addWidget(health_title)
        health_col.addWidget(HealthRow("Supplier Files", "Ready", "#22C55E"))
        health_col.addWidget(HealthRow("Image Library", "Loaded", "#22C55E"))
        health_col.addWidget(HealthRow("Descriptions", "Needs work", "#F59E0B"))
        health_col.addWidget(HealthRow("Shopify Output", "Ready", "#22C55E"))
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
        self.images.set_value(stats["images"])
        self.descriptions.set_value(stats["descriptions"])
        self.status.set_value(stats["status"])

        self.last_build.setText(f"Last Build: {stats['run_date']}")

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