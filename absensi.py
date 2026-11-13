"""Attendance (Absensi) automation for SIMPEG - Friday WFH online attendance."""
import time
import logging
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import config
import logger
import utils
from exceptions import LoginError, CaptchaRecognitionError, ManualLoginTimeoutError
from automation import SimpegAutomator, AutomationState

log = logger.get_logger()


class AbsensiAutomator(SimpegAutomator):
    """Handles SIMPEG online attendance (absensi) for Friday WFH."""

    def __init__(
        self,
        username: str,
        password: str,
        mode: str = "datang",
        latitude: float = -8.5925,
        longitude: float = 116.0947,
        show_browser: bool = False,
        dry_run: bool = False,
        **kwargs,
    ):
        super().__init__(
            username=username,
            password=password,
            show_browser=show_browser,
            dry_run=dry_run,
            **kwargs,
        )
        self.mode = mode  # "datang" or "pulang"
        self.latitude = latitude
        self.longitude = longitude

    def _navigate_to_absensi(self) -> None:
        """Navigate to the attendance page after login."""
        self._update_status("Membuka halaman Absensi...")
        self._close_information_dialog()

        # Click ABSENSI menu
        absensi_link = self.page.get_by_role("link", name="ABSENSI")
        absensi_link.wait_for(state="visible", timeout=15000)
        absensi_link.click()
        time.sleep(2)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

    def _click_absensi_button(self) -> str:
        """Click the appropriate attendance button based on mode.
        
        Flow from recording:
        1. Click "Absensi Online" button first (or navigate to inout page)
        2. Then click "Rekam Absen Masuk" or "Rekam Absen Pulang"
        
        Returns:
            The text of the button that was clicked.
        """
        # Step 1: Click "Absensi Online" to open the attendance panel
        self._update_status("Mengklik tombol Absensi Online...")
        
        # Check if already on the inout page
        if "/AbsensiOnline/inout" not in self.page.url:
            try:
                absensi_online_btn = self.page.get_by_role("button", name="Absensi Online")
                absensi_online_btn.wait_for(state="visible", timeout=15000)
                if not self.dry_run:
                    absensi_online_btn.click()
                    try:
                        self.page.wait_for_url("**/AbsensiOnline/inout**", timeout=20000)
                    except Exception:
                        pass
                else:
                    self._update_status("[DRY RUN] Tombol 'Absensi Online' ditemukan, tidak diklik.")
                    return "Absensi Online"
            except Exception as e:
                log.warning(f"Tombol 'Absensi Online' tidak ditemukan atau gagal ({e}), direct goto inout...")
                self.page.goto(
                    "https://simpeg.kemenkum.go.id/devp/siap/index.php/AbsensiOnline/inout",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

        # Check for 504 / 502 / RELOAD BROWSER error and reload if needed
        content = self.page.content()
        if "504 Gateway" in content or "502 Bad Gateway" in content or "RELOAD BROWSER" in content:
            log.warning("Halaman absensi menampilkan 504/502/RELOAD, mencoba reload dalam 3 detik...")
            time.sleep(3)
            self.page.reload(wait_until="domcontentloaded", timeout=30000)

        # Step 2: Click the correct attendance button
        if self.mode == "datang":
            keyword = "Masuk"
            selector = "input[value='Rekam Absen Masuk'], input[value*='Masuk'], button:has-text('Absen Masuk'), button:has-text('Masuk')"
        else:
            keyword = "Pulang"
            selector = "input[value='Rekam Absen Pulang'], input[value*='Pulang'], button:has-text('Absen Pulang'), button:has-text('Pulang')"

        clicked_name = None
        try:
            btn = self.page.locator(selector).first
            btn.wait_for(state="visible", timeout=25000)
            clicked_name = btn.get_attribute("value") or btn.inner_text() or f"Absen {keyword}"
            btn.click()
            self._update_status(f"Tombol '{clicked_name}' diklik.")
        except Exception as exc:
            log.warning(f"Tombol absensi belum terlihat via selector '{selector}': {exc}. Mencoba reload 1x...")
            try:
                self.page.reload(wait_until="domcontentloaded", timeout=25000)
                btn = self.page.locator(selector).first
                btn.wait_for(state="visible", timeout=20000)
                clicked_name = btn.get_attribute("value") or btn.inner_text() or f"Absen {keyword}"
                btn.click()
                self._update_status(f"Tombol '{clicked_name}' diklik setelah reload.")
            except Exception:
                pass

        if not clicked_name:
            raise Exception(
                f"Tombol '{'Rekam Absen Masuk' if self.mode == 'datang' else 'Rekam Absen Pulang'}' "
                f"tidak ditemukan. Mungkin bukan hari Jumat atau di luar jam absensi."
            )

        return clicked_name

    def _handle_location_permission(self) -> None:
        """Handle the geolocation permission dialog."""
        time.sleep(2)
        # Try clicking OK/Izinkan on any confirmation dialog
        for btn_name in ["OK", "Izinkan", "Allow", "Ya"]:
            try:
                btn = self.page.get_by_role("button", name=btn_name, exact=True)
                if btn.count() > 0 and btn.first.is_visible():
                    if not self.dry_run:
                        btn.click()
                    self._update_status(f"Dialog lokasi dikonfirmasi ({btn_name}).")
                    time.sleep(2)
                    return
            except Exception:
                continue

        self._update_status("Tidak ada dialog konfirmasi lokasi yang perlu diklik.")

    def _handle_success_confirmation(self) -> None:
        """Handle success confirmation after attendance submission."""
        time.sleep(2)
        for btn_name in ["OK", "Tutup", "Close"]:
            try:
                btn = self.page.get_by_role("button", name=btn_name, exact=True)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.click()
                    self._update_status(f"Dialog sukses ditutup ({btn_name}).")
                    time.sleep(1)
                    return
            except Exception:
                continue

    def run_absensi(self) -> dict[str, str]:
        """Execute the attendance automation.
        
        Returns:
            Dict with result status.
        """
        mode_label = "Absen Datang" if self.mode == "datang" else "Absen Pulang"
        result = {"mode": self.mode, "status": "unknown", "timestamp": ""}

        self._set_state(AutomationState.STARTING)

        try:
            config.validate_configuration()
            self.template = []  # Not needed for absensi
        except Exception as exc:
            result["status"] = f"failed: {exc}"
            return result

        self._create_debug_dir()

        try:
            # Launch browser WITH geolocation spoofing
            self._playwright = sync_playwright().start()
            self.browser = self._playwright.chromium.launch(headless=not self.show_browser)
            self.context = self.browser.new_context(
                ignore_https_errors=True,
                geolocation={"latitude": self.latitude, "longitude": self.longitude},
                permissions=["geolocation"],
            )
            self.page = self.context.new_page()
            self._set_page_defaults()

            # Login
            self._perform_login()

            # Navigate to absensi
            self._set_state(AutomationState.OPENING_JOURNAL)
            self._navigate_to_absensi()

            # Click the attendance button
            self._set_state(AutomationState.SUBMITTING)
            clicked = self._click_absensi_button()

            if not self.dry_run:
                # Handle location permission popup
                self._handle_location_permission()

                # Handle success confirmation
                self._handle_success_confirmation()

            result["status"] = "dry_run" if self.dry_run else "success"
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
            result["button"] = clicked

            self._update_status(f"✅ {mode_label} berhasil pada {result['timestamp']}!")
            self._set_state(AutomationState.SUCCESS)

        except Exception as exc:
            self._set_state(AutomationState.FAILED)
            self._save_debug_artifacts(f"absensi-{self.mode}-error", str(exc))
            result["status"] = f"failed: {exc}"
            self._update_status(f"❌ {mode_label} gagal: {exc}")

        finally:
            self.close_browser()

        return result

