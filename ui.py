"""CustomTkinter UI for the SIMPEG journal automation app."""
import os
import threading
import customtkinter as ctk
from tkinter import messagebox
import config
from automation import AutomationState, SimpegAutomator
from logger import get_logger
from template_loader import load_journal_template
from typing import Callable


class RunGuard:
    """Simple guard to prevent duplicate automation runs."""

    def __init__(self):
        self._running = False

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running


def request_automation_start(
    *,
    dry_run: bool,
    confirmation_callback: Callable[[], bool],
    start_callback: Callable[[], None],
    run_guard: RunGuard,
) -> bool:
    """Decide whether automation may start and invoke the start callback if allowed."""
    if not run_guard.start():
        return False

    if not dry_run and not confirmation_callback():
        run_guard.stop()
        return False

    start_callback()
    return True

log = get_logger()


class JournalApp(ctk.CTk):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("SIMPEG Jurnal Harian Otomatis")
        self.geometry("760x640")
        self.resizable(False, False)
        self.current_state = AutomationState.IDLE
        self._run_guard = RunGuard()

        self._build_login_frame()
        self._build_status_frame()
        self._build_actions_frame()

    def _build_login_frame(self):
        self.login_frame = ctk.CTkFrame(self, corner_radius=12)
        self.login_frame.pack(padx=24, pady=(24, 12), fill="x")

        self.header_label = ctk.CTkLabel(self.login_frame, text="Login SIMPEG", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(pady=(16, 12))

        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username")
        self.username_entry.pack(padx=20, pady=(0, 12), fill="x")

        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Password", show="*")
        self.password_entry.pack(padx=20, pady=(0, 12), fill="x")

        self.show_browser_var = ctk.BooleanVar(value=True)
        self.show_browser_checkbox = ctk.CTkCheckBox(self.login_frame, text="Tampilkan browser", variable=self.show_browser_var)
        self.show_browser_checkbox.pack(padx=20, pady=(0, 12), anchor="w")

        self.dry_run_var = ctk.BooleanVar(value=True)
        self.dry_run_checkbox = ctk.CTkCheckBox(self.login_frame, text="Dry run (tidak submit)", variable=self.dry_run_var)
        self.dry_run_checkbox.pack(padx=20, pady=(0, 12), anchor="w")

        self.login_button = ctk.CTkButton(self.login_frame, text="Mulai Otomatisasi", command=self._on_login)
        self.login_button.pack(padx=20, pady=(0, 16), fill="x")

        self.progress = ctk.CTkProgressBar(self.login_frame)
        self.progress.set(0)
        self.progress.pack(padx=20, pady=(0, 16), fill="x")

        self.state_label = ctk.CTkLabel(self.login_frame, text="Status proses: IDLE", anchor="w")
        self.state_label.pack(padx=20, pady=(0, 16), fill="x")

    def _build_status_frame(self):
        self.status_frame = ctk.CTkFrame(self, corner_radius=12)
        self.status_frame.pack(padx=24, pady=(0, 12), fill="both", expand=True)

        self.status_label = ctk.CTkLabel(self.status_frame, text="Status:", anchor="w")
        self.status_label.pack(padx=20, pady=(16, 0), fill="x")

        self.status_text = ctk.CTkTextbox(self.status_frame, width=700, height=300, state="normal")
        self.status_text.pack(padx=20, pady=(8, 12), fill="both", expand=True)
        self.status_text.configure(state="disabled")

    def _build_actions_frame(self):
        self.actions_frame = ctk.CTkFrame(self, corner_radius=12)
        self.actions_frame.pack(padx=24, pady=(0, 24), fill="x")

        self.open_template_button = ctk.CTkButton(self.actions_frame, text="Buka template jurnal", command=self._open_template_file)
        self.open_template_button.grid(row=0, column=0, padx=10, pady=10)

        self.open_log_button = ctk.CTkButton(self.actions_frame, text="Buka file log", command=self._open_log_file)
        self.open_log_button.grid(row=0, column=1, padx=10, pady=10)

        self.open_debug_button = ctk.CTkButton(self.actions_frame, text="Buka folder debug", command=self._open_debug_directory)
        self.open_debug_button.grid(row=0, column=2, padx=10, pady=10)

    def _log(self, message: str) -> None:
        formatted = f"{message}\n"
        self.status_text.configure(state="normal")
        self.status_text.insert("end", formatted)
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def _set_state(self, state: AutomationState) -> None:
        self.current_state = state
        self.after(0, lambda: self.state_label.configure(text=f"Status proses: {state.value}"))
        self.after(0, lambda: self.progress.set(min(1.0, self.progress.get() + 0.15) if state != AutomationState.IDLE else 0))

    def _set_running(self, running: bool) -> None:
        state = "normal" if not running else "disabled"
        self.after(0, lambda: self.login_button.configure(state=state))
        self.after(0, lambda: self.username_entry.configure(state=state))
        self.after(0, lambda: self.password_entry.configure(state=state))
        self.after(0, lambda: self.show_browser_checkbox.configure(state=state))
        self.after(0, lambda: self.dry_run_checkbox.configure(state=state))
        if not running:
            self._run_guard.stop()

    def _open_template_file(self):
        try:
            os.startfile(config.TEMPLATE_FILE.resolve())
        except Exception as exc:
            self._thread_status(f"Gagal membuka template: {exc}")

    def _open_log_file(self):
        try:
            os.startfile(config.LOG_FILE.resolve())
        except Exception as exc:
            self._thread_status(f"Gagal membuka file log: {exc}")

    def _open_debug_directory(self):
        try:
            path = config.DEBUG_DIR.resolve()
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as exc:
            self._thread_status(f"Gagal membuka folder debug: {exc}")

    def _confirm_production_submission(self) -> bool:
        if self.dry_run_var.get():
            return True

        template = load_journal_template()
        if not template:
            self._log("Template jurnal kosong. Tidak dapat melakukan konfirmasi pengiriman.")
            return False

        entry = template[0]
        message = (
            "Anda akan mengirim jurnal berikut ke SIMPEG. Periksa kembali data sebelum melanjutkan.\n\n"
            f"Jam mulai: {entry['start_hour']}\n"
            f"Jam selesai: {entry['end_hour']}\n"
            f"Deskripsi kegiatan: {entry['activity_description']}\n"
            f"Nilai penyelesaian: {entry['completion_value']}"
        )
        return messagebox.askyesno(
            "Konfirmasi Pengiriman Produksi",
            message,
            icon="warning",
            default="no",
        )

    def _start_automation(self, username: str, password: str) -> None:
        self._set_running(True)
        self._set_state(AutomationState.STARTING)
        self.progress.set(0)
        self._log("Memulai proses otomatisasi...")
        thread = threading.Thread(target=self._run_automation, args=(username, password), daemon=True)
        thread.start()

    def _on_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            self._log("Mohon masukkan username dan password.")
            return

        if not request_automation_start(
            dry_run=self.dry_run_var.get(),
            confirmation_callback=self._confirm_production_submission,
            start_callback=lambda: self._start_automation(username, password),
            run_guard=self._run_guard,
        ):
            if self._run_guard.running:
                self._log("Otomatisasi sedang berjalan. Tunggu hingga selesai.")
            else:
                self._log("Pengiriman produksi dibatalkan oleh pengguna.")
            return

    def _run_automation(self, username: str, password: str):
        try:
            automator = SimpegAutomator(
                username,
                password,
                show_browser=self.show_browser_var.get(),
                dry_run=self.dry_run_var.get(),
                on_status=self._thread_status,
                on_state=self._thread_state,
            )
            automator.run()
            self._thread_status("Proses selesai. Periksa log di file simpeg_journal.log jika diperlukan.")
        except Exception as exc:
            log.exception("Terjadi kesalahan otomatisasi")
            self._thread_status(f"Terjadi kesalahan: {exc}")
        finally:
            self.after(0, lambda: self._set_running(False))

    def _thread_status(self, message: str) -> None:
        self.after(0, lambda: self._log(message))

    def _thread_state(self, state: AutomationState) -> None:
        self.after(0, lambda: self._set_state(state))
