from PySide6.QtWidgets import QVBoxLayout, QWidget

from widgets import PageTitle, PageSubtitle


class ReportsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        layout.addWidget(PageTitle("Reports"))
        layout.addWidget(
            PageSubtitle(
                "Build reports and catalogue health checks will appear here."
            )
        )

        layout.addStretch()