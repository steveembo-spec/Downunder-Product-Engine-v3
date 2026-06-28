import os
import subprocess
import sys
from pathlib import Path
from dashboard_data import load_dashboard_stats

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parent
RUNNER_FILE = PROJECT_ROOT / "run_dpe_v3.py"
OUTPUT_FILE = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
REPORT_FILE = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"


class BuildWorker(QThread):
    log_line = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def run(self):
        try:
            process = subprocess.Popen(
                ["python", str(RUNNER_FILE)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in process.stdout:
                self.log_line.emit(line)

            process.wait()

            if process.returncode == 0:
                self.finished_ok.emit()
            else:
                self.failed.emit("DPE build failed. Check the build log.")

        except Exception as e:
            self.failed.emit(str(e))


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Welcome to Downunder Product Engine")
        subtitle.setObjectName("MutedText")

        cards = QHBoxLayout()
        cards.setSpacing(16)

        cards.addWidget(self.make_card("Products", "62,753"))
        cards.addWidget(self.make_card("Images", "8,320"))
        cards.addWidget(self.make_card("Descriptions", "1,207"))
        cards.addWidget(self.make_card("Status", "READY"))

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(cards)
        layout.addStretch()

    def make_card(self, title, value):
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return card


class CataloguePage(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(18)

        title = QLabel("Catalogue Builder")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Build a Shopify-ready draft product CSV from supplier files.")
        subtitle.setObjectName("MutedText")

        self.build_button = QPushButton("BUILD SHOPIFY CATALOGUE")
        self.build_button.setObjectName("PrimaryButton")
        self.build_button.setFixedHeight(58)
        self.build_button.clicked.connect(self.start_build)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("LogBox")

        button_row = QHBoxLayout()

        open_output = QPushButton("Open Output Folder")
        open_output.setObjectName("SecondaryButton")
        open_output.clicked.connect(lambda: os.startfile(PROJECT_ROOT / "output"))

        open_csv = QPushButton("Open Shopify CSV")
        open_csv.setObjectName("SecondaryButton")
        open_csv.clicked.connect(self.open_csv)

        open_report = QPushButton("Open Build Report")
        open_report.setObjectName("SecondaryButton")
        open_report.clicked.connect(self.open_report)

        button_row.addWidget(open_output)
        button_row.addWidget(open_csv)
        button_row.addWidget(open_report)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.build_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_box)
        layout.addLayout(button_row)

    def start_build(self):
        self.log_box.clear()
        self.build_button.setEnabled(False)
        self.build_button.setText("BUILDING...")
        self.progress.show()

        self.worker = BuildWorker()
        self.worker.log_line.connect(self.add_log)
        self.worker.finished_ok.connect(self.build_complete)
        self.worker.failed.connect(self.build_failed)
        self.worker.start()

    def add_log(self, text):
        self.log_box.append(text.rstrip())

    def build_complete(self):
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.build_button.setText("BUILD SHOPIFY CATALOGUE")
        QMessageBox.information(self, "Complete", "Shopify catalogue built successfully.")

    def build_failed(self, message):
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.build_button.setText("BUILD SHOPIFY CATALOGUE")
        QMessageBox.critical(self, "Build Failed", message)

    def open_csv(self):
        if OUTPUT_FILE.exists():
            os.startfile(OUTPUT_FILE)
        else:
            QMessageBox.warning(self, "Missing File", "Run the build first.")

    def open_report(self):
        if REPORT_FILE.exists():
            os.startfile(REPORT_FILE)
        else:
            QMessageBox.warning(self, "Missing Report", "Run the build first.")


class PlaceholderPage(QWidget):
    def __init__(self, title, message):
        super().__init__()

        layout = QVBoxLayout(self)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")

        text = QLabel(message)
        text.setObjectName("MutedText")
        text.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Downunder Product Engine")
        self.resize(1200, 760)

        main = QWidget()
        self.setCentralWidget(main)

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self.build_sidebar()
        self.pages = QStackedWidget()

        self.pages.addWidget(DashboardPage())
        self.pages.addWidget(CataloguePage())
        self.pages.addWidget(PlaceholderPage("Images", "Image library tools will live here."))
        self.pages.addWidget(PlaceholderPage("Descriptions", "Description matching and content tools will live here."))
        self.pages.addWidget(PlaceholderPage("Reports", "Build reports and health checks will live here."))
        self.pages.addWidget(PlaceholderPage("Settings", "Supplier priorities, pricing rules and output settings will live here."))

        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        self.apply_theme()

    def build_sidebar(self):
        sidebar = QListWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)

        items = [
            "Dashboard",
            "Catalogue",
            "Images",
            "Descriptions",
            "Reports",
            "Settings",
        ]

        for item in items:
            widget_item = QListWidgetItem(item)
            widget_item.setTextAlignment(Qt.AlignVCenter)
            sidebar.addItem(widget_item)

        return sidebar

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #111827;
                color: #f9fafb;
                font-family: Segoe UI;
                font-size: 14px;
            }

            QListWidget#Sidebar {
                background-color: #020617;
                border: none;
                padding-top: 24px;
                font-size: 15px;
                font-weight: 600;
            }

            QListWidget#Sidebar::item {
                padding: 16px 24px;
                color: #9ca3af;
            }

            QListWidget#Sidebar::item:selected {
                background-color: #f59e0b;
                color: #111827;
            }

            QLabel#PageTitle {
                font-size: 34px;
                font-weight: 800;
                color: #f9fafb;
                margin-top: 30px;
                margin-left: 30px;
            }

            QLabel#MutedText {
                color: #9ca3af;
                font-size: 15px;
                margin-left: 30px;
            }

            QFrame#Card {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 16px;
                min-height: 130px;
                margin-left: 30px;
            }

            QLabel#CardTitle {
                color: #9ca3af;
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#CardValue {
                color: #f9fafb;
                font-size: 30px;
                font-weight: 800;
            }

            QPushButton#PrimaryButton {
                background-color: #f59e0b;
                color: #111827;
                border: none;
                border-radius: 12px;
                font-size: 17px;
                font-weight: 800;
                margin-left: 30px;
                margin-right: 30px;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #fbbf24;
            }

            QPushButton#SecondaryButton {
                background-color: #1f2937;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 12px;
                font-weight: 700;
                margin-left: 30px;
                margin-right: 10px;
            }

            QPushButton#SecondaryButton:hover {
                background-color: #374151;
            }

            QTextEdit#LogBox {
                background-color: #020617;
                color: #d1d5db;
                border: 1px solid #374151;
                border-radius: 12px;
                margin-left: 30px;
                margin-right: 30px;
                padding: 12px;
                font-family: Consolas;
                font-size: 12px;
            }

            QProgressBar {
                margin-left: 30px;
                margin-right: 30px;
                height: 18px;
                border: 1px solid #374151;
                border-radius: 9px;
                background-color: #020617;
            }

            QProgressBar::chunk {
                background-color: #f59e0b;
                border-radius: 9px;
            }
        """)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()