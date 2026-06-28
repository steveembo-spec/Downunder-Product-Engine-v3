import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QMessageBox,
    QProgressBar,
    QLabel,
)

from widgets import (
    PageTitle,
    PageSubtitle,
    PrimaryButton,
    SecondaryButton,
    HealthRow,
)

from dpe_v3.supplier_plugins.loader import discover_enabled_supplier_file_statuses


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNNER = PROJECT_ROOT / "run_dpe_v3.py"
OUTPUT = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
REPORT = PROJECT_ROOT / "output" / "dpe_v3_build_report.txt"
MANIFEST = PROJECT_ROOT / "output" / "build_manifest.json"

CONTENT_FILES = {
    "Image Library": PROJECT_ROOT / "output" / "image_urls.csv",
    "Legacy Descriptions": PROJECT_ROOT / "output" / "shopify_import_smart.csv",
}


class BuildThread(QThread):
    log = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.process = None
        self.cancel_requested = False

    def run(self):
        try:
            self.process = subprocess.Popen(
                ["python", str(RUNNER)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if self.process.stdout:
                for line in self.process.stdout:
                    if self.cancel_requested:
                        self._terminate_process()
                        self.cancelled.emit()
                        return

                    self.log.emit(line.rstrip())

            self.process.wait()

            if self.cancel_requested:
                self.cancelled.emit()
                return

            if self.process.returncode == 0:
                self.finished_ok.emit()
            else:
                self.failed.emit("Catalogue build failed. Check the build log.")

        except Exception as e:
            self.failed.emit(str(e))

    def cancel(self):
        self.cancel_requested = True
        self._terminate_process()

    def _terminate_process(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass


class CataloguePage(QWidget):

    def __init__(self):
        super().__init__()

        self.worker = None
        self.file_status_layout = None
        self.start_time = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)

        self.build_ui()
        self.refresh_files()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        layout.addWidget(PageTitle("Build Centre"))
        layout.addWidget(PageSubtitle("Run the full DPE catalogue pipeline from the desktop."))

        section_title = QLabel("Supplier & Content Files")
        section_title.setStyleSheet("font-size:18px; font-weight:800;")
        layout.addWidget(section_title)

        self.file_status_layout = QVBoxLayout()
        self.file_status_layout.setSpacing(8)
        layout.addLayout(self.file_status_layout)

        buttons_top = QHBoxLayout()

        self.refresh_btn = SecondaryButton("Refresh File Status")
        self.refresh_btn.clicked.connect(self.refresh_files)

        open_input_btn = SecondaryButton("Open Input Folder")
        open_input_btn.clicked.connect(lambda: os.startfile(PROJECT_ROOT / "input"))

        buttons_top.addWidget(self.refresh_btn)
        buttons_top.addWidget(open_input_btn)
        layout.addLayout(buttons_top)

        build_controls = QHBoxLayout()

        self.build_button = PrimaryButton("BUILD SHOPIFY CATALOGUE")
        self.build_button.clicked.connect(self.build)

        self.cancel_button = SecondaryButton("Cancel Build")
        self.cancel_button.clicked.connect(self.cancel_build)
        self.cancel_button.setEnabled(False)

        build_controls.addWidget(self.build_button)
        build_controls.addWidget(self.cancel_button)

        layout.addLayout(build_controls)

        self.step_label = QLabel("Ready")
        self.step_label.setStyleSheet("font-size:15px; color:#9CA3AF; font-weight:700;")
        layout.addWidget(self.step_label)

        self.timer_label = QLabel("Build Time: 00:00")
        self.timer_label.setStyleSheet("font-size:13px; color:#9CA3AF;")
        layout.addWidget(self.timer_label)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.hide()
        layout.addWidget(self.log)

        buttons_bottom = QHBoxLayout()

        open_output = SecondaryButton("Open Output Folder")
        open_output.clicked.connect(lambda: os.startfile(PROJECT_ROOT / "output"))

        open_csv = SecondaryButton("Open Shopify CSV")
        open_csv.clicked.connect(self.open_csv)

        open_report = SecondaryButton("Open Build Report")
        open_report.clicked.connect(self.open_report)

        open_manifest = SecondaryButton("Open Manifest")
        open_manifest.clicked.connect(self.open_manifest)

        toggle_log = SecondaryButton("Show / Hide Advanced Log")
        toggle_log.clicked.connect(self.toggle_log)

        buttons_bottom.addWidget(open_output)
        buttons_bottom.addWidget(open_csv)
        buttons_bottom.addWidget(open_report)
        buttons_bottom.addWidget(open_manifest)
        buttons_bottom.addWidget(toggle_log)

        layout.addLayout(buttons_bottom)
        layout.addStretch()

    def refresh_files(self):
        while self.file_status_layout.count():
            item = self.file_status_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        all_found = True

        suppliers = discover_enabled_supplier_file_statuses()

        for supplier in suppliers:
            name = f"{supplier.supplier_name} File"

            if supplier.file_exists:
                self.file_status_layout.addWidget(
                    HealthRow(
                        name,
                        f"Loaded ({supplier.file_size_kb:,.0f} KB)",
                        "#22C55E",
                    )
                )
            else:
                self.file_status_layout.addWidget(
                    HealthRow(name, "Missing", "#EF4444")
                )
                all_found = False

        for name, path in CONTENT_FILES.items():
            if path.exists():
                size_kb = path.stat().st_size / 1024
                self.file_status_layout.addWidget(
                    HealthRow(name, f"Loaded ({size_kb:,.0f} KB)", "#22C55E")
                )
            else:
                self.file_status_layout.addWidget(
                    HealthRow(name, "Missing", "#EF4444")
                )
                all_found = False

        self.build_button.setEnabled(all_found and not self.is_build_running())

        if all_found:
            if not self.is_build_running():
                self.step_label.setText("Ready")
        else:
            self.step_label.setText("Missing required files")

    def build(self):
        if self.is_build_running():
            return

        self.log.clear()
        self.log.show()
        self.progress.show()
        self.progress.setRange(0, 0)

        self.start_time = time.time()
        self.timer_label.setText("Build Time: 00:00")
        self.timer.start(1000)

        self.build_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.refresh_btn.setEnabled(False)
        self.step_label.setText("Starting catalogue build...")

        self.worker = BuildThread()
        self.worker.log.connect(self.handle_log)
        self.worker.finished_ok.connect(self.finished)
        self.worker.failed.connect(self.failed)
        self.worker.cancelled.connect(self.cancelled)
        self.worker.start()

    def cancel_build(self):
        if self.worker:
            self.step_label.setText("Cancelling build...")
            self.cancel_button.setEnabled(False)
            self.worker.cancel()

    def handle_log(self, line):
        self.log.append(line)

        if line.startswith("Loading "):
            self.step_label.setText("Reading supplier files...")

        elif "Supplier rows loaded" in line:
            self.step_label.setText("Supplier files loaded...")

        elif "Unique SKUs" in line:
            self.step_label.setText("Merging supplier catalogues...")

        elif "Business rules" in line:
            self.step_label.setText("Applying pricing and business rules...")

        elif "Image library loaded" in line:
            self.step_label.setText("Loading image library...")

        elif "Image matches" in line:
            self.step_label.setText("Matching product images...")

        elif "Descriptions attached" in line:
            self.step_label.setText("Adding product descriptions...")

        elif "Rows written" in line:
            self.step_label.setText("Writing Shopify CSV...")

        elif "Build manifest created" in line:
            self.step_label.setText("Writing build manifest...")

        elif "Build history saved" in line:
            self.step_label.setText("Saving build history...")

        elif "COMPLETED" in line or "Complete" in line:
            self.step_label.setText("Complete")

    def finished(self):
        self.stop_build_ui()
        self.step_label.setText("Complete")
        self.refresh_files()
        self.refresh_dashboard()

        QMessageBox.information(
            self,
            "Complete",
            "Shopify catalogue created successfully."
        )

    def failed(self, message):
        self.stop_build_ui()
        self.step_label.setText("Failed")
        self.refresh_files()

        QMessageBox.critical(
            self,
            "Build Failed",
            message
        )

    def cancelled(self):
        self.stop_build_ui()
        self.step_label.setText("Build cancelled")
        self.refresh_files()

        QMessageBox.warning(
            self,
            "Build Cancelled",
            "The catalogue build was cancelled."
        )

    def stop_build_ui(self):
        self.timer.stop()
        self.progress.hide()
        self.build_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh_btn.setEnabled(True)

    def update_timer(self):
        if self.start_time is None:
            return

        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60

        self.timer_label.setText(f"Build Time: {minutes:02d}:{seconds:02d}")

    def is_build_running(self):
        return self.worker is not None and self.worker.isRunning()

    def refresh_dashboard(self):
        parent = self.parent()

        while parent:
            if hasattr(parent, "dashboard_page"):
                try:
                    parent.dashboard_page.refresh()
                except Exception:
                    pass
                return

            parent = parent.parent()

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())

    def open_csv(self):
        if OUTPUT.exists():
            os.startfile(OUTPUT)
        else:
            QMessageBox.warning(self, "Missing CSV", "Run the build first.")

    def open_report(self):
        if REPORT.exists():
            os.startfile(REPORT)
        else:
            QMessageBox.warning(self, "Missing Report", "Run the build first.")

    def open_manifest(self):
        if MANIFEST.exists():
            os.startfile(MANIFEST)
        else:
            QMessageBox.warning(self, "Missing Manifest", "Run the build first.")