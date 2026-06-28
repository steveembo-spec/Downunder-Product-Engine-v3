import os
import subprocess
import sys
from pathlib import Path

from dashboard_data import load_dashboard_stats
from core.product.product_database import ProductDatabase, ProductRecord

from PySide6.QtCore import Qt, QThread, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTextEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parent
RUNNER_FILE = PROJECT_ROOT / "run_dpe_v3.py"
OUTPUT_FILE = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
REPORT_FILE = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"
LOGO_FILE = PROJECT_ROOT / "assets" / "logo.png"


class BuildWorker(QThread):
    log_line = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def run(self):
        try:
            process = subprocess.Popen(
                ["python", str(RUNNER_FILE)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in process.stdout:
                self.log_line.emit(line)

            process.wait()

            if process.returncode == 0:
                self.finished_ok.emit()
            else:
                self.failed.emit("DPE build failed. Check the build log.")

        except Exception as e:
            self.failed.emit(str(e))


class ProductTableModel(QAbstractTableModel):
    HEADERS = [
        "SKU",
        "Title",
        "Brand",
        "Supplier",
        "Cost",
        "RRP",
        "Margin",
        "Stock",
        "Image",
        "Description",
    ]

    def __init__(self):
        super().__init__()
        self.products = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.products)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        product = self.products[index.row()]

        values = [
            product.sku,
            product.title,
            product.brand,
            product.supplier,
            product.cost,
            product.rrp,
            product.margin,
            product.stock,
            product.image_status,
            product.description_status,
        ]

        return values[index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.HEADERS[section]

        return section + 1

    def set_products(self, products):
        self.beginResetModel()
        self.products = products
        self.endResetModel()

    def product_at(self, row):
        if row < 0 or row >= len(self.products):
            return None
        return self.products[row]


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        stats = load_dashboard_stats()

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Welcome to Downunder Product Engine")
        subtitle.setObjectName("MutedText")

        cards = QHBoxLayout()
        cards.setSpacing(16)

        cards.addWidget(self.make_card("Products", stats.get("products", "0")))
        cards.addWidget(self.make_card("Images", stats.get("images", "0")))
        cards.addWidget(self.make_card("Descriptions", stats.get("descriptions", "0")))
        cards.addWidget(self.make_card("Status", stats.get("status", "UNKNOWN")))

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(cards)
        layout.addStretch()

    def make_card(self, title, value):
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return card


class CataloguePage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.database = ProductDatabase(PROJECT_ROOT)
        self.all_products = []
        self.filtered_products = []
        self.selected_product = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Catalogue")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Search supplier catalogues and manage Shopify-ready product data.")
        subtitle.setObjectName("MutedText")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SKU, partial SKU, brand, title, supplier or category...")
        self.search_input.setObjectName("SearchBox")
        self.search_input.textChanged.connect(self.apply_filter)

        self.summary_label = QLabel("Products loaded: 0")
        self.summary_label.setObjectName("MutedText")

        self.table_model = ProductTableModel()

        self.table = QTableView()
        self.table.setObjectName("ProductTable")
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.clicked.connect(self.select_product)

        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 410)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 90)
        self.table.setColumnWidth(9, 120)

        self.detail_card = QFrame()
        self.detail_card.setObjectName("DetailCard")

        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setSpacing(10)

        self.detail_title = QLabel("Select a product")
        self.detail_title.setObjectName("DetailTitle")

        self.detail_subtitle = QLabel("Click a row to view full product details.")
        self.detail_subtitle.setObjectName("MutedTextNoMargin")

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(22)
        detail_grid.setVerticalSpacing(8)

        self.detail_sku = self.make_detail_value()
        self.detail_supplier = self.make_detail_value()
        self.detail_brand = self.make_detail_value()
        self.detail_category = self.make_detail_value()
        self.detail_cost = self.make_detail_value()
        self.detail_rrp = self.make_detail_value()
        self.detail_margin = self.make_detail_value()
        self.detail_stock = self.make_detail_value()
        self.detail_image = self.make_detail_value()
        self.detail_description = self.make_detail_value()

        details = [
            ("SKU", self.detail_sku),
            ("Supplier", self.detail_supplier),
            ("Brand", self.detail_brand),
            ("Category", self.detail_category),
            ("Cost", self.detail_cost),
            ("RRP", self.detail_rrp),
            ("Margin", self.detail_margin),
            ("Stock", self.detail_stock),
            ("Image", self.detail_image),
            ("Description", self.detail_description),
        ]

        for row, (label, widget) in enumerate(details):
            key = QLabel(label + ":")
            key.setObjectName("DetailKey")
            detail_grid.addWidget(key, row // 4, (row % 4) * 2)
            detail_grid.addWidget(widget, row // 4, (row % 4) * 2 + 1)

        self.raw_box = QTextEdit()
        self.raw_box.setObjectName("LogBox")
        self.raw_box.setReadOnly(True)
        self.raw_box.setFixedHeight(110)

        future_button_row = QHBoxLayout()

        for text in [
            "Open Shopify Product",
            "Edit Product",
            "Rebuild Description",
            "Find Image",
            "Export Selected",
        ]:
            button = QPushButton(text)
            button.setObjectName("SecondaryButton")
            button.setEnabled(False)
            future_button_row.addWidget(button)

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_subtitle)
        detail_layout.addLayout(detail_grid)
        detail_layout.addWidget(self.raw_box)
        detail_layout.addLayout(future_button_row)

        self.build_button = QPushButton("BUILD SHOPIFY CATALOGUE")
        self.build_button.setObjectName("PrimaryButton")
        self.build_button.setFixedHeight(50)
        self.build_button.clicked.connect(self.start_build)

        button_row = QHBoxLayout()

        reload_button = QPushButton("Reload Product Database")
        reload_button.setObjectName("SecondaryButton")
        reload_button.clicked.connect(self.load_products)

        open_output = QPushButton("Open Output Folder")
        open_output.setObjectName("SecondaryButton")
        open_output.clicked.connect(lambda: os.startfile(PROJECT_ROOT / "output"))

        open_csv = QPushButton("Open Shopify CSV")
        open_csv.setObjectName("SecondaryButton")
        open_csv.clicked.connect(self.open_csv)

        open_report = QPushButton("Open Build Report")
        open_report.setObjectName("SecondaryButton")
        open_report.clicked.connect(self.open_report)

        button_row.addWidget(reload_button)
        button_row.addWidget(open_output)
        button_row.addWidget(open_csv)
        button_row.addWidget(open_report)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("LogBox")
        self.log_box.setFixedHeight(105)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.search_input)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.detail_card)
        layout.addWidget(self.build_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_box)
        layout.addLayout(button_row)

        self.load_products()

    def make_detail_value(self):
        label = QLabel("-")
        label.setObjectName("DetailValue")
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def load_products(self):
        self.all_products = self.database.load()
        self.filtered_products = self.all_products
        self.table_model.set_products(self.filtered_products)
        self.update_summary()
        self.clear_details()

    def apply_filter(self):
        self.filtered_products = self.database.search(self.search_input.text())
        self.table_model.set_products(self.filtered_products)
        self.update_summary()
        self.clear_details()

    def update_summary(self):
        total = len(self.all_products)
        shown = len(self.filtered_products)
        source = self.database.source_file.name if self.database.source_file else "No source file"

        if self.search_input.text().strip():
            self.summary_label.setText(f"Showing {shown:,} of {total:,} products | Source: {source}")
        else:
            self.summary_label.setText(f"Products loaded: {total:,} | Source: {source}")

    def select_product(self, index):
        product = self.table_model.product_at(index.row())

        if not product:
            self.clear_details()
            return

        self.selected_product = product
        self.detail_title.setText(product.title or "Untitled Product")
        self.detail_subtitle.setText("Product details from current DPE catalogue source.")

        self.detail_sku.setText(product.sku or "-")
        self.detail_supplier.setText(product.supplier or "-")
        self.detail_brand.setText(product.brand or "-")
        self.detail_category.setText(product.category or "-")
        self.detail_cost.setText(product.cost or "-")
        self.detail_rrp.setText(product.rrp or "-")
        self.detail_margin.setText(product.margin or "-")
        self.detail_stock.setText(product.stock or "-")
        self.detail_image.setText(product.image_status or "-")
        self.detail_description.setText(product.description_status or "-")

        self.raw_box.setPlainText("\n".join(f"{k}: {v}" for k, v in product.raw.items()))

    def clear_details(self):
        self.selected_product = None
        self.detail_title.setText("Select a product")
        self.detail_subtitle.setText("Click a row to view full product details.")

        for widget in [
            self.detail_sku,
            self.detail_supplier,
            self.detail_brand,
            self.detail_category,
            self.detail_cost,
            self.detail_rrp,
            self.detail_margin,
            self.detail_stock,
            self.detail_image,
            self.detail_description,
        ]:
            widget.setText("-")

        self.raw_box.clear()

    def start_build(self):
        self.log_box.clear()
        self.build_button.setEnabled(False)
        self.build_button.setText("BUILDING...")
        self.progress.show()

        self.worker = BuildWorker()
        self.worker.log_line.connect(self.add_log)
        self.worker.finished_ok.connect(self.build_complete)
        self.worker.failed.connect(self.build_failed)
        self.worker.start()

    def add_log(self, text):
        self.log_box.append(text.rstrip())

    def build_complete(self):
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.build_button.setText("BUILD SHOPIFY CATALOGUE")
        self.load_products()
        QMessageBox.information(self, "Complete", "Shopify catalogue built successfully.")

    def build_failed(self, message):
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.build_button.setText("BUILD SHOPIFY CATALOGUE")
        QMessageBox.critical(self, "Build Failed", message)

    def open_csv(self):
        if OUTPUT_FILE.exists():
            os.startfile(OUTPUT_FILE)
        else:
            QMessageBox.warning(self, "Missing File", "Run the build first.")

    def open_report(self):
        if REPORT_FILE.exists():
            os.startfile(REPORT_FILE)
        else:
            QMessageBox.warning(self, "Missing Report", "Run the build first.")


class PlaceholderPage(QWidget):
    def __init__(self, title, message):
        super().__init__()

        layout = QVBoxLayout(self)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")

        text = QLabel(message)
        text.setObjectName("MutedText")
        text.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Downunder Product Engine")
        self.resize(1200, 760)

        main = QWidget()
        self.setCentralWidget(main)

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar_container = self.build_sidebar_container()
        self.sidebar = self.sidebar_container.findChild(QListWidget, "Sidebar")

        self.pages = QStackedWidget()

        self.pages.addWidget(DashboardPage())
        self.pages.addWidget(CataloguePage())
        self.pages.addWidget(PlaceholderPage("Images", "Image library tools will live here."))
        self.pages.addWidget(PlaceholderPage("Descriptions", "Description matching and content tools will live here."))
        self.pages.addWidget(PlaceholderPage("Reports", "Build reports and health checks will live here."))
        self.pages.addWidget(PlaceholderPage("Settings", "Supplier priorities, pricing rules and output settings will live here."))

        layout.addWidget(self.sidebar_container)
        layout.addWidget(self.pages, 1)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        self.apply_theme()

    def build_sidebar_container(self):
        container = QWidget()
        container.setObjectName("SidebarContainer")
        container.setFixedWidth(260)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(14)

        logo_label = QLabel()
        logo_label.setObjectName("LogoLabel")
        logo_label.setAlignment(Qt.AlignCenter)

        if LOGO_FILE.exists():
            pixmap = QPixmap(str(LOGO_FILE))
            logo_label.setPixmap(
                pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            logo_label.setText("DPE")
            logo_label.setObjectName("LogoFallback")

        app_title = QLabel("DOWNUNDER\nPRODUCT ENGINE")
        app_title.setObjectName("AppBrandTitle")
        app_title.setAlignment(Qt.AlignCenter)

        app_subtitle = QLabel("Catalogue Control Centre")
        app_subtitle.setObjectName("AppBrandSubtitle")
        app_subtitle.setAlignment(Qt.AlignCenter)

        version = QLabel("v3 Desktop")
        version.setObjectName("VersionBadge")
        version.setAlignment(Qt.AlignCenter)

        sidebar = QListWidget()
        sidebar.setObjectName("Sidebar")

        items = [
            "Dashboard",
            "Catalogue",
            "Images",
            "Descriptions",
            "Reports",
            "Settings",
        ]

        for item in items:
            widget_item = QListWidgetItem(item)
            widget_item.setTextAlignment(Qt.AlignVCenter)
            sidebar.addItem(widget_item)

        layout.addWidget(logo_label)
        layout.addWidget(app_title)
        layout.addWidget(app_subtitle)
        layout.addWidget(version)
        layout.addSpacing(16)
        layout.addWidget(sidebar, 1)

        return container

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #111827;
                color: #f9fafb;
                font-family: Segoe UI;
                font-size: 14px;
            }

            QWidget#SidebarContainer {
                background-color: #020617;
                border-right: 1px solid #1f2937;
            }

            QLabel#LogoFallback {
                background-color: #f59e0b;
                color: #111827;
                border-radius: 44px;
                min-width: 88px;
                min-height: 88px;
                font-size: 28px;
                font-weight: 900;
            }

            QLabel#AppBrandTitle {
                color: #f9fafb;
                font-size: 17px;
                font-weight: 900;
                letter-spacing: 1px;
            }

            QLabel#AppBrandSubtitle {
                color: #9ca3af;
                font-size: 13px;
                font-weight: 600;
            }

            QLabel#VersionBadge {
                background-color: #1f2937;
                color: #f59e0b;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 6px;
                font-weight: 800;
            }

            QListWidget#Sidebar {
                background-color: #020617;
                border: none;
                font-size: 15px;
                font-weight: 600;
            }

            QListWidget#Sidebar::item {
                padding: 15px 18px;
                color: #9ca3af;
                border-radius: 10px;
            }

            QListWidget#Sidebar::item:selected {
                background-color: #f59e0b;
                color: #111827;
            }

            QLabel#PageTitle {
                font-size: 34px;
                font-weight: 800;
                color: #f9fafb;
                margin-top: 30px;
                margin-left: 30px;
            }

            QLabel#MutedText {
                color: #9ca3af;
                font-size: 15px;
                margin-left: 30px;
            }

            QLabel#MutedTextNoMargin {
                color: #9ca3af;
                font-size: 14px;
            }

            QFrame#Card {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 16px;
                min-height: 130px;
                margin-left: 30px;
            }

            QFrame#DetailCard {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 14px;
                margin-left: 30px;
                margin-right: 30px;
                padding: 10px;
            }

            QLabel#CardTitle {
                color: #9ca3af;
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#CardValue {
                color: #f9fafb;
                font-size: 30px;
                font-weight: 800;
            }

            QLabel#DetailTitle {
                color: #f9fafb;
                font-size: 20px;
                font-weight: 800;
            }

            QLabel#DetailKey {
                color: #9ca3af;
                font-weight: 700;
            }

            QLabel#DetailValue {
                color: #f9fafb;
                font-weight: 600;
            }

            QLineEdit#SearchBox {
                background-color: #020617;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 14px;
                font-size: 15px;
                margin-left: 30px;
                margin-right: 30px;
            }

            QTableView#ProductTable {
                background-color: #020617;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 12px;
                gridline-color: #374151;
                margin-left: 30px;
                margin-right: 30px;
                selection-background-color: #f59e0b;
                selection-color: #111827;
            }

            QHeaderView::section {
                background-color: #1f2937;
                color: #f9fafb;
                padding: 8px;
                border: 1px solid #374151;
                font-weight: 700;
            }

            QPushButton#PrimaryButton {
                background-color: #f59e0b;
                color: #111827;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 800;
                padding: 12px;
                margin-left: 30px;
                margin-right: 30px;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #fbbf24;
            }

            QPushButton#SecondaryButton {
                background-color: #1f2937;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 12px;
                font-weight: 700;
                margin-left: 30px;
                margin-right: 10px;
            }

            QPushButton#SecondaryButton:hover {
                background-color: #374151;
            }

            QPushButton#SecondaryButton:disabled {
                color: #6b7280;
                background-color: #111827;
            }

            QTextEdit#LogBox {
                background-color: #020617;
                color: #d1d5db;
                border: 1px solid #374151;
                border-radius: 12px;
                margin-left: 30px;
                margin-right: 30px;
                padding: 12px;
                font-family: Consolas;
                font-size: 12px;
            }

            QProgressBar {
                margin-left: 30px;
                margin-right: 30px;
                height: 18px;
                border: 1px solid #374151;
                border-radius: 9px;
                background-color: #020617;
            }

            QProgressBar::chunk {
                background-color: #f59e0b;
                border-radius: 9px;
            }
        """)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()