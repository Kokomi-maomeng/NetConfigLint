"""Reject stale editable metadata before compiling a differently versioned application."""

from pathlib import Path

import pytest

from scripts.check_build_environment import check_application_version


def test_current_application_metadata_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.0.0"\n', encoding="utf-8")
    monkeypatch.setattr("importlib.metadata.version", lambda name: "3.0.0")
    assert check_application_version(tmp_path) == "3.0.0"


def test_stale_editable_metadata_is_rejected_before_packaging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.0.0"\n', encoding="utf-8")
    monkeypatch.setattr("importlib.metadata.version", lambda name: "2.5.0")
    with pytest.raises(ValueError, match="Application metadata mismatch"):
        check_application_version(tmp_path)
