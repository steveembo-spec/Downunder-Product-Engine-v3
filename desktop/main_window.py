from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
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

from core.paths import get_assets_path
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

        # Set window icon from assets
        self._set_window_icon()

        self.build_ui()

    def _set_window_icon(self):
        """Set window icon from PNG logo. Fails gracefully if file missing."""
        try:
            logo_path = get_assets_path(__file__) / "logo.png"
            if logo_path.exists():
                self.setWindowIcon(QIcon(str(logo_path)))
        except Exception:
            # Silently fail; window will use default icon
            pass

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
                background:#F2F4F7;
                border-right:1px solid #E0E7F1;
            }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 18)
        sidebar_layout.setSpacing(14)

        # Logo panel - matches light sidebar background
        logo_panel = QFrame()
        logo_panel.setStyleSheet("""
            QFrame {
                background:#F2F4F7;
                padding:8px;
            }
        """)
        
        logo_layout = QVBoxLayout(logo_panel)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(0)
        
        # Load PNG logo - transparent, full logo visible
        logo = QLabel()
        logo_path = get_assets_path(__file__) / "logo.png"
        if logo_path.exists():
            try:
                pixmap = QPixmap(str(logo_path))
                # Scale to fit ~220x140px, maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    QSize(220, 140),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                logo.setPixmap(scaled_pixmap)
                logo.setAlignment(Qt.AlignCenter)
            except Exception:
                # Fallback if image load fails
                logo.setText("DPE")
                logo.setStyleSheet("font-size:24px; font-weight:bold; color:#F2B705;")
                logo.setAlignment(Qt.AlignCenter)
        else:
            # Fallback if file not found
            logo.setText("DPE")
            logo.setStyleSheet("font-size:24px; font-weight:bold; color:#F2B705;")
            logo.setAlignment(Qt.AlignCenter)
        
        logo_layout.addWidget(logo)
        sidebar_layout.addWidget(logo_panel)

        sidebar_layout.addSpacing(8)

        # App branding labels - centred
        app_name = QLabel("DOWNUNDER\nPRODUCT ENGINE")
        app_name.setAlignment(Qt.AlignCenter)
        app_name.setStyleSheet("""
            font-size:16px;
            font-weight:900;
            color:#1E293B;
            line-height:110%;
        """)

        company = QLabel("Downunder Dirtbikes")
        company.setAlignment(Qt.AlignCenter)
        company.setStyleSheet("""
            color:#64748B;
            font-size:11px;
            font-weight:600;
        """)

        version = QLabel("Version 1.0.0")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("""
            color:#F2B705;
            font-size:11px;
            font-weight:700;
        """)

        sidebar_layout.addWidget(app_name)
        sidebar_layout.addWidget(company)
        sidebar_layout.addWidget(version)

        sidebar_layout.addSpacing(12)

        self.nav = QListWidget()
        self.nav.setStyleSheet("""
            QListWidget {
                background:#F2F4F7;
                border:none;
                outline:none;
            }

            QListWidget::item {
                padding:14px 12px;
                margin:4px 0;
                color:#1E293B;
                border-radius:10px;
                font-size:15px;
                font-weight:700;
            }

            QListWidget::item:selected {
                background:#F2B705;
                color:#FFFFFF;
            }

            QListWidget::item:hover {
                background:#E5E9EF;
                color:#1E293B;
            }

            QListWidget::item:hover:!selected {
                background:#E5E9EF;
            }

            QScrollBar:vertical {
                background:#F2F4F7;
                width:8px;
                border:none;
            }

            QScrollBar::handle:vertical {
                background:#CBD5E1;
                border-radius:4px;
                min-height:20px;
            }

            QScrollBar::handle:vertical:hover {
                background:#94A3B8;
            }

            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background:none;
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
                background:#FFFFFF;
                border:1px solid #E0E7F1;
                border-radius:8px;
            }
        """)

        user_layout = QVBoxLayout(user_box)
        user_layout.setContentsMargins(14, 12, 14, 12)

        user_name = QLabel("Steve Emery")
        user_name.setStyleSheet("font-weight:800; color:#1E293B;")

        user_role = QLabel("Administrator")
        user_role.setStyleSheet("color:#64748B; font-size:12px;")

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