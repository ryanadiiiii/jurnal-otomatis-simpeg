"""Telegram notification module for SIMPEG journal automation."""
import logging
from typing import Optional

import requests

log = logging.getLogger("simpeg_journal")


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    message: str,
    parse_mode: str = "HTML",
) -> bool:
    """Send a message via Telegram Bot API.

    Returns True if the message was sent successfully, False otherwise.
    """
    if not bot_token or not chat_id:
        log.warning("Telegram bot_token atau chat_id belum dikonfigurasi. Notifikasi dilewati.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            log.info("Notifikasi Telegram berhasil dikirim.")
            return True
        else:
            log.warning(f"Telegram API error {resp.status_code}: {resp.text}")
            return False
    except requests.RequestException as exc:
        log.warning(f"Gagal mengirim notifikasi Telegram: {exc}")
        return False


def format_result_message(results: dict[str, str], dry_run: bool = False) -> str:
    """Format automation results into a Telegram-friendly message."""
    mode = "🧪 DRY RUN" if dry_run else "📋 PRODUKSI"
    header = f"<b>SIMPEG Jurnal Harian Otomatis</b>\nMode: {mode}\n\n"

    lines = []
    success_count = 0
    skip_count = 0
    fail_count = 0

    for date_str, status in results.items():
        if status == "success" or status == "dry_run":
            lines.append(f"✅ {date_str}: Berhasil")
            success_count += 1
        elif status == "skipped_duplicate":
            lines.append(f"⏭️ {date_str}: Sudah terisi (skip)")
            skip_count += 1
        elif status == "skipped_weekend":
            lines.append(f"🗓️ {date_str}: Weekend (skip)")
            skip_count += 1
        else:
            lines.append(f"❌ {date_str}: {status}")
            fail_count += 1

    summary = f"\n\n📊 <b>Ringkasan:</b> ✅{success_count} ⏭️{skip_count} ❌{fail_count}"
    return header + "\n".join(lines) + summary


class TelegramNotifier:
    """Wrapper class for sending Telegram notifications."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, message: str) -> bool:
        return send_telegram_message(self.bot_token, self.chat_id, message)

    def send_results(self, results: dict[str, str], dry_run: bool = False) -> bool:
        message = format_result_message(results, dry_run)
        return self.send(message)
