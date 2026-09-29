"""Prune unused macOS Qt modules, preserving the remaining native dependency closure."""

from __future__ import annotations

import plistlib
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

if __package__:
    from .assemble_licenses import native
    from .macho_provenance import dependencies, runtime_search_paths
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
    from macho_provenance import dependencies, runtime_search_paths
    from prepare_linux_runtime import (
        _CONTROL_STYLES,
        _PLUGIN_FILES,
        _PYSIDE_MODULES,
        _QML_MODULES,
        _QTQML_MODULES,
        _QTQUICK_MODULES,
        _prune_children,
    )


def _normalized_rpath(value: str) -> str | None:
    if value.startswith(("@loader_path", "@executable_path")):
        return None
    if value == "$ORIGIN":
        return "@executable_path"
    if not value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_.+/-]{1,120}", value) or value.startswith("/"):
        raise ValueError(f"Unsupported app RPATH (length={len(value)}, prefix={value[:1].encode().hex()})")
    location = posixpath.normpath("Contents/MacOS/" + value)
    if not location.startswith("Contents/"):
        raise ValueError("App RPATH escapes its bundle")
    return "@executable_path" if value == "." else "@executable_path/" + value


def _normalize_app_rpaths(executable: Path) -> None:
    changed = False
    for value in runtime_search_paths(executable):
        replacement = _normalized_rpath(value)
        if replacement is None:
            continue
        args = (
            ["install_name_tool", "-rpath", value, replacement]
            if replacement
            else ["install_name_tool", "-delete_rpath", value]
        )
        subprocess.run([*args, str(executable)], check=True)
        changed = True
    if changed:
        # arm64 executes only a correctly signed Mach-O after load-command edits.
        # Signing inside Contents/MacOS makes codesign interpret adjacent Nuitka
        # data directories as unsigned nested bundles. Sign the raw binary alone.
        with tempfile.TemporaryDirectory(prefix="netconfiglint-macos-sign-") as directory:
            temporary = Path(directory) / executable.name
            shutil.copy2(executable, temporary)
            subprocess.run(["codesign", "--force", "--sign", "-", str(temporary)], check=True)
            subprocess.run(["codesign", "--verify", "--strict", str(temporary)], check=True)
            shutil.copy2(temporary, executable)
        dependencies(executable)


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

    # Nuitka's app executable has no file extension, so native() does not
    # identify it. It is the root of the Qt framework dependency graph.
    with (distribution / "Contents/Info.plist").open("rb") as stream:
        entry = plistlib.load(stream).get("CFBundleExecutable")
    if not isinstance(entry, str) or not entry or Path(entry).name != entry:
        raise ValueError("Invalid macOS application executable name")
    executable = distribution / "Contents/MacOS" / entry
    if not executable.is_file() or executable.is_symlink():
        raise ValueError("macOS application executable missing")
    if sys.platform == "darwin":
        _normalize_app_rpaths(executable)
    files = [
        path for path in distribution.rglob("*") if path.is_file() and (native(path) or path == executable)
    ]
    metadata = {}
    for path in files:
        try:
            metadata[path] = dependencies(path)
        except ValueError as exc:
            raise ValueError(f"{path.relative_to(distribution).as_posix()}: {exc}") from exc
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
