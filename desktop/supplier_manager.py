from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from widgets import PageTitle, PageSubtitle, SecondaryButton
from dpe_v3.supplier_plugins.loader import discover_plugin_statuses


class SupplierManagerPage(QWidget):

    def __init__(self):
        super().__init__()
        self.build_ui()
        self.refresh()

    def build_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        layout.addWidget(PageTitle("Supplier Manager"))
        layout.addWidget(PageSubtitle("Automatically discovered supplier plugins"))

        self.refresh_button = SecondaryButton("Refresh Suppliers")
        self.refresh_button.clicked.connect(self.refresh)

        layout.addWidget(self.refresh_button)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Supplier",
                "Plugin Key",
                "Enabled",
                "Installed",
                "Configured",
                "Status",
            ]
        )

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        self.note = QLabel(
            "Supplier plugins are discovered from dpe_v3/supplier_plugins. "
            "Enabled suppliers are controlled by config/suppliers.json."
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet("font-size:13px; color:#9CA3AF;")

        layout.addWidget(self.note)

    def refresh(self):

        suppliers = discover_plugin_statuses()

        self.table.setRowCount(len(suppliers))

        for row, supplier in enumerate(suppliers):

            values = [
                supplier.supplier_name,
                supplier.key,
                "Yes" if supplier.enabled else "No",
                "Yes" if supplier.installed else "No",
                "Yes" if supplier.configured else "No",
                supplier.status,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.table.setItem(row, column, item)