import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from version import WINDOW_TITLE
from theme import APP_STYLE
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(WINDOW_TITLE)
    app.setStyleSheet(APP_STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()