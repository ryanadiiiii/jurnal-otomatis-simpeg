import pathlib

import utils


def test_clean_ocr_text_removes_non_alphanumeric():
    assert utils.clean_ocr_text(" 12a-BC_# ") == "12aBC"


def test_clean_ocr_text_none_returns_empty_string():
    assert utils.clean_ocr_text(None) == ""


def test_clean_ocr_text_keeps_numbers_and_letters():
    assert utils.clean_ocr_text("a1b2c3") == "a1b2c3"
