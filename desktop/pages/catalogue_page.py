from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QMessageBox,
    QComboBox,
    QMenu,
    QApplication,
)

from core.product_database import ProductDatabase, ProductRecord
from desktop.dialogs.product_detail_dialog import ProductDetailDialog


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALL_SUPPLIERS = "All Suppliers"
ALL_BRANDS = "All Brands"
ALL_IMAGES = "All Images"
ALL_DESCRIPTIONS = "All Descriptions"


class ProductTableModel(QAbstractTableModel):
    HEADERS = [
        "SKU", "Title", "Brand", "Supplier", "Cost", "RRP", "Stock", "Category", "Image", "Description",
    ]

    def __init__(self, products=None):
        super().__init__()
        self.products = products or []
        self.sort_column = 0
        self.sort_order = Qt.AscendingOrder

    def rowCount(self, parent=QModelIndex()):
        return len(self.products)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        p = self.products[index.row()]

        if role == Qt.DisplayRole:
            return [
                p.sku,
                p.title,
                p.brand,
                p.supplier,
                p.cost,
                p.rrp,
                p.stock,
                p.category,
                p.image_status,
                p.description_status,
            ][index.column()]

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        return self.HEADERS[section] if orientation == Qt.Horizontal else section + 1

    def set_products(self, products):
        self.beginResetModel()
        self.products = products
        self._sort_products()
        self.endResetModel()

    def product_at(self, row):
        return self.products[row] if 0 <= row < len(self.products) else None

    def sort(self, column, order=Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        self.sort_column = column
        self.sort_order = order
        self._sort_products()
        self.layoutChanged.emit()

    def _sort_products(self):
        reverse = self.sort_order == Qt.DescendingOrder

        self.products.sort(
            key=lambda product: self._sort_value(product, self.sort_column),
            reverse=reverse,
        )

    def _sort_value(self, product, column):
        values = [
            product.sku,
            product.title,
            product.brand,
            product.supplier,
            product.cost,
            product.rrp,
            product.stock,
            product.category,
            product.image_status,
            product.description_status,
        ]

        value = values[column]

        if column in (4, 5, 6):
            return self._numeric_value(value)

        return str(value or "").strip().lower()

    def _numeric_value(self, value):
        if value is None:
            return 0

        cleaned = str(value).replace("$", "").replace(",", "").strip()

        try:
            return float(cleaned)
        except ValueError:
            return 0


class CataloguePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = ProductDatabase(PROJECT_ROOT)
        self.all_products = []
        self.filtered_products = []
        self._build_ui()
        self._load_products()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        h = QLabel("Catalogue")
        h.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(h)

        s = QLabel("Search all supplier catalogues by SKU, title, brand, supplier or category.")
        s.setStyleSheet("color:#666;")
        layout.addWidget(s)

        sr = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SKU, partial SKU, brand, title, supplier...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.reload_button = QPushButton("Reload Catalogue")
        self.reload_button.clicked.connect(self._load_products)

        sr.addWidget(self.search_input)
        sr.addWidget(self.reload_button)

        layout.addLayout(sr)

        filter_row_one = QHBoxLayout()

        self.supplier_filter = QComboBox()
        self.supplier_filter.currentTextChanged.connect(self._apply_filter)

        self.brand_filter = QComboBox()
        self.brand_filter.currentTextChanged.connect(self._apply_filter)

        for txt, widget in [
            ("Supplier:", self.supplier_filter),
            ("Brand:", self.brand_filter),
        ]:
            l = QLabel(txt)
            l.setStyleSheet("font-weight:bold;")
            filter_row_one.addWidget(l)
            filter_row_one.addWidget(widget)

        filter_row_one.addStretch()
        layout.addLayout(filter_row_one)

        filter_row_two = QHBoxLayout()

        self.image_filter = QComboBox()
        self.image_filter.currentTextChanged.connect(self._apply_filter)

        self.description_filter = QComboBox()
        self.description_filter.currentTextChanged.connect(self._apply_filter)

        for txt, widget in [
            ("Image:", self.image_filter),
            ("Description:", self.description_filter),
        ]:
            l = QLabel(txt)
            l.setStyleSheet("font-weight:bold;")
            filter_row_two.addWidget(l)
            filter_row_two.addWidget(widget)

        filter_row_two.addStretch()
        layout.addLayout(filter_row_two)

        self.summary_label = QLabel("Products loaded: 0")
        layout.addWidget(self.summary_label)

        self.table_model = ProductTableModel([])

        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open_selected_product)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        widths = [140, 420, 160, 120, 90, 90, 90, 180, 100, 120]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)

        layout.addWidget(self.table)

    def _load_products(self):
        self.all_products = self.database.load()

        if not self.all_products:
            QMessageBox.warning(
                self,
                "Catalogue File Missing",
                "Could not load catalogue data.\\n\\nRun the build pipeline first.",
            )

        self._populate_supplier_filter()
        self._populate_brand_filter()

        self.image_filter.blockSignals(True)
        self.image_filter.clear()
        self.image_filter.addItems([ALL_IMAGES, "Has Image", "Missing Image"])
        self.image_filter.blockSignals(False)

        self.description_filter.blockSignals(True)
        self.description_filter.clear()
        self.description_filter.addItems([ALL_DESCRIPTIONS, "Has Description", "Missing Description"])
        self.description_filter.blockSignals(False)

        self._apply_filter()

    def _populate_supplier_filter(self):
        cur = self.supplier_filter.currentText() if self.supplier_filter.count() else ALL_SUPPLIERS
        vals = sorted({p.supplier.strip() for p in self.all_products if p.supplier and p.supplier.strip()})

        self.supplier_filter.blockSignals(True)
        self.supplier_filter.clear()
        self.supplier_filter.addItem(ALL_SUPPLIERS)
        self.supplier_filter.addItems(vals)
        self.supplier_filter.setCurrentText(
            cur if cur in [self.supplier_filter.itemText(i) for i in range(self.supplier_filter.count())] else ALL_SUPPLIERS
        )
        self.supplier_filter.blockSignals(False)

    def _populate_brand_filter(self):
        cur = self.brand_filter.currentText() if self.brand_filter.count() else ALL_BRANDS
        vals = sorted({p.brand.strip() for p in self.all_products if p.brand and p.brand.strip()})

        self.brand_filter.blockSignals(True)
        self.brand_filter.clear()
        self.brand_filter.addItem(ALL_BRANDS)
        self.brand_filter.addItems(vals)
        self.brand_filter.setCurrentText(
            cur if cur in [self.brand_filter.itemText(i) for i in range(self.brand_filter.count())] else ALL_BRANDS
        )
        self.brand_filter.blockSignals(False)

    def _apply_filter(self):
        products = self.database.search(self.search_input.text())

        sup = self.supplier_filter.currentText()
        br = self.brand_filter.currentText()
        img = self.image_filter.currentText()
        desc = self.description_filter.currentText()

        if sup != ALL_SUPPLIERS:
            products = [p for p in products if (p.supplier or "").strip() == sup]

        if br != ALL_BRANDS:
            products = [p for p in products if (p.brand or "").strip() == br]

        if img == "Has Image":
            products = [p for p in products if str(p.image_status).strip().lower() not in ("", "missing", "no", "none")]
        elif img == "Missing Image":
            products = [p for p in products if str(p.image_status).strip().lower() in ("", "missing", "no", "none")]

        if desc == "Has Description":
            products = [p for p in products if str(p.description_status).strip().lower() not in ("", "missing", "no", "none")]
        elif desc == "Missing Description":
            products = [p for p in products if str(p.description_status).strip().lower() in ("", "missing", "no", "none")]

        self.filtered_products = products
        self.table_model.set_products(products)

        total = len(self.all_products)
        shown = len(products)

        active = (
            bool(self.search_input.text().strip())
            or sup != ALL_SUPPLIERS
            or br != ALL_BRANDS
            or img != ALL_IMAGES
            or desc != ALL_DESCRIPTIONS
        )

        self.summary_label.setText(
            f"Showing {shown:,} of {total:,} products" if active else f"Products loaded: {total:,}"
        )

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        selected_index = self.table.selectionModel().currentIndex()

        if not selected_index.isValid() and index.isValid():
            selected_index = index

        if not selected_index.isValid():
            return

        menu = QMenu(self.table)
        menu.addAction("Copy SKU", lambda: self._copy_sku_from_index(selected_index))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_sku_from_index(self, index):
        product = self.table_model.product_at(index.row())
        if not product:
            return

        sku = str(product.sku or "").strip()
        if not sku:
            return

        QApplication.clipboard().setText(sku)

    def _open_selected_product(self, index):
        p = self.table_model.product_at(index.row())

        if p:
            ProductDetailDialog(p, self).exec()