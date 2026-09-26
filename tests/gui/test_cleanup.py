from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from netconfiglint.gui.app.cleanup import remove_all_user_data


def test_remove_all_user_data_is_bounded_and_clears_current_settings(qapp: object, tmp_path: Path) -> None:
    app_dir = tmp_path / "installed/NetConfigLint"
    history = app_dir / "history"
    temporary = app_dir / "temporary"
    user_data = tmp_path / "user/NetConfigLint/data"
    unrelated = tmp_path / "user/another-product"
    for directory in (history, temporary, user_data, unrelated):
        directory.mkdir(parents=True)
        (directory / "record.json").write_text("synthetic", encoding="utf-8")
    QSettings().setValue("privacy/historyEnabled", True)

    remove_all_user_data(app_dir, [user_data, unrelated], user_home=tmp_path)

    assert not history.exists()
    assert not temporary.exists()
    assert not user_data.exists()
    assert not user_data.parent.exists()
    assert unrelated.is_dir()
    assert QSettings().value("privacy/historyEnabled") is None


def test_remove_all_user_data_never_removes_application_directory(qapp: object, tmp_path: Path) -> None:
    app_dir = tmp_path / "installed/NetConfigLint"
    app_dir.mkdir(parents=True)
    executable = app_dir / "NetConfigLint.exe"
    executable.write_bytes(b"synthetic")

    remove_all_user_data(app_dir, [app_dir], user_home=tmp_path)

    assert executable.is_file()


def test_remove_all_user_data_removes_unix_settings_file(
    qapp: object, tmp_path: Path, monkeypatch: object
) -> None:
    app_dir = tmp_path / "installed/NetConfigLint"
    app_dir.mkdir(parents=True)
    settings = QSettings()
    settings.setValue("privacy/historyEnabled", True)
    settings.sync()
    settings_file = Path(settings.fileName())
    assert settings_file.is_file()
    namespace = settings_file.parent
    (namespace / "future-version-state.bin").write_bytes(b"synthetic")
    monkeypatch.setattr("netconfiglint.gui.app.cleanup.sys.platform", "linux")

    remove_all_user_data(app_dir, user_home=tmp_path)

    assert not settings_file.exists()
    assert not namespace.exists()
