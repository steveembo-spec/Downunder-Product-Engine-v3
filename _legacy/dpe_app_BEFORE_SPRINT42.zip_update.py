import csv
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parent
RUNNER_FILE = PROJECT_ROOT / "run_dpe_v3.py"

SHOPIFY_OUTPUT_FILE = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
SUPPLIER_CATALOGUE_FILE = PROJECT_ROOT / "output" / "dpe_supplier_catalogue.csv"
REPORT_FILE = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"


def first_value(row, possible_names):
    for name in possible_names:
        if name in row and row[name] not in (None, ""):
            return str(row[name]).strip()
    return ""


def money(value):
    if value == "":
        return ""
    try:
        return f"${float(str(value).replace('$', '').replace(',', '')):,.2f}"
    except Exception:
        return str(value)


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


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Welcome to Downunder Product Engine")
        subtitle.setObjectName("MutedText")

        cards = QHBoxLayout()
        cards.setSpacing(16)

        cards.addWidget(self.make_card("Products", "62,753"))
        cards.addWidget(self.make_card("Images", "8,320"))
        cards.addWidget(self.make_card("Descriptions", "1,207"))
        cards.addWidget(self.make_card("Status", "READY"))

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


class BuildCentrePage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(18)

        title = QLabel("Build Centre")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Build a Shopify-ready draft product CSV from supplier files.")
        subtitle.setObjectName("MutedText")

        self.build_button = QPushButton("BUILD SHOPIFY CATALOGUE")
        self.build_button.setObjectName("PrimaryButton")
        self.build_button.setFixedHeight(58)
        self.build_button.clicked.connect(self.start_build)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("LogBox")

        button_row = QHBoxLayout()

        open_output = QPushButton("Open Output Folder")
        open_output.setObjectName("SecondaryButton")
        open_output.clicked.connect(lambda: os.startfile(PROJECT_ROOT / "output"))

        open_csv = QPushButton("Open Shopify CSV")
        open_csv.setObjectName("SecondaryButton")
        open_csv.clicked.connect(self.open_csv)

        open_report = QPushButton("Open Build Report")
        open_report.setObjectName("SecondaryButton")
        open_report.clicked.connect(self.open_report)

        button_row.addWidget(open_output)
        button_row.addWidget(open_csv)
        button_row.addWidget(open_report)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.build_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_box)
        layout.addLayout(button_row)

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
        QMessageBox.information(self, "Complete", "Shopify catalogue built successfully.")

    def build_failed(self, message):
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.build_button.setText("BUILD SHOPIFY CATALOGUE")
        QMessageBox.critical(self, "Build Failed", message)

    def open_csv(self):
        if SHOPIFY_OUTPUT_FILE.exists():
            os.startfile(SHOPIFY_OUTPUT_FILE)
        else:
            QMessageBox.warning(self, "Missing File", "Run the build first.")

    def open_report(self):
        if REPORT_FILE.exists():
            os.startfile(REPORT_FILE)
        else:
            QMessageBox.warning(self, "Missing Report", "Run the build first.")


class CatalogueControlCentrePage(QWidget):
    def __init__(self):
        super().__init__()

        self.rows = []
        self.filtered_rows = []

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Catalogue Control Centre")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Search SKUs, products, brands and suppliers. Supplier comparison will use matching SKUs.")
        subtitle.setObjectName("MutedText")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search SKU, title, brand, supplier...")
        self.search_box.setObjectName("SearchBox")
        self.search_box.textChanged.connect(self.apply_filters)

        filters = QHBoxLayout()

        self.supplier_filter = QComboBox()
        self.supplier_filter.addItem("All Suppliers")
        self.supplier_filter.currentTextChanged.connect(self.apply_filters)

        self.brand_filter = QComboBox()
        self.brand_filter.addItem("All Brands")
        self.brand_filter.currentTextChanged.connect(self.apply_filters)

        self.image_filter = QComboBox()
        self.image_filter.addItems(["All Images", "Has Image", "Missing Image"])
        self.image_filter.currentTextChanged.connect(self.apply_filters)

        filters.addWidget(self.supplier_filter)
        filters.addWidget(self.brand_filter)
        filters.addWidget(self.image_filter)

        self.status_label = QLabel("Loading catalogue...")
        self.status_label.setObjectName("MutedText")

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "SKU",
            "Title",
            "Brand",
            "Supplier",
            "Cost",
            "RRP",
            "Image",
            "Description",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.view_product)

        buttons = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Catalogue")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.load_catalogue)

        view_btn = QPushButton("View Product")
        view_btn.setObjectName("SecondaryButton")
        view_btn.clicked.connect(self.view_product)

        compare_btn = QPushButton("Compare Suppliers")
        compare_btn.setObjectName("PrimaryButton")
        compare_btn.clicked.connect(self.compare_suppliers)

        buttons.addWidget(refresh_btn)
        buttons.addWidget(view_btn)
        buttons.addWidget(compare_btn)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.search_box)
        layout.addLayout(filters)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.load_catalogue()

    def load_catalogue(self):
        source_file = SUPPLIER_CATALOGUE_FILE if SUPPLIER_CATALOGUE_FILE.exists() else SHOPIFY_OUTPUT_FILE

        if not source_file.exists():
            self.rows = []
            self.filtered_rows = []
            self.table.setRowCount(0)
            self.status_label.setText("No catalogue file found. Run the Build Centre first.")
            return

        try:
            with open(source_file, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                self.rows = list(reader)
        except Exception as e:
            QMessageBox.critical(self, "Catalogue Load Failed", str(e))
            return

        self.populate_filters()
        self.apply_filters()
        self.status_label.setText(f"Loaded {len(self.rows):,} rows from {source_file.name}")

    def populate_filters(self):
        suppliers = sorted(set(self.get_supplier(row) for row in self.rows if self.get_supplier(row)))
        brands = sorted(set(self.get_brand(row) for row in self.rows if self.get_brand(row)))

        self.supplier_filter.blockSignals(True)
        self.brand_filter.blockSignals(True)

        self.supplier_filter.clear()
        self.supplier_filter.addItem("All Suppliers")
        self.supplier_filter.addItems(suppliers)

        self.brand_filter.clear()
        self.brand_filter.addItem("All Brands")
        self.brand_filter.addItems(brands)

        self.supplier_filter.blockSignals(False)
        self.brand_filter.blockSignals(False)

    def apply_filters(self):
        query = self.search_box.text().strip().lower()
        supplier = self.supplier_filter.currentText()
        brand = self.brand_filter.currentText()
        image_filter = self.image_filter.currentText()

        results = []

        for row in self.rows:
            searchable = " ".join([
                self.get_sku(row),
                self.get_title(row),
                self.get_brand(row),
                self.get_supplier(row),
            ]).lower()

            if query and query not in searchable:
                continue

            if supplier != "All Suppliers" and self.get_supplier(row) != supplier:
                continue

            if brand != "All Brands" and self.get_brand(row) != brand:
                continue

            has_image = bool(self.get_image(row))
            if image_filter == "Has Image" and not has_image:
                continue
            if image_filter == "Missing Image" and has_image:
                continue

            results.append(row)

        self.filtered_rows = results
        self.populate_table(results[:500])

        extra = "" if len(results) <= 500 else " Showing first 500."
        self.status_label.setText(f"Results: {len(results):,}.{extra}")

    def populate_table(self, rows):
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            values = [
                self.get_sku(row),
                self.get_title(row),
                self.get_brand(row),
                self.get_supplier(row),
                money(self.get_cost(row)),
                money(self.get_rrp(row)),
                "Yes" if self.get_image(row) else "Missing",
                "Yes" if self.get_description(row) else "Missing",
            ]

            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.table.setItem(r, c, item)

    def selected_row(self):
        row_index = self.table.currentRow()

        if row_index < 0 or row_index >= len(self.filtered_rows):
            QMessageBox.warning(self, "No Product Selected", "Select a product first.")
            return None

        return self.filtered_rows[row_index]

    def view_product(self):
        row = self.selected_row()
        if not row:
            return

        dlg = ProductDialog(row, self.find_supplier_matches(self.get_sku(row)), self)
        dlg.exec()

    def compare_suppliers(self):
        row = self.selected_row()
        if not row:
            return

        sku = self.get_sku(row)
        matches = self.find_supplier_matches(sku)

        dlg = SupplierCompareDialog(sku, matches, self)
        dlg.exec()

    def find_supplier_matches(self, sku):
        if not sku:
            return []

        sku_clean = sku.strip().lower()
        return [row for row in self.rows if self.get_sku(row).strip().lower() == sku_clean]

    def get_sku(self, row):
        return first_value(row, ["SKU", "sku", "Variant SKU", "Supplier SKU", "Part Number", "part_number"])

    def get_title(self, row):
        return first_value(row, ["Title", "title", "Product Title", "Name", "name", "Description", "description"])

    def get_brand(self, row):
        return first_value(row, ["Brand", "brand", "Vendor", "vendor", "Manufacturer", "manufacturer"])

    def get_supplier(self, row):
        return first_value(row, ["Supplier", "supplier", "Source", "source"])

    def get_cost(self, row):
        return first_value(row, ["Cost", "cost", "WSP", "wsp", "Wholesale", "wholesale", "Variant Cost"])

    def get_rrp(self, row):
        return first_value(row, ["RRP", "rrp", "Price", "price", "Variant Price", "Sell Price"])

    def get_image(self, row):
        return first_value(row, ["Image Src", "Image", "image", "Image URL", "image_url", "Variant Image"])

    def get_description(self, row):
        return first_value(row, ["Body (HTML)", "Description", "description", "Body", "Product Description"])


class ProductDialog(QDialog):
    def __init__(self, row, supplier_matches, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Product Inspector")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        title = first_value(row, ["Title", "title", "Product Title", "Name", "Description"])
        sku = first_value(row, ["SKU", "sku", "Variant SKU", "Supplier SKU", "Part Number"])

        heading = QLabel(title or "Product Inspector")
        heading.setStyleSheet("font-size:24px; font-weight:800;")

        sku_label = QLabel(f"SKU: {sku}")
        sku_label.setStyleSheet("font-size:15px; color:#9ca3af;")

        details = QTextEdit()
        details.setReadOnly(True)

        lines = []
        for key, value in row.items():
            if value not in (None, ""):
                lines.append(f"{key}: {value}")

        details.setText("\n".join(lines))

        compare = SupplierCompareDialog.build_supplier_table(supplier_matches)

        layout.addWidget(heading)
        layout.addWidget(sku_label)
        layout.addWidget(QLabel("Product Data"))
        layout.addWidget(details)
        layout.addWidget(QLabel("Supplier Matches"))
        layout.addWidget(compare)


class SupplierCompareDialog(QDialog):
    def __init__(self, sku, matches, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Compare Suppliers - {sku}")
        self.resize(850, 420)

        layout = QVBoxLayout(self)

        heading = QLabel(f"Supplier Comparison: {sku}")
        heading.setStyleSheet("font-size:24px; font-weight:800;")

        note = QLabel("Recommendation logic will come next. For now this shows every supplier row with the same SKU.")
        note.setStyleSheet("color:#9ca3af;")

        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addWidget(self.build_supplier_table(matches))

    @staticmethod
    def build_supplier_table(matches):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Supplier", "Brand", "Title", "Cost", "RRP", "Stock"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(matches))

        for r, row in enumerate(matches):
            values = [
                first_value(row, ["Supplier", "supplier", "Source", "source"]),
                first_value(row, ["Brand", "brand", "Vendor", "vendor"]),
                first_value(row, ["Title", "title", "Name", "Description", "description"]),
                money(first_value(row, ["Cost", "cost", "WSP", "wsp", "Wholesale", "Variant Cost"])),
                money(first_value(row, ["RRP", "rrp", "Price", "price", "Variant Price"])),
                first_value(row, ["Stock", "stock", "Qty", "Quantity", "Available", "availability"]),
            ]

            for c, value in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(value))

        return table


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
        self.resize(1250, 780)

        main = QWidget()
        self.setCentralWidget(main)

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self.build_sidebar()
        self.pages = QStackedWidget()

        self.pages.addWidget(DashboardPage())
        self.pages.addWidget(BuildCentrePage())
        self.pages.addWidget(CatalogueControlCentrePage())
        self.pages.addWidget(PlaceholderPage("Images", "Image library tools will live here."))
        self.pages.addWidget(PlaceholderPage("Descriptions", "Description matching and content tools will live here."))
        self.pages.addWidget(PlaceholderPage("Reports", "Build reports and health checks will live here."))
        self.pages.addWidget(PlaceholderPage("Shopify API", "Shopify API connection settings will live here."))
        self.pages.addWidget(PlaceholderPage("Settings", "Supplier priorities, pricing rules and output settings will live here."))

        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        self.apply_theme()

    def build_sidebar(self):
        sidebar = QListWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)

        items = [
            "Dashboard",
            "Build Centre",
            "Catalogue Control",
            "Images",
            "Descriptions",
            "Reports",
            "Shopify API",
            "Settings",
        ]

        for item in items:
            widget_item = QListWidgetItem(item)
            widget_item.setTextAlignment(Qt.AlignVCenter)
            sidebar.addItem(widget_item)

        return sidebar

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #111827;
                color: #f9fafb;
                font-family: Segoe UI;
                font-size: 14px;
            }

            QListWidget#Sidebar {
                background-color: #020617;
                border: none;
                padding-top: 24px;
                font-size: 15px;
                font-weight: 600;
            }

            QListWidget#Sidebar::item {
                padding: 16px 24px;
                color: #9ca3af;
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

            QFrame#Card {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 16px;
                min-height: 130px;
                margin-left: 30px;
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

            QPushButton#PrimaryButton {
                background-color: #f59e0b;
                color: #111827;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 800;
                padding: 12px;
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
            }

            QPushButton#SecondaryButton:hover {
                background-color: #374151;
            }

            QTextEdit#LogBox, QTextEdit {
                background-color: #020617;
                color: #d1d5db;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 12px;
                font-family: Consolas;
                font-size: 12px;
            }

            QLineEdit#SearchBox {
                background-color: #020617;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 14px;
                margin-left: 30px;
                margin-right: 30px;
                font-size: 16px;
            }

            QComboBox {
                background-color: #1f2937;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 10px;
                margin-left: 30px;
            }

            QTableWidget {
                background-color: #020617;
                color: #f9fafb;
                gridline-color: #374151;
                border: 1px solid #374151;
                margin-left: 30px;
                margin-right: 30px;
            }

            QHeaderView::section {
                background-color: #1f2937;
                color: #f9fafb;
                padding: 8px;
                border: 1px solid #374151;
                font-weight: 800;
            }

            QProgressBar {
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