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
    """Compute target dates respecting SIMPEG's strict +/- 1 calendar day rule.

    SIMPEG only permits journal creation for date D when the current date
    is in {D - 1, D, D + 1} calendar days.
    Therefore:
    - On Monday: Friday was 3 days ago (SIMPEG rejects it).
      Target dates: [Monday, Tuesday]
    - On Friday: Monday is 3 days ahead (SIMPEG rejects it).
      Target dates: [Thursday, Friday]
    - On Tuesday, Wednesday, Thursday:
      Target dates: [yesterday, today, tomorrow]
    """
    if today is None:
        today = date.today()

    # If today is weekend, use the nearest weekday as "today"
    if not _is_weekday(today):
        today = _next_weekday(today, direction=-1)

    weekday = today.weekday()  # 0=Monday, 4=Friday

    if weekday == 0:  # Monday
        tomorrow = _next_weekday(today, direction=+1)
        return [today, tomorrow]
    elif weekday == 4:  # Friday
        yesterday = _next_weekday(today, direction=-1)
        return [yesterday, today]
    else:
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
    activity_description: str | None = None,
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
        activity_description_override=activity_description,
    )

    results = automator.run_multi_day(
        [format_date_simpeg(d) for d in target_dates]
    )

    return results


def run_absensi_scheduled(
    nip: str,
    password: str,
    mode: str = "datang",
    dry_run: bool = False,
    show_browser: bool = False,
    latitude: float = -8.5925,
    longitude: float = 116.0947,
) -> dict[str, str]:
    """Run the attendance automation.

    Args:
        mode: 'datang' for morning check-in, 'pulang' for afternoon check-out.
    """
    from absensi import AbsensiAutomator

    automator = AbsensiAutomator(
        username=nip,
        password=password,
        mode=mode,
        latitude=latitude,
        longitude=longitude,
        show_browser=show_browser,
        dry_run=dry_run,
    )

    return automator.run_absensi()


def wait_for_internet(timeout: int = 120) -> bool:
    """Wait for internet connection to be available."""
    import socket
    import time as _time
    start_time = _time.time()
    while _time.time() - start_time < timeout:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            _time.sleep(5)
    return False


def load_accounts() -> list[dict] | None:
    """Load accounts from accounts.json if it exists.

    Returns a list of account dicts, or None if file doesn't exist.
    Each account has: nip, password, nama, wa_target, latitude, longitude.
    """
    import json
    accounts_path = Path(__file__).resolve().parent / "accounts.json"
    if not accounts_path.exists():
        return None

    with open(accounts_path, "r", encoding="utf-8") as f:
        accounts = json.load(f)

    if not isinstance(accounts, list) or len(accounts) == 0:
        return None

    return accounts


def _run_single_account_jurnal(
    account: dict,
    dry_run: bool,
    today_only: bool,
    show_browser: bool,
    fonnte_token: str,
) -> dict[str, str]:
    """Run journal automation for a single account and notify the client."""
    nama = account.get("nama", account["nip"])
    wa_target = account.get("wa_target", "")

    log.info(f"\n{'='*60}")
    log.info(f"👤 Memproses akun: {nama} ({account['nip']})")
    log.info(f"{'='*60}")

    results = run_scheduled(
        nip=account["nip"],
        password=account["password"],
        dry_run=dry_run,
        today_only=today_only,
        show_browser=show_browser,
        activity_description=account.get("activity_description"),
    )

    log.info(f"Hasil {nama}: {results}")

    # Send WA notification to this client's number
    if fonnte_token and wa_target:
        from notifier import WhatsAppNotifier, format_result_message
        client_wa = WhatsAppNotifier(token=fonnte_token, target=wa_target)
        client_wa.send_results(results, dry_run=dry_run)

    return results


def _run_single_account_absensi(
    account: dict,
    absen_mode: str,
    mode_label: str,
    dry_run: bool,
    show_browser: bool,
    fonnte_token: str,
) -> dict[str, str]:
    """Run attendance automation for a single account and notify the client."""
    nama = account.get("nama", account["nip"])
    wa_target = account.get("wa_target", "")
    latitude = account.get("latitude", -8.5925)
    longitude = account.get("longitude", 116.0947)

    log.info(f"\n{'='*60}")
    log.info(f"👤 Memproses absensi: {nama} ({account['nip']})")
    log.info(f"{'='*60}")

    result = run_absensi_scheduled(
        nip=account["nip"],
        password=account["password"],
        mode=absen_mode,
        dry_run=dry_run,
        show_browser=show_browser,
        latitude=latitude,
        longitude=longitude,
    )

    log.info(f"Hasil Absensi {nama}: {result}")

    # Send WA notification to this client's number
    if fonnte_token and wa_target:
        from notifier import WhatsAppNotifier
        client_wa = WhatsAppNotifier(token=fonnte_token, target=wa_target)
        status_emoji = "✅" if result["status"] in ("success", "dry_run") else "❌"
        msg = (
            f"*SIMPEG Absensi Otomatis*\n"
            f"Mode: {mode_label}\n"
            f"{'📋 DRY RUN' if dry_run else '📋 PRODUKSI'}\n\n"
            f"{status_emoji} Status: {result['status']}\n"
        )
        if result.get("timestamp"):
            msg += f"⏰ Waktu: {result['timestamp']}\n"
        if result.get("button"):
            msg += f"🔘 Tombol: {result['button']}\n"
        client_wa.send(msg)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="SIMPEG Jurnal Harian - Scheduled Runner")
    parser.add_argument("--dry-run", action="store_true", help="Test mode (tidak submit)")
    parser.add_argument("--today-only", action="store_true", help="Hanya isi hari ini")
    parser.add_argument("--show-browser", action="store_true", help="Tampilkan browser")
    parser.add_argument(
        "--mode",
        choices=["jurnal", "absen-datang", "absen-pulang"],
        default="jurnal",
        help="Mode: jurnal (default), absen-datang, absen-pulang",
    )
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

    # Load .env for shared config (Fonnte token, Telegram, DRY_RUN)
    env = _load_env()
    telegram_token = env.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = env.get("TELEGRAM_CHAT_ID", "")
    fonnte_token = env.get("FONNTE_TOKEN", "")
    env_dry_run = env.get("DRY_RUN", "True").lower() in ("true", "1", "yes")

    # CLI --dry-run flag overrides .env
    dry_run = args.dry_run or env_dry_run

    # Admin notifiers (for summary)
    from notifier import TelegramNotifier, WhatsAppNotifier
    tg_notifier = TelegramNotifier(bot_token=telegram_token, chat_id=telegram_chat_id)
    admin_wa_target = env.get("FONNTE_TARGET", "")
    admin_wa = WhatsAppNotifier(token=fonnte_token, target=admin_wa_target)

    mode_label = {
        "jurnal": "📋 Jurnal Harian",
        "absen-datang": "🟢 Absen Datang (Jumat)",
        "absen-pulang": "🔴 Absen Pulang (Jumat)",
    }[args.mode]

    # Check for multi-account mode
    accounts = load_accounts()
    is_multi = accounts is not None and len(accounts) > 0

    if is_multi:
        log.info("=" * 60)
        log.info(f"SIMPEG Otomatis - {mode_label} [MULTI-AKUN: {len(accounts)} akun]")
        log.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUKSI'}")
        log.info("=" * 60)

        all_results: dict[str, dict] = {}
        total_success = 0
        total_fail = 0

        for idx, account in enumerate(accounts, 1):
            nama = account.get("nama", account.get("nip", f"Akun {idx}"))
            try:
                if args.mode == "jurnal":
                    results = _run_single_account_jurnal(
                        account, dry_run, args.today_only, args.show_browser, fonnte_token
                    )
                    all_results[nama] = results
                    successes = sum(1 for v in results.values() if v in ("success", "dry_run", "skipped_duplicate"))
                    fails = sum(1 for v in results.values() if v.startswith("failed"))
                    total_success += successes
                    total_fail += fails
                else:
                    absen_mode = "datang" if args.mode == "absen-datang" else "pulang"
                    result = _run_single_account_absensi(
                        account, absen_mode, mode_label, dry_run, args.show_browser, fonnte_token
                    )
                    all_results[nama] = result
                    if result["status"] in ("success", "dry_run"):
                        total_success += 1
                    else:
                        total_fail += 1

            except Exception as exc:
                log.error(f"❌ Fatal error untuk {nama}: {exc}", exc_info=True)
                all_results[nama] = {"status": f"fatal: {exc}"}
                total_fail += 1

        # Send admin summary
        summary = (
            f"<b>SIMPEG {mode_label} - Ringkasan Multi-Akun</b>\n"
            f"{'📋 DRY RUN' if dry_run else '📋 PRODUKSI'}\n"
            f"Total: {len(accounts)} akun\n\n"
        )
        for nama, result in all_results.items():
            if isinstance(result, dict) and "status" in result:
                # Absensi result
                emoji = "✅" if result["status"] in ("success", "dry_run") else "❌"
                summary += f"{emoji} {nama}: {result['status']}\n"
            else:
                # Jurnal results (dict of date->status)
                successes = sum(1 for v in result.values() if v in ("success", "dry_run", "skipped_duplicate"))
                fails = sum(1 for v in result.values() if v.startswith("failed"))
                emoji = "✅" if fails == 0 else "⚠️"
                summary += f"{emoji} {nama}: ✅{successes} ❌{fails}\n"

        summary += f"\n📊 Total: ✅{total_success} ❌{total_fail}"

        if tg_notifier.is_configured:
            tg_notifier.send(summary)
        if admin_wa.is_configured:
            admin_wa.send(summary)

        log.info(f"\n{'='*60}")
        log.info(f"SELESAI - {len(accounts)} akun diproses: ✅{total_success} ❌{total_fail}")
        log.info(f"{'='*60}")

        sys.exit(1 if total_fail > 0 else 0)

    else:
        # Single account mode (backward compatible with .env)
        nip = env.get("SIMPEG_NIP", "")
        password = env.get("SIMPEG_PASSWORD", "")
        fonnte_target = env.get("FONNTE_TARGET", "")
        latitude = float(env.get("OFFICE_LATITUDE", "-8.5925"))
        longitude = float(env.get("OFFICE_LONGITUDE", "116.0947"))

        if not nip or not password:
            log.error("SIMPEG_NIP dan SIMPEG_PASSWORD harus diisi di file .env, "
                      "atau buat file accounts.json untuk multi-akun.")
            sys.exit(1)

        wa_notifier = WhatsAppNotifier(token=fonnte_token, target=fonnte_target)

        log.info("=" * 60)
        log.info(f"SIMPEG Otomatis - {mode_label}")
        log.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUKSI'}")
        log.info(f"Telegram: {'Aktif' if tg_notifier.is_configured else 'Tidak dikonfigurasi'}")
        log.info(f"WhatsApp (Fonnte): {'Aktif' if wa_notifier.is_configured else 'Tidak dikonfigurasi'}")
        log.info("=" * 60)

        try:
            if args.mode == "jurnal":
                results = run_scheduled(
                    nip=nip, password=password, dry_run=dry_run,
                    today_only=args.today_only, show_browser=args.show_browser,
                )
                log.info(f"Hasil: {results}")
                if tg_notifier.is_configured:
                    tg_notifier.send_results(results, dry_run=dry_run)
                if wa_notifier.is_configured:
                    wa_notifier.send_results(results, dry_run=dry_run)
                has_failure = any(v.startswith("failed") for v in results.values())
                sys.exit(1 if has_failure else 0)
            else:
                absen_mode = "datang" if args.mode == "absen-datang" else "pulang"
                result = run_absensi_scheduled(
                    nip=nip, password=password, mode=absen_mode,
                    dry_run=dry_run, show_browser=args.show_browser,
                    latitude=latitude, longitude=longitude,
                )
                log.info(f"Hasil Absensi: {result}")
                status_emoji = "✅" if result["status"] in ("success", "dry_run") else "❌"
                msg = (
                    f"<b>SIMPEG Absensi Otomatis</b>\n"
                    f"Mode: {mode_label}\n"
                    f"{'📋 DRY RUN' if dry_run else '📋 PRODUKSI'}\n\n"
                    f"{status_emoji} Status: {result['status']}\n"
                )
                if result.get("timestamp"):
                    msg += f"⏰ Waktu: {result['timestamp']}\n"
                if result.get("button"):
                    msg += f"🔘 Tombol: {result['button']}\n"
                if tg_notifier.is_configured:
                    tg_notifier.send(msg)
                if wa_notifier.is_configured:
                    wa_notifier.send(msg)
                has_failure = result["status"].startswith("failed")
                sys.exit(1 if has_failure else 0)
        except Exception as exc:
            log.error(f"Fatal error: {exc}", exc_info=True)
            error_msg = f"❌ <b>SIMPEG {mode_label} GAGAL</b>\n\nError: {exc}"
            if tg_notifier.is_configured:
                tg_notifier.send(error_msg)
            if wa_notifier.is_configured:
                wa_notifier.send(error_msg)
            sys.exit(1)


if __name__ == "__main__":
    main()

