from PySide6.QtWidgets import QVBoxLayout, QWidget

from widgets import PageTitle, PageSubtitle


class SettingsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        layout.addWidget(PageTitle("Settings"))
        layout.addWidget(
            PageSubtitle(
                "Supplier priorities, pricing rules and application settings."
            )
        )

        layout.addStretch()