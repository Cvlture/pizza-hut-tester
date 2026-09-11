from dataclasses import asdict
from datetime import datetime
import json
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from main import AppSettings, run


SETTINGS_FILE = Path(__file__).with_name("pizza_settings.json")


def load_settings() -> AppSettings:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        fields = {field: data[field] for field in asdict(AppSettings()) if field in data}
        return AppSettings(**fields)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    SETTINGS_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


class SettingsApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NZ Pizza Hut Tester")
        self.geometry("760x680")
        self.minsize(680, 560)
        self.ready_event = threading.Event()
        self.close_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_event = self.close_event
        self.worker: threading.Thread | None = None
        self.events: queue.Queue[str] = queue.Queue()
        self.settings = load_settings()
        self._apply_windows_theme()
        self._build_ui()
        self.after(100, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _apply_windows_theme(self) -> None:
        dark_mode = False
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                dark_mode = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except (ImportError, OSError):
            pass

        if dark_mode:
            colors = {
                "window": "#202020",
                "text": "#f1f1f1",
                "field": "#333333",
                "console": "#171717",
                "button": "#3a3a3a",
                "muted": "#a9a9a9",
                "accent": "#62c7ff",
            }
        else:
            colors = {
                "window": "#f3f3f3",
                "text": "#1f1f1f",
                "field": "#ffffff",
                "console": "#ffffff",
                "button": "#e1e1e1",
                "muted": "#666666",
                "accent": "#0067c0",
            }

        self.configure(background=colors["window"])
        style = ttk.Style(self)
        if dark_mode and "clam" in style.theme_names():
            style.theme_use("clam")
        elif "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TFrame", background=colors["window"])
        style.configure(
            "TLabel", background=colors["window"], foreground=colors["text"], font=("Segoe UI", 10)
        )
        style.configure(
            "Subtitle.TLabel", background=colors["window"], foreground=colors["muted"], font=("Segoe UI", 10)
        )
        style.configure(
            "Status.TLabel", background=colors["window"], foreground=colors["accent"], font=("Segoe UI", 10, "bold")
        )
        style.configure("TCheckbutton", background=colors["window"], foreground=colors["text"])
        style.configure(
            "TButton", background=colors["button"], foreground=colors["text"]
        )
        style.map(
            "TButton",
            background=[
                ("disabled", colors["button"]),
                ("active", colors["button"]),
                ("pressed", colors["button"]),
                ("!disabled", colors["button"]),
            ],
            foreground=[
                ("disabled", "#888888"),
                ("active", colors["text"]),
                ("pressed", colors["text"]),
                ("!disabled", colors["text"]),
            ],
        )
        style.configure("TEntry", fieldbackground=colors["field"], foreground=colors["text"])
        self._theme_colors = colors

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(11, weight=1)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Pizza Hut Tester", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 16)
        )
        ttk.Label(
            frame,
            text="Configure a session, open the browser, and monitor progress here.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.status_var = tk.StringVar(value="Ready - Click Open Browser to start a session.")
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 14)
        )

        defaults = self.settings
        self.url = self._field(frame, 3, "Pizza Hut URL", defaults.pizza_hut_url)
        self.count = self._field(frame, 4, "Code count", str(defaults.required_codes_count))
        self.profile = self._field(frame, 5, "Profile folder", defaults.user_data_dir)
        dimensions = ttk.Frame(frame)
        dimensions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)
        dimensions.columnconfigure(0, weight=1)
        dimensions.columnconfigure(1, weight=1)
        self.width = self._inline_field(dimensions, 0, "Browser width", str(defaults.browser_width))
        self.height = self._inline_field(dimensions, 1, "Browser height", str(defaults.browser_height))
        self.headless = tk.BooleanVar(value=defaults.headless)
        headless_frame = ttk.Frame(frame)
        headless_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 16))
        ttk.Checkbutton(
            headless_frame, text="Run browser headless", variable=self.headless,
            command=self._toggle_coupons_url,
        ).grid(row=0, column=0, sticky="w")
        self.coupons_url = tk.StringVar(value=defaults.coupons_url)
        self.coupons_url_entry = ttk.Entry(
            headless_frame, textvariable=self.coupons_url, width=42, state="disabled"
        )
        self.coupons_url_entry.grid(row=0, column=1, padx=(12, 0), sticky="ew")
        headless_frame.columnconfigure(1, weight=1)
        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 14))
        self.open_button = ttk.Button(buttons, text="Open Browser", command=self._start)
        self.open_button.pack(side="left")
        self.test_button = ttk.Button(
            buttons, text="Start Testing", command=self._start_testing, state="disabled"
        )
        self.test_button.pack(side="left", padx=8)
        self.pause_button = ttk.Button(
            buttons, text="Pause", command=self._toggle_pause, state="disabled"
        )
        self.pause_button.pack(side="left")
        self.cancel_button = ttk.Button(
            buttons, text="Cancel", command=self._cancel_run, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=8)
        self.close_button = ttk.Button(
            buttons, text="Close Browser", command=self._close_browser, state="disabled"
        )
        self.close_button.pack(side="right")
        ttk.Button(buttons, text="Reset", command=self._reset_settings).pack(side="right", padx=8)
        ttk.Button(buttons, text="Export Log", command=self._export_log).pack(side="right")

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(frame, text="Progress console").grid(row=10, column=0, columnspan=2, sticky="w")
        console_frame = ttk.Frame(frame)
        console_frame.grid(row=11, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
        console_frame.rowconfigure(0, weight=1)
        console_frame.columnconfigure(0, weight=1)
        self.console = tk.Text(console_frame, height=12, state="disabled", wrap="word")
        self.console.configure(
            background=self._theme_colors["console"],
            foreground=self._theme_colors["text"],
            insertbackground=self._theme_colors["text"],
        )
        self.console.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.console.configure(yscrollcommand=scrollbar.set)

    def _field(self, parent: ttk.Frame, row: int, label: str, value: str) -> tk.StringVar:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        variable = tk.StringVar(value=value)
        ttk.Entry(parent, textvariable=variable, width=34).grid(
            row=row, column=1, sticky="ew", pady=5
        )
        return variable

    def _inline_field(
        self, parent: ttk.Frame, column: int, label: str, value: str
    ) -> tk.StringVar:
        ttk.Label(parent, text=label).grid(row=0, column=column, sticky="w")
        variable = tk.StringVar(value=value)
        ttk.Entry(parent, textvariable=variable, width=16).grid(
            row=1, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0)
        )
        return variable

    def _start(self) -> None:
        try:
            settings = AppSettings(
                pizza_hut_url=self.url.get().strip(),
                coupons_url=self.coupons_url.get().strip(),
                required_codes_count=int(self.count.get()),
                user_data_dir=self.profile.get().strip(),
                browser_width=int(self.width.get()),
                browser_height=int(self.height.get()),
                headless=self.headless.get(),
            )
            if not settings.pizza_hut_url or not settings.user_data_dir:
                raise ValueError("URL and profile folder are required.")
            for label, value in (("Pizza Hut URL", settings.pizza_hut_url), ("Coupons URL", settings.coupons_url)):
                parsed = urlparse(value)
                if label == "Coupons URL" and not settings.headless:
                    continue
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError(f"{label} must be a valid http or https URL.")
            if settings.headless and not settings.coupons_url:
                raise ValueError("A coupons URL is required in headless mode.")
            if settings.required_codes_count < 1:
                raise ValueError("Code count must be at least 1.")
            if settings.browser_width < 1 or settings.browser_height < 1:
                raise ValueError("Browser dimensions must be positive.")
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error))
            return

        save_settings(settings)
        self.open_button.config(state="disabled")
        self.close_button.config(state="normal")
        self.cancel_button.config(state="normal")
        self.pause_button.config(state="disabled")
        self.status_var.set("Opening browser...")
        self.ready_event.clear()
        self.close_event.clear()
        self.pause_event.set()
        self.console.config(state="normal")
        self.console.insert("end", "\n--- New browser session ---\n")
        self.console.config(state="disabled")
        self.worker = threading.Thread(
            target=self._run_engine,
            args=(settings,),
            daemon=True,
        )
        self.worker.start()

    def _toggle_coupons_url(self) -> None:
        state = "normal" if self.headless.get() else "disabled"
        self.coupons_url_entry.config(state=state)

    def _run_engine(self, settings: AppSettings) -> None:
        try:
            run(
                settings,
                report=self._report,
                ready_event=self.ready_event,
                close_event=self.close_event,
                pause_event=self.pause_event,
            )
        except Exception as error:
            self._report(f"ERROR: {error}")

    def _report(self, message: str) -> None:
        self.events.put(message)

    def _process_events(self) -> None:
        while not self.events.empty():
            message = self.events.get()
            self.status_var.set(message)
            status_only = (
                message.startswith("Opening ")
                or message.startswith("Confirm your location")
                or message.startswith("When the coupon field")
                or message.startswith("Closing browser session")
                or message.startswith("Stopped before testing")
            )
            if not status_only:
                self.console.config(state="normal")
                self.console.insert("end", message + "\n")
                self.console.see("end")
                self.console.config(state="disabled")
            if message.startswith("When the coupon field"):
                self.test_button.config(state="normal")
            attempt = re.match(r"\[(\d+)/(\d+)\]", message)
            if attempt:
                self.progress.configure(maximum=int(attempt.group(2)), value=int(attempt.group(1)))
                self.pause_button.config(state="normal")
            if message.startswith("Confirm your location"):
                self._bring_to_front()
        if self.worker is not None and not self.worker.is_alive():
            self.worker = None
            self.open_button.config(state="normal")
            self.test_button.config(state="disabled")
            self.pause_button.config(state="disabled")
            self.pause_button.config(text="Pause")
            self.cancel_button.config(state="disabled")
            self.close_button.config(state="disabled")
            self.progress.configure(value=0)
            self.status_var.set("Ready")
            self.ready_event = threading.Event()
            self.close_event = threading.Event()
            self.console.config(state="normal")
            self.console.insert("end", "Browser closed. Ready for another session.\n")
            self.console.config(state="disabled")
        self.after(100, self._process_events)

    def _bring_to_front(self) -> None:
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(300, lambda: self.attributes("-topmost", False))

    def _start_testing(self) -> None:
        self.ready_event.set()
        self.pause_event.set()
        self.test_button.config(state="disabled")
        self.pause_button.config(state="normal")
        self.status_var.set("Testing authorized codes...")

    def _toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.config(text="Resume")
            self.status_var.set("Paused")
        else:
            self.pause_event.set()
            self.pause_button.config(text="Pause")
            self.status_var.set("Testing authorized codes...")

    def _cancel_run(self) -> None:
        self.status_var.set("Cancelling...")
        self.close_event.set()
        self.pause_event.set()
        self.cancel_button.config(state="disabled")

    def _reset_settings(self) -> None:
        if self.worker is not None:
            messagebox.showinfo("Session active", "Close the current browser before resetting settings.")
            return
        self.settings = AppSettings()
        self.url.set(self.settings.pizza_hut_url)
        self.count.set(str(self.settings.required_codes_count))
        self.profile.set(self.settings.user_data_dir)
        self.coupons_url.set(self.settings.coupons_url)
        self.width.set(str(self.settings.browser_width))
        self.height.set(str(self.settings.browser_height))
        self.headless.set(self.settings.headless)
        self._toggle_coupons_url()
        save_settings(self.settings)
        self.status_var.set("Settings reset to defaults.")

    def _export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export progress log",
            initialfile=f"pizza-hut-log-{datetime.now():%Y%m%d-%H%M%S}.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            Path(path).write_text(self.console.get("1.0", "end-1c"), encoding="utf-8")
            self.status_var.set(f"Log exported: {path}")

    def _close_browser(self) -> None:
        self.status_var.set("Closing browser...")
        self.close_event.set()
        self.pause_event.set()
        self.close_button.config(state="disabled")

    def _close_app(self) -> None:
        self.status_var.set("Closing...")
        self.close_event.set()
        self.destroy()


if __name__ == "__main__":
    SettingsApp().mainloop()
