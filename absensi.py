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
        absensi_link.wait_for(state="visible", timeout=10000)
        absensi_link.click()
        time.sleep(2)
        self.page.wait_for_load_state("networkidle", timeout=15000)

    def _click_absensi_button(self) -> str:
        """Click the appropriate attendance button based on mode.
        
        Flow from recording:
        1. Click "Absensi Online" button first
        2. Then click "Rekam Absen Masuk" or "Rekam Absen Pulang"
        
        Returns:
            The text of the button that was clicked.
        """
        # Step 1: Click "Absensi Online" to open the attendance panel
        self._update_status("Mengklik tombol Absensi Online...")
        absensi_online_btn = self.page.get_by_role("button", name="Absensi Online")
        absensi_online_btn.wait_for(state="visible", timeout=10000)

        if not self.dry_run:
            absensi_online_btn.click()
            time.sleep(2)
        else:
            self._update_status("[DRY RUN] Tombol 'Absensi Online' ditemukan, tidak diklik.")
            return "Absensi Online"

        # Step 2: Click the correct attendance button
        if self.mode == "datang":
            button_names = ["Rekam Absen Masuk", "Absen Datang", "Absensi Datang"]
        else:
            button_names = ["Rekam Absen Pulang", "Absen Pulang", "Absensi Pulang"]

        clicked_name = None
        for name in button_names:
            try:
                btn = self.page.get_by_role("button", name=name)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.click()
                    clicked_name = name
                    self._update_status(f"Tombol '{name}' diklik.")
                    break
            except Exception:
                continue

        if not clicked_name:
            # Fallback: look for any button containing "Absen Masuk" or "Absen Pulang"
            keyword = "Masuk" if self.mode == "datang" else "Pulang"
            try:
                btn = self.page.locator(f"button:has-text('{keyword}')").first
                if btn.is_visible():
                    btn_text = btn.inner_text()
                    btn.click()
                    clicked_name = btn_text
                    self._update_status(f"Tombol '{btn_text}' diklik.")
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

