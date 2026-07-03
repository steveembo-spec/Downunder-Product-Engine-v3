"""
Supplier Mapping Confirmation Dialog

Allows user to confirm detected CSV header mappings for required fields
(SKU, Title, Cost, RRP) before importing a new supplier.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QWidget,
    QScrollArea,
)
from PySide6.QtGui import QIcon
from pathlib import Path

from widgets import PrimaryButton, SecondaryButton


class SupplierMappingDialog(QDialog):
    """
    Dialog to confirm CSV header mappings for a supplier import.
    
    User can:
    - Review detected mappings for 4 required fields
    - See confidence scores
    - See warnings for low-confidence matches
    - Modify mappings via dropdowns
    - Choose to remember the mapping
    """

    def __init__(
        self,
        supplier_name: str,
        file_name: str,
        headers: list[str],
        detected_mapping: dict,  # master_field -> HeaderMatch
        parent=None,
    ):
        """
        Args:
            supplier_name: Name of the supplier
            file_name: Name of the CSV file
            headers: List of all CSV headers
            detected_mapping: dict[str, HeaderMatch] with detected mappings
            parent: Parent widget
        """
        super().__init__(parent)
        self.supplier_name = supplier_name
        self.file_name = file_name
        self.headers = headers
        self.detected_mapping = detected_mapping
        self.confirmed_mapping = {}  # master_field -> selected_header
        self.remember_mapping = True
        
        self.setWindowTitle("Confirm Column Mappings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #111827;
                color: #F9FAFB;
            }
        """)
        
        self.build_ui()
        self.load_mappings()

    def build_ui(self):
        """Build the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header
        header_label = QLabel("Confirm Column Mappings")
        header_label.setStyleSheet("font-size:18px; font-weight:800; color:#F9FAFB;")
        main_layout.addWidget(header_label)

        info_label = QLabel(f"Supplier: {self.supplier_name}  •  File: {self.file_name}")
        info_label.setStyleSheet("color:#9CA3AF; font-size:12px;")
        main_layout.addWidget(info_label)

        description = QLabel(
            "Review the detected column mappings below. Select the correct column for each required field."
        )
        description.setStyleSheet("color:#D1D5DB; font-size:13px;")
        description.setWordWrap(True)
        main_layout.addWidget(description)

        # Scrollable mappings area
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
                background-color: #1F2937;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #374151;
                border-radius: 6px;
            }
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Create mapping controls for required fields only
        self.mapping_controls = {}
        required_fields = ["sku", "title", "cost", "rrp"]
        
        for field_name in required_fields:
            field_layout = self._create_field_mapping(field_name)
            if field_layout:
                scroll_layout.addLayout(field_layout)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Remember checkbox
        self.remember_checkbox = QCheckBox("Remember this mapping for future imports")
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                color: #D1D5DB;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        main_layout.addWidget(self.remember_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.cancel_button = SecondaryButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.save_button = PrimaryButton("Save & Import")
        self.save_button.clicked.connect(self.on_save_clicked)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

    def _create_field_mapping(self, field_name: str):
        """
        Create UI for one field mapping.
        Returns QHBoxLayout with label, combobox, and confidence/warning.
        """
        header_match = self.detected_mapping.get(field_name)
        if not header_match:
            return None

        layout = QHBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # Field label
        field_label = QLabel(field_name.upper())
        field_label.setStyleSheet("color:#9CA3AF; font-size:13px; font-weight:600; min-width:80px;")
        layout.addWidget(field_label)

        # ComboBox with headers
        combo = QComboBox()
        combo.setStyleSheet("""
            QComboBox {
                background-color: #1F2937;
                color: #F9FAFB;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        
        # Add headers to combo
        for header in self.headers:
            combo.addItem(header)
        
        # Set default (detected header if available)
        if header_match.detected_header:
            index = combo.findText(header_match.detected_header)
            if index >= 0:
                combo.setCurrentIndex(index)
        
        layout.addWidget(combo)
        self.mapping_controls[field_name] = combo

        # Confidence and warning
        confidence_text = f"{header_match.confidence}%"
        if header_match.confidence < 80:
            confidence_text += " ⚠ Review"
            confidence_label = QLabel(confidence_text)
            confidence_label.setStyleSheet("color:#F59E0B; font-size:12px;")
        else:
            confidence_label = QLabel(confidence_text)
            confidence_label.setStyleSheet("color:#10B981; font-size:12px;")
        
        confidence_label.setMinimumWidth(100)
        layout.addWidget(confidence_label)

        layout.addStretch()
        return layout

    def load_mappings(self):
        """Load initial mapping selection from detected results."""
        for field_name, combo in self.mapping_controls.items():
            header_match = self.detected_mapping.get(field_name)
            if header_match and header_match.detected_header:
                index = combo.findText(header_match.detected_header)
                if index >= 0:
                    combo.setCurrentIndex(index)

    def on_save_clicked(self):
        """Collect confirmed mappings and close dialog."""
        # Collect user selections
        for field_name, combo in self.mapping_controls.items():
            selected_header = combo.currentText()
            self.confirmed_mapping[field_name] = selected_header

        # Check if all required fields are mapped
        if not all(field in self.confirmed_mapping for field in ["sku", "title", "cost", "rrp"]):
            # This shouldn't happen as comboboxes are always populated
            self.save_button.setEnabled(False)
            return

        self.remember_mapping = self.remember_checkbox.isChecked()
        self.accept()

    def get_confirmed_mapping(self) -> dict[str, str]:
        """Return the user-confirmed mapping (master_field -> header)."""
        return self.confirmed_mapping

    def should_remember(self) -> bool:
        """Return whether user wants to remember this mapping."""
        return self.remember_mapping
