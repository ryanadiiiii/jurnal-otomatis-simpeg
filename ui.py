"""CustomTkinter UI for the SIMPEG journal automation app."""
import threading
import customtkinter as ctk
from automation import SimpegAutomator
from logger import get_logger

log = get_logger()


class JournalApp(ctk.CTk):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("SIMPEG Jurnal Harian Otomatis")
        self.geometry("640x520")
        self.resizable(False, False)

        self._build_login_frame()
        self._build_status_frame()

    def _build_login_frame(self):
        self.login_frame = ctk.CTkFrame(self, corner_radius=12)
        self.login_frame.pack(padx=24, pady=(24, 12), fill="x")

        self.header_label = ctk.CTkLabel(self.login_frame, text="Login SIMPEG", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(pady=(16, 12))

        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username")
        self.username_entry.pack(padx=20, pady=(0, 12), fill="x")

        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Password", show="*")
        self.password_entry.pack(padx=20, pady=(0, 16), fill="x")

        self.login_button = ctk.CTkButton(self.login_frame, text="Mulai Otomatisasi", command=self._on_login)
        self.login_button.pack(padx=20, pady=(0, 16), fill="x")

    def _build_status_frame(self):
        self.status_frame = ctk.CTkFrame(self, corner_radius=12)
        self.status_frame.pack(padx=24, pady=(0, 24), fill="both", expand=True)

        self.status_label = ctk.CTkLabel(self.status_frame, text="Status:", anchor="w")
        self.status_label.pack(padx=20, pady=(16, 0), fill="x")

        self.status_text = ctk.CTkTextbox(self.status_frame, width=580, height=250, state="normal")
        self.status_text.pack(padx=20, pady=(8, 12), fill="both", expand=True)
        self.status_text.configure(state="disabled")

    def _log(self, message: str) -> None:
        formatted = f"{message}\n"
        self.status_text.configure(state="normal")
        self.status_text.insert("end", formatted)
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def _on_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            self._log("Mohon masukkan username dan password.")
            return

        self.login_button.configure(state="disabled")
        self._log("Memulai proses otomatisasi...")
        thread = threading.Thread(target=self._run_automation, args=(username, password), daemon=True)
        thread.start()

    def _run_automation(self, username: str, password: str):
        try:
            automator = SimpegAutomator(username, password, on_status=self._thread_status)
            automator.run()
            self._thread_status("Proses selesai. Periksa log di file simpeg_journal.log jika diperlukan.")
        except Exception as exc:
            log.exception("Terjadi kesalahan otomatisasi")
            self._thread_status(f"Terjadi kesalahan: {exc}")
        finally:
            self.after(0, lambda: self.login_button.configure(state="normal"))

    def _thread_status(self, message: str) -> None:
        self.after(0, lambda: self._log(message))
