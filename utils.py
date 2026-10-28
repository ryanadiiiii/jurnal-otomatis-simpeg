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

    SIMPEG uses simple math captcha images (e.g. '68 - 3 = ?').
    This reads the image with OCR, extracts the math expression,
    and returns the computed result as a string.

    Uses multiple preprocessing strategies to handle noise lines
    that can confuse OCR (e.g. '6' misread as '5').
    """
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        return ""

    # Upscale small captcha images for better OCR accuracy
    h, w = img.shape[:2]
    if max(h, w) < 400:
        scale = 4  # Increased from 3 for better digit clarity
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 1: Try reading raw upscaled image first (often cleanest for EasyOCR)
    try:
        raw_dets = reader.readtext(str(image_path), detail=1, allowlist='0123456789+-x*=/? ')
        if raw_dets:
            sorted_dets = sorted(raw_dets, key=lambda r: r[0][0][0])
            raw_text = " ".join(r[1] for r in sorted_dets).strip()
            answer = _evaluate_math_expression(raw_text)
            if answer is not None and 0 <= answer <= 200:
                return str(answer)
    except Exception:
        pass

    # Step 2: Try multiple preprocessing strategies
    candidates: list[tuple[str, int | None]] = []

    for threshold_val in (120, 140, 160, 180):
        for use_morph in (True, False):
            _, thresh = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY_INV)

            if use_morph:
                # Morphological opening to remove thin noise lines
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
                dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                thresh = cv2.dilate(thresh, dilate_kernel, iterations=1)

            temp_path = image_path.with_name(f"cleaned_{image_path.name}")
            cv2.imwrite(str(temp_path), thresh)

            try:
                results = reader.readtext(
                    str(temp_path), detail=1,
                    allowlist='0123456789+-x*=/? '
                )
            finally:
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            if not results:
                continue

            # Sort bounding boxes left-to-right
            sorted_results = sorted(results, key=lambda r: r[0][0][0])
            raw_text = " ".join(r[1] for r in sorted_results).strip()
            answer = _evaluate_math_expression(raw_text)
            candidates.append((raw_text, answer))

            # If we found a valid math answer, check if it's reasonable
            if answer is not None and 0 <= answer <= 200:
                return str(answer)

    # If no valid answer from any strategy, pick the first non-None answer
    for raw_text, answer in candidates:
        if answer is not None:
            return str(answer)

    # Last fallback: return cleaned text from first candidate
    if candidates:
        return clean_ocr_text(candidates[0][0].replace(" ", ""))

    return ""


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
