"""Prune unused macOS Qt modules, preserving the remaining native dependency closure."""

from __future__ import annotations

import re
import shutil
from collections import deque
from pathlib import Path

if __package__:
    from .assemble_licenses import native
    from .macho_provenance import dependencies
    from .prepare_linux_runtime import (
        _CONTROL_STYLES,
        _PLUGIN_FILES,
        _PYSIDE_MODULES,
        _QML_MODULES,
        _QTQML_MODULES,
        _QTQUICK_MODULES,
        _prune_children,
    )
else:
    from assemble_licenses import native
    from macho_provenance import dependencies
    from prepare_linux_runtime import (
        _CONTROL_STYLES,
        _PLUGIN_FILES,
        _PYSIDE_MODULES,
        _QML_MODULES,
        _QTQML_MODULES,
        _QTQUICK_MODULES,
        _prune_children,
    )


def prune(distribution: Path) -> dict[str, object]:
    if distribution.is_symlink():
        raise ValueError("Refusing a linked macOS bundle")
    distribution = distribution.resolve()
    pyside = distribution / "Contents/MacOS/PySide6"
    if distribution.suffix != ".app" or distribution.parent.name != "dist" or not pyside.is_dir():
        raise ValueError("Expected a real dist/*.app bundle with PySide6")
    for path in distribution.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(distribution):
            raise ValueError("macOS bundle link escapes its directory")
    removed: list[str] = []
    for path in pyside.glob("Qt*.so"):
        if path.name.removesuffix(".so") not in _PYSIDE_MODULES:
            path.unlink()
            removed.append(path.relative_to(distribution).as_posix())
    qml = pyside / "qml"
    for folder, allowed in (
        (qml, _QML_MODULES),
        (qml / "QtQuick", _QTQUICK_MODULES),
        (qml / "QtQuick/Controls", _CONTROL_STYLES),
        (qml / "QtQml", _QTQML_MODULES),
    ):
        removed.extend(_prune_children(folder, allowed, distribution))
    plugins = pyside / "qt-plugins"
    removed.extend(
        _prune_children(
            plugins,
            {
                "accessiblebridge",
                "iconengines",
                "imageformats",
                "platforminputcontexts",
                "platforms",
                "platformthemes",
                "scenegraph",
                "vectorimageformats",
            },
            distribution,
        )
    )
    for group in ("iconengines", "imageformats", "platforms"):
        allowed = {name.removesuffix(".so") + ".dylib" for name in _PLUGIN_FILES[group]}
        if group == "platforms":
            allowed = {"libqcocoa.dylib", "libqminimal.dylib", "libqoffscreen.dylib"}
        if (plugins / group).is_dir():
            for path in (plugins / group).iterdir():
                if path.is_file() and path.name not in allowed:
                    path.unlink()
                    removed.append(path.relative_to(distribution).as_posix())

    files = [path for path in distribution.rglob("*") if path.is_file() and native(path)]
    metadata = {path: dependencies(path) for path in files}
    by_name: dict[str, set[Path]] = {}
    for path in files:
        by_name.setdefault(path.name, set()).add(path)
    candidates = {
        path for path in files if re.fullmatch(r"(?:lib)?Qt[A-Z0-9]\w*(?:\.\d+)*(?:\.dylib)?", path.name)
    }
    required = set(files) - candidates
    queue = deque(required)
    while queue:
        for name in metadata[queue.popleft()]:
            for target in by_name.get(Path(name).name, ()):
                if target not in required:
                    required.add(target)
                    queue.append(target)
    unused = candidates - required
    frameworks = {
        parent
        for path in unused
        for parent in path.parents
        if parent.suffix == ".framework"
        and parent.is_relative_to(distribution)
        and not any(item.is_relative_to(parent) for item in required)
    }
    for framework in sorted(frameworks):
        if framework.exists():
            shutil.rmtree(framework)
            removed.append(framework.relative_to(distribution).as_posix())
    for path in sorted(unused):
        if path.exists() or path.is_symlink():
            path.unlink()
            removed.append(path.relative_to(distribution).as_posix())
    return {"removed_count": len(removed), "removed": sorted(removed)}
