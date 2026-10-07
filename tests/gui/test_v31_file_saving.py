from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.file_saving import FileChangedError, file_identity, save_configuration
from netconfiglint.gui.models.history import HistoryStore


@pytest.fixture
def controller(tmp_path: Path, qapp: object):  # type: ignore[no-untyped-def]
    value = AnalysisController(
        async_enabled=False, history_store=HistoryStore(tmp_path / "history.json", enabled=False)
    )
    yield value
    value.close()


@pytest.mark.parametrize("change", ["edit", "replace", "delete"])
def test_external_conflict_and_cancel_preserve_both_versions(
    controller: AnalysisController, tmp_path: Path, change: str
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    if change == "edit":
        path.write_text("sysname EXTERNAL\n", encoding="utf-8")
    elif change == "replace":
        other = tmp_path / "replacement"
        other.write_text("sysname ORIGINAL\n", encoding="utf-8")
        other.replace(path)
    else:
        path.unlink()
    before = path.read_bytes() if path.exists() else None
    assert not controller.saveSourceFile(str(path))
    assert controller.fileConflict["reason"] == "changed"
    controller.resolveFileConflict("cancel")
    assert controller.sourceDirty and controller.sourceText == "sysname LOCAL\n"
    assert (path.read_bytes() if path.exists() else None) == before
    assert controller.saveSourceFile(str(tmp_path / "local-copy.cfg"))
    assert (tmp_path / "local-copy.cfg").read_text() == "sysname LOCAL\n"


def test_explicit_overwrite_is_rechecked_and_reload_keeps_external(
    controller: AnalysisController, tmp_path: Path
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n")
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    path.write_text("sysname EXTERNAL\n")
    assert not controller.saveSourceFile(str(path))
    path.write_text("sysname EXTERNAL2\n")
    controller.resolveFileConflict("overwrite")
    assert path.read_text() == "sysname EXTERNAL2\n" and controller.sourceDirty
    controller.resolveFileConflict("overwrite")
    assert path.read_text() == "sysname LOCAL\n" and not controller.sourceDirty
    controller.sourceText = "sysname LOCAL2\n"
    path.write_text("sysname RELOADED\n")
    assert not controller.saveSourceFile(str(path))
    controller.resolveFileConflict("reload")
    assert controller.sourceText == "sysname RELOADED\n" and not controller.sourceDirty


@pytest.mark.parametrize("relative", [False, True])
def test_link_updates_only_explicit_target_and_keeps_link(
    controller: AnalysisController, tmp_path: Path, relative: bool
) -> None:
    path, target = tmp_path / "link.cfg", tmp_path / "target.cfg"
    target.write_text("sysname ORIGINAL\n")
    try:
        path.symlink_to(target.name if relative else target)
    except OSError:
        pytest.skip("Creating file symlinks is unavailable")
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    assert not controller.saveSourceFile(str(path))
    assert controller.fileConflict["reason"] == "link"
    assert path.is_symlink() and target.read_text() == "sysname ORIGINAL\n"
    controller.resolveFileConflict("overwrite")
    assert path.is_symlink() and target.read_text() == "sysname LOCAL\n"
    assert not controller.sourceDirty


def test_readonly_never_silently_replaced(controller: AnalysisController, tmp_path: Path) -> None:
    path = tmp_path / "readonly.cfg"
    path.write_text("sysname ORIGINAL\n")
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    path.chmod(stat.S_IREAD)
    try:
        assert not controller.saveSourceFile(str(path))
        assert controller.fileConflict["reason"] == "readonly"
        assert not controller.fileConflict["canOverwrite"]
        controller.resolveFileConflict("overwrite")
        assert path.read_text() == "sysname ORIGINAL\n" and controller.sourceDirty
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644])
def test_existing_permissions_preserved(tmp_path: Path, mode: int) -> None:
    path = tmp_path / "permissions.cfg"
    path.write_text("old")
    path.chmod(mode)
    save_configuration(path, "new", file_identity(path))
    assert stat.S_IMODE(path.stat().st_mode) == mode
    new = tmp_path / "new.cfg"
    save_configuration(new, "new", None)
    assert stat.S_IMODE(new.stat().st_mode) == 0o600


def test_save_failure_retains_destination_and_removes_temporary(
    controller: AnalysisController, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n")
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"

    def fail(*args: object) -> None:
        raise PermissionError("Simulated denied metadata/replace")

    monkeypatch.setattr("netconfiglint.gui.file_saving._replace", fail)
    assert not controller.saveSourceFile(str(path))
    assert path.read_text() == "sysname ORIGINAL\n" and controller.sourceDirty
    assert not list(tmp_path.glob(".netconfiglint-*"))


def test_new_destination_race_cannot_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "new.cfg"
    path.write_text("external")
    with pytest.raises(FileChangedError):
        save_configuration(path, "local", None)
    assert path.read_text() == "external"


def test_existing_draft_is_protected_before_startup_read(tmp_path: Path, qapp: object) -> None:
    draft = tmp_path / "temporary" / "editor.txt"
    draft.parent.mkdir()
    draft.write_text("synthetic draft")
    if os.name != "nt":
        draft.parent.chmod(0o755)
        draft.chmod(0o644)
    controller = AnalysisController(
        async_enabled=False, history_store=HistoryStore(tmp_path / "history.json", enabled=False)
    )
    try:
        assert controller.temporaryText == "synthetic draft"
        if os.name != "nt":
            assert stat.S_IMODE(draft.stat().st_mode) == 0o600
            assert stat.S_IMODE(draft.parent.stat().st_mode) == 0o700
    finally:
        controller.close()


def test_existing_draft_privacy_failure_preserves_file_and_reports(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = tmp_path / "temporary" / "editor.txt"
    draft.parent.mkdir()
    draft.write_text("synthetic draft")

    def fail(path: Path) -> None:
        raise PermissionError("Cannot set private permissions")

    monkeypatch.setattr("netconfiglint.gui.controllers.analysis.protect_private_file", fail)
    controller = AnalysisController(
        async_enabled=False, history_store=HistoryStore(tmp_path / "history.json", enabled=False)
    )
    try:
        assert controller.temporaryText == ""
        assert controller.statusMessage == "temporary.private_error"
        assert draft.read_text() == "synthetic draft"
    finally:
        controller.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows NTFS streams")
def test_windows_replace_preserves_alternate_stream(tmp_path: Path) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("old")
    stream = Path(str(path) + ":audit-test")
    stream.write_text("retained metadata")
    save_configuration(path, "new", file_identity(path))
    assert path.read_text() == "new" and stream.read_text() == "retained metadata"
