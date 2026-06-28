from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QFormLayout,
    QWidget,
)


class ProductDetailDialog(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)

        self.product = product
        self.setWindowTitle(f"Product Detail - {product.sku}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        title = QLabel(product.title or "Untitled Product")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel(f"SKU: {product.sku}")
        subtitle.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(subtitle)

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        form.addRow("Brand:", QLabel(product.brand))
        form.addRow("Supplier:", QLabel(product.supplier))
        form.addRow("Category:", QLabel(product.category))
        form.addRow("Cost:", QLabel(product.cost))
        form.addRow("RRP:", QLabel(product.rrp))
        form.addRow("Stock:", QLabel(product.stock))
        form.addRow("Margin:", QLabel(product.margin))
        form.addRow("Image:", QLabel(product.image_status))
        form.addRow("Description:", QLabel(product.description_status))

        layout.addWidget(form_widget)

        raw_label = QLabel("Raw Product Data")
        raw_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(raw_label)

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setPlainText(self._format_raw_data(product.raw))
        layout.addWidget(self.raw_text)

        button_row = QHBoxLayout()
        button_row.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _format_raw_data(self, raw: dict) -> str:
        if not raw:
            return "No raw data available."

        lines = []

        for key in sorted(raw.keys()):
            value = raw.get(key, "")
            lines.append(f"{key}: {value}")

        return "\n".join(lines)
