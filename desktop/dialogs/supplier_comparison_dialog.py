from __future__ import annotations

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
)

from core.product_database import ProductDatabase


class SupplierComparisonTableModel(QAbstractTableModel):
    """Table model for displaying supplier comparison data."""
    
    HEADERS = [
        "Supplier", "SKU", "Brand", "Title", "Cost", "RRP", "Stock", "Image", "Description",
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
                p.supplier,
                p.sku,
                p.brand,
                p.title,
                p.cost,
                p.rrp,
                p.stock,
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
            product.supplier,
            product.sku,
            product.brand,
            product.title,
            product.cost,
            product.rrp,
            product.stock,
            product.image_status,
            product.description_status,
        ]

        value = values[column]

        # Numeric columns: Cost (4), RRP (5), Stock (6)
        if column in (4, 5, 6):
            return self._numeric_value(value)

        return str(value or "").strip().lower()

    @staticmethod
    def _numeric_value(value):
        if value is None:
            return 0

        cleaned = str(value).replace("$", "").replace(",", "").strip()

        try:
            return float(cleaned)
        except ValueError:
            return 0


class SupplierComparisonDialog(QDialog):
    """Dialog for comparing products across suppliers for a given SKU."""
    
    def __init__(self, sku: str, database: ProductDatabase, parent=None):
        super().__init__(parent)
        
        self.sku = sku
        self.database = database
        
        self.setWindowTitle(f"Supplier Comparison - {sku}")
        self.resize(1400, 600)
        
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        title = QLabel(f"Supplier Comparison for SKU: {self.sku}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Table
        self.table_model = SupplierComparisonTableModel([])
        
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        
        # Set column widths
        widths = [120, 140, 160, 350, 90, 90, 90, 100, 120]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        
        layout.addWidget(self.table)
        
        # Button row
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _load_data(self):
        """Search the database for all products matching the SKU."""
        # Search for all products with this SKU
        all_products = self.database.load()
        matching_products = [p for p in all_products if (p.sku or "").strip() == self.sku.strip()]
        
        # Sort by supplier
        matching_products.sort(key=lambda p: (p.supplier or "").strip().lower())
        
        self.table_model.set_products(matching_products)
