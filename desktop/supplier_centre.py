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
    QComboBox,
)
from pathlib import Path
from datetime import datetime

from widgets import (
    PageTitle,
    PageSubtitle,
    PrimaryButton,
    SecondaryButton,
)
from dpe_v3.supplier_plugins.loader import discover_plugin_statuses
from core.product.supplier_import_service import SupplierImportService


class SupplierCentrePage(QWidget):

    def __init__(self):
        super().__init__()
        self.supplier_statuses = []
        self.selected_file_path = None
        self.supplier_selector = None
        self.selected_file_info_label = None
        self.validation_result_label = None
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

        # Supplier selector
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(10)
        
        selector_label = QLabel("Select Supplier:")
        selector_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        selector_layout.addWidget(selector_label)
        
        self.supplier_selector = QComboBox()
        self.supplier_selector.setStyleSheet("""
            QComboBox {
                background-color: #1F2937;
                color: #F9FAFB;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
        """)
        self.supplier_selector.setMinimumWidth(200)
        selector_layout.addWidget(self.supplier_selector)
        
        self.refresh_button = SecondaryButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_supplier_statuses)
        selector_layout.addStretch()
        selector_layout.addWidget(self.refresh_button)
        layout.addLayout(selector_layout)

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

        # Selected File Section
        file_title = QLabel("Selected File")
        file_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        layout.addWidget(file_title)

        self.selected_file_info_label = QLabel("No file selected")
        self.selected_file_info_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.selected_file_info_label.setWordWrap(True)
        self.selected_file_info_label.setMaximumHeight(100)
        layout.addWidget(self.selected_file_info_label)

        # Validation Result Section
        self.validation_result_label = QLabel("")
        self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.validation_result_label.setWordWrap(True)
        self.validation_result_label.setMaximumHeight(150)
        self.validation_result_label.hide()
        layout.addWidget(self.validation_result_label)

        # Action Buttons Section
        buttons_title = QLabel("Actions")
        buttons_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        layout.addWidget(buttons_title)

        self.browse_button = SecondaryButton("Browse CSV")
        self.browse_button.setEnabled(True)
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
        self.populate_supplier_selector()

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

    def populate_supplier_selector(self):
        """Populate the supplier selector dropdown."""
        self.supplier_selector.clear()
        for status in self.supplier_statuses:
            self.supplier_selector.addItem(status.supplier_name)

    def _format_display_path(self, file_path: str, max_chars: int = 70) -> str:
        """Format file path for display with ellipsis if too long."""
        if len(file_path) <= max_chars:
            return file_path
        
        # Show last parts of path with ellipsis
        path_parts = file_path.replace("\\", "/").split("/")
        # Try to show at least the filename and one parent directory
        display_path = "/".join(path_parts[-2:])  # e.g., "A1/A1 pricefile.csv"
        if len(display_path) < len(file_path):
            display_path = "..." + display_path
        return display_path

    def on_browse_csv(self):
        """Handler for Browse CSV button - opens file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.selected_file_path = file_path
            self.update_file_info_display()
            # Enable Validate button after file selection
            self.validate_button.setEnabled(True)

    def update_file_info_display(self):
        """Update the display of selected file information."""
        if not self.selected_file_path:
            self.selected_file_info_label.setText("No file selected")
            return
        
        file_path = Path(self.selected_file_path)
        
        if not file_path.exists():
            self.selected_file_info_label.setText(f"File not found: {self.selected_file_path}")
            return
        
        # Get file metadata
        file_stats = file_path.stat()
        file_size_bytes = file_stats.st_size
        file_mtime = file_stats.st_mtime
        
        # Format file size
        if file_size_bytes > 1024 * 1024:
            size_text = f"{file_size_bytes / (1024 * 1024):.2f} MB"
        elif file_size_bytes > 1024:
            size_text = f"{file_size_bytes / 1024:.2f} KB"
        else:
            size_text = f"{file_size_bytes} bytes"
        
        # Format last modified
        last_modified = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # Display info with formatted path
        formatted_path = self._format_display_path(str(file_path))
        info_text = f"""Selected File:  {file_path.name}
Path:  {formatted_path}
File Size:  {size_text}
Last Modified:  {last_modified}"""
        
        self.selected_file_info_label.setText(info_text)
        self.selected_file_info_label.setStyleSheet("color:#10B981; font-size:13px;")

    def on_validate_file(self):
        """Handler for Validate File button - validates the selected file against selected supplier."""
        if not self.selected_file_path:
            self.validation_result_label.setText("❌ No file selected")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()
            self.import_button.setEnabled(False)
            return
        
        # Get selected supplier name from dropdown
        selected_supplier_name = self.supplier_selector.currentText()
        
        # Find the supplier status for this supplier to get expected file path
        expected_file_path = None
        for status in self.supplier_statuses:
            if status.supplier_name == selected_supplier_name:
                expected_file_path = status.input_file
                break
        
        # Validate the file with folder matching
        result = SupplierImportService.validate_selected_file(
            self.selected_file_path,
            selected_supplier_name,
            expected_file_path=expected_file_path
        )
        
        # Display validation result with selected supplier information
        if result.valid:
            result_text = f"""✓ Validation Successful
Selected Supplier:  {selected_supplier_name}
File:  {Path(result.file_path).name}
Encoding:  {result.encoding}
Rows:  {result.row_count}
File Size:  {self._format_file_size(result.file_size_bytes)}"""
            self.validation_result_label.setStyleSheet("color:#10B981; font-size:13px;")
            self.import_button.setEnabled(True)
        else:
            # Format error message to fit width
            error_msg = result.error_message or "Unknown error"
            # Shorten long paths in error messages
            if "Expected:" in error_msg:
                error_msg = error_msg.replace("\\", "/")
                # Extract just the supplier folder name from the path
                parts = error_msg.split("/")
                if len(parts) > 1:
                    expected_folder = parts[-1]  # e.g., "A1"
                    got_folder = "Got:"
                    if "Got:" in error_msg:
                        got_part = error_msg.split("Got:")[1].strip()
                        error_msg = f"Selected file is not in the configured folder for {selected_supplier_name}. Expected: .../{expected_folder}, Got: {got_part}"
            
            result_text = f"""❌ Validation Failed
Selected Supplier:  {selected_supplier_name}
Selected File:  {Path(result.file_path).name}
Error:  {error_msg}"""
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.import_button.setEnabled(False)
        
        self.validation_result_label.setText(result_text)
        self.validation_result_label.show()

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes > 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes > 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"

    def on_import_file(self):
        """Handler for Import Supplier File button (placeholder)."""
        pass
