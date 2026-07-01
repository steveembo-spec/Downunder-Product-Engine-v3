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
from desktop.dialogs.supplier_comparison_dialog import SupplierComparisonDialog


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# SPRINT 7.2: Load products from MasterProductService instead of CSV
# Set to False to use original CSV ProductDatabase
TEST_MODE_USE_MASTER_PRODUCTS = True
TEST_MODE_LIMIT = 1000  # 1000 products for validation, None = all, or set to N to limit
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
        # Always instantiate ProductDatabase (no validation happens in __init__)
        # Validation (CSV file check) only happens in load(), which we skip in TEST_MODE
        # This keeps dialogs working when they need to access self.database
        self.database = ProductDatabase(PROJECT_ROOT)
        self.all_products = []
        self.filtered_products = []
        self._build_ui()
        self._load_products()

    def _load_from_master_products(self):
        """Smoke test: Load first 10 products from MasterProductService.
        
        This is a minimal test to verify MasterProductService can populate
        the Catalogue table without changes to dialogs or filters.
        
        Database stores supplier_cost and supplier_rrp as TEXT, so they must
        be converted to float before formatting as currency.
        
        Returns:
            List of ProductRecord objects (compatible with existing code)
        """
        def format_currency(value_str):
            """Safely convert TEXT value to formatted currency string.
            
            Args:
                value_str: Value from database (may be TEXT, None, or invalid)
                
            Returns:
                Formatted string like "$20.25" or empty string
            """
            if not value_str:
                return ""
            
            try:
                float_value = float(value_str)
                if float_value > 0:
                    return f"${float_value:.2f}"
                return ""
            except (ValueError, TypeError):
                # If conversion fails, return as-is (shouldn't happen with valid data)
                return str(value_str) if value_str else ""
        
        try:
            from core.product.master_product_service import MasterProductService
            
            service = MasterProductService(PROJECT_ROOT)
            
            # Load master products from database
            # If TEST_MODE_LIMIT is None, load all; otherwise limit to first N
            master_products = service.list_master_products() if TEST_MODE_LIMIT is None else service.list_master_products(limit=TEST_MODE_LIMIT)
            
            products = []
            skipped = 0
            
            # Build supplier name cache
            conn = service.get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, supplier_name FROM suppliers")
                supplier_map = {row[0]: row[1] for row in cur.fetchall()}
            finally:
                conn.close()
            
            # Convert to ProductRecord format (same as CSV)
            for master in master_products:
                # Get supplier products for this master SKU
                supplier_products = service.list_supplier_products_for_sku(master.sku)
                
                if not supplier_products:
                    # No suppliers - create default record
                    try:
                        products.append(ProductRecord(
                            sku=master.sku,
                            title=master.title or "",
                            supplier="",
                            cost="",
                            rrp="",
                            stock="",
                            brand=master.brand or "",
                            category=master.category or "",
                            image_status="Unknown",
                            description_status=master.description_status or "",
                            margin="",
                            raw={"sku": master.sku, "title": master.title}
                        ))
                    except Exception as e:
                        print(f"⚠ Warning: Skipped product {master.sku}: {e}")
                        skipped += 1
                else:
                    # Create one ProductRecord per supplier (flattened)
                    for sp in supplier_products:
                        try:
                            supplier_name = supplier_map.get(sp.supplier_id, "")
                            # Use format_currency to safely convert TEXT to formatted string
                            cost = format_currency(sp.supplier_cost)
                            rrp = format_currency(sp.supplier_rrp)
                            
                            products.append(ProductRecord(
                                sku=master.sku,
                                title=master.title or "",
                                supplier=supplier_name,
                                cost=cost,
                                rrp=rrp,
                                stock=str(sp.supplier_stock or 0),
                                brand=master.brand or "",
                                category=master.category or "",
                                image_status="Unknown",
                                description_status=master.description_status or "",
                                margin="",
                                raw={"sku": master.sku, "title": master.title}
                            ))
                        except Exception as e:
                            print(f"⚠ Warning: Skipped supplier variant for {master.sku}: {e}")
                            skipped += 1
                            continue
            
            result_msg = f"✓ Smoke test: Loaded {len(products)} product records from MasterProductService"
            if skipped > 0:
                result_msg += f" ({skipped} skipped due to data issues)"
            print(result_msg)
            
            return products
            
        except Exception as e:
            print(f"✗ Smoke test failed: {e}")
            import traceback
            traceback.print_exc()
            return []

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
        # SMOKE TEST: Use MasterProductService if TEST_MODE enabled
        if TEST_MODE_USE_MASTER_PRODUCTS:
            self.all_products = self._load_from_master_products()
            # In TEST_MODE, don't show error if no products - database may not be populated yet
            if not self.all_products:
                print("⚠ Warning: Smoke test loaded 0 products (database may be empty)")
        else:
            self.all_products = self.database.load()
            # In normal mode, show error if no products
            if not self.all_products:
                QMessageBox.warning(
                    self,
                    "Catalogue File Missing",
                    "Could not load catalogue data.\n\nRun the build pipeline first.",
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

    def _search_products(self, query):
        """Search products by query string.
        
        Works with both TEST_MODE (MasterProductService) and normal mode (CSV).
        Searches SKU, title, brand, supplier, and category.
        """
        query = query.strip().lower()
        
        if not query:
            return self.all_products
        
        results = []
        for product in self.all_products:
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

    def _apply_filter(self):
        products = self._search_products(self.search_input.text())

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
        menu.addAction("Supplier Comparison", lambda: self._show_supplier_comparison(selected_index))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_sku_from_index(self, index):
        product = self.table_model.product_at(index.row())
        if not product:
            return

        sku = str(product.sku or "").strip()
        if not sku:
            return

        QApplication.clipboard().setText(sku)

    def _show_supplier_comparison(self, index):
        product = self.table_model.product_at(index.row())
        if not product:
            return

        sku = str(product.sku or "").strip()
        if not sku:
            return

        SupplierComparisonDialog(sku, self.database, self).exec()

    def _open_selected_product(self, index):
        p = self.table_model.product_at(index.row())

        if p:
            ProductDetailDialog(p, self).exec()