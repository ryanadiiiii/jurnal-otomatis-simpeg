"""Playwright automation layer for SIMPEG daily journal submission."""
import json
import os
import tempfile
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import config
import logger
import utils
from exceptions import (
    CaptchaRecognitionError,
    DuplicateJournalError,
    JournalEntryError,
    JournalPageError,
    JournalSubmissionError,
    LoginError,
    ManualLoginTimeoutError,
)
from template_loader import load_journal_template

log = logger.get_logger()


class AutomationState(Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    LOGGING_IN = "LOGGING_IN"
    WAITING_FOR_MANUAL_CAPTCHA = "WAITING_FOR_MANUAL_CAPTCHA"
    OPENING_JOURNAL = "OPENING_JOURNAL"
    FILLING_JOURNAL = "FILLING_JOURNAL"
    SUBMITTING = "SUBMITTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CLOSING = "CLOSING"


class SimpegAutomator:
    """Encapsulates login, captcha resolution, and journal submission."""

    def __init__(
        self,
        username: str,
        password: str,
        show_browser: bool = True,
        dry_run: bool | None = None,
        on_status: Callable[[str], None] | None = None,
        on_state: Callable[[AutomationState], None] | None = None,
        activity_description_override: str | None = None,
    ):
        self.username = username
        self.password = password
        self.show_browser = show_browser
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self.on_status = on_status or (lambda message: None)
        self.on_state = on_state or (lambda state: None)
        self.state = AutomationState.IDLE
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self.template = []
        self._ocr_reader = None
        self._submission_started = False
        self._duplicate_detection_available = False
        self._activity_description_override = activity_description_override

    def _update_status(self, message: str) -> None:
        log.info(message)
        self.on_status(message)

    def _audit_record(self, entry: dict, result: str) -> None:
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "mode": "dry-run" if self.dry_run else "production",
            "activity_description_short": entry["activity_description"][:64],
            "start_hour": entry["start_hour"],
            "end_hour": entry["end_hour"],
            "result": result,
        }
        try:
            with open(config.AUDIT_LOG_FILE, "a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.warning(f"Gagal menulis audit log: {exc}")

    def _set_state(self, new_state: AutomationState) -> None:
        self.state = new_state
        log.info(f"State updated: {new_state.value}")
        self.on_state(new_state)

    def _debug_path(self, prefix: str, extension: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return config.DEBUG_DIR / f"{prefix}-{timestamp}.{extension}"

    def _save_debug_artifacts(self, prefix: str, summary: str) -> None:
        try:
            config.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            screenshot_path = self._debug_path(prefix, "png")
            html_path = self._debug_path(prefix, "html")
            summary_path = self._debug_path(prefix, "txt")

            if self.page:
                self.page.screenshot(path=str(screenshot_path), full_page=True)
                html_content = self.page.content()
                html_path.write_text(html_content, encoding="utf-8")
                summary_text = f"URL: {self.page.url}\nSummary: {summary}\nState: {self.state.value}\n"
            else:
                summary_text = f"Summary: {summary}\nState: {self.state.value}\n"

            summary_path.write_text(summary_text, encoding="utf-8")
            log.warning(f"Debug artifacts saved: {screenshot_path}, {html_path}, {summary_path}")
        except Exception as exc:
            log.warning(f"Gagal menyimpan debug artifacts: {exc}")

    def _initialize_ocr_reader(self) -> None:
        if self._ocr_reader is None:
            self._ocr_reader = utils.get_ocr_reader(languages=("en", "id"))

    def _set_page_defaults(self) -> None:
        if self.page is None:
            return
        self.page.set_default_timeout(config.SELECTOR_TIMEOUT)
        self.page.set_default_navigation_timeout(config.PAGE_LOAD_TIMEOUT)

    def _verify_portal_entry_visible(self) -> bool:
        try:
            portal_entry = self.page.get_by_role("definition").filter(
                has_text="SIMPEG HUKUMSIMPEG HUKUM"
            ).get_by_role("img")
            portal_entry.wait_for(state="visible", timeout=config.PAGE_LOAD_TIMEOUT)
            return True
        except PlaywrightTimeoutError:
            return False
        except Exception as exc:
            log.info(f"Portal verification error: {exc}")
            return False

    def _make_locator(self, selector: str):
        if selector.startswith("css:"):
            return self.page.locator(selector[4:])
        if selector.startswith("locator:"):
            return self.page.locator(selector[8:])
        if selector.startswith("role:"):
            parts = selector.split("|")
            role_name = parts[0][5:]
            kwargs = {}
            nested_role = None
            has_text = None
            for part in parts[1:]:
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                if key == "name":
                    kwargs["name"] = value
                elif key == "exact":
                    kwargs["exact"] = value.lower() == "true"
                elif key == "has_text":
                    has_text = value
                elif key == "nested_role":
                    nested_role = value
            locator = self.page.get_by_role(role_name, **kwargs)
            if has_text is not None:
                locator = locator.filter(has_text=has_text)
            if nested_role is not None:
                locator = locator.get_by_role(nested_role)
            return locator
        if selector.startswith("text:"):
            parts = selector.split("|")
            text_value = parts[0][5:]
            exact = False
            for part in parts[1:]:
                if part.startswith("exact:"):
                    exact = part.split(":", 1)[1].lower() == "true"
            return self.page.get_by_text(text_value, exact=exact)
        return self.page.locator(selector)

    def _normalize_text(self, text: str) -> str:
        return " ".join(str(text or "").split()).strip()

    def _get_locator_by_label_or_selector(self, selector_key: str, label_text: str | None = None):
        if label_text and hasattr(self.page, "get_by_label"):
            try:
                label_locator = self.page.get_by_label(label_text)
                if label_locator.count() > 0:
                    return label_locator
            except Exception:
                pass

        selector = config.SELECTORS.get(selector_key)
        if not selector:
            raise JournalPageError(
                f"Locator untuk field '{selector_key}' tidak ditemukan. Periksa konfigurasi dan label terkait."
            )

        locator = self._make_locator(selector)
        if locator.count() == 0:
            raise JournalPageError(f"Field jurnal '{selector_key}' tidak ditemukan atau tidak terlihat.")
        return locator

    def _select_dropdown_option(self, locator, label: str) -> None:
        self._update_status(f"Memilih kategori SKP: {label}...")
        try:
            # Attempt 1: Exact label match with a short timeout
            locator.select_option(label=label, timeout=3000)
        except Exception:
            try:
                # Attempt 2: Case-insensitive label match
                options = locator.locator("option").element_handles()
                matched_value = None
                for opt in options:
                    opt_text = opt.inner_text()
                    if opt_text and opt_text.strip().lower() == label.strip().lower():
                        matched_value = opt.get_attribute("value")
                        break
                
                if matched_value is not None:
                    locator.select_option(value=matched_value)
                else:
                    # Attempt 3: exact value match if user put the value in template
                    locator.select_option(value=label)
            except Exception as e:
                self._save_debug_artifacts(
                    "skp-category-error",
                    f"Gagal memilih SKP: {e}",
                )
                raise JournalEntryError(
                    f'Pilihan SKP "{label}" tidak ditemukan di dropdown.'
                ) from e

        selected_text = ""
        try:
            selected_text = locator.locator("option:checked").inner_text()
        except Exception:
            selected_text = locator.input_value()

        if self._normalize_text(selected_text).lower() != self._normalize_text(label).lower():
            self._save_debug_artifacts(
                "skp-category-mismatch",
                f"Pilihan SKP terdeteksi: {selected_text}",
            )
            raise JournalEntryError(
                f'Pilihan SKP gagal diubah menjadi "{label}". Pengiriman dibatalkan.'
            )

        self._update_status("Kategori SKP berhasil dipilih.")

    def _verify_field_value(self, locator, expected: str, field_name: str) -> None:
        actual = self._normalize_text(locator.input_value())
        if actual.lower() != self._normalize_text(expected).lower():
            raise JournalEntryError(
                f"Nilai field '{field_name}' tidak cocok. Diharapkan '{expected}', ditemukan '{actual}'."
            )

    def _wait_for_selector(self, selector_key: str, timeout: int | None = None):
        timeout = timeout or config.TIMEOUTS["selector"]
        locator = self._make_locator(config.SELECTORS[selector_key])
        locator.wait_for(state="visible", timeout=timeout)
        return locator

    def _click_selector(self, selector_key: str) -> None:
        locator = self._make_locator(config.SELECTORS[selector_key])
        locator.click()

    def _take_captcha_screenshot(self) -> Path:
        selector = config.SELECTORS.get("captcha_image")
        if not selector:
            raise CaptchaRecognitionError("Selector captcha_image tidak dikonfigurasi."
                                         "Gunakan login manual.")
        element = self._make_locator(selector)
        element.wait_for(state="visible", timeout=config.TIMEOUTS["selector"])
        temp_file = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".png").name)
        element.screenshot(path=str(temp_file))
        return temp_file

    def _recognize_captcha(self) -> str:
        self._update_status("Memindai captcha dengan EasyOCR...")
        self._initialize_ocr_reader()
        screenshot_path = self._take_captcha_screenshot()
        try:
            # Use math captcha solver for SIMPEG's math-based captcha
            text = utils.solve_math_captcha(screenshot_path, reader=self._ocr_reader)
            if not text:
                raise CaptchaRecognitionError("OCR gagal membaca captcha.")
            if config.CAPTCHA_EXPECTED_LENGTH and len(text) != config.CAPTCHA_EXPECTED_LENGTH:
                raise CaptchaRecognitionError(
                    "Hasil OCR captcha tidak sesuai panjang yang diharapkan."
                )
            self._update_status(f"Captcha terdeteksi: {text}")
            return text
        finally:
            try:
                screenshot_path.unlink()
            except Exception:
                pass

    def _refresh_captcha(self) -> None:
        """Click the captcha refresh button to get a new captcha image."""
        try:
            refresh_selector = config.SELECTORS.get("captcha_refresh_button")
            if refresh_selector:
                refresh_button = self._make_locator(refresh_selector)
                if refresh_button.count() > 0:
                    refresh_button.click()
                    time.sleep(1)  # Wait for new captcha to load
        except Exception as exc:
            log.info(f"Gagal refresh captcha: {exc}")

    def _open_login_page(self) -> None:
        for attempt in range(1, 4):
            self._update_status(f"Membuka portal SIMPEG... percobaan {attempt}/3")
            try:
                self.page.goto(
                    config.PORTAL_URL,
                    wait_until="commit",
                    timeout=config.PAGE_LOAD_TIMEOUT,
                )
            except PlaywrightTimeoutError as exc:
                current_url = getattr(self.page, "url", "") or ""
                if current_url.startswith(config.SIMPEG_BASE_URL) and self._verify_portal_entry_visible():
                    self._update_status(
                        "Portal SIMPEG tersedia meskipun navigasi timeout. Melanjutkan."
                    )
                    break
                if attempt == 3:
                    self._save_debug_artifacts(
                        "portal-navigation-failed",
                        f"Gagal membuka portal setelah {attempt} percobaan. URL saat ini: {current_url}",
                    )
                    raise LoginError(
                        "Gagal membuka portal SIMPEG setelah beberapa kali percobaan. Periksa koneksi jaringan dan coba lagi."
                    ) from exc
                self._update_status(f"Timeout pada portal, mencoba ulang ({attempt + 1}/3)...")
                time.sleep(config.TIMEOUTS["login_retry_delay"] / 1000.0)
                continue

            if self._verify_portal_entry_visible():
                break

            if attempt == 3:
                self._save_debug_artifacts(
                    "portal-navigation-failed",
                    f"Portal SIMPEG tidak muncul setelah {attempt} percobaan. URL saat ini: {getattr(self.page, 'url', '')}",
                )
                raise LoginError(
                    "Elemen SIMPEG HUKUM tidak muncul setelah membuka portal. Periksa koneksi jaringan atau perubahan tampilan portal."
                )

            self._update_status(f"Portal tidak ditemukan, mencoba ulang ({attempt + 1}/3)...")
            time.sleep(config.TIMEOUTS["login_retry_delay"] / 1000.0)

        with self.page.expect_popup() as popup_info:
            self._click_selector("portal_simpeg_hukum")
        self.page = popup_info.value
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_url("**/devp/siap/signin.php", timeout=config.PAGE_LOAD_TIMEOUT)
        self._wait_for_selector("nip_input")

    def _fill_login_step1(self) -> None:
        self._update_status("Mengisi NIP...")
        nip_input = self._make_locator(config.SELECTORS["nip_input"])
        nip_input.fill(self.username)
        self._click_selector("continue_button")
        try:
            self._wait_for_selector("password_input", timeout=config.TIMEOUTS["login_result"])
        except PlaywrightTimeoutError as exc:
            self._save_debug_artifacts("login-password-missing", str(exc))
            raise LoginError(
                "Field password tidak muncul setelah klik Masuk. Periksa apakah halaman NIP telah dimuat dengan benar."
            ) from exc

    def _fill_login_step2(self) -> None:
        self._update_status("Mengisi password...")
        self._make_locator(config.SELECTORS["password_input"]).fill(self.password)

        # Try auto-solve captcha first
        captcha_solved = False
        for captcha_attempt in range(1, config.MAX_CAPTCHA_ATTEMPTS + 1):
            try:
                self._update_status(f"Mencoba solve captcha otomatis (percobaan {captcha_attempt}/{config.MAX_CAPTCHA_ATTEMPTS})...")
                captcha_answer = self._recognize_captcha()
                if captcha_answer:
                    captcha_input = self._make_locator(config.SELECTORS["captcha_input"])
                    captcha_input.fill(captcha_answer)
                    self._update_status(f"Captcha terdeteksi: {captcha_answer}. Mengklik Login...")
                    self._click_selector("login_button")

                    # Check if login succeeded
                    if self._wait_for_login_result(config.TIMEOUTS["login_result"]):
                        self._update_status("Login berhasil dengan captcha otomatis!")
                        captcha_solved = True
                        break

                    # Login failed, captcha might be wrong - refresh and retry
                    self._update_status("Captcha salah, mencoba refresh...")
                    self._refresh_captcha()
                    time.sleep(config.TIMEOUTS["captcha_retry_delay"] / 1000.0)
                    continue
            except CaptchaRecognitionError as exc:
                self._update_status(f"OCR captcha gagal: {exc}")
                self._update_status("Mencoba refresh...")
                self._refresh_captcha()
                time.sleep(config.TIMEOUTS["captcha_retry_delay"] / 1000.0)
                continue
            except Exception as exc:
                self._update_status(f"Error saat solve captcha: {exc}")
                break

        if not captcha_solved:
            # Fall back to manual captcha
            self._request_manual_captcha()

        self._update_status("Login berhasil. Melanjutkan ke Jurnal Harian...")

    def _wait_for_login_result(self, timeout: int) -> bool:
        try:
            self._wait_for_selector("kinerja_menu", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            try:
                self._make_locator(config.SELECTORS["close_dialog_button"]).wait_for(
                    state="visible",
                    timeout=timeout,
                )
                return True
            except PlaywrightTimeoutError:
                return False

    def _request_manual_captcha(self) -> None:
        self._set_state(AutomationState.WAITING_FOR_MANUAL_CAPTCHA)
        self._update_status(
            "OCR gagal. Silakan isi captcha secara manual di browser dan klik login. Menunggu login manual..."
        )
        if not self._wait_for_login_result(config.TIMEOUTS["manual_captcha"]):
            raise ManualLoginTimeoutError("Login manual tidak selesai sebelum batas waktu.")

    def _close_information_dialog(self) -> None:
        try:
            dialog_button = self._make_locator(config.SELECTORS["close_dialog_button"])
            if dialog_button.count() > 0:
                dialog_button.click()
                self._update_status("Dialog informasi setelah login ditutup.")
        except Exception:
            log.info("Dialog informasi tidak ditemukan atau tidak dapat ditutup.")

    def _cleanup_modals_and_backdrops(self) -> None:
        """Forcefully close any open modal, dialog, or lingering backdrop."""
        try:
            # 1. Click common close/OK buttons if visible
            for selector in [
                "button:has-text('OK')",
                "button:has-text('Ok')",
                "button:has-text('TUTUP')",
                "button:has-text('Tutup')",
                "button:has-text('Close')",
                ".modal .close",
                "#button-close",
            ]:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=1000)
                        time.sleep(0.5)
                except Exception:
                    pass

            # 2. Force remove via JavaScript
            self.page.evaluate("""
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.querySelectorAll('.swal2-container').forEach(el => el.remove());
                document.querySelectorAll('.modal').forEach(el => {
                    el.classList.remove('in', 'show');
                    el.style.display = 'none';
                });
                document.body.classList.remove('modal-open', 'swal2-shown');
            """)
            time.sleep(0.5)
        except Exception as exc:
            log.info(f"Pembersihan modal selesai: {exc}")

    def _close_success_dialog_if_present(self) -> None:
        self._cleanup_modals_and_backdrops()

    def _detect_duplicate_journal(self) -> bool:
        if not all(
            config.SELECTORS.get(key)
            for key in [
                "journal_table_rows",
                "journal_row_description",
                "journal_row_start_hour",
                "journal_row_end_hour",
            ]
        ):
            log.info("Duplicate detection selectors unavailable. Duplicate checking not performed.")
            self._duplicate_detection_available = False
            return False

        self._duplicate_detection_available = True
        rows = self._make_locator(config.SELECTORS["journal_table_rows"])
        if rows.count() == 0:
            return False

        entry = self.template[0]
        for index in range(rows.count()):
            row = rows.nth(index)
            try:
                description = row.locator(config.SELECTORS["journal_row_description"]).inner_text().strip()
                start_hour = row.locator(config.SELECTORS["journal_row_start_hour"]).inner_text().strip()
                end_hour = row.locator(config.SELECTORS["journal_row_end_hour"]).inner_text().strip()

                desc_match = description == entry["activity_description"].strip()
                start_match = (
                    start_hour == entry["start_hour"].strip()
                    or start_hour.startswith(entry["start_hour"].strip())
                )
                end_match = (
                    end_hour == entry["end_hour"].strip()
                    or end_hour.startswith(entry["end_hour"].strip())
                )

                if desc_match or (start_match and end_match):
                    return True
            except Exception:
                continue

        # If any journal row already exists on this date
        if rows.count() >= len(self.template):
            return True

        return False

    def _verify_submission_in_table(self) -> None:
        if not all(
            config.SELECTORS.get(key)
            for key in [
                "journal_table_rows",
                "journal_row_description",
                "journal_row_start_hour",
                "journal_row_end_hour",
            ]
        ):
            log.info("Post-submit verification selectors unavailable. Cannot verify submitted row in table.")
            return

        rows = self._make_locator(config.SELECTORS["journal_table_rows"])
        entry = self.template[0]
        for index in range(rows.count()):
            row = rows.nth(index)
            try:
                description = row.locator(config.SELECTORS["journal_row_description"]).inner_text().strip()
                start_hour = row.locator(config.SELECTORS["journal_row_start_hour"]).inner_text().strip()
                end_hour = row.locator(config.SELECTORS["journal_row_end_hour"]).inner_text().strip()

                desc_match = description == entry["activity_description"].strip()
                start_match = (
                    start_hour == entry["start_hour"].strip()
                    or start_hour.startswith(entry["start_hour"].strip())
                )
                end_match = (
                    end_hour == entry["end_hour"].strip()
                    or end_hour.startswith(entry["end_hour"].strip())
                )

                if desc_match or (start_match and end_match):
                    self._update_status("Entri jurnal yang dikirim telah diverifikasi muncul di tabel.")
                    return
            except Exception:
                continue
        self._update_status("Entri jurnal tidak dapat diverifikasi di tabel setelah pengiriman.")

    def _open_journal_page(self) -> None:
        self._update_status("Membuka halaman jurnal harian...")
        self._close_information_dialog()
        self._click_selector("kinerja_menu")
        self._click_selector("daily_journal_cell")
        self.page.goto(config.JOURNAL_URL, wait_until="domcontentloaded", timeout=config.TIMEOUTS["journal_page"])

        if self._detect_duplicate_journal():
            self._audit_record(self.template[0], "prevented_duplicate")
            message = (
                "Jurnal yang sama sudah tercatat. Pengiriman dibatalkan untuk mencegah duplikasi."
            )
            raise DuplicateJournalError(message)

        self._click_selector("add_journal_link")
        self._wait_for_selector("start_hour")

    def _open_journal_page_base(self) -> None:
        """Navigate to the journal page without checking duplicates or opening the form."""
        self._update_status("Membuka halaman jurnal harian...")
        self._close_information_dialog()
        self._click_selector("kinerja_menu")
        self._click_selector("daily_journal_cell")
        self.page.goto(config.JOURNAL_URL, wait_until="domcontentloaded", timeout=config.TIMEOUTS["journal_page"])

    def _set_journal_date(self, date_str: str) -> None:
        """Change the date on the journal page and wait for table reload.

        Args:
            date_str: Date in DD-MM-YYYY format (e.g., '03-10-2026').
        """
        self._update_status(f"Mengatur tanggal jurnal ke {date_str}...")
        # Set the date input value and trigger the AJAX table reload
        self.page.evaluate(f"""
            document.getElementById('tgla').value = '{date_str}';
            loadlist('a');
        """)
        # Wait for the AJAX table reload to complete
        time.sleep(2)
        self.page.wait_for_load_state("networkidle", timeout=10000)

    def _fill_journal_entries(self) -> None:
        self._update_status("Memeriksa data jurnal...")
        if not self.template:
            raise JournalEntryError("Template jurnal kosong. Tidak ada entri untuk diisi.")

        entry = self.template[0]
        self._update_status("Memproses entri jurnal pertama...")

        start_hour_input = self._get_locator_by_label_or_selector("start_hour")
        end_hour_input = self._get_locator_by_label_or_selector("end_hour")
        skp_category_input = self._get_locator_by_label_or_selector(
            "skp_category",
            label_text="SKP Tahunan/Tugas Tambahan/Kreatifitas",
        )
        description_input = self._get_locator_by_label_or_selector("activity_description")
        completion_input = self._get_locator_by_label_or_selector("completion_value")

        start_minute_input = None
        end_minute_input = None
        if entry.get("start_minute") and config.SELECTORS.get("start_minute"):
            start_minute_input = self._get_locator_by_label_or_selector("start_minute")
        elif entry.get("start_minute"):
            if self.dry_run:
                self._update_status("Selector menit mulai belum diverifikasi; field dilewati.")
            else:
                raise JournalEntryError(
                    "Field menit belum terverifikasi. Pengiriman jurnal dibatalkan."
                )

        if entry.get("end_minute") and config.SELECTORS.get("end_minute"):
            end_minute_input = self._get_locator_by_label_or_selector("end_minute")
        elif entry.get("end_minute"):
            if self.dry_run:
                self._update_status("Selector menit selesai belum diverifikasi; field dilewati.")
            else:
                raise JournalEntryError(
                    "Field menit belum terverifikasi. Pengiriman jurnal dibatalkan."
                )

        for locator, name in (
            (start_hour_input, "start_hour"),
            (end_hour_input, "end_hour"),
            (skp_category_input, "skp_category"),
            (description_input, "activity_description"),
            (completion_input, "completion_value"),
        ):
            if locator.count() == 0 or not locator.first.is_visible():
                raise JournalEntryError(f"Field jurnal '{name}' tidak ditemukan atau tidak terlihat.")

        start_hour_input.select_option(entry["start_hour"])
        self._verify_field_value(start_hour_input, entry["start_hour"], "start_hour")

        if start_minute_input is not None:
            start_minute_input.select_option(entry["start_minute"])
            self._verify_field_value(start_minute_input, entry["start_minute"], "start_minute")

        end_hour_input.select_option(entry["end_hour"])
        self._verify_field_value(end_hour_input, entry["end_hour"], "end_hour")

        if end_minute_input is not None:
            end_minute_input.select_option(entry["end_minute"])
            self._verify_field_value(end_minute_input, entry["end_minute"], "end_minute")

        self._select_dropdown_option(skp_category_input, entry["skp_category"])

        description_input.fill(entry["activity_description"])
        self._verify_field_value(description_input, entry["activity_description"], "activity_description")

        completion_input.fill(entry["completion_value"])
        self._verify_field_value(completion_input, entry["completion_value"], "completion_value")

        # Fill satuan (unit) field if available in template
        if entry.get("satuan") and config.SELECTORS.get("satuan"):
            satuan_input = self._get_locator_by_label_or_selector("satuan")
            satuan_input.fill(entry["satuan"])
            self._verify_field_value(satuan_input, entry["satuan"], "satuan")

    def _submit_and_verify_journal(self) -> None:
        self._update_status("Mengirim jurnal ke SIMPEG...")

        submit_button = self._make_locator(config.SELECTORS["submit_button"])
        if submit_button.count() == 0 or not submit_button.first.is_visible():
            raise JournalSubmissionError("Tombol submit jurnal tidak ditemukan atau tidak terlihat.")

        if self._submission_started:
            raise JournalSubmissionError("Submit sudah dimulai sebelumnya. Tidak boleh mengklik tombol Simpan dua kali.")

        self._submission_started = True
        if self.dry_run:
            self._update_status("Tombol Simpan ditemukan.")
            self._update_status("Dry run aktif: tombol Simpan tidak diklik dan data tidak dikirim.")
            if self.template:
                self._audit_record(self.template[0], "dry_run")
            return

        if not submit_button.first.is_enabled():
            raise JournalSubmissionError("Tombol Simpan tidak aktif saat pengiriman jurnal.")

        self._update_status("Tombol Simpan ditemukan.")
        submit_button.click()
        self._update_status("Menunggu konfirmasi SIMPEG...")

        if config.SELECTORS.get("success_message"):
            try:
                success_indicator = self._make_locator(config.SELECTORS["success_message"])
                success_indicator.wait_for(state="visible", timeout=config.TIMEOUTS["submission_confirmation"])
                self._update_status("Jurnal berhasil dikirim dan dikonfirmasi oleh SIMPEG.")
                self._audit_record(self.template[0], "confirmed_success")
                self._close_success_dialog_if_present()
                self._verify_submission_in_table()
                return
            except PlaywrightTimeoutError as exc:
                self._save_debug_artifacts("submission-uncertain", str(exc))
                self._update_status(
                    "Status pengiriman belum dapat dipastikan. Jangan kirim ulang sebelum memeriksa jurnal di SIMPEG."
                )
                self._audit_record(self.template[0], "uncertain")
                raise JournalSubmissionError(
                    "Status pengiriman belum dapat dipastikan. Jangan kirim ulang sebelum memeriksa jurnal di SIMPEG."
                ) from exc
        raise JournalSubmissionError(
            "Tidak dapat memverifikasi penyimpanan jurnal. Periksa selector success_message di config.py."
        )

    def _perform_login(self) -> None:
        for attempt in range(1, config.MAX_LOGIN_ATTEMPTS + 1):
            self._set_state(AutomationState.LOGGING_IN)
            self._update_status(f"Percobaan login #{attempt}...")
            self._open_login_page()
            self._fill_login_step1()

            try:
                self._fill_login_step2()
                return  # _fill_login_step2 already handles login verification
            except ManualLoginTimeoutError:
                raise  # Don't retry manual login timeout
            except CaptchaRecognitionError as exc:
                self._save_debug_artifacts("captcha-error", str(exc))
                if attempt < config.MAX_LOGIN_ATTEMPTS:
                    self._update_status(f"Login gagal, mencoba ulang ({attempt + 1}/{config.MAX_LOGIN_ATTEMPTS})...")
                    time.sleep(config.TIMEOUTS["login_retry_delay"] / 1000.0)
                    continue
            except Exception as exc:
                self._save_debug_artifacts("login-error", str(exc))
                raise LoginError("Terjadi kesalahan saat proses login.") from exc

        raise LoginError("Login gagal setelah beberapa percobaan.")

    def close_browser(self) -> None:
        self._set_state(AutomationState.CLOSING)
        for resource_name, close_method in (
            ("page", lambda: self.page.close() if self.page else None),
            ("context", lambda: self.context.close() if self.context else None),
            ("browser", lambda: self.browser.close() if self.browser else None),
            ("playwright", lambda: self._playwright.stop() if self._playwright else None),
        ):
            try:
                close_method()
            except Exception as exc:
                log.warning(f"Gagal menutup {resource_name}: {exc}")

    def run_multi_day(self, target_dates: list[str]) -> dict[str, str]:
        """Run journal automation for multiple dates in a single browser session.

        Logs in once, navigates to the journal page, then for each date:
        1. Sets the date on the page
        2. Checks for duplicate entries
        3. Fills the journal form
        4. Submits (or dry-run skips)

        Args:
            target_dates: List of date strings in DD-MM-YYYY format.

        Returns:
            Dict mapping each date string to its result status:
            'success', 'dry_run', 'skipped_duplicate', or 'failed: <reason>'.
        """
        results: dict[str, str] = {}

        self._set_state(AutomationState.STARTING)
        try:
            config.validate_configuration()
            self.template = load_journal_template()
            # Override activity_description if per-account override is set
            if self._activity_description_override:
                for entry in self.template:
                    entry["activity_description"] = self._activity_description_override
        except Exception as exc:
            for d in target_dates:
                results[d] = f"failed: Validasi konfigurasi gagal: {exc}"
            return results

        self._create_debug_dir()

        try:
            # Start browser and login ONCE
            self._playwright = sync_playwright().start()
            self.browser = self._playwright.chromium.launch(headless=not self.show_browser)
            self.context = self.browser.new_context(ignore_https_errors=True)
            self.page = self.context.new_page()
            self._set_page_defaults()

            self._perform_login()

            # Navigate to journal page ONCE
            self._set_state(AutomationState.OPENING_JOURNAL)
            self._open_journal_page_base()

            # Process each date
            for date_str in target_dates:
                # Ensure no lingering modals or backdrops from previous operations
                self._cleanup_modals_and_backdrops()

                try:
                    self._update_status(f"\n{'='*40}")
                    self._update_status(f"📅 Mengisi jurnal untuk tanggal {date_str}...")
                    self._update_status(f"{'='*40}")

                    # Set the date on the page
                    self._set_journal_date(date_str)

                    # Check for duplicate
                    if self._detect_duplicate_journal():
                        self._update_status(f"⏭️ Jurnal {date_str} sudah ada, dilewati.")
                        self._audit_record(self.template[0], "prevented_duplicate")
                        results[date_str] = "skipped_duplicate"
                        continue

                    # Open the form
                    self._click_selector("add_journal_link")
                    self._wait_for_selector("start_hour")

                    # Fill the journal
                    self._set_state(AutomationState.FILLING_JOURNAL)
                    self._fill_journal_entries()

                    # Submit
                    self._set_state(AutomationState.SUBMITTING)
                    self._submission_started = False  # Reset for each date
                    self._submit_and_verify_journal()

                    if self.dry_run:
                        results[date_str] = "dry_run"
                    else:
                        results[date_str] = "success"

                    self._update_status(f"✅ Jurnal {date_str} berhasil!")

                except DuplicateJournalError:
                    self._update_status(f"⏭️ Jurnal {date_str} sudah ada, dilewati.")
                    results[date_str] = "skipped_duplicate"

                except Exception as exc:
                    self._update_status(f"❌ Gagal mengisi jurnal {date_str}: {exc}")
                    self._save_debug_artifacts(f"multi-day-error-{date_str}", str(exc))
                    results[date_str] = f"failed: {exc}"

                    # Forcefully clean up any open modal / backdrop so next date is never blocked
                    self._cleanup_modals_and_backdrops()

            self._set_state(AutomationState.SUCCESS)

        except Exception as exc:
            self._set_state(AutomationState.FAILED)
            self._save_debug_artifacts("multi-day-fatal", str(exc))
            # Mark remaining dates as failed
            for d in target_dates:
                if d not in results:
                    results[d] = f"failed: {exc}"
        finally:
            self.close_browser()

        return results

    def _create_debug_dir(self) -> None:
        config.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        self._set_state(AutomationState.STARTING)
        try:
            config.validate_configuration()
            self.template = load_journal_template()
            # Override activity_description if per-account override is set
            if self._activity_description_override:
                for entry in self.template:
                    entry["activity_description"] = self._activity_description_override
        except Exception as exc:
            raise LoginError(f"Validasi konfigurasi gagal: {exc}") from exc

        self._create_debug_dir()

        try:
            self._playwright = sync_playwright().start()
            self.browser = self._playwright.chromium.launch(headless=not self.show_browser)
            self.context = self.browser.new_context(ignore_https_errors=True)
            self.page = self.context.new_page()
            self._set_page_defaults()

            self._perform_login()
            self._set_state(AutomationState.OPENING_JOURNAL)
            self._open_journal_page()
            self._set_state(AutomationState.FILLING_JOURNAL)
            self._fill_journal_entries()
            if self._detect_duplicate_journal():
                self._audit_record(self.template[0], "prevented_duplicate")
                message = (
                    "Jurnal yang sama sudah tercatat. Pengiriman dibatalkan untuk mencegah duplikasi."
                )
                raise DuplicateJournalError(message)
            self._set_state(AutomationState.SUBMITTING)
            self._submit_and_verify_journal()
            self._set_state(AutomationState.SUCCESS)
        except ManualLoginTimeoutError:
            self._set_state(AutomationState.FAILED)
            raise
        except DuplicateJournalError:
            self._set_state(AutomationState.FAILED)
            raise
        except Exception as exc:
            self._set_state(AutomationState.FAILED)
            if self.template and not self.dry_run:
                try:
                    self._audit_record(self.template[0], "failed")
                except Exception:
                    pass
            self._save_debug_artifacts("automation-error", str(exc))
            raise
        finally:
            self.close_browser()
