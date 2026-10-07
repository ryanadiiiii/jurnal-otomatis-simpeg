"""Headless scheduler for SIMPEG journal automation.

This script is designed to be run by Windows Task Scheduler (or manually)
without any GUI. It loads credentials from .env, fills journals for
multiple dates (yesterday, today, tomorrow — skipping weekends),
and sends a Telegram notification with the results.

Usage:
    python scheduler.py              # Normal run (fills yesterday, today, tomorrow)
    python scheduler.py --dry-run    # Test mode (no submission)
    python scheduler.py --today-only # Only fill today's journal
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from automation import SimpegAutomator, DuplicateJournalError
from notifier import TelegramNotifier

log = logging.getLogger("simpeg_journal")


import os

def _load_env() -> dict[str, str]:
    """Load environment variables from .env file and OS environment."""
    env_vars: dict[str, str] = dict(os.environ)
    env_path = Path(__file__).resolve().parent / ".env"

    if not env_path.exists():
        log.warning(f".env file tidak ditemukan, menggunakan OS environment variables.")
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                # Local .env overrides OS env for local dev
                env_vars[key.strip()] = value.strip()

    return env_vars


def _is_weekday(d: date) -> bool:
    """Return True if the date is Monday-Friday."""
    return d.weekday() < 5  # 0=Mon, 4=Fri


def _next_weekday(d: date, direction: int = 1) -> date:
    """Find the next weekday in the given direction (+1 or -1)."""
    candidate = d + timedelta(days=direction)
    while not _is_weekday(candidate):
        candidate += timedelta(days=direction)
    return candidate


def compute_target_dates(today: date | None = None) -> list[date]:
    """Compute the 3 target dates: previous weekday, today, next weekday.

    Weekends are automatically skipped. Examples:
    - Monday  → [Friday, Monday, Tuesday]
    - Friday  → [Thursday, Friday, Monday]
    - Wednesday → [Tuesday, Wednesday, Thursday]
    """
    if today is None:
        today = date.today()

    # If today is weekend, use the nearest weekday as "today"
    if not _is_weekday(today):
        today = _next_weekday(today, direction=-1)

    yesterday = _next_weekday(today, direction=-1)
    tomorrow = _next_weekday(today, direction=+1)

    return [yesterday, today, tomorrow]


def format_date_simpeg(d: date) -> str:
    """Format a date as DD-MM-YYYY for SIMPEG's date input."""
    return d.strftime("%d-%m-%Y")


def run_scheduled(
    nip: str,
    password: str,
    dry_run: bool = False,
    today_only: bool = False,
    show_browser: bool = False,
) -> dict[str, str]:
    """Run the journal automation for multiple dates.

    Returns a dict mapping date strings to their result status.
    """
    today = date.today()

    if today_only:
        if not _is_weekday(today):
            return {format_date_simpeg(today): "skipped_weekend"}
        target_dates = [today]
    else:
        target_dates = compute_target_dates(today)

    log.info(f"Target tanggal: {[format_date_simpeg(d) for d in target_dates]}")

    automator = SimpegAutomator(
        username=nip,
        password=password,
        show_browser=show_browser,
        dry_run=dry_run,
    )

    results = automator.run_multi_day(
        [format_date_simpeg(d) for d in target_dates]
    )

    return results


def wait_for_internet(timeout: int = 120) -> bool:
    """Wait for internet connection to be available."""
    import socket
    import time
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            time.sleep(5)
    return False

def main() -> None:
    parser = argparse.ArgumentParser(description="SIMPEG Jurnal Harian - Scheduled Runner")
    parser.add_argument("--dry-run", action="store_true", help="Test mode (tidak submit)")
    parser.add_argument("--today-only", action="store_true", help="Hanya isi hari ini")
    parser.add_argument("--show-browser", action="store_true", help="Tampilkan browser")
    args = parser.parse_args()

    # Wait for internet connection first (max 2 minutes)
    wait_for_internet(timeout=120)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Load .env
    env = _load_env()
    nip = env.get("SIMPEG_NIP", "")
    password = env.get("SIMPEG_PASSWORD", "")
    telegram_token = env.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = env.get("TELEGRAM_CHAT_ID", "")
    env_dry_run = env.get("DRY_RUN", "True").lower() in ("true", "1", "yes")

    # CLI --dry-run flag overrides .env
    dry_run = args.dry_run or env_dry_run

    if not nip or not password:
        log.error("SIMPEG_NIP dan SIMPEG_PASSWORD harus diisi di file .env")
        sys.exit(1)

    # Telegram notifier
    notifier = TelegramNotifier(bot_token=telegram_token, chat_id=telegram_chat_id)

    log.info("=" * 60)
    log.info("SIMPEG Jurnal Harian Otomatis - Scheduled Run")
    log.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUKSI'}")
    log.info(f"Telegram: {'Aktif' if notifier.is_configured else 'Tidak dikonfigurasi'}")
    log.info("=" * 60)

    try:
        results = run_scheduled(
            nip=nip,
            password=password,
            dry_run=dry_run,
            today_only=args.today_only,
            show_browser=args.show_browser,
        )

        log.info(f"Hasil: {results}")

        # Send Telegram notification
        if notifier.is_configured:
            notifier.send_results(results, dry_run=dry_run)
        else:
            log.info("Telegram belum dikonfigurasi. Tambahkan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di .env")

        # Exit with error code if any date failed
        has_failure = any(
            v.startswith("failed") for v in results.values()
        )
        sys.exit(1 if has_failure else 0)

    except Exception as exc:
        log.error(f"Fatal error: {exc}", exc_info=True)

        # Try to notify via Telegram even on fatal error
        if notifier.is_configured:
            notifier.send(f"❌ <b>SIMPEG Jurnal Otomatis GAGAL</b>\n\nError: {exc}")

        sys.exit(1)


if __name__ == "__main__":
    main()
