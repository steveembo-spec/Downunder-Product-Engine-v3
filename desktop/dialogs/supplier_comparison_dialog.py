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
        "Supplier", "SKU", "Brand", "Title", "Cost", "RRP", "Stock", "Image", "Description", "Recommendation",
    ]

    def __init__(self, products=None, preferred_suppliers=None):
        super().__init__()
        self.products = products or []
        self.preferred_suppliers = preferred_suppliers or []
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
            if index.column() == 9:  # Recommendation column
                return self._get_recommendation(p)
            
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
        if column == 9:  # Recommendation column
            # Sort by score (descending), then by recommendation text
            score = self._calculate_score(product)
            return (-score, self._get_recommendation(product))
        
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

    def _calculate_score(self, product):
        """
        Calculate the recommendation score for a product.
        
        Scoring rules:
        - Start with 0 points
        - +100 if supplier is in preferred suppliers list
        - +50 if product is in stock (stock > 0)
        - +25 if has image (image_status not "Missing" or empty)
        - +25 if has description (description_status not "Missing" or empty)
        - +10 if has lowest cost among all matching suppliers
        """
        score = 0
        
        # Check if preferred supplier
        supplier = (product.supplier or "").strip().lower()
        preferred = [s.strip().lower() for s in self.preferred_suppliers]
        if supplier in preferred:
            score += 100
        
        # Check if in stock
        stock_value = self._numeric_value(product.stock)
        if stock_value > 0:
            score += 50
        
        # Check if has image
        image = str(product.image_status or "").strip().lower()
        if image and image not in ("missing", "no", "none", ""):
            score += 25
        
        # Check if has description
        description = str(product.description_status or "").strip().lower()
        if description and description not in ("missing", "no", "none", ""):
            score += 25
        
        # Check if lowest cost
        if self._has_lowest_cost(product):
            score += 10
        
        return score

    def _has_lowest_cost(self, product):
        """Check if this product has the lowest cost among all matching suppliers."""
        if not self.products:
            return False
        
        product_cost = self._numeric_value(product.cost)
        
        for other in self.products:
            other_cost = self._numeric_value(other.cost)
            # If another product has lower cost, return False
            if other_cost < product_cost:
                return False
            # If same cost but different supplier, only one can be "lowest"
            if other_cost == product_cost and other.supplier != product.supplier:
                # Use supplier order as tiebreaker (first in list wins)
                if self.products.index(other) < self.products.index(product):
                    return False
        
        return True

    def _get_recommendation(self, product):
        """
        Determine the recommendation text based on product data and score.
        
        Rules:
        - If stock <= 0: "Out of Stock"
        - If highest score: "⭐ Recommended"
        - Otherwise: "Good Alternative"
        """
        # Check if out of stock
        stock_value = self._numeric_value(product.stock)
        if stock_value <= 0:
            return "Out of Stock"
        
        # Check if has highest score
        product_score = self._calculate_score(product)
        max_score = max(self._calculate_score(p) for p in self.products) if self.products else 0
        
        if product_score == max_score and max_score > 0:
            return "⭐ Recommended"
        
        return "Good Alternative"


class SupplierComparisonDialog(QDialog):
    """Dialog for comparing products across suppliers for a given SKU."""
    
    # Supplier priority configuration - can be expanded later
    PREFERRED_SUPPLIERS = [
        "A1",
        "Cassons",
        "Link",
    ]
    
    def __init__(self, sku: str, database: ProductDatabase, parent=None):
        super().__init__(parent)
        
        self.sku = sku
        self.database = database
        
        self.setWindowTitle(f"Supplier Comparison - {sku}")
        self.resize(1500, 600)
        
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        title = QLabel(f"Supplier Comparison for SKU: {self.sku}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Table
        self.table_model = SupplierComparisonTableModel([], self.PREFERRED_SUPPLIERS)
        
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        
        # Set column widths (now including Recommendation)
        widths = [120, 140, 160, 350, 90, 90, 90, 100, 120, 140]
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
