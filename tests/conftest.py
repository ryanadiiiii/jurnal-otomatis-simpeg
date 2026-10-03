import pathlib
import pytest


@pytest.fixture
def temp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield
