import sys
from pathlib import Path

from PySide6.QtCore import QSettings

from netconfiglint.gui.app.main import configure_portable_storage
from netconfiglint.gui.models.history import default_history_path, default_temporary_path


def test_portable_runtime_paths_stay_adjacent_to_executable(
    tmp_path: Path, qapp: object, monkeypatch: object
) -> None:
    root = tmp_path / "NetConfigLint Portable"
    root.mkdir()
    (root / "portable.flag").write_text("portable", encoding="ascii")
    monkeypatch.setattr(sys, "executable", str(root / "NetConfigLint.exe"))
    data = configure_portable_storage()
    assert data == root / "data"
    assert default_history_path() == root / "history" / "history.json"
    assert default_temporary_path() == root / "temporary" / "editor.txt"
    assert Path(QSettings().fileName()).is_relative_to(data / "settings")
    assert (data / "cache").is_dir()
    assert (data / "tmp").is_dir()
