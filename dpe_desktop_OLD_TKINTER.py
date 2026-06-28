import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk


PROJECT_ROOT = Path(__file__).resolve().parent

FILES = {
    "A1 price file": PROJECT_ROOT / "input" / "A1" / "A1 pricefile.csv",
    "Cassons file": PROJECT_ROOT / "input" / "Cassons" / "Cassons.csv",
    "Image library": PROJECT_ROOT / "output" / "image_urls.csv",
    "Legacy descriptions 1": PROJECT_ROOT / "output" / "shopify_import_smart.csv",
    "Legacy descriptions 2": PROJECT_ROOT / "output" / "shopify_import.csv",
}

OUTPUT_FILE = PROJECT_ROOT / "output" / "dpe_v3_shopify_ready.csv"
RUNNER_FILE = PROJECT_ROOT / "run_dpe_v3.py"


class DPEDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Downunder Product Engine v3")
        self.root.geometry("950x680")
        self.root.resizable(False, False)

        self.bg = "#111827"
        self.card = "#1f2937"
        self.card_2 = "#273449"
        self.text = "#f9fafb"
        self.muted = "#9ca3af"
        self.green = "#22c55e"
        self.red = "#ef4444"
        self.gold = "#f59e0b"
        self.blue = "#38bdf8"

        self.root.configure(bg=self.bg)

        self.file_labels = {}
        self.build_ui()
        self.refresh_file_status()

    def build_ui(self):
        header = tk.Frame(self.root, bg=self.bg)
        header.pack(fill="x", padx=28, pady=(22, 10))

        tk.Label(
            header,
            text="DOWNUNDER PRODUCT ENGINE",
            font=("Segoe UI", 26, "bold"),
            bg=self.bg,
            fg=self.text,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Shopify Catalogue Builder · v3.0",
            font=("Segoe UI", 12),
            bg=self.bg,
            fg=self.muted,
        ).pack(anchor="w", pady=(2, 0))

        main = tk.Frame(self.root, bg=self.bg)
        main.pack(fill="both", expand=True, padx=28, pady=10)

        left = tk.Frame(main, bg=self.bg)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))

        right = tk.Frame(main, bg=self.bg, width=300)
        right.pack(side="right", fill="y")

        self.build_status_card(left)
        self.build_log_card(left)
        self.build_action_card(right)

    def make_card(self, parent):
        frame = tk.Frame(parent, bg=self.card, bd=0, highlightthickness=1, highlightbackground="#374151")
        frame.pack(fill="x", pady=(0, 14))
        return frame

    def build_status_card(self, parent):
        card = self.make_card(parent)

        tk.Label(
            card,
            text="Supplier & Content Status",
            font=("Segoe UI", 15, "bold"),
            bg=self.card,
            fg=self.text,
        ).pack(anchor="w", padx=18, pady=(16, 8))

        for name in FILES.keys():
            label = tk.Label(
                card,
                text=f"Checking {name}...",
                font=("Segoe UI", 10),
                bg=self.card,
                fg=self.muted,
                anchor="w",
            )
            label.pack(anchor="w", padx=20, pady=4)
            self.file_labels[name] = label

        tk.Button(
            card,
            text="Refresh File Status",
            font=("Segoe UI", 10, "bold"),
            bg=self.card_2,
            fg=self.text,
            activebackground="#334155",
            activeforeground=self.text,
            relief="flat",
            cursor="hand2",
            command=self.refresh_file_status,
            padx=12,
            pady=7,
        ).pack(anchor="w", padx=18, pady=(12, 16))

    def build_log_card(self, parent):
        card = self.make_card(parent)

        tk.Label(
            card,
            text="Build Log",
            font=("Segoe UI", 15, "bold"),
            bg=self.card,
            fg=self.text,
        ).pack(anchor="w", padx=18, pady=(16, 8))

        self.output_box = tk.Text(
            card,
            height=19,
            width=78,
            font=("Consolas", 9),
            bg="#020617",
            fg="#d1d5db",
            insertbackground=self.text,
            relief="flat",
            padx=10,
            pady=10,
        )
        self.output_box.pack(padx=18, pady=(0, 18))

    def build_action_card(self, parent):
        card = tk.Frame(parent, bg=self.card, highlightthickness=1, highlightbackground="#374151")
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="Catalogue Builder",
            font=("Segoe UI", 17, "bold"),
            bg=self.card,
            fg=self.text,
        ).pack(anchor="w", padx=18, pady=(18, 4))

        tk.Label(
            card,
            text="Build a Shopify-ready draft product CSV from supplier files.",
            wraplength=250,
            justify="left",
            font=("Segoe UI", 10),
            bg=self.card,
            fg=self.muted,
        ).pack(anchor="w", padx=18, pady=(0, 18))

        self.status = tk.Label(
            card,
            text="Ready",
            font=("Segoe UI", 13, "bold"),
            bg=self.card,
            fg=self.green,
        )
        self.status.pack(anchor="w", padx=18, pady=(0, 10))

        self.progress = ttk.Progressbar(
            card,
            orient="horizontal",
            length=250,
            mode="indeterminate",
        )
        self.progress.pack(padx=18, pady=(0, 18))

        self.run_button = tk.Button(
            card,
            text="BUILD SHOPIFY CATALOGUE",
            font=("Segoe UI", 12, "bold"),
            bg=self.gold,
            fg="#111827",
            activebackground="#fbbf24",
            activeforeground="#111827",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.run_dpe_threaded,
        )
        self.run_button.pack(fill="x", padx=18, pady=(0, 14))

        self.make_side_button(card, "Open Input Folder", self.open_input_folder)
        self.make_side_button(card, "Open Output Folder", self.open_output_folder)
        self.make_side_button(card, "Open Shopify CSV", self.open_shopify_csv)

        tk.Frame(card, bg=self.card).pack(expand=True)

        tk.Button(
            card,
            text="Exit",
            font=("Segoe UI", 10),
            bg="#374151",
            fg=self.text,
            activebackground="#4b5563",
            activeforeground=self.text,
            relief="flat",
            cursor="hand2",
            command=self.root.destroy,
        ).pack(fill="x", padx=18, pady=(0, 18))

    def make_side_button(self, parent, text, command):
        tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg=self.card_2,
            fg=self.text,
            activebackground="#334155",
            activeforeground=self.text,
            relief="flat",
            cursor="hand2",
            command=command,
            pady=8,
        ).pack(fill="x", padx=18, pady=5)

    def refresh_file_status(self):
        all_ok = True

        for name, path in FILES.items():
            if path.exists():
                size_kb = path.stat().st_size / 1024
                self.file_labels[name].config(
                    text=f"✓ {name}: Found ({size_kb:,.0f} KB)",
                    fg=self.green,
                )
            else:
                self.file_labels[name].config(
                    text=f"✗ {name}: Missing",
                    fg=self.red,
                )
                all_ok = False

        if all_ok:
            self.status.config(text="Ready", fg=self.green)
            self.run_button.config(state=tk.NORMAL)
        else:
            self.status.config(text="Missing required files", fg=self.red)
            self.run_button.config(state=tk.DISABLED)

    def log(self, text):
        self.output_box.insert(tk.END, text)
        self.output_box.see(tk.END)
        self.root.update_idletasks()

    def run_dpe_threaded(self):
        thread = threading.Thread(target=self.run_dpe)
        thread.daemon = True
        thread.start()

    def run_dpe(self):
        self.run_button.config(state=tk.DISABLED)
        self.status.config(text="Running DPE...", fg=self.gold)
        self.output_box.delete("1.0", tk.END)
        self.progress.start(12)

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
                self.log(line)

            process.wait()

            if process.returncode == 0:
                self.status.config(text="Complete", fg=self.green)
                messagebox.showinfo("DPE Complete", "Shopify CSV created successfully.")
            else:
                self.status.config(text="Failed", fg=self.red)
                messagebox.showerror("DPE Failed", "Check the build log.")

        except Exception as e:
            self.status.config(text="Error", fg=self.red)
            messagebox.showerror("Error", str(e))

        self.progress.stop()
        self.run_button.config(state=tk.NORMAL)
        self.refresh_file_status()

    def open_input_folder(self):
        os.startfile(PROJECT_ROOT / "input")

    def open_output_folder(self):
        os.startfile(PROJECT_ROOT / "output")

    def open_shopify_csv(self):
        if OUTPUT_FILE.exists():
            os.startfile(OUTPUT_FILE)
        else:
            messagebox.showwarning("File not found", "Run DPE first.")


if __name__ == "__main__":
    root = tk.Tk()
    app = DPEDesktopApp(root)
    root.mainloop()