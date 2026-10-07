"""Windows-only saves use synthetic NTFS files with explicit security/locks."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

import pytest

from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.file_saving import SaveRecoveryError, file_identity, save_configuration
from netconfiglint.gui.models.history import HistoryStore

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows NTFS metadata and sharing")


def _security() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetFileSecurityW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.c_void_p,
    ]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    api.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    return api, kernel


def _get_sddl(path: Path, security_information: int = 5) -> str:
    api, kernel = _security()
    size = wintypes.DWORD()
    api.GetFileSecurityW(str(path), security_information, None, 0, ctypes.byref(size))
    descriptor = ctypes.create_string_buffer(size.value)
    if not api.GetFileSecurityW(str(path), security_information, descriptor, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    value = wintypes.LPWSTR()
    if not api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        descriptor, 1, security_information, ctypes.byref(value), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return value.value or ""
    finally:
        kernel.LocalFree(ctypes.cast(value, ctypes.c_void_p))


def _set_sddl(path: Path, value: str, security_information: int = 0x80000004) -> None:
    api, kernel = _security()
    descriptor = ctypes.c_void_p()
    if not api.ConvertStringSecurityDescriptorToSecurityDescriptorW(value, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not api.SetFileSecurityW(str(path), security_information, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def _token_user_sid() -> str:
    api, kernel = _security()
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    api.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    api.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    assert api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token))
    value = wintypes.LPWSTR()
    try:
        size = wintypes.DWORD()
        api.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        data = ctypes.create_string_buffer(size.value)
        assert api.GetTokenInformation(token, 1, data, size, ctypes.byref(size))
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        assert api.ConvertSidToStringSidW(sid, ctypes.byref(value))
        return value.value or ""
    finally:
        if value:
            kernel.LocalFree(ctypes.cast(value, ctypes.c_void_p))
        kernel.CloseHandle(token)


def test_special_protected_dacl_and_current_owner_survive_configuration_save(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    owner = _get_sddl(path, 1).removeprefix("O:")
    _set_sddl(path, f"D:P(A;;FA;;;{owner})(A;;FR;;;BU)")
    before = _get_sddl(path)
    save_configuration(path, "UPDATED", file_identity(path))
    assert path.read_text() == "UPDATED"
    # ReplaceFile can set the auto-inherited bookkeeping flag without changing
    # protected status or the explicit access rules.
    assert _get_sddl(path).replace("D:PAI", "D:P") == before.replace("D:PAI", "D:P")


def test_alternate_assignable_owner_is_preserved_or_save_fails_before_replacement(tmp_path: Path) -> None:
    path = tmp_path / "synthetic-owner.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    try:
        assigned = _token_user_sid()
        if _get_sddl(path, 1) == f"O:{assigned}":
            assigned = "BA"
        _set_sddl(path, f"O:{assigned}", 1)
    except OSError as exc:
        pytest.skip(f"Token cannot assign the synthetic alternate owner: {exc}")
    before = _get_sddl(path, 1)
    try:
        save_configuration(path, "UPDATED", file_identity(path))
    except OSError:
        assert path.read_text() == "ORIGINAL"
    assert _get_sddl(path, 1) == before


def test_real_windows_sharing_lock_preserves_disk_and_dirty_controller(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "synthetic-locked.cfg"
    path.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    controller.loadFile(str(path))
    controller.sourceText = "sysname LOCAL\n"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        assert not controller.saveSourceFile(str(path))
        assert path.read_text() == "sysname ORIGINAL\n"
        assert controller.sourceDirty and controller.sourceText == "sysname LOCAL\n"
        assert not list(tmp_path.glob(".netconfiglint-*"))
    finally:
        kernel.CloseHandle(handle)
        controller.close()


def test_windows_dacl_denying_file_writes_is_respected(tmp_path: Path) -> None:
    path = tmp_path / "synthetic-denied.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    owner = _get_sddl(path, 1).removeprefix("O:")
    _set_sddl(path, f"D:P(D;;0x00000006;;;{owner})(A;;FA;;;{owner})")
    before = _get_sddl(path)
    try:
        with pytest.raises(PermissionError):
            save_configuration(path, "UPDATED", file_identity(path))
        assert path.read_text() == "ORIGINAL"
        assert _get_sddl(path) == before
    finally:
        _set_sddl(path, f"D:P(A;;FA;;;{owner})")


def test_new_configuration_and_temporary_are_private_even_in_shared_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import netconfiglint.gui.file_saving as saving

    shared = tmp_path / "synthetic-shared"
    shared.mkdir()
    sid = _token_user_sid()
    _set_sddl(shared, f"D:P(A;OICI;FA;;;{sid})(A;OICI;FR;;;BU)")
    protect = saving.protect_private_file
    protected: list[Path] = []

    def check_before_content(path: Path) -> None:
        assert path.stat().st_size == 0
        protect(path)
        assert ";;;BU)" not in _get_sddl(path, 4)
        protected.append(path)

    monkeypatch.setattr(saving, "protect_private_file", check_before_content)
    target = shared / "new.cfg"
    save_configuration(target, "SYNTHETIC-PRIVATE", None)
    assert protected and target.read_text() == "SYNTHETIC-PRIVATE"
    value = _get_sddl(target, 4)
    assert value.startswith("D:P") and ";;;BU)" not in value and ";;;WD)" not in value
    assert value.count("(A;") == 3


@pytest.mark.parametrize("error_code,recovery_denied", [(1176, False), (1177, False), (1177, True)])
def test_partial_replace_errors_recover_original_or_retain_both_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_code: int, recovery_denied: bool
) -> None:
    path = tmp_path / "synthetic-partial.cfg"
    path.write_text("ORIGINAL", encoding="utf-8")
    expected = file_identity(path)
    real_dll = ctypes.WinDLL

    class PartialReplace:
        argtypes: object = None
        restype: object = None

        def __call__(self, target: str, temporary: str, backup: str, *args: object) -> bool:
            assert Path(target) == path
            assert Path(temporary).read_text() == "UPDATED"
            assert backup and not Path(backup).exists()
            if error_code == 1177:
                # ReplaceFile's documented partial state: original renamed to
                # backup; replacement still under its temporary filename.
                Path(target).rename(backup)
            ctypes.set_last_error(error_code)
            return False

    class KernelProxy:
        def __init__(self, kernel: ctypes.CDLL) -> None:
            self.kernel = kernel
            self.ReplaceFileW = PartialReplace()

        def __getattr__(self, name: str) -> object:
            return getattr(self.kernel, name)

    def library(name: str, *args: object, **kwargs: object) -> object:
        result = real_dll(name, *args, **kwargs)
        return KernelProxy(result) if name == "kernel32" else result

    monkeypatch.setattr(ctypes, "WinDLL", library)
    if recovery_denied:

        def deny_recovery(source: Path, destination: Path) -> None:
            raise PermissionError("Synthetic recovery unavailable")

        monkeypatch.setattr(os, "link", deny_recovery)
        with pytest.raises(SaveRecoveryError) as caught:
            save_configuration(path, "UPDATED", expected)
        assert not path.exists()
        retained = caught.value.paths
        assert len(retained) == 2
        assert {item.read_text() for item in retained} == {"ORIGINAL", "UPDATED"}
        assert set(tmp_path.glob(".netconfiglint-*")) == set(retained)
    else:
        with pytest.raises(OSError) as caught:
            save_configuration(path, "UPDATED", expected)
        assert caught.value.winerror == error_code
        assert path.read_text() == "ORIGINAL"
        assert not list(tmp_path.glob(".netconfiglint-*"))
