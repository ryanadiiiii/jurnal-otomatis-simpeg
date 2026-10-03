"""Application configuration and selector settings for SIMPEG journal automation."""
from pathlib import Path
from urllib.parse import urlparse

SIMPEG_BASE_URL = "https://simpeg.kemenkum.go.id"
PORTAL_URL = SIMPEG_BASE_URL + "/"
LOGIN_URL = PORTAL_URL
JOURNAL_URL = "https://simpeg.kemenkum.go.id/devp/siap/skp_journal.php"

LOG_FILE = Path("simpeg_journal.log")
AUDIT_LOG_FILE = Path("submission_audit.log")
DEBUG_DIR = Path("debug")
TEMPLATE_FILE = Path("journal_template.json")

PAGE_LOAD_TIMEOUT = 60_000
SELECTOR_TIMEOUT = 30_000

SELECTORS = {
    "portal_simpeg_hukum": "role:definition|has_text:SIMPEG HUKUMSIMPEG HUKUM",
    "nip_input": "role:textbox|name:N I P",
    "continue_button": "role:button|name:Masuk",
    "password_input": "css:#vpassword",
    "captcha_input": "role:textbox|name:Masukkan jawaban",
    "login_button": "role:button|name:Login",
    "close_dialog_button": "text:TUTUP|exact:True",
    "kinerja_menu": "role:link|name:KINERJA|exact:True",
    "daily_journal_cell": "role:cell|name:Jurnal Harian",
    "add_journal_link": "role:link|name:Tambah",
    "start_hour": "css:#jammulai",
    "start_minute": "css:#menitmulai",
    "end_hour": "css:#jamselesai",
    "end_minute": "css:#menitselesai",
    "skp_category": "css:#skpkgid",
    "activity_description": "css:#keterangan",
    "completion_value": "css:#jumlah",
    "submit_button": "role:button|name:Simpan|exact:True",
    "success_message": "text:Data Sudah Disimpan|exact:True",
    # Optional selectors for duplicate detection and table verification.
    "journal_table_rows": "css:#data tbody tr",
    "journal_row_date": None,
    "journal_row_description": "css:td:nth-child(4)",
    "journal_row_start_hour": "css:td:nth-child(8)",
    "journal_row_end_hour": "css:td:nth-child(9)",
    "captcha_image": "css:#simple-captcha-image",
    "captcha_refresh_button": "css:#simple-captcha-refresh",
    "satuan": "css:#satuan",
}

TIMEOUTS = {
    "page_load": PAGE_LOAD_TIMEOUT,
    "selector": SELECTOR_TIMEOUT,
    "login_result": 20000,
    "manual_captcha": 300000,
    "journal_page": 20000,
    "submission_confirmation": 20000,
    "login_retry_delay": 3000,
    "captcha_ocr": 10000,
    "captcha_retry_delay": 2000,
}

MAX_LOGIN_ATTEMPTS = 6
CAPTCHA_EXPECTED_LENGTH = None
MAX_CAPTCHA_ATTEMPTS = 5
DRY_RUN = True


def _validate_url(value: str, name: str) -> None:
    if not value or not isinstance(value, str):
        raise ValueError(f"{name} harus diisi dengan URL yang valid.")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{name} harus menggunakan http atau https: {value}")


def validate_configuration() -> None:
    _validate_url(LOGIN_URL, "LOGIN_URL")
    _validate_url(JOURNAL_URL, "JOURNAL_URL")

    required_selectors = [
        "portal_simpeg_hukum",
        "nip_input",
        "continue_button",
        "password_input",
        "captcha_input",
        "login_button",
        "close_dialog_button",
        "kinerja_menu",
        "daily_journal_cell",
        "add_journal_link",
        "start_hour",
        "end_hour",
        "skp_category",
        "activity_description",
        "completion_value",
        "submit_button",
    ]

    missing = [key for key in required_selectors if key not in SELECTORS or not SELECTORS[key]]
    if missing:
        raise ValueError(f"Missing required selectors: {', '.join(missing)}")

    if not TEMPLATE_FILE:
        raise ValueError("TEMPLATE_FILE harus dikonfigurasi di config.py.")
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"File template jurnal tidak ditemukan: {TEMPLATE_FILE}")

    if DEBUG_DIR.exists() and not DEBUG_DIR.is_dir():
        raise ValueError(f"DEBUG_DIR bukan direktori: {DEBUG_DIR}")
    if not DEBUG_DIR.exists():
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    log_parent = LOG_FILE.parent
    if log_parent and not log_parent.exists():
        log_parent.mkdir(parents=True, exist_ok=True)

    audit_parent = AUDIT_LOG_FILE.parent
    if audit_parent and not audit_parent.exists():
        audit_parent.mkdir(parents=True, exist_ok=True)
