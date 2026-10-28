# SIMPEG Daily Journal Automation 🤖

Bot otomatis untuk mengisi **Jurnal Harian** dan **Absensi Jumat** di SIMPEG Kemenkumham (`simpeg.kemenkum.go.id`).

## ✨ Fitur

- 🗓️ **Jurnal Harian otomatis** — Senin-Jumat jam 08:00 (via Task Scheduler)
- 📋 **Multi-akun** — support banyak akun sekaligus via `accounts.json`
- 🧮 **Captcha OCR otomatis** — EasyOCR multi-pass dengan retry
- 📅 **Absensi Jumat** — Absen datang (07:00) & pulang (17:35) otomatis
- 💬 **Notifikasi WhatsApp** — setiap akun dapat WA via Fonnte
- 📱 **Notifikasi Telegram** — ringkasan admin ke Telegram
- 😴 **Wake from sleep** — laptop bangun sendiri dari sleep untuk menjalankan task
- 🖥️ **Desktop GUI** — mode manual via CustomTkinter (opsional)
- 🏃 **Dry-run mode** — test tanpa submit ke SIMPEG

## 📋 Prasyarat

- **Windows 10/11**
- **Python 3.11+**
- **Koneksi internet**

## 🚀 Setup Cepat

### 1. Clone & Install

```powershell
git clone https://github.com/ryanadiiiii/jurnal-otomatis-simpeg.git
cd jurnal-otomatis-simpeg

py -m venv .venv
.venv\Scripts\Activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Konfigurasi `.env`

Buat file `.env` di root project (jangan di-commit!):

```env
# Mode (True = test, False = produksi)
DRY_RUN=True

# Telegram (opsional - untuk notifikasi admin)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Fonnte WhatsApp (opsional - untuk notifikasi ke klien)
FONNTE_TOKEN=your_fonnte_token
FONNTE_TARGET=admin_wa_number
```

### 3. Konfigurasi `accounts.json`

Buat file `accounts.json` di root project (jangan di-commit!):

```json
[
  {
    "nip": "200005272025061011",
    "password": "password_simpeg",
    "nama": "Nama Lengkap",
    "wa_target": "08xxxxxxxxxx",
    "latitude": -8.5925,
    "longitude": 116.0947,
    "activity_description": "Pelaksanaan layanan IT"
  }
]
```

| Field | Keterangan |
|-------|-----------|
| `nip` | NIP pegawai (login SIMPEG) |
| `password` | Password SIMPEG |
| `nama` | Nama untuk notifikasi |
| `wa_target` | Nomor WA untuk notifikasi Fonnte |
| `latitude`, `longitude` | Koordinat kantor (untuk absensi) |
| `activity_description` | Deskripsi kegiatan jurnal harian |

> ⚠️ **Jangan commit `.env` dan `accounts.json` ke Git!** Sudah ada di `.gitignore`.

### 4. Test (Dry Run)

```powershell
# Test jurnal (tidak submit)
python scheduler.py --dry-run

# Test dengan browser terlihat
python scheduler.py --dry-run --show-browser
```

### 5. Produksi

Ubah `DRY_RUN=False` di `.env`, lalu:

```powershell
# Jalankan jurnal produksi
python scheduler.py

# Jalankan absensi datang
python scheduler.py --mode absen-datang

# Jalankan absensi pulang
python scheduler.py --mode absen-pulang
```

## ⏰ Setup Task Scheduler (Auto Harian)

Jalankan sebagai **Administrator**:

```powershell
# Jurnal Harian (Senin-Jumat jam 08:00)
schtasks /create /tn "SIMPEG Jurnal Harian" /tr "C:\path\to\python.exe scheduler.py" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:00 /rl HIGHEST /f

# Absen Datang Jumat (jam 07:00)
schtasks /create /tn "SIMPEG Absen Datang Jumat" /tr "C:\path\to\python.exe scheduler.py --mode absen-datang" /sc weekly /d FRI /st 07:00 /rl HIGHEST /f

# Absen Pulang Jumat (jam 17:35)
schtasks /create /tn "SIMPEG Absen Pulang Jumat" /tr "C:\path\to\python.exe scheduler.py --mode absen-pulang" /sc weekly /d FRI /st 17:35 /rl HIGHEST /f
```

Lalu jalankan `fix_task_scheduler.ps1` sebagai Administrator agar task bisa **bangunkan laptop dari sleep**:

```powershell
powershell -ExecutionPolicy Bypass -File .\fix_task_scheduler.ps1
```

## 🖥️ Mode GUI (Manual)

```powershell
python main.py
```

## 📁 Struktur File

```
├── scheduler.py          # Entry point scheduler (CLI)
├── automation.py         # Login & pengisian jurnal
├── absensi.py           # Absensi Jumat
├── config.py            # Selectors & konfigurasi
├── utils.py             # Captcha OCR solver
├── notifier.py          # Telegram & WhatsApp notifier
├── template_loader.py   # Loader template jurnal
├── journal_template.json # Template kegiatan jurnal
├── main.py              # Desktop GUI (CustomTkinter)
├── ui.py                # UI components
├── .env                 # Kredensial (JANGAN COMMIT!)
├── accounts.json        # Data akun (JANGAN COMMIT!)
├── fix_task_scheduler.ps1    # Fix task scheduler
└── remove_logon_trigger.ps1  # Hapus logon trigger
```

## 🔧 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Captcha gagal terus | Bot retry otomatis (5x captcha × 6x login) |
| `RELOAD BROWSER` | SIMPEG maintenance (tgl 15-18 setiap bulan) |
| Task tidak jalan saat laptop sleep | Jalankan `fix_task_scheduler.ps1` sebagai Admin |
| Task jalan 2x sehari | Jalankan `remove_logon_trigger.ps1` sebagai Admin |
| `accounts.json` error | Pastikan JSON valid (tanpa komentar `//`) |

## 📅 Maintenance SIMPEG

SIMPEG offline setiap **tanggal 15-18** setiap bulan. Bot akan mendeteksi ini dan gagal dengan pesan jelas (bukan timeout).

## 🔒 Keamanan

- `.env` dan `accounts.json` **tidak di-commit** ke Git
- Debug screenshots mungkin berisi data sensitif — folder `debug/` juga di-gitignore
- Bot tidak menyimpan password, cookie, atau token di log

## 📝 Lisensi

Private use only.
