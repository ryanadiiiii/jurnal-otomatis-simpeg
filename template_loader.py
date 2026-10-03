"""Load and validate journal templates from JSON files."""
import json
from pathlib import Path

import config
from exceptions import TemplateValidationError


def _validate_entry(entry: dict, index: int) -> None:
    if not isinstance(entry, dict):
        raise TemplateValidationError(f"Entri template nomor {index + 1} harus berupa objek JSON.")

    required_keys = (
        "start_hour",
        "end_hour",
        "skp_category",
        "activity_description",
        "completion_value",
    )

    for key in required_keys:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            raise TemplateValidationError(
                f"Entri template nomor {index + 1} harus berisi field '{key}' dengan teks yang tidak kosong."
            )

    for key in ("start_minute", "end_minute"):
        if key in entry and entry[key] is not None and not isinstance(entry[key], str):
            raise TemplateValidationError(
                f"Entri template nomor {index + 1} field '{key}' harus berupa teks jika disediakan."
            )


def load_journal_template(template_path: Path | None = None) -> list[dict]:
    path = template_path or config.TEMPLATE_FILE
    if not path.exists():
        raise TemplateValidationError(f"File template jurnal tidak ditemukan: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateValidationError(f"Format JSON tidak valid di {path}: {exc.msg}") from exc

    if not isinstance(data, list):
        raise TemplateValidationError("Template jurnal harus berupa daftar JSON.")
    if not data:
        raise TemplateValidationError("Template jurnal tidak boleh kosong.")

    for index, entry in enumerate(data):
        _validate_entry(entry, index)

    return data
