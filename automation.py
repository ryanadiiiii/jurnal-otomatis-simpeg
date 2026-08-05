"""Playwright automation layer for SIMPEG daily journal submission."""
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config
import logger
import utils

log = logger.get_logger()


class SimpegAutomator:
    """Encapsulates login, captcha resolution, and journal submission."""

    def __init__(self, username: str, password: str, on_status=None):
        self.username = username
        self.password = password
        self.on_status = on_status or (lambda message: None)
        self.browser = None
        self.page = None

    def _update_status(self, message: str) -> None:
        log.info(message)
        self.on_status(message)

    def _solve_captcha(self) -> str:
        captcha_file = Path("captcha.png")
        element = self.page.query_selector(config.SELECTORS["captcha_image"])
        if not element:
            raise RuntimeError("Captcha image selector tidak ditemukan pada halaman.")

        element.screenshot(path=str(captcha_file))
        self._update_status("Memindai captcha dengan EasyOCR...")
        text = utils.solve_captcha(captcha_file, languages=("en", "id"))
        if not text:
            self._update_status("Captcha OCR gagal membaca teks.")
        else:
            self._update_status(f"Captcha terdeteksi: {text}")
        return text

    def _check_login_success(self) -> bool:
        try:
            self.page.wait_for_selector(config.SELECTORS["journal_submit"], timeout=5000)
            return True
        except PlaywrightTimeoutError:
            return False

    def _fill_journal(self):
        self._update_status("Membuka halaman jurnal harian...")
        self.page.goto(config.JOURNAL_URL)
        self.page.wait_for_load_state("networkidle")

        for index, entry in enumerate(config.JOURNAL_TEMPLATE, start=1):
            self._update_status(f"Mengisi entri jurnal ke-{index}: {entry['task']}")
            task_selector = f"{config.SELECTORS['journal_task']}:nth-of-type({index})"
            status_selector = f"{config.SELECTORS['journal_status']}:nth-of-type({index})"
            notes_selector = f"{config.SELECTORS['journal_notes']}:nth-of-type({index})"

            try:
                self.page.fill(task_selector, entry["task"])
                self.page.select_option(status_selector, label=entry["status"])
                self.page.fill(notes_selector, entry["notes"])
            except Exception:
                self._update_status("Peringatan: struktur form jurnal mungkin berbeda. Periksa selector.")

        self._update_status("Menyimpan entri jurnal...")
        self.page.click(config.SELECTORS["journal_submit"])
        self.page.wait_for_timeout(2000)
        self._update_status("Enti jurnal telah disimpan.")

    def run(self) -> None:
        self._update_status("Memulai browser Playwright...")
        with sync_playwright() as browser_context:
            self.browser = browser_context.chromium.launch(headless=False)
            self.page = self.browser.new_page()
            self.page.goto(config.LOGIN_URL)
            self.page.wait_for_load_state("networkidle")

            self.page.fill(config.SELECTORS["username"], self.username)
            self.page.fill(config.SELECTORS["password"], self.password)

            for attempt in range(1, config.MAX_CAPTCHA_RETRIES + 1):
                self._update_status(f"Percobaan login #{attempt}...")
                captcha_text = self._solve_captcha()
                if not captcha_text:
                    self._update_status("Gagal mendapatkan captcha, mencoba ulang...")
                    self.page.reload()
                    continue

                self.page.fill(config.SELECTORS["captcha_input"], captcha_text)
                self.page.click(config.SELECTORS["login_button"])
                self.page.wait_for_timeout(2000)

                if self._check_login_success():
                    self._update_status("Login berhasil.")
                    self._fill_journal()
                    return

                self._update_status("Login gagal. Mengulang percobaan captcha...")
                self.page.reload()

            raise RuntimeError("Login gagal setelah beberapa percobaan captcha. Coba lagi nanti.")
