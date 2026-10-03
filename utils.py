"""Utility helpers used across the SIMPEG automation modules."""
import re
from pathlib import Path
from typing import Iterable

from easyocr import Reader

_OCR_READER = None


def clean_ocr_text(text: str) -> str:
    """Normalize OCR output and remove non-alphanumeric clutter."""
    if text is None:
        return ""
    text = text.strip()
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return text


def get_ocr_reader(languages: Iterable[str] = ("en",)) -> Reader:
    """Return a cached EasyOCR reader instance."""
    global _OCR_READER
    if _OCR_READER is None:
        _OCR_READER = Reader(list(languages), gpu=False)
    return _OCR_READER


def solve_captcha(image_path: Path, reader: Reader) -> str:
    """Read captcha from an image using a cached EasyOCR Reader."""
    results = reader.readtext(str(image_path), detail=0)
    if not results:
        return ""
    return clean_ocr_text("".join(results))


def solve_math_captcha(image_path: Path, reader: Reader) -> str:
    """Read a math captcha image and return the computed answer.

    SIMPEG uses simple math captcha images (e.g. '3 + 5 = ?').
    This reads the image with OCR, extracts the math expression,
    and returns the computed result as a string.
    """
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        return ""

    # Upscale small captcha images for better OCR accuracy
    h, w = img.shape[:2]
    if max(h, w) < 400:
        scale = 3
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale and apply threshold to remove noise lines
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    temp_path = image_path.with_name(f"cleaned_{image_path.name}")
    cv2.imwrite(str(temp_path), thresh)

    try:
        # Use allowlist to force OCR to only recognize digits and math symbols
        results = reader.readtext(
            str(temp_path), detail=0,
            allowlist='0123456789+-x*=/? '
        )
    finally:
        try:
            temp_path.unlink()
        except Exception:
            pass

    if not results:
        return ""

    raw_text = " ".join(results).strip()

    # Try to extract and evaluate math expression
    answer = _evaluate_math_expression(raw_text)
    if answer is not None:
        return str(answer)

    # Fallback: return cleaned OCR text (might be plain text captcha)
    return clean_ocr_text("".join(results))


def _evaluate_math_expression(text: str) -> int | None:
    """Parse a simple math expression from OCR text and return the result.

    Handles common OCR misreads:
    - Spaces inside numbers: '6 7' -> 67
    - '=' read as ';' or '&': cleaned away
    - 'x' or 'X' as multiplication
    """
    import re

    # Remove captcha noise characters that OCR might pick up
    cleaned = text.replace('=', ' ').replace('?', ' ')
    cleaned = cleaned.replace('&', ' ').replace(';', ' ')
    cleaned = cleaned.strip()

    # Normalize multiplication and division symbols
    cleaned = cleaned.replace('×', '*').replace('x', '*').replace('X', '*')
    cleaned = cleaned.replace('÷', '/').replace(':', '/')

    # Try to find: number(s) operator number(s)
    # Numbers may have spaces inside them from OCR (e.g. '6 7' = 67)
    match = re.search(r'([\d\s]+?)\s*([+\-*/])\s*([\d\s]+)', cleaned)
    if not match:
        return None

    num1_str = match.group(1).replace(" ", "")
    op = match.group(2)
    num2_str = match.group(3).replace(" ", "")

    if not num1_str or not num2_str:
        return None

    try:
        a = int(num1_str)
        b = int(num2_str)
        if op == '+':
            return a + b
        elif op == '-':
            return a - b
        elif op == '*':
            return a * b
        elif op == '/':
            return a // b if b != 0 else None
    except (ValueError, ZeroDivisionError):
        return None

    return None
