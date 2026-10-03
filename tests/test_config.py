import config
import pytest
from pathlib import Path


def test_validate_configuration_missing_template_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_FILE", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        config.validate_configuration()


def test_validate_configuration_invalid_selector(monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_FILE", Path("journal_template.json"))
    old_selector = config.SELECTORS["portal_simpeg_hukum"]
    monkeypatch.setitem(config.SELECTORS, "portal_simpeg_hukum", "")
    with pytest.raises(ValueError, match="portal_simpeg_hukum"):
        config.validate_configuration()
    config.SELECTORS["portal_simpeg_hukum"] = old_selector


def test_verified_portal_and_journal_urls():
    assert config.PORTAL_URL == "https://simpeg.kemenkum.go.id/"
    assert config.LOGIN_URL == config.PORTAL_URL
    assert config.JOURNAL_URL == "https://simpeg.kemenkum.go.id/devp/siap/skp_journal.php"
