from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dashboard import DashboardPage
from catalogue import CataloguePage as BuildCentrePage
from pages.catalogue_page import CataloguePage
from reports import ReportsPage
from settings import SettingsPage
from supplier_centre import SupplierCentrePage
from supplier_manager import SupplierManagerPage
from version import APP_NAME, COMPANY, VERSION


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1400, 850)

        self.build_ui()

    def build_ui(self):

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("""
            QFrame {
                background:#020617;
                border-right:1px solid #1F2937;
            }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 18)
        sidebar_layout.setSpacing(14)

        logo = QLabel("🏍")
        logo.setStyleSheet("font-size:38px;")

        app_name = QLabel("DOWNUNDER\nPRODUCT ENGINE")
        app_name.setStyleSheet("""
            font-size:18px;
            font-weight:900;
            color:#F9FAFB;
            line-height:120%;
        """)

        company = QLabel(COMPANY)
        company.setStyleSheet("""
            color:#9CA3AF;
            font-size:12px;
            font-weight:600;
        """)

        version = QLabel(f"Version {VERSION}")
        version.setStyleSheet("""
            color:#F59E0B;
            font-size:12px;
            font-weight:700;
        """)

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(app_name)
        sidebar_layout.addWidget(company)
        sidebar_layout.addWidget(version)

        sidebar_layout.addSpacing(18)

        self.nav = QListWidget()
        self.nav.setStyleSheet("""
            QListWidget {
                background:#020617;
                border:none;
                outline:none;
            }

            QListWidget::item {
                padding:14px 12px;
                margin:4px 0;
                color:#9CA3AF;
                border-radius:10px;
                font-size:15px;
                font-weight:700;
            }

            QListWidget::item:selected {
                background:#F59E0B;
                color:#111827;
            }

            QListWidget::item:hover {
                background:#1F2937;
                color:#F9FAFB;
            }
        """)

        pages = [
            "🏠  Dashboard",
            "📦  Catalogue",
            "🛠  Build Centre",
            "🏭  Supplier Centre",
            "📊  Reports",
            "⚙  Settings",
        ]

        for page in pages:
            item = QListWidgetItem(page)
            item.setTextAlignment(Qt.AlignVCenter)
            self.nav.addItem(item)

        sidebar_layout.addWidget(self.nav)

        user_box = QFrame()
        user_box.setStyleSheet("""
            QFrame {
                background:#0F172A;
                border:1px solid #1F2937;
                border-radius:14px;
            }
        """)

        user_layout = QVBoxLayout(user_box)
        user_layout.setContentsMargins(14, 12, 14, 12)

        user_name = QLabel("Steve Emery")
        user_name.setStyleSheet("font-weight:800; color:#F9FAFB;")

        user_role = QLabel("Administrator")
        user_role.setStyleSheet("color:#9CA3AF; font-size:12px;")

        user_layout.addWidget(user_name)
        user_layout.addWidget(user_role)

        sidebar_layout.addWidget(user_box)

        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage()
        self.catalogue_page = CataloguePage()
        self.build_centre_page = BuildCentrePage()
        self.supplier_centre_page = SupplierCentrePage()
        self.reports_page = ReportsPage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.catalogue_page)
        self.stack.addWidget(self.build_centre_page)
        self.stack.addWidget(self.supplier_centre_page)
        self.stack.addWidget(self.reports_page)
        self.stack.addWidget(self.settings_page)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack)