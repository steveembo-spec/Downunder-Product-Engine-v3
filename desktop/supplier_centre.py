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
    QLineEdit,
    QDialog,
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
from core.product.supplier_centre_workflow_service import SupplierCentreWorkflowService
from dialogs.supplier_mapping_dialog import SupplierMappingDialog


class SupplierCentrePage(QWidget):

    def __init__(self):
        super().__init__()
        self.supplier_statuses = []
        self.selected_file_path = None
        self.supplier_selector = None
        self.custom_supplier_name_input = None
        self.selected_file_info_label = None
        self.validation_result_label = None
        self.workflow_service = SupplierCentreWorkflowService()
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
            "Import supplier product files to the Master Product Database. "
            "Use configured supplier plugins or import generic suppliers via CSV."
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

        # Generic/Custom Supplier Section
        generic_title = QLabel("Generic Supplier (Custom Import)")
        generic_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        scroll_layout.addWidget(generic_title)

        generic_note = QLabel("Import any CSV file as a new supplier without needing a plugin.")
        generic_note.setStyleSheet("color:#9CA3AF; font-size:12px; font-style:italic;")
        generic_note.setWordWrap(True)
        scroll_layout.addWidget(generic_note)

        generic_input_layout = QHBoxLayout()
        generic_input_layout.setSpacing(10)

        generic_label = QLabel("Supplier Name:")
        generic_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        generic_input_layout.addWidget(generic_label)

        self.custom_supplier_name_input = QLineEdit()
        self.custom_supplier_name_input.setPlaceholderText("e.g., My Supplier, Test Supplier")
        self.custom_supplier_name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1F2937;
                color: #F9FAFB;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.custom_supplier_name_input.setMinimumWidth(300)
        generic_input_layout.addWidget(self.custom_supplier_name_input)
        generic_input_layout.addStretch()
        scroll_layout.addLayout(generic_input_layout)

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

        self.export_shopify_button = SecondaryButton("Export Shopify CSV")
        self.export_shopify_button.setEnabled(True)
        self.export_shopify_button.clicked.connect(self.on_export_shopify)
        scroll_layout.addWidget(self.export_shopify_button)

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
        """Validate selected file using workflow service."""
        if not self.selected_file_path:
            self.validation_result_label.setText("ERROR: No file selected")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()
            self.import_button.setEnabled(False)
            return

        custom_name = self.custom_supplier_name_input.text().strip()
        supplier_name = custom_name if custom_name else self.supplier_selector.currentText()

        result = self.workflow_service.validate_file(supplier_name, self.selected_file_path)

        # Check if mapping confirmation dialog is needed
        if result.action_type == "confirm_mapping" and result.validation_data:
            self._show_mapping_confirmation_dialog(
                supplier_name=result.validation_data.get("supplier_name"),
                file_path=result.validation_data.get("file_path"),
                headers=result.validation_data.get("headers", []),
                detected_mapping=result.validation_data.get("detected_mapping", {}),
            )
            return

        # Normal validation result display
        self.validation_result_label.setText(
            f"{result.title}\n\n{result.message}"
        )
        self.validation_result_label.setStyleSheet(f"color:{result.status_color}; font-size:13px;")
        self.validation_result_label.show()
        self.import_button.setEnabled(result.success)

    def _show_mapping_confirmation_dialog(
        self,
        supplier_name: str,
        file_path: str,
        headers: list[str],
        detected_mapping: dict,
    ):
        """Show the mapping confirmation dialog for a supplier."""
        try:
            dialog = SupplierMappingDialog(
                supplier_name=supplier_name,
                file_name=Path(file_path).name,
                headers=headers,
                detected_mapping=detected_mapping,
                parent=self,
            )

            # Call exec() once and store the result
            dialog_result = dialog.exec()
            
            if dialog_result == QDialog.Accepted:
                # User confirmed the mapping
                confirmed_mapping = dialog.get_confirmed_mapping()
                remember_mapping = dialog.should_remember()

                # Show import progress
                self.validation_result_label.setText("IMPORTING: Processing supplier file...")
                self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
                self.validation_result_label.show()
                self.import_button.setEnabled(False)

                # Call workflow service to save profile and import
                result = self.workflow_service.confirm_mapping_and_import(
                    supplier_name=supplier_name,
                    file_path=file_path,
                    confirmed_mapping=confirmed_mapping,
                    remember_mapping=remember_mapping,
                )

                # Display import result
                self.validation_result_label.setText(
                    f"{result.title}\n\n{result.message}"
                )
                self.validation_result_label.setStyleSheet(f"color:{result.status_color}; font-size:13px;")
                self.validation_result_label.show()

                # Refresh supplier status table for managed imports
                if self.workflow_service._is_managed_supplier(supplier_name):
                    self.refresh_supplier_statuses()
        except Exception as e:
            self.validation_result_label.setText(f"ERROR: {type(e).__name__}: {e}")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()

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
        """Import supplier file using workflow service."""
        if not self.selected_file_path:
            self.validation_result_label.setText("ERROR: No file selected for import")
            self.validation_result_label.setStyleSheet("color:#EF4444; font-size:13px;")
            self.validation_result_label.show()
            return

        custom_name = self.custom_supplier_name_input.text().strip()
        supplier_name = custom_name if custom_name else self.supplier_selector.currentText()

        self.validation_result_label.setText("IMPORTING: Processing supplier file...")
        self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.validation_result_label.show()
        self.import_button.setEnabled(False)

        result = self.workflow_service.import_file(supplier_name, self.selected_file_path)

        # Display result
        self.validation_result_label.setText(
            f"{result.title}\n\n{result.message}"
        )
        self.validation_result_label.setStyleSheet(f"color:{result.status_color}; font-size:13px;")
        self.validation_result_label.show()

        # Refresh supplier status table for managed imports
        if self.workflow_service._is_managed_supplier(supplier_name):
            self.refresh_supplier_statuses()

    def on_export_shopify(self):
        """Export Master Product Database to Shopify CSV using workflow service."""
        self.validation_result_label.setText("EXPORTING: Creating Shopify CSV...")
        self.validation_result_label.setStyleSheet("color:#9CA3AF; font-size:13px;")
        self.validation_result_label.show()

        result = self.workflow_service.export_shopify()

        # Display result
        self.validation_result_label.setText(
            f"{result.title}\n\n{result.message}"
        )
        self.validation_result_label.setStyleSheet(f"color:{result.status_color}; font-size:13px;")
        self.validation_result_label.show()

