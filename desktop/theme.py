from PySide6.QtGui import QColor


class Colours:
    BACKGROUND = "#111827"
    SIDEBAR = "#0F172A"

    CARD = "#1F2937"
    CARD_BORDER = "#374151"

    # Downunder Dirtbikes brand colours
    PRIMARY = "#F2B705"          # Brand gold
    PRIMARY_HOVER = "#FFC72C"    # Brighter gold
    NAVY = "#17135E"             # Brand navy

    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"

    TEXT = "#F9FAFB"
    MUTED = "#9CA3AF"

    LOG_BACKGROUND = "#020617"


APP_STYLE = f"""
QMainWindow {{
    background-color: {Colours.BACKGROUND};
}}

QWidget {{
    background-color: {Colours.BACKGROUND};
    color: {Colours.TEXT};
    font-family: Segoe UI;
    font-size: 14px;
}}

QListWidget {{
    background-color: {Colours.SIDEBAR};
    border: none;
    outline: none;
}}

QListWidget::item {{
    color: {Colours.MUTED};
    padding: 16px 20px;
    border-radius: 8px;
    margin: 4px;
}}

QListWidget::item:selected {{
    background: {Colours.PRIMARY};
    color: black;
    font-weight: bold;
}}

QPushButton {{
    background-color: {Colours.CARD};
    border: 1px solid {Colours.CARD_BORDER};
    border-radius: 10px;
    padding: 10px;
}}

QPushButton:hover {{
    background-color: {Colours.PRIMARY};
    color: black;
}}

QFrame#Card {{
    background-color: {Colours.CARD};
    border: 1px solid {Colours.CARD_BORDER};
    border-radius: 14px;
}}

QLabel#Title {{
    font-size: 28px;
    font-weight: 700;
}}

QLabel#Subtitle {{
    color: {Colours.MUTED};
    font-size: 13px;
}}

QTextEdit {{
    background-color: {Colours.LOG_BACKGROUND};
    border: 1px solid {Colours.CARD_BORDER};
    border-radius: 10px;
    color: white;
}}

QProgressBar {{
    height:18px;
    border-radius:9px;
    border:1px solid {Colours.CARD_BORDER};
    background:{Colours.LOG_BACKGROUND};
}}

QProgressBar::chunk {{
    background:{Colours.PRIMARY};
    border-radius:9px;
}}
"""