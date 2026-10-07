"""Synthetic deletion boundaries and independent-process privacy revocation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import QSettings

from netconfiglint import analyze
from netconfiglint.gui.app.cleanup import _safe_user_path, remove_all_user_data
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore
from netconfiglint.gui.secure_storage import atomic_write_private, is_link_or_reparse


@pytest.mark.parametrize("ancestor", ["neutral", "NetConfigLint-audit", "netconfiglint-admin"])
def test_cleanup_rejects_product_substrings_and_unrelated_descendants(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch, ancestor: str
) -> None:
    monkeypatch.setattr("netconfiglint.gui.app.cleanup._remove_windows_settings_key", lambda: None)
    home = tmp_path / ancestor
    app = home / "installed" / "NetConfigLint"
    owned = home / "user" / "NetConfigLint" / "data"
    preserved = [
        home / "user" / "another-product",
        home / "user" / "NetConfigLintBackup",
        home / "NetConfigLint" / "another-product",
        app / "data",
    ]
    for directory in [owned, *preserved]:
        directory.mkdir(parents=True)
        (directory / "keep.bin").write_bytes(b"synthetic")
    remove_all_user_data(app, [owned, *preserved, app, home], user_home=home)
    assert not owned.exists()
    assert all((directory / "keep.bin").read_bytes() == b"synthetic" for directory in preserved)
    assert not _safe_user_path(home / "user" / "another-product", home)
    assert not _safe_user_path(home / "NetConfigLintBackup", home)


def _symlink(link: Path, target: Path, kind: str = "symlink") -> None:
    try:
        if kind == "junction":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as exc:
        pytest.skip(f"Host cannot create test symlinks: {exc}")


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        pytest.param(
            "junction", marks=pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions")
        ),
    ],
)
def test_cleanup_never_follows_candidate_ancestor_or_nested_links(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr("netconfiglint.gui.app.cleanup._remove_windows_settings_key", lambda: None)
    home, outside = tmp_path / "home", tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.bin").write_bytes(b"synthetic")
    app = home / "installed"
    owned = home / "NetConfigLint" / "data"
    owned.mkdir(parents=True)
    _symlink(owned / "nested-link", outside, kind)
    linked = home / "NetConfigLintBackup"
    _symlink(linked, outside, kind)
    redirected = home / "redirected"
    _symlink(redirected, outside, kind)
    (outside / "NetConfigLint").mkdir()
    (outside / "NetConfigLint" / "keep.bin").write_bytes(b"synthetic")
    portable = app / "history"
    app.mkdir()
    _symlink(portable, outside, kind)
    remove_all_user_data(app, [owned, linked, redirected / "NetConfigLint"], user_home=home)
    assert not owned.exists()
    assert is_link_or_reparse(linked) and is_link_or_reparse(portable)
    assert (outside / "keep.bin").read_bytes() == b"synthetic"
    assert (outside / "NetConfigLint" / "keep.bin").read_bytes() == b"synthetic"
    if os.name == "nt":
        assert not _safe_user_path(Path(r"\\invalid.synthetic\share\NetConfigLint"), home)


_PROCESS = """
import json, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QSettings
from netconfiglint import analyze
from netconfiglint.gui.models.history import HistoryStore
app=QCoreApplication([])
app.setOrganizationName('NetConfigLintTests')
app.setApplicationName('NetConfigLintTests')
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, sys.argv[2])
store=HistoryStore(Path(sys.argv[1]), enabled=True, retention='full')
token=store.privacy_token()
print(json.dumps({'ready': True, 'token': token}), flush=True)
for line in sys.stdin:
    action=json.loads(line)
    if action['action']=='quit': break
    source='sysname SYNTHETIC\\npassword cipher SYNTHETIC-PRIVATE\\n'
    store.append(analyze(source, vendor='huawei'), source,
                 privacy_token=token if action.get('old_token') else None)
    print(json.dumps({'enabled': store.enabled, 'retention': store.retention,
                      'count': len(store.entries)}), flush=True)
"""


def test_two_real_processes_cannot_restore_full_history_or_disabled_file(
    tmp_path: Path, qapp: object
) -> None:
    settings = QSettings()
    settings.setValue("privacy/historyEnabled", True)
    settings.setValue("privacy/historyRetention", "full")
    settings.sync()
    path = tmp_path / "history" / "history.json"
    source = "sysname SYNTHETIC\npassword cipher SYNTHETIC-PRIVATE\n"
    store = HistoryStore(path, enabled=True, retention="full")
    store.append(analyze(source, vendor="huawei"), source)
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", _PROCESS, str(path), str(Path(settings.fileName()).parent.parent)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        assert json.loads(process.stdout.readline())["ready"]

        def append(*, old_token: bool = False) -> dict[str, object]:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(json.dumps({"action": "append", "old_token": old_token}) + "\n")
            process.stdin.flush()
            return json.loads(process.stdout.readline())  # type: ignore[no-any-return]

        store.set_retention("summary")
        assert append()["retention"] == "summary"
        assert "SYNTHETIC-PRIVATE" not in path.read_text(encoding="utf-8")
        store.set_enabled(False)
        assert not append()["enabled"]
        assert not path.exists()
        store.set_enabled(True)
        store.set_retention("full")
        assert append(old_token=True)["count"] == 0
        assert not path.exists()
        assert append()["count"] == 1
        assert "SYNTHETIC-PRIVATE" in path.read_text(encoding="utf-8")
    finally:
        process.stdin.write('{"action":"quit"}\n')
        process.stdin.flush()
        _, errors = process.communicate(timeout=15)
        assert process.returncode == 0, errors


def test_privacy_revocation_survives_scrub_failure(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    import netconfiglint.gui.models.history as history

    path = tmp_path / "history.json"
    first = HistoryStore(path, enabled=True, retention="full", persist_settings=False)
    stale = HistoryStore(path, enabled=True, retention="full", persist_settings=False)
    result = analyze("sysname SYNTHETIC\n", vendor="huawei")
    first.append(result, "SYNTHETIC-PRIVATE")
    write = history.atomic_write_private

    def fail_history(target: Path, data: str | bytes) -> None:
        if target == path:
            raise OSError("Synthetic storage failure")
        write(target, data)

    with monkeypatch.context() as patch:
        patch.setattr(history, "atomic_write_private", fail_history)
        with pytest.raises(OSError, match="Synthetic"):
            first.set_retention("summary")
    stale.append(result, "SYNTHETIC-PRIVATE")
    assert stale.retention == "summary"
    assert "SYNTHETIC-PRIVATE" not in path.read_text(encoding="utf-8")
    first._policy_path.write_text("broken synthetic policy", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(OSError, match="privacy policy"):
        stale.append(result, "SYNTHETIC-PRIVATE")
    assert path.read_bytes() == before
    reopened = HistoryStore(path, enabled=True, persist_settings=False)
    assert not reopened.enabled and reopened.load_warning


@pytest.mark.parametrize("operation", ["summary", "off"])
def test_privacy_revocation_retries_disk_cleanup_after_initial_failure(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore(path, enabled=True, retention="full", persist_settings=False)
    result = analyze("sysname SYNTHETIC\n", vendor="huawei")
    store.append(result, "SYNTHETIC-PRIVATE")

    def change() -> None:
        if operation == "summary":
            store.set_retention("summary")
        else:
            store.set_enabled(False)

    with monkeypatch.context() as patch:
        if operation == "summary":

            def fail_write() -> None:
                raise PermissionError("Synthetic scrub failure")

            patch.setattr(store, "_write", fail_write)
        else:
            unlink = Path.unlink

            def fail_delete(target: Path, missing_ok: bool = False) -> None:
                if target == path:
                    raise PermissionError("Synthetic delete failure")
                unlink(target, missing_ok=missing_ok)

            patch.setattr(Path, "unlink", fail_delete)
        with pytest.raises(PermissionError, match="Synthetic"):
            change()
    assert "SYNTHETIC-PRIVATE" in path.read_text(encoding="utf-8")
    change()
    if operation == "summary":
        assert "SYNTHETIC-PRIVATE" not in path.read_text(encoding="utf-8")
        assert store.enabled and store.retention == "summary"
    else:
        assert not path.exists() and not store.enabled


@pytest.mark.parametrize("phase", ["queued", "running"])
@pytest.mark.parametrize("change", ["summary", "off"])
def test_remote_privacy_change_invalidates_queued_and_running_controller_work(
    tmp_path: Path, qapp: object, phase: str, change: str
) -> None:
    from PySide6.QtTest import QTest

    started, release = Event(), Event()

    def delayed(source: str, mode: str, vendor: str):  # type: ignore[no-untyped-def]
        started.set()
        assert release.wait(10)
        return analyze(source, mode, vendor)

    path = tmp_path / "history" / "history.json"
    store = HistoryStore(path, enabled=True, retention="full", persist_settings=False)
    other = HistoryStore(path, enabled=True, retention="full", persist_settings=False)
    controller = AnalysisController(analyzer=delayed, history_store=store)
    controller.vendor = "huawei"
    controller.sourceText = "sysname SYNTHETIC\npassword cipher SYNTHETIC-PRIVATE\n"
    try:
        if phase == "queued":
            controller._executor.submit(lambda: release.wait(10))
        controller.analyzeConfig()
        if phase == "running":
            assert started.wait(5)
        else:
            assert not started.is_set()
        if change == "summary":
            other.set_retention("summary")
        else:
            other.set_enabled(False)
        after_revocation = path.read_bytes() if path.exists() else None
        release.set()
        deadline = monotonic() + 10
        while controller.busy and monotonic() < deadline:
            QTest.qWait(10)
        assert not controller.busy and controller.resultCurrent
        assert (path.read_bytes() if path.exists() else None) == after_revocation
        controller.refreshHistory()
        assert not store.entries
        assert store.retention == "summary" if change == "summary" else not store.enabled
    finally:
        release.set()
        controller.close()


def test_rejected_background_write_does_not_reuse_old_history_identity(tmp_path: Path, qapp: object) -> None:
    from PySide6.QtTest import QTest

    started, release = Event(), Event()

    def delayed(source: str, mode: str, vendor: str):  # type: ignore[no-untyped-def]
        started.set()
        assert release.wait(10)
        return analyze(source, mode, vendor)

    store = HistoryStore(tmp_path / "history.json", enabled=True, retention="full", persist_settings=False)
    old_source = "sysname OLD-HISTORY\n"
    old_id = store.append(analyze(old_source, vendor="huawei"), old_source)
    assert old_id is not None
    other = HistoryStore(store.path, enabled=True, retention="full", persist_settings=False)
    controller = AnalysisController(analyzer=delayed, history_store=store)
    controller.vendor = "huawei"
    controller.sourceText = "sysname NEW-ANALYSIS\n"

    def wait_idle() -> None:
        deadline = monotonic() + 10
        while controller.busy and monotonic() < deadline:
            QTest.qWait(10)
        assert not controller.busy and controller.resultCurrent

    try:
        controller.analyzeConfig()
        assert started.wait(5)
        other.set_retention("summary")
        release.set()
        wait_idle()
        assert controller._active_history_id is None
        controller.refreshHistory()
        assert len(store.entries) == 1 and store.entries[0].entry_id == old_id
        controller.analyzeConfig()
        wait_idle()
        assert len(store.entries) == 2
        assert controller._active_history_id == store.entries[0].entry_id != old_id
    finally:
        release.set()
        controller.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
@pytest.mark.parametrize("mask", [0o022, 0o002, 0o077])
def test_private_atomic_draft_permissions_under_each_umask(tmp_path: Path, mask: int) -> None:
    path = tmp_path / "shared-xdg" / "temporary" / "editor.txt"
    previous = os.umask(mask)
    try:
        atomic_write_private(path, "SYNTHETIC-PRIVATE")
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        path.chmod(0o644)
        path.parent.chmod(0o755)
        atomic_write_private(path, "UPDATED")
        assert path.read_text() == "UPDATED"
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
    finally:
        os.umask(previous)


def test_failed_private_replace_preserves_draft_and_removes_unique_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "temporary" / "editor.txt"
    atomic_write_private(path, "BASE")

    def fail_replace(source: Path, target: Path) -> None:
        assert source.name.startswith("editor.txt.") and source.name.endswith(".tmp")
        assert source.read_text() == "UPDATED"
        if os.name != "nt":
            assert source.stat().st_mode & 0o777 == 0o600
        raise OSError("Synthetic replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="Synthetic replace"):
        atomic_write_private(path, "UPDATED")
    assert path.read_text() == "BASE"
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL inspection")
def test_windows_private_draft_has_protected_explicit_acl(tmp_path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    path = tmp_path / "temporary" / "editor.txt"
    atomic_write_private(path, "SYNTHETIC-PRIVATE")
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security.GetFileSecurityW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    security.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.c_void_p,
    ]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    for target in (path, path.parent):
        size = wintypes.DWORD()
        security.GetFileSecurityW(str(target), 4, None, 0, ctypes.byref(size))
        descriptor = ctypes.create_string_buffer(size.value)
        assert security.GetFileSecurityW(str(target), 4, descriptor, size, ctypes.byref(size))
        sddl = wintypes.LPWSTR()
        assert security.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(sddl), None
        )
        try:
            value = sddl.value or ""
            assert value.startswith("D:P") and ";ID;" not in value
            assert ";;;SY)" in value and ";;;BA)" in value
            assert ";;;WD)" not in value and ";;;BU)" not in value
            assert value.count("(A;") == 3
        finally:
            kernel.LocalFree(ctypes.cast(sddl, ctypes.c_void_p))
