"""Prune pyside6-deploy's broad Linux Qt payload to the used runtime closure."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import deque
from pathlib import Path

if __package__:
    from .assemble_licenses import _cstring, _dynamic_entries, elf_snapshot
else:
    from assemble_licenses import _cstring, _dynamic_entries, elf_snapshot

_PYSIDE_MODULES = {
    "QtCore",
    "QtGui",
    "QtNetwork",
    "QtOpenGL",
    "QtQml",
    "QtQuick",
    "QtQuickControls2",
    "QtWidgets",
}
_QML_MODULES = {"QtCore", "QtNetwork", "QtQml", "QtQuick"}
_QTQUICK_MODULES = {"Controls", "Dialogs", "Layouts", "Templates", "Window"}
_CONTROL_STYLES = {"Basic", "Material", "impl"}
_QTQML_MODULES = {"Models", "WorkerScript"}
_QT_PLUGIN_GROUPS = {
    "iconengines",
    "imageformats",
    "platforminputcontexts",
    "platforms",
    "xcbglintegrations",
}
_PLUGIN_FILES = {
    "iconengines": {"libqsvgicon.so"},
    "imageformats": {"libqgif.so", "libqico.so", "libqjpeg.so", "libqsvg.so"},
    "platforminputcontexts": {
        "libcomposeplatforminputcontextplugin.so",
        "libibusplatforminputcontextplugin.so",
    },
    "platforms": {"libqminimal.so", "libqoffscreen.so", "libqxcb.so"},
}
_DEBIAN_SYSTEM_LIBRARIES = {
    "libbz2.so.1.0",
    "libcrypto.so.3",
    "libexpat.so.1",
    "libffi.so.8",
    "liblzma.so.5",
    "libssl.so.3",
    "libzstd.so.1",
}


def _prune_children(root: Path, allowed: set[str], distribution: Path) -> list[str]:
    removed: list[str] = []
    if root.is_dir():
        for path in root.iterdir():
            if path.is_dir() and path.name not in allowed:
                shutil.rmtree(path)
                removed.append(path.relative_to(distribution).as_posix())
    return removed


def _elf_metadata(path: Path) -> tuple[str | None, tuple[str, ...]] | None:
    snapshot = elf_snapshot(path)
    if snapshot is None:
        return None
    _, sections, _ = snapshot
    try:
        strings = sections[".dynstr"]
        entries = _dynamic_entries(sections[".dynamic"])
    except KeyError:
        return None
    if entries is None:
        return None
    needed: list[str] = []
    soname: str | None = None
    for tag, value in entries:
        if tag not in {1, 14}:  # DT_NEEDED, DT_SONAME
            continue
        item = _cstring(strings, value)
        if item is None:
            return None
        try:
            decoded = item.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
        if tag == 1:
            needed.append(decoded)
        else:
            soname = decoded
    return soname, tuple(needed)


def _prune_unreachable_qt_libraries(distribution: Path) -> list[str]:
    """Delete only Qt shared libraries outside the real ELF dependency closure.

    Every executable, Python extension and retained plugin is a root.  This is
    intentionally conservative: non-Qt libraries are never deleted here, while
    every bundled ``libQt6*.so`` must be a dependency of at least one root.
    """
    metadata: dict[Path, tuple[str | None, tuple[str, ...]]] = {}
    by_name: dict[str, set[Path]] = {}
    candidates: set[Path] = set()
    for path in distribution.rglob("*"):
        if not path.is_file():
            continue
        if re.fullmatch(r"libQt6.+\.so(?:\.\d+)*", path.name):
            candidates.add(path)
        details = _elf_metadata(path)
        if details is None:
            continue
        metadata[path] = details
        soname, _ = details
        by_name.setdefault(path.name, set()).add(path)
        if soname:
            by_name.setdefault(soname, set()).add(path)
    unreadable = candidates - metadata.keys()
    if unreadable:
        listed = ", ".join(sorted(path.relative_to(distribution).as_posix() for path in unreadable))
        raise ValueError(f"Cannot prove Linux Qt dependency closure: {listed}")

    required = set(metadata) - candidates
    queue = deque(required)
    while queue:
        path = queue.popleft()
        for dependency in metadata[path][1]:
            for target in by_name.get(dependency, ()):
                if target not in required:
                    required.add(target)
                    queue.append(target)

    removed: list[str] = []
    for path in sorted(candidates - required):
        removed.append(path.relative_to(distribution).as_posix())
        path.unlink()
    return removed


def prune(distribution: Path) -> dict[str, object]:
    distribution = distribution.resolve()
    pyside = distribution / "PySide6"
    if (
        distribution.suffix != ".dist"
        or distribution.parent.name != "dist"
        or not pyside.is_dir()
        or pyside.is_symlink()
    ):
        raise ValueError("Refusing to prune outside a dist/*.dist Linux distribution")

    removed: list[str] = []
    for duplicate_name in ("gui", "resources", "vendors"):
        duplicate = distribution / duplicate_name
        packaged = distribution / "netconfiglint" / duplicate_name
        if duplicate.is_dir() and packaged.is_dir():
            shutil.rmtree(duplicate)
            removed.append(duplicate.relative_to(distribution).as_posix())

    for path in pyside.glob("Qt*.so"):
        if path.name.removesuffix(".so") not in _PYSIDE_MODULES:
            path.unlink()
            removed.append(path.relative_to(distribution).as_posix())

    # The Debian package declares these ABI-specific libraries as dependencies.
    # Do not ship copies from the build VM under untracked distro provenance.
    for name in _DEBIAN_SYSTEM_LIBRARIES:
        path = distribution / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
            removed.append(path.relative_to(distribution).as_posix())

    qml_root = pyside / "qml"
    removed.extend(_prune_children(qml_root, _QML_MODULES, distribution))
    removed.extend(_prune_children(qml_root / "QtQuick", _QTQUICK_MODULES, distribution))
    removed.extend(_prune_children(qml_root / "QtQuick" / "Controls", _CONTROL_STYLES, distribution))
    removed.extend(_prune_children(qml_root / "QtQml", _QTQML_MODULES, distribution))
    removed.extend(_prune_children(pyside / "qt-plugins", _QT_PLUGIN_GROUPS, distribution))
    for group, allowed_files in _PLUGIN_FILES.items():
        plugin_dir = pyside / "qt-plugins" / group
        if plugin_dir.is_dir():
            for path in plugin_dir.iterdir():
                if path.is_file() and path.name not in allowed_files:
                    path.unlink()
                    removed.append(path.relative_to(distribution).as_posix())

    removed.extend(_prune_unreachable_qt_libraries(distribution))
    return {"removed_count": len(removed), "removed": sorted(removed)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("distribution", type=Path)
    args = parser.parse_args()
    print(json.dumps(prune(args.distribution), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
