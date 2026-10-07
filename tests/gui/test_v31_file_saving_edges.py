"""Save races, OS metadata failures and recoverable partial filesystem writes."""

from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path

import pytest

from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.file_saving import (
    FileChangedError,
    SaveRecoveryError,
    file_identity,
    inspect_destination,
    save_configuration,
)
from netconfiglint.gui.models.history import HistoryStore


def _controller(tmp_path: Path) -> AnalysisController:
    return AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )


def _link(path: Path, target: Path, *, directory: bool = False) -> None:
    try:
        path.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"Creating synthetic symlinks is unavailable: {exc}")


@pytest.mark.parametrize("kind", ["directory", "dangling-file", "dangling-parent"])
def test_nonregular_and_unresolved_destinations_are_never_replaced(tmp_path: Path, kind: str) -> None:
    missing = tmp_path / "missing"
    if kind == "directory":
        path = tmp_path / "directory"
        path.mkdir()
        (path / "keep.bin").write_bytes(b"synthetic")
    elif kind == "dangling-file":
        path = tmp_path / "dangling.cfg"
        _link(path, missing)
    else:
        parent = tmp_path / "dangling-parent"
        _link(parent, missing, directory=True)
        path = parent / "new.cfg"
    with pytest.raises(OSError):
        inspect_destination(path)
    with pytest.raises(OSError):
        save_configuration(path, "LOCAL", None)
    assert not missing.exists()
    if kind == "directory":
        assert (path / "keep.bin").read_bytes() == b"synthetic"
    elif kind == "dangling-file":
        assert path.is_symlink()
    else:
        assert path.parent.is_symlink()
    assert not list(tmp_path.glob(".netconfiglint-*"))


def test_destination_appearing_after_last_check_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import netconfiglint.gui.file_saving as saving

    path = tmp_path / "new.cfg"
    replace = saving._replace

    def external_writer(temporary: Path, target: Path, existing: bool) -> None:
        assert not existing and not target.exists()
        target.write_text("EXTERNAL", encoding="utf-8")
        replace(temporary, target, existing)

    monkeypatch.setattr(saving, "_replace", external_writer)
    with pytest.raises(FileExistsError):
        save_configuration(path, "LOCAL", None)
    assert path.read_text() == "EXTERNAL"
    assert not list(tmp_path.glob(".netconfiglint-*"))


def test_link_retargeted_during_save_preserves_both_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import netconfiglint.gui.file_saving as saving

    first, second, link = tmp_path / "first.cfg", tmp_path / "second.cfg", tmp_path / "alias.cfg"
    for target in (first, second):
        target.write_text("ORIGINAL", encoding="utf-8")
    _link(link, first)
    expected = file_identity(link)
    preserve = saving._preserve_metadata

    def retarget(source: Path, temporary: Path) -> None:
        preserve(source, temporary)
        link.unlink()
        link.symlink_to(second)

    monkeypatch.setattr(saving, "_preserve_metadata", retarget)
    with pytest.raises(FileChangedError, match="during saving"):
        save_configuration(link, "LOCAL", expected)
    assert link.resolve() == second
    assert first.read_text() == second.read_text() == "ORIGINAL"
    assert not list(tmp_path.glob(".netconfiglint-*"))


def test_identity_rejects_source_that_changes_while_being_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    path = tmp_path / "source.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    digest = hashlib.file_digest

    def edit_during_hash(stream: object, algorithm: str):  # type: ignore[no-untyped-def]
        result = digest(stream, algorithm)
        with path.open("a", encoding="utf-8") as external:
            external.write("-EXTERNAL")
        return result

    monkeypatch.setattr(hashlib, "file_digest", edit_during_hash)
    with pytest.raises(FileChangedError, match="while reading"):
        file_identity(path)
    assert path.read_text() == "ORIGINAL-EXTERNAL"


def test_fsync_failure_retains_original_and_controller_dirty_state(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller = _controller(tmp_path)
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"

    def disk_full(handle: int) -> None:
        raise OSError(errno.ENOSPC, "Synthetic full filesystem")

    monkeypatch.setattr(os, "fsync", disk_full)
    try:
        assert not controller.saveSourceFile(str(path))
        assert path.read_text() == "sysname ORIGINAL\n"
        assert controller.sourceDirty and controller.sourceText == "sysname LOCAL\n"
        assert not list(tmp_path.glob(".netconfiglint-*"))
    finally:
        controller.close()


def test_startup_draft_link_is_preserved_without_reading_or_modifying_target(
    tmp_path: Path, qapp: object
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("SYNTHETIC-PRIVATE", encoding="utf-8")
    before = outside.stat().st_mode
    draft = tmp_path / "temporary" / "editor.txt"
    draft.parent.mkdir()
    _link(draft, outside)
    controller = _controller(tmp_path)
    try:
        assert controller.temporaryText == "" and controller.statusMessage == "temporary.private_error"
        assert draft.is_symlink()
        assert outside.read_text() == "SYNTHETIC-PRIVATE" and outside.stat().st_mode == before
    finally:
        controller.close()


def test_new_file_cleanup_failure_reports_private_recovery_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "new.cfg"
    unlink = Path.unlink

    def retain_temporary(target: Path, missing_ok: bool = False) -> None:
        if target.name.startswith(".netconfiglint-"):
            raise PermissionError("Synthetic temporary cleanup denial")
        unlink(target, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", retain_temporary)
    with pytest.raises(SaveRecoveryError) as caught:
        save_configuration(path, "LOCAL", None)
    assert path.read_text() == "LOCAL"
    assert len(caught.value.paths) == 1 and caught.value.paths[0].read_text() == "LOCAL"


def test_fsync_and_cleanup_failure_explains_retained_local_copy_without_changing_original(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller = _controller(tmp_path)
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    unlink = Path.unlink

    def disk_full(handle: int) -> None:
        raise OSError(errno.ENOSPC, "Synthetic full filesystem")

    def cleanup_denied(target: Path, missing_ok: bool = False) -> None:
        if target.name.startswith(".netconfiglint-"):
            raise PermissionError("Synthetic cleanup permission denial")
        unlink(target, missing_ok=missing_ok)

    monkeypatch.setattr(os, "fsync", disk_full)
    monkeypatch.setattr(Path, "unlink", cleanup_denied)
    try:
        assert not controller.saveSourceFile(str(path))
        assert path.read_text() == "sysname ORIGINAL\n" and controller.sourceDirty
        assert controller.fileConflict["reason"] == "recovery"
        retained = Path(controller.fileConflict["target"])
        assert retained.read_text() == "sysname LOCAL\n"
        assert not controller.fileConflict["canOverwrite"]
    finally:
        controller.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX extended attributes")
@pytest.mark.parametrize("deny_copy", [False, True])
def test_real_posix_xattrs_are_preserved_or_copy_failure_leaves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deny_copy: bool
) -> None:
    if not hasattr(os, "setxattr"):
        pytest.skip("Host Python has no extended-attribute API")
    path = tmp_path / "xattr.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    path.chmod(0o640)
    attribute, value = "user.netconfiglint.synthetic", b"synthetic\x00\xff"
    try:
        os.setxattr(path, attribute, value)
    except OSError as exc:
        if exc.errno in {errno.ENOTSUP, errno.EOPNOTSUPP}:
            pytest.skip(f"Temporary filesystem has no xattr support: {exc}")
        raise
    before = path.stat()
    if deny_copy:

        def denied(target: Path, name: str, contents: bytes) -> None:
            raise PermissionError("Synthetic metadata permission denial")

        monkeypatch.setattr(os, "setxattr", denied)
        with pytest.raises(PermissionError):
            save_configuration(path, "LOCAL", file_identity(path))
        assert path.read_text() == "ORIGINAL"
    else:
        save_configuration(path, "LOCAL", file_identity(path))
        assert path.read_text() == "LOCAL"
    assert os.getxattr(path, attribute) == value
    after = path.stat()
    assert (after.st_uid, after.st_gid, after.st_mode) == (before.st_uid, before.st_gid, before.st_mode)
    assert not list(tmp_path.glob(".netconfiglint-*"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership")
def test_privileged_posix_save_preserves_a_different_owner(tmp_path: Path) -> None:
    if os.geteuid() != 0:
        pytest.skip("Assigning an alternate owner requires the root-only isolated POSIX check")
    path = tmp_path / "alternate-owner.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    os.chown(path, 65534, 65534)
    path.chmod(0o640)
    save_configuration(path, "LOCAL", file_identity(path))
    after = path.stat()
    assert path.read_text() == "LOCAL" and (after.st_uid, after.st_gid) == (65534, 65534)


def _fake_windows_replace(monkeypatch: pytest.MonkeyPatch, operation: object) -> None:
    real = ctypes.WinDLL

    class Replace:
        argtypes: object = None
        restype: object = None

        def __call__(self, target: str, temporary: str, backup: str, *args: object) -> bool:
            return operation(Path(target), Path(temporary), Path(backup))  # type: ignore[operator, no-any-return]

    class Kernel:
        def __init__(self, library: ctypes.CDLL) -> None:
            self.library = library
            self.ReplaceFileW = Replace()

        def __getattr__(self, name: str) -> object:
            return getattr(self.library, name)

    def library(name: str, *args: object, **kwargs: object) -> object:
        result = real(name, *args, **kwargs)
        return Kernel(result) if name == "kernel32" else result

    monkeypatch.setattr(ctypes, "WinDLL", library)


@pytest.mark.skipif(os.name != "nt", reason="Windows partial replacement state")
def test_windows_recovery_does_not_overwrite_a_third_party_new_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")

    def concurrent_writer(target: Path, temporary: Path, backup: Path) -> bool:
        target.rename(backup)
        target.write_text("OTHER-WRITER", encoding="utf-8")
        ctypes.set_last_error(1177)
        return False

    _fake_windows_replace(monkeypatch, concurrent_writer)
    with pytest.raises(SaveRecoveryError) as caught:
        save_configuration(path, "LOCAL", file_identity(path))
    assert path.read_text() == "OTHER-WRITER"
    assert {file.read_text() for file in caught.value.paths} == {"ORIGINAL", "LOCAL"}


@pytest.mark.skipif(os.name != "nt", reason="Windows replacement backup cleanup")
def test_successful_windows_write_with_backup_cleanup_denied_explains_recovery(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.cfg"
    path.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller = _controller(tmp_path)
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"

    def successful_replace(target: Path, temporary: Path, backup: Path) -> bool:
        target.rename(backup)
        temporary.rename(target)
        return True

    _fake_windows_replace(monkeypatch, successful_replace)
    unlink = Path.unlink

    def deny_backup_delete(target: Path, missing_ok: bool = False) -> None:
        if target.name.startswith(".netconfiglint-backup-") and target.stat().st_size:
            raise PermissionError("Synthetic backup cleanup denial")
        unlink(target, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", deny_backup_delete)
    try:
        assert not controller.saveSourceFile(str(path))
        assert path.read_text() == "sysname LOCAL\n" and controller.sourceDirty
        assert controller.fileConflict["reason"] == "recovery"
        assert not controller.fileConflict["canOverwrite"] and controller.fileConflict["canReload"]
        backup = Path(controller.fileConflict["target"])
        assert backup.read_text() == "sysname ORIGINAL\n"
        controller.resolveFileConflict("cancel")
        assert backup.exists() and controller.sourceDirty
    finally:
        controller.close()
