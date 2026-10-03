import json
from pathlib import Path

import pytest

import template_loader
from exceptions import TemplateValidationError


def test_load_journal_template_valid(tmp_path):
    data = [
        {
            "start_hour": "07",
            "start_minute": "00",
            "end_hour": "16",
            "end_minute": "30",
            "skp_category": "Lain-lain",
            "activity_description": "Melakukan tugas administratif.",
            "completion_value": "1",
        }
    ]
    path = tmp_path / "journal_template.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    result = template_loader.load_journal_template(path)
    assert result == data


def test_load_journal_template_missing_file(tmp_path):
    path = tmp_path / "missing.json"
    with pytest.raises(TemplateValidationError, match="tidak ditemukan"):
        template_loader.load_journal_template(path)


def test_load_journal_template_invalid_json(tmp_path):
    path = tmp_path / "journal_template.json"
    path.write_text("{ invalid json }", encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="Format JSON tidak valid"):
        template_loader.load_journal_template(path)


def test_load_journal_template_empty_list(tmp_path):
    path = tmp_path / "journal_template.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="tidak boleh kosong"):
        template_loader.load_journal_template(path)


def test_load_journal_template_missing_required_field(tmp_path):
    data = [
        {
            "start_hour": "07",
            "start_minute": "00",
            "end_hour": "16",
            "end_minute": "30",
            "activity_description": "Melakukan tugas administratif.",
            "completion_value": "1",
        }
    ]
    path = tmp_path / "journal_template.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="field 'skp_category'"):
        template_loader.load_journal_template(path)


def test_load_journal_template_empty_required_value(tmp_path):
    data = [
        {
            "start_hour": "",
            "start_minute": "00",
            "end_hour": "16",
            "end_minute": "30",
            "skp_category": "Lain-lain",
            "activity_description": "Melakukan tugas administratif.",
            "completion_value": "1",
        }
    ]
    path = tmp_path / "journal_template.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="field 'start_hour'"):
        template_loader.load_journal_template(path)


def test_load_journal_template_valid_without_minute_fields(tmp_path):
    data = [
        {
            "start_hour": "07",
            "end_hour": "16",
            "skp_category": "Lain-lain",
            "activity_description": "Melakukan tugas administratif.",
            "completion_value": "1",
        }
    ]
    path = tmp_path / "journal_template.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    result = template_loader.load_journal_template(path)
    assert result == data
