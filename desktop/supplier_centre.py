from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QScrollArea,
)
from PySide6.QtGui import QShowEvent
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
from core.product.master_product_service import MasterProductService


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

    def showEvent(self, event: QShowEvent):
        """Handle show event to refresh table rendering when page becomes visible."""
        super().showEvent(event)
        # Force table to update its viewport when the page becomes visible
        # This ensures the table is properly rendered in PyInstaller bundled exe
        if hasattr(self, 'suppliers_table'):
            self.suppliers_table.viewport().update()
            self.suppliers_table.update()

    def build_ui(self):
        """Build the Supplier Centre UI with scrollable content area."""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(24)

        # Header (fixed at top, not scrollable)
        main_layout.addWidget(PageTitle("Supplier Centre"))
        main_layout.addWidget(PageSubtitle(
            "Import supplier catalogue files and synchronise the Master Product Database. "
            "Only suppliers with a configured supplier plugin can be imported."
        ))

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #111827;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #374151;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4B5563;
            }
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container widget for scroll area
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(24)

        # Configured Suppliers Section
        suppliers_title = QLabel("Configured Supplier Plugins")
        suppliers_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        scroll_layout.addWidget(suppliers_title)

        plugin_note = QLabel("Only configured suppliers with a supplier plugin can be imported.")
        plugin_note.setStyleSheet("color:#9CA3AF; font-size:12px; font-style:italic;")
        plugin_note.setWordWrap(True)
        scroll_layout.addWidget(plugin_note)

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
        scroll_layout.addLayout(selector_layout)

        # Suppliers table (reduced height for scroll area)
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
        self.suppliers_table.setMinimumHeight(200)
        scroll_layout.addWidget(self.suppliers_table)

        # Selected File Section
        file_title = QLabel("Selected File")
        file_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        scroll_layout.addWidget(file_title)

        self.selected_file_info_label = QLabel("No file selected")
        self.selected_file_info_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.selected_file_info_label.setWordWrap(True)
        self.selected_file_info_label.setMaximumHeight(100)
        scroll_layout.addWidget(self.selected_file_info_label)

        # Validation / Status Section
        self.validation_result_label = QLabel("")
        self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.validation_result_label.setWordWrap(True)
        self.validation_result_label.setMaximumHeight(350)
        self.validation_result_label.hide()
        scroll_layout.addWidget(self.validation_result_label)

        # Action Buttons Section
        buttons_title = QLabel("Actions")
        buttons_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        scroll_layout.addWidget(buttons_title)

        self.browse_button = SecondaryButton("Browse CSV")
        self.browse_button.setEnabled(True)
        self.browse_button.clicked.connect(self.on_browse_csv)
        scroll_layout.addWidget(self.browse_button)

        self.validate_button = SecondaryButton("Validate File")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self.on_validate_file)
        scroll_layout.addWidget(self.validate_button)

        self.import_button = PrimaryButton("Import Supplier File")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.on_import_file)
        scroll_layout.addWidget(self.import_button)

        scroll_layout.addStretch()

        # Set the scroll area's widget and add to main layout
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

    def refresh_supplier_statuses(self):
        """Refresh the supplier statuses from the loader."""
        try:
            self.supplier_statuses = discover_plugin_statuses()
            self.populate_suppliers_table()
            self.populate_supplier_selector()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def populate_suppliers_table(self):
        """Populate the suppliers table with current statuses."""
        self.suppliers_table.setRowCount(len(self.supplier_statuses))

        try:
            for row, status in enumerate(self.supplier_statuses):
                try:
                    # Supplier Name
                    name_item = QTableWidgetItem(status.supplier_name)
                    name_item.setForeground(self._get_color_for_status(status.enabled))
                    self.suppliers_table.setItem(row, 0, name_item)

                    # Enabled
                    enabled_text = "Yes" if status.enabled else "No"
                    enabled_item = QTableWidgetItem(enabled_text)
                    enabled_item.setForeground(self._get_color_for_status(status.enabled))
                    self.suppliers_table.setItem(row, 1, enabled_item)

                    # File Exists
                    file_exists_text = "Yes" if status.file_exists else "No"
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
                except Exception as e:
                    import traceback
                    traceback.print_exc()

            # Resize columns to content
            self.suppliers_table.resizeColumnsToContents()
        except Exception as e:
            import traceback
            traceback.print_exc()

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
        
        # Display info (shorten path to prevent horizontal scrolling)
        path_str = str(file_path).replace("\\", "/")
        path_parts = path_str.split("/")
        # Show last two parts (folder/filename) with ellipsis if path is longer
        if len(path_parts) > 2:
            shortened_path = ".../" + "/".join(path_parts[-2:])
        else:
            shortened_path = path_str
        
        info_text = f"""Selected File:  {file_path.name}
Path:  {shortened_path}
File Size:  {size_text}
Last Modified:  {last_modified}"""
        
        self.selected_file_info_label.setText(info_text)
        self.selected_file_info_label.setStyleSheet("color:#10B981; font-size:13px;")

    def on_validate_file(self):
        """Validate file and display a full validation summary including destination and archive paths."""
        if not self.selected_file_path:
            self.validation_result_label.setText("ERROR: No file selected")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()
            self.import_button.setEnabled(False)
            return

        selected_supplier_name = self.supplier_selector.currentText()

        # Step 1: validate the file
        result = SupplierImportService.validate_selected_file(
            self.selected_file_path,
            selected_supplier_name,
        )

        if not result.valid:
            error_msg = result.error_message or "Unknown error"
            if "Expected:" in error_msg:
                error_msg = error_msg.replace("\\", "/")
                parts = error_msg.split("/")
                if len(parts) > 1 and "Got:" in error_msg:
                    expected_folder = parts[-1]
                    got_part = error_msg.split("Got:")[1].strip()
                    error_msg = (
                        f"File is not in the configured folder for {selected_supplier_name}. "
                        f"Expected: .../{expected_folder}, Got: {got_part}"
                    )
            result_text = (
                f"ERROR: Validation Failed\n"
                f"Supplier:       {selected_supplier_name}\n"
                f"File:           {Path(result.file_path).name}\n"
                f"Error:          {error_msg}"
            )
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.setText(result_text)
            self.validation_result_label.show()
            self.import_button.setEnabled(False)
            return

        # Step 2: dry-run install to discover destination and archive paths
        preview = SupplierImportService.install_validated_file(
            self.selected_file_path,
            selected_supplier_name,
            dry_run=True,
        )

        dest_name = Path(preview.destination_file).name if preview.destination_file else "(unknown)"
        dest_short = self._shorten_path(preview.destination_file)
        archive_short = self._shorten_path(preview.archived_file) if preview.archived_file else "(no existing file to archive)"

        row_count_fmt = f"{result.row_count:,}"
        size_fmt = self._format_file_size(result.file_size_bytes)

        result_text = (
            f"SUCCESS: Validation Summary\n"
            f"\n"
            f"Supplier:       {selected_supplier_name}\n"
            f"Selected File:  {Path(result.file_path).name}\n"
            f"Destination:    {dest_short}\n"
            f"Archive Target: {archive_short}\n"
            f"Encoding:       {result.encoding}\n"
            f"Rows:           {row_count_fmt}\n"
            f"File Size:      {size_fmt}\n"
            f"\n"
            f"Ready to import - click \"Import Supplier File\" to proceed."
        )
        self.validation_result_label.setStyleSheet("color:#10B981; font-size:13px;")
        self.validation_result_label.setText(result_text)
        self.validation_result_label.show()
        self.import_button.setEnabled(True)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes > 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes > 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"

    def _shorten_path(self, path_str: str) -> str:
        """Shorten a path to last two parts with ellipsis to avoid horizontal overflow."""
        if not path_str:
            return ""
        parts = str(path_str).replace("\\", "/").split("/")
        if len(parts) > 2:
            return "../" + "/".join(parts[-2:])
        return path_str

    def on_import_file(self):
        """Archive existing supplier CSV, install selected file, sync Master Product Database."""
        if not self.selected_file_path:
            self.validation_result_label.setText("ERROR: No file selected for import")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()
            return

        selected_supplier_name = self.supplier_selector.currentText()

        # Step 1: Live import - archive existing file and copy selected file into place
        self.validation_result_label.setText("IMPORTING: supplier file...")
        self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.validation_result_label.show()
        self.import_button.setEnabled(False)

        import_result = SupplierImportService.install_validated_file(
            self.selected_file_path,
            selected_supplier_name,
            dry_run=False,
        )

        if not import_result.success:
            result_text = (
                f"ERROR: Import Failed\n"
                f"Supplier:  {import_result.supplier_name}\n"
                f"Error:     {import_result.error_message}"
            )
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.setText(result_text)
            self.validation_result_label.show()
            self.import_button.setEnabled(True)
            return

        # Step 2: Synchronise Master Product Database via existing pipeline
        self.validation_result_label.setText("IMPORTING: Synchronising Master Product Database...")
        self.validation_result_label.show()

        try:
            service = MasterProductService()
            sync_stats = service.sync_from_supplier_loader()
            total_products = service.count_master_products()
        except Exception as exc:
            result_text = (
                f"WARNING: File Imported - Database Sync Failed\n"
                f"Supplier:   {import_result.supplier_name}\n"
                f"Installed:  {Path(import_result.destination_file).name}\n"
                f"Error:      {exc}"
            )
            self.validation_result_label.setStyleSheet("color:#F59E0B; font-size:13px;")
            self.validation_result_label.setText(result_text)
            self.validation_result_label.show()
            self.refresh_supplier_statuses()
            return

        # Step 3: Build completion summary from real stats
        added = sync_stats.get('master_products_added', 0)
        skipped = sync_stats.get('master_products_skipped', 0)
        sp_added = sync_stats.get('supplier_products_added', 0)
        sp_skipped = sync_stats.get('supplier_products_skipped', 0)

        archive_line = ""
        if import_result.archived_file:
            archive_line = f"Archived:                  {Path(import_result.archived_file).name}\n"

        result_text = (
            f"SUCCESS: Supplier Import Complete\n"
            f"\n"
            f"Supplier:                  {import_result.supplier_name}\n"
            f"Installed:                 {Path(import_result.destination_file).name}\n"
            f"{archive_line}"
            f"\n"
            f"New Master Products:       {added:,}\n"
            f"Existing (Skipped):        {skipped:,}\n"
            f"New Supplier Products:     {sp_added:,}\n"
            f"Existing (Skipped):        {sp_skipped:,}\n"
            f"Master Products Total:     {total_products:,}\n"
            f"\n"
            f"Database Synchronised\n"
            f"Ready for Build Centre"
        )
        self.validation_result_label.setStyleSheet("color:#10B981; font-size:13px;")
        self.validation_result_label.setText(result_text)
        self.validation_result_label.show()

        # Step 4: Refresh supplier status table
        self.refresh_supplier_statuses()

