"""File identity checks and metadata-preserving atomic configuration saves."""

from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from netconfiglint.gui.secure_storage import protect_private_file


@dataclass(frozen=True)
class FileIdentity:
    target: Path
    links: tuple[tuple[str, int, int, str], ...]
    device: int
    inode: int
    size: int
    modified: int
    mode: int
    digest: str


class FileChangedError(OSError):
    """The destination no longer matches the identity approved by the user."""


class SaveRecoveryError(OSError):
    """Recovery files must remain available after a partial filesystem failure."""

    def __init__(self, paths: tuple[Path, ...]) -> None:
        super().__init__("Save recovery files retained")
        self.paths = paths


def file_identity(path: Path) -> FileIdentity | None:
    path = Path(os.path.abspath(path))
    links: list[tuple[str, int, int, str]] = []
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            links.append((str(part), info.st_dev, info.st_ino, os.readlink(part)))
    target = path.resolve(strict=True)
    info = target.stat()
    if not stat.S_ISREG(info.st_mode):
        raise OSError("Destination is not a regular file")
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise FileChangedError("Destination changed while reading")
    return FileIdentity(
        target,
        tuple(links),
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        stat.S_IMODE(info.st_mode),
        digest,
    )


def inspect_destination(path: Path) -> FileIdentity | None:
    try:
        return file_identity(path)
    except FileNotFoundError:
        # A dangling link must never be replaced as if it were a new file.
        if path.is_symlink() or path.exists():
            raise OSError("Unresolved destination link") from None
        for parent in path.parents:
            if parent.is_symlink() and not parent.exists():
                raise OSError("Unresolved parent link") from None
        return None


def writable_destination(identity: FileIdentity) -> bool:
    info = identity.target.stat()
    if not identity.mode & 0o222 or getattr(info, "st_file_attributes", 0) & 1:
        return False
    if os.name == "nt":
        try:
            _check_windows_write_access(identity.target)
        except PermissionError:
            return False
    return True


def _check_windows_write_access(path: Path) -> None:
    if sys.platform != "win32":
        raise OSError("Windows file access checks are unavailable on this platform")
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x40000000, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.CloseHandle(handle)


def _preserve_metadata(source: Path, temporary: Path) -> None:
    info = source.stat()
    if os.name == "nt":
        _preserve_windows_owner(source, temporary)
    else:
        current = temporary.stat()
        if (current.st_uid, current.st_gid) != (info.st_uid, info.st_gid):
            getattr(os, "chown")(temporary, info.st_uid, info.st_gid)  # noqa: B009 - POSIX-only API
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        if hasattr(os, "listxattr"):
            for name in os.listxattr(source):
                getattr(os, "setxattr")(temporary, name, getattr(os, "getxattr")(source, name))  # noqa: B009


def _preserve_windows_owner(source: Path, temporary: Path) -> None:
    if sys.platform != "win32":
        raise OSError("Windows ownership checks are unavailable on this platform")
    import ctypes
    from ctypes import wintypes

    security = ctypes.WinDLL("advapi32", use_last_error=True)
    security.GetFileSecurityW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    security.GetFileSecurityW.restype = wintypes.BOOL
    security.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    security.SetFileSecurityW.restype = wintypes.BOOL

    def descriptor(path: Path) -> bytes:
        size = wintypes.DWORD()
        security.GetFileSecurityW(str(path), 3, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        data = ctypes.create_string_buffer(size.value)
        if not security.GetFileSecurityW(str(path), 3, data, size.value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return data.raw

    original = descriptor(source)
    if original != descriptor(temporary):
        data = ctypes.create_string_buffer(original)
        if not security.SetFileSecurityW(str(temporary), 3, data):
            raise ctypes.WinError(ctypes.get_last_error())


def _replace(temporary: Path, target: Path, existing: bool) -> None:
    if sys.platform == "win32" and existing:
        # ReplaceFileW merges the original DACL, streams and Windows metadata.
        # Do not ignore merge errors: preserving metadata is part of saving.
        import ctypes
        from ctypes import wintypes

        replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
        replace_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.LPVOID,
        ]
        replace_file.restype = wintypes.BOOL
        handle, name = tempfile.mkstemp(prefix=".netconfiglint-backup-", dir=target.parent)
        os.close(handle)
        backup = Path(name)
        backup.unlink()
        if not replace_file(str(target), str(temporary), str(backup), 0, None, None):
            error = ctypes.WinError(ctypes.get_last_error())
            if backup.exists():
                try:
                    # Never overwrite a destination created by another writer.
                    os.link(backup, target)
                    backup.unlink()
                except OSError:
                    raise SaveRecoveryError(tuple(p for p in (backup, temporary) if p.exists())) from error
            if not target.exists():
                raise SaveRecoveryError(tuple(p for p in (backup, temporary) if p.exists())) from error
            raise error
        try:
            backup.unlink(missing_ok=True)
        except OSError as error:
            # The write succeeded, but report the retained original explicitly.
            raise SaveRecoveryError((backup,)) from error
    elif existing:
        os.replace(temporary, target)
    else:
        # Unlike replace(), this cannot overwrite a newly appeared destination.
        os.link(temporary, target)
        try:
            temporary.unlink()
        except OSError as error:
            raise SaveRecoveryError((temporary,)) from error


def save_configuration(path: Path, text: str, expected: FileIdentity | None) -> FileIdentity:
    if inspect_destination(path) != expected:
        raise FileChangedError("Destination changed before saving")
    if expected is not None and not writable_destination(expected):
        raise PermissionError("Destination is read-only")
    target = expected.target if expected is not None else Path(os.path.abspath(path))
    temporary: Path | None = None
    retain_recovery = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=target.parent, prefix=".netconfiglint-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            protect_private_file(temporary)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is not None:
            _preserve_metadata(target, temporary)
        if inspect_destination(path) != expected:
            raise FileChangedError("Destination changed during saving")
        _replace(temporary, target, expected is not None)
        result = file_identity(path)
        if result is None:
            raise OSError("Saved file is missing")
        return result
    except SaveRecoveryError:
        retain_recovery = True
        raise
    finally:
        if temporary is not None and not retain_recovery:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                raise SaveRecoveryError((temporary,)) from error
