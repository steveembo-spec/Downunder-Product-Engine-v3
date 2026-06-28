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
)

from core.product_database import ProductDatabase, ProductRecord
from desktop.dialogs.product_detail_dialog import ProductDetailDialog


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALL_SUPPLIERS = "All Suppliers"


class ProductTableModel(QAbstractTableModel):
    HEADERS = [
        "SKU",
        "Title",
        "Brand",
        "Supplier",
        "Cost",
        "RRP",
        "Stock",
        "Category",
        "Image",
        "Description",
    ]

    def __init__(self, products: list[ProductRecord] | None = None):
        super().__init__()
        self.products = products or []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.products)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        product = self.products[index.row()]

        if role == Qt.DisplayRole:
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
            return values[index.column()]

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.HEADERS[section]

        return section + 1

    def set_products(self, products: list[ProductRecord]) -> None:
        self.beginResetModel()
        self.products = products
        self.endResetModel()

    def product_at(self, row: int) -> ProductRecord | None:
        if row < 0 or row >= len(self.products):
            return None
        return self.products[row]


class CataloguePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.database = ProductDatabase(PROJECT_ROOT)

        self.all_products: list[ProductRecord] = []
        self.filtered_products: list[ProductRecord] = []

        self._build_ui()
        self._load_products()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Catalogue")
        heading.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(heading)

        subtitle = QLabel("Search all supplier catalogues by SKU, title, brand, supplier or category.")
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SKU, partial SKU, brand, title, supplier...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.reload_button = QPushButton("Reload Catalogue")
        self.reload_button.clicked.connect(self._load_products)

        search_row.addWidget(self.search_input)
        search_row.addWidget(self.reload_button)

        layout.addLayout(search_row)

        filter_row = QHBoxLayout()

        supplier_label = QLabel("Supplier:")
        supplier_label.setStyleSheet("font-weight: bold;")

        self.supplier_filter = QComboBox()
        self.supplier_filter.currentTextChanged.connect(self._apply_filter)

        filter_row.addWidget(supplier_label)
        filter_row.addWidget(self.supplier_filter)
        filter_row.addStretch()

        layout.addLayout(filter_row)

        self.summary_label = QLabel("Products loaded: 0")
        layout.addWidget(self.summary_label)

        self.table_model = ProductTableModel([])
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.doubleClicked.connect(self._open_selected_product)

        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 420)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 180)
        self.table.setColumnWidth(8, 100)
        self.table.setColumnWidth(9, 120)

        layout.addWidget(self.table)

        button_row = QHBoxLayout()

        self.open_shopify_button = QPushButton("Open Shopify Product")
        self.edit_product_button = QPushButton("Edit Product")
        self.rebuild_description_button = QPushButton("Rebuild Description")
        self.find_image_button = QPushButton("Find Image")
        self.export_selected_button = QPushButton("Export Selected")

        for button in [
            self.open_shopify_button,
            self.edit_product_button,
            self.rebuild_description_button,
            self.find_image_button,
            self.export_selected_button,
        ]:
            button.setEnabled(False)
            button_row.addWidget(button)

        layout.addLayout(button_row)

    def _load_products(self) -> None:
        self.all_products = self.database.load()

        if not self.all_products:
            QMessageBox.warning(
                self,
                "Catalogue File Missing",
                "Could not load catalogue data.\n\nRun the build pipeline first.",
            )

        self._populate_supplier_filter()
        self._apply_filter()

    def _populate_supplier_filter(self) -> None:
        current_supplier = (
            self.supplier_filter.currentText()
            if self.supplier_filter.count()
            else ALL_SUPPLIERS
        )

        suppliers = sorted({
            product.supplier.strip()
            for product in self.all_products
            if product.supplier and product.supplier.strip()
        })

        self.supplier_filter.blockSignals(True)
        self.supplier_filter.clear()
        self.supplier_filter.addItem(ALL_SUPPLIERS)

        for supplier in suppliers:
            self.supplier_filter.addItem(supplier)

        if current_supplier in [
            self.supplier_filter.itemText(i)
            for i in range(self.supplier_filter.count())
        ]:
            self.supplier_filter.setCurrentText(current_supplier)
        else:
            self.supplier_filter.setCurrentText(ALL_SUPPLIERS)

        self.supplier_filter.blockSignals(False)

    def _apply_filter(self) -> None:
        query = self.search_input.text()
        selected_supplier = self.supplier_filter.currentText()

        products = self.database.search(query)

        if selected_supplier and selected_supplier != ALL_SUPPLIERS:
            products = [
                product
                for product in products
                if product.supplier and product.supplier.strip() == selected_supplier
            ]

        self.filtered_products = products
        self.table_model.set_products(self.filtered_products)
        self._update_summary()

    def _update_summary(self) -> None:
        total = len(self.all_products)
        shown = len(self.filtered_products)

        supplier = self.supplier_filter.currentText()
        search_active = bool(self.search_input.text().strip())
        supplier_active = supplier and supplier != ALL_SUPPLIERS

        if search_active or supplier_active:
            self.summary_label.setText(f"Showing {shown:,} of {total:,} products")
        else:
            self.summary_label.setText(f"Products loaded: {total:,}")

    def _open_selected_product(self, index: QModelIndex) -> None:
        product = self.table_model.product_at(index.row())

        if not product:
            return

        dialog = ProductDetailDialog(product, self)
        dialog.exec()