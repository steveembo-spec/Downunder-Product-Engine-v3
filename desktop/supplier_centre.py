from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
)

from widgets import (
    PageTitle,
    PageSubtitle,
    PrimaryButton,
    SecondaryButton,
)
from dpe_v3.supplier_plugins.loader import discover_plugin_statuses


class SupplierCentrePage(QWidget):

    def __init__(self):
        super().__init__()
        self.supplier_statuses = []
        self.build_ui()
        self.refresh_supplier_statuses()

    def build_ui(self):
        """Build the Supplier Centre UI shell."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(24)

        # Header
        layout.addWidget(PageTitle("Supplier Centre"))
        layout.addWidget(PageSubtitle(
            "Import and validate supplier catalogue files before synchronising the Master Product Database."
        ))

        # Configured Suppliers Section
        suppliers_title = QLabel("Configured Suppliers")
        suppliers_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        layout.addWidget(suppliers_title)

        # Suppliers table header layout
        table_header = QHBoxLayout()
        table_header.setSpacing(10)
        
        self.refresh_button = SecondaryButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_supplier_statuses)
        table_header.addStretch()
        table_header.addWidget(self.refresh_button)
        layout.addLayout(table_header)

        # Suppliers table
        self.suppliers_table = QTableWidget()
        self.suppliers_table.setColumnCount(6)
        self.suppliers_table.setHorizontalHeaderLabels([
            "Supplier Name",
            "Enabled",
            "File Exists",
            "File Size (KB)",
            "Last Modified",
            "Status"
        ])
        self.suppliers_table.setStyleSheet("""
            QTableWidget {
                background-color: #1F2937;
                gridline-color: #374151;
                border: 1px solid #374151;
                border-radius: 8px;
            }
            QTableWidget::item {
                padding: 8px;
                color: #F9FAFB;
            }
            QHeaderView::section {
                background-color: #111827;
                color: #F9FAFB;
                padding: 8px;
                border: none;
                font-weight: 700;
            }
        """)
        self.suppliers_table.setMinimumHeight(300)
        layout.addWidget(self.suppliers_table)

        # Action Buttons Section (disabled for now)
        buttons_title = QLabel("Actions")
        buttons_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        layout.addWidget(buttons_title)

        self.browse_button = SecondaryButton("Browse CSV")
        self.browse_button.setEnabled(False)
        self.browse_button.clicked.connect(self.on_browse_csv)
        layout.addWidget(self.browse_button)

        self.validate_button = SecondaryButton("Validate File")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self.on_validate_file)
        layout.addWidget(self.validate_button)

        self.import_button = PrimaryButton("Import Supplier File")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.on_import_file)
        layout.addWidget(self.import_button)

        layout.addStretch()

    def refresh_supplier_statuses(self):
        """Refresh the supplier statuses from the loader."""
        self.supplier_statuses = discover_plugin_statuses()
        self.populate_suppliers_table()

    def populate_suppliers_table(self):
        """Populate the suppliers table with current statuses."""
        self.suppliers_table.setRowCount(len(self.supplier_statuses))

        for row, status in enumerate(self.supplier_statuses):
            # Supplier Name
            name_item = QTableWidgetItem(status.supplier_name)
            name_item.setForeground(self._get_color_for_status(status.enabled))
            self.suppliers_table.setItem(row, 0, name_item)

            # Enabled
            enabled_text = "✓ Yes" if status.enabled else "✗ No"
            enabled_item = QTableWidgetItem(enabled_text)
            enabled_item.setForeground(self._get_color_for_status(status.enabled))
            self.suppliers_table.setItem(row, 1, enabled_item)

            # File Exists
            file_exists_text = "✓ Yes" if status.file_exists else "✗ No"
            file_exists_item = QTableWidgetItem(file_exists_text)
            file_exists_item.setForeground(self._get_color_for_status(status.file_exists))
            self.suppliers_table.setItem(row, 2, file_exists_item)

            # File Size
            if status.file_size_kb > 0:
                if status.file_size_kb > 1024:
                    size_text = f"{status.file_size_kb / 1024:.2f} MB"
                else:
                    size_text = f"{status.file_size_kb:.2f} KB"
            else:
                size_text = "N/A"
            size_item = QTableWidgetItem(size_text)
            self.suppliers_table.setItem(row, 3, size_item)

            # Last Modified
            modified_item = QTableWidgetItem(status.last_modified)
            self.suppliers_table.setItem(row, 4, modified_item)

            # Status
            status_item = QTableWidgetItem(status.status)
            status_item.setForeground(self._get_color_for_status_text(status.status))
            self.suppliers_table.setItem(row, 5, status_item)

        # Resize columns to content
        self.suppliers_table.resizeColumnsToContents()

    def _get_color_for_status(self, is_valid: bool):
        """Get color based on boolean status."""
        from PySide6.QtGui import QColor
        return QColor("#10B981") if is_valid else QColor("#EF4444")  # Green or Red

    def _get_color_for_status_text(self, status_text: str):
        """Get color based on status text."""
        from PySide6.QtGui import QColor
        if "Enabled" in status_text and "missing" not in status_text:
            return QColor("#10B981")  # Green
        elif "missing" in status_text or "error" in status_text.lower():
            return QColor("#EF4444")  # Red
        else:
            return QColor("#9CA3AF")  # Gray

    def on_browse_csv(self):
        """Handler for Browse CSV button (disabled for now)."""
        pass

    def on_validate_file(self):
        """Handler for Validate File button (disabled for now)."""
        pass

    def on_import_file(self):
        """Handler for Import Supplier File button (disabled for now)."""
        pass
