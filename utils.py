"""Utility helpers used across the SIMPEG automation modules."""
import re
from pathlib import Path
from easyocr import Reader


def clean_ocr_text(text: str) -> str:
    """Normalize OCR output and remove non-alphanumeric clutter."""
    if text is None:
        return ""
    text = text.strip()
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def solve_captcha(image_path: Path, languages=("en",)) -> str:
    """Read captcha from an image using EasyOCR."""
    reader = Reader(list(languages), gpu=False)
    results = reader.readtext(str(image_path), detail=0)
    if not results:
        return ""
    return clean_ocr_text("".join(results))
