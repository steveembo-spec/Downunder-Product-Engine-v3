from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", icon: str = "●"):
        super().__init__()

        self.setObjectName("Card")
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        top = QHBoxLayout()

        self.icon = QLabel(icon)
        self.icon.setStyleSheet("""
            font-size:26px;
        """)

        self.title = QLabel(title)
        self.title.setObjectName("Subtitle")

        top.addWidget(self.icon)
        top.addWidget(self.title)
        top.addStretch()

        self.value = QLabel(value)
        self.value.setAlignment(Qt.AlignLeft)
        self.value.setStyleSheet("""
            font-size:34px;
            font-weight:800;
            color:#F9FAFB;
        """)

        self.subtitle = QLabel(subtitle)
        self.subtitle.setStyleSheet("""
            color:#9CA3AF;
            font-size:12px;
        """)

        layout.addLayout(top)
        layout.addStretch()
        layout.addWidget(self.value)
        layout.addWidget(self.subtitle)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_subtitle(self, text):
        self.subtitle.setText(str(text))


class HealthRow(QFrame):
    def __init__(self, label: str, status: str, colour: str = "#22C55E"):
        super().__init__()

        self.setObjectName("Card")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{colour}; font-size:16px;")

        name = QLabel(label)
        name.setStyleSheet("font-size:14px; font-weight:600;")

        value = QLabel(status)
        value.setStyleSheet("color:#9CA3AF; font-size:13px;")

        layout.addWidget(dot)
        layout.addWidget(name)
        layout.addStretch()
        layout.addWidget(value)


class PageTitle(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("Title")


class PageSubtitle(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("Subtitle")
        self.setWordWrap(True)


class PrimaryButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)

        self.setMinimumHeight(54)

        self.setStyleSheet("""
        QPushButton{
            background:#F59E0B;
            color:black;
            font-size:16px;
            font-weight:800;
            border-radius:14px;
            padding:12px;
        }

        QPushButton:hover{
            background:#FBBF24;
        }
        """)


class SecondaryButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)

        self.setMinimumHeight(44)

        self.setStyleSheet("""
        QPushButton{
            background:#1F2937;
            color:#F9FAFB;
            border:1px solid #374151;
            border-radius:12px;
            padding:10px;
            font-weight:700;
        }

        QPushButton:hover{
            background:#374151;
        }
        """)