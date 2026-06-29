from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QFileDialog,
)

from widgets import (
    PageTitle,
    PageSubtitle,
    PrimaryButton,
    SecondaryButton,
)


class SupplierCentrePage(QWidget):

    def __init__(self):
        super().__init__()
        self.build_ui()

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

        # Main content area
        content = QHBoxLayout()
        content.setSpacing(20)

        # Left column: File selection and validation
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # Configured Suppliers Section
        suppliers_title = QLabel("Configured Suppliers")
        suppliers_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        left_col.addWidget(suppliers_title)

        suppliers_card = QFrame()
        suppliers_card.setObjectName("Card")
        suppliers_card.setMinimumHeight(120)
        suppliers_layout = QVBoxLayout(suppliers_card)
        suppliers_layout.setContentsMargins(16, 12, 16, 12)
        suppliers_layout.setSpacing(10)

        suppliers_placeholder = QLabel("• A1 (Priority: 100)")
        suppliers_placeholder.setStyleSheet("color:#9CA3AF; font-size:13px;")
        suppliers_layout.addWidget(suppliers_placeholder)

        suppliers_placeholder2 = QLabel("• Cassons (Priority: 90)")
        suppliers_placeholder2.setStyleSheet("color:#9CA3AF; font-size:13px;")
        suppliers_layout.addWidget(suppliers_placeholder2)

        suppliers_placeholder3 = QLabel("• Serco (Priority: 70)")
        suppliers_placeholder3.setStyleSheet("color:#9CA3AF; font-size:13px;")
        suppliers_layout.addWidget(suppliers_placeholder3)

        suppliers_layout.addStretch()
        left_col.addWidget(suppliers_card)

        # File Selection Section
        file_title = QLabel("Selected Supplier File")
        file_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        left_col.addWidget(file_title)

        file_card = QFrame()
        file_card.setObjectName("Card")
        file_card.setMinimumHeight(100)
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(16, 12, 16, 12)

        file_placeholder = QLabel("No file selected")
        file_placeholder.setStyleSheet("color:#9CA3AF; font-size:13px;")
        file_layout.addWidget(file_placeholder)

        file_info = QLabel("Select a CSV file from one of the configured suppliers")
        file_info.setStyleSheet("color:#6B7280; font-size:12px;")
        file_layout.addWidget(file_info)

        file_layout.addStretch()
        left_col.addWidget(file_card)

        left_col.addStretch()

        # Right column: Actions and status
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # Action Buttons Section
        buttons_title = QLabel("Actions")
        buttons_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        right_col.addWidget(buttons_title)

        self.browse_button = SecondaryButton("Browse CSV")
        self.browse_button.setEnabled(False)
        self.browse_button.clicked.connect(self.on_browse_csv)
        right_col.addWidget(self.browse_button)

        self.validate_button = SecondaryButton("Validate File")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self.on_validate_file)
        right_col.addWidget(self.validate_button)

        self.import_button = PrimaryButton("Import Supplier File")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.on_import_file)
        right_col.addWidget(self.import_button)

        # Validation Summary Section
        validation_title = QLabel("Validation Summary")
        validation_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        right_col.addWidget(validation_title)

        validation_card = QFrame()
        validation_card.setObjectName("Card")
        validation_card.setMinimumHeight(120)
        validation_layout = QVBoxLayout(validation_card)
        validation_layout.setContentsMargins(16, 12, 16, 12)

        validation_placeholder = QLabel("Waiting for file selection")
        validation_placeholder.setStyleSheet("color:#9CA3AF; font-size:13px;")
        validation_layout.addWidget(validation_placeholder)

        validation_layout.addStretch()
        right_col.addWidget(validation_card)

        # Import Summary Section
        summary_title = QLabel("Import Summary")
        summary_title.setStyleSheet("font-size:16px; font-weight:800; color:#F9FAFB;")
        right_col.addWidget(summary_title)

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        summary_card.setMinimumHeight(120)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(16, 12, 16, 12)

        summary_placeholder = QLabel("No import performed yet")
        summary_placeholder.setStyleSheet("color:#9CA3AF; font-size:13px;")
        summary_layout.addWidget(summary_placeholder)

        summary_layout.addStretch()
        right_col.addWidget(summary_card)

        right_col.addStretch()

        # Add columns to main content
        content.addLayout(left_col, 1)
        content.addLayout(right_col, 1)

        layout.addLayout(content)

    def on_browse_csv(self):
        """Handler for Browse CSV button (disabled for now)."""
        pass

    def on_validate_file(self):
        """Handler for Validate File button (disabled for now)."""
        pass

    def on_import_file(self):
        """Handler for Import Supplier File button (disabled for now)."""
        pass
