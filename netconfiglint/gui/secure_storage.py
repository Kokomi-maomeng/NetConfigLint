"""Atomic writes for application-owned private data, independent of the umask."""

from __future__ import annotations

import ctypes
import os
import stat
import sys
import tempfile
from pathlib import Path


def is_link_or_reparse(path: Path) -> bool:
    """Do not follow Windows junctions or other reparse points either."""
    metadata = path.lstat()
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def has_link_ancestor(path: Path) -> bool:
    for component in (path, *path.parents):
        try:
            if is_link_or_reparse(component):
                return True
        except FileNotFoundError:
            continue
    return False


def _windows_private_acl(path: Path, *, directory: bool) -> None:
    if sys.platform != "win32":
        raise OSError("Windows private permissions are unavailable on this platform")
    # chmod on Windows does not remove inherited read access. Use a protected
    # DACL granting the current token user, SYSTEM and local Administrators.
    from ctypes import wintypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    token = wintypes.HANDLE()
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    sid_text = wintypes.LPWSTR()
    descriptor = ctypes.c_void_p()
    try:
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        data = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, data, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
            raise ctypes.WinError(ctypes.get_last_error())
        inheritance = "OICI" if directory else ""
        sddl = "D:P" + "".join(
            f"(A;{inheritance};FA;;;{identity})" for identity in (sid_text.value, "SY", "BA")
        )
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not advapi.SetFileSecurityW(str(path), 0x80000004, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if descriptor:
            kernel.LocalFree(descriptor)
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        kernel.CloseHandle(token)


def make_private_directory(path: Path) -> None:
    if has_link_ancestor(path):
        raise OSError("Private storage cannot use linked or redirected directories")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if os.name == "nt":
        _windows_private_acl(path, directory=True)
    else:
        path.chmod(0o700)


def protect_private_file(path: Path) -> None:
    """Apply private permissions before writing any sensitive file contents."""
    if has_link_ancestor(path):
        raise OSError("Private file cannot use a link or reparse point")
    if os.name == "nt":
        _windows_private_acl(path, directory=False)
    else:
        path.chmod(0o600)


def atomic_write_private(path: Path, contents: str | bytes) -> None:
    """Tighten the app-owned parent and replace with a private, unique file.

    Existing shared permissions deliberately become private. This helper is for
    history and drafts, never for user-selected configuration/export files.
    """
    if has_link_ancestor(path):
        raise OSError("Private storage cannot replace a link or reparse point")
    make_private_directory(path.parent)
    handle, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            protect_private_file(temporary)
            stream.write(contents.encode("utf-8") if isinstance(contents, str) else contents)
            stream.flush()
            os.fsync(stream.fileno())
        if has_link_ancestor(path):
            raise OSError("Private storage destination changed to a link or reparse point")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
