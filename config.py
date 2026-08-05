"""Application configuration and default journal template."""

SIMPEG_BASE_URL = "https://simpeg.kemenkumham.go.id"
LOGIN_URL = f"{SIMPEG_BASE_URL}/login"
JOURNAL_URL = f"{SIMPEG_BASE_URL}/jurnal-harian"

# Adjust these selectors if the website structure changes.
SELECTORS = {
    "username": "input[name='username']",
    "password": "input[name='password']",
    "captcha_image": "img#captcha",
    "captcha_input": "input[name='captcha']",
    "login_button": "button[type='submit']",
    "login_error": "#login-error",
    "journal_row": "div.journal-row",
    "journal_task": "input[name='task']",
    "journal_status": "select[name='status']",
    "journal_notes": "textarea[name='notes']",
    "journal_submit": "button#save-journal",
}

MAX_CAPTCHA_RETRIES = 6
LOG_FILE = "simpeg_journal.log"

JOURNAL_TEMPLATE = [
    {
        "task": "Mengikuti briefing dan koordinasi tim",
        "status": "Selesai",
        "notes": "Persiapan tugas dan pembagian kerja dengan tim." ,
    },
    {
        "task": "Melakukan verifikasi data pegawai",
        "status": "Selesai",
        "notes": "Memastikan kelengkapan dokumen administrasi pegawai." ,
    },
    {
        "task": "Menyiapkan laporan harian",
        "status": "Selesai",
        "notes": "Menyusun ringkasan kegiatan dan kendala harian." ,
    },
]
