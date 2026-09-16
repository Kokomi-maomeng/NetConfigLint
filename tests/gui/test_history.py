from pathlib import Path

from PySide6.QtCore import QStandardPaths

from netconfiglint import analyze
from netconfiglint.gui.models import HistoryStore
from netconfiglint.gui.models.history import default_history_path


def test_history_is_opt_in_and_excludes_configuration_content(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore(path, enabled=False, persist_settings=False)
    result = analyze("sysname PRIVATE-NAME\npassword cipher SYNTHETIC-SECRET", vendor="huawei")

    store.append(result)
    assert not path.exists()

    store.set_enabled(True)
    store.append(result)
    content = path.read_text(encoding="utf-8")
    assert "SYNTHETIC-SECRET" not in content
    assert "PRIVATE-NAME" not in content
    assert store.entries[0].diagnostic_count >= 1


def test_history_store_recovers_from_invalid_json(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "history.json"
    path.write_text("not json", encoding="utf-8")
    assert HistoryStore(path, enabled=True, persist_settings=False).entries == []


def test_installed_or_source_history_uses_platform_app_data(qapp: object) -> None:
    path = default_history_path()
    assert path.name == "history.json"
    assert path.parent.name == "history"
    expected = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    assert path.parent.parent == expected
    assert Path(__file__).resolve().parents[2] not in path.parents
