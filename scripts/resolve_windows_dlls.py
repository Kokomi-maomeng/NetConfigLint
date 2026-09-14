"""Copy only wheel DLLs reachable from the standalone PE import graph."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import deque
from pathlib import Path

import pefile

_API_SET_PREFIXES = ("api-ms-win-", "ext-ms-")
_DYNAMIC_HELPERS = {"opengl32sw.dll", "d3dcompiler_47.dll"}


def imports_for(path: Path) -> set[str]:
    try:
        pe = pefile.PE(str(path), fast_load=True)
    except pefile.PEFormatError:
        return set()
    try:
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
            ]
        )
        return {
            entry.dll.decode("ascii", errors="ignore").lower()
            for directory in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT")
            for entry in getattr(pe, directory, ())
        }
    finally:
        pe.close()


def _index_dlls(roots: tuple[Path, ...], suffixes: tuple[str, ...] = (".dll",)) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for root in roots:
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in suffixes:
                    index.setdefault(path.name.lower(), path)
    return index


def resolve(distribution: Path, site_packages: Path) -> dict[str, object]:
    distribution = distribution.resolve()
    if distribution.parent.name != "dist" or not (distribution / "PySide6").is_dir():
        raise ValueError("Refusing to modify outside a dist/*.dist directory")
    files = [path for path in distribution.rglob("*") if path.is_file()]
    if any(not path.resolve().is_relative_to(distribution) for path in files):
        raise ValueError("Distribution link escapes its directory")
    wheel_roots = (site_packages / "PySide6", site_packages / "shiboken6")
    wheel_dlls = _index_dlls(wheel_roots)
    system_root = Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32"
    system_dlls = _index_dlls((system_root,), (".dll", ".drv", ".cpl"))
    bundled = _index_dlls((distribution,))
    queue = deque(
        path
        for path in files
        if path.suffix.lower() in {".exe", ".pyd"}
        # Qt loads the retained QML/platform/image plugins by name, not PE imports.
        or (
            path.suffix.lower() == ".dll"
            and (
                path.is_relative_to(distribution / "PySide6" / "qml")
                or path.is_relative_to(distribution / "PySide6" / "qt-plugins")
                or path.name.lower() in _DYNAMIC_HELPERS
            )
        )
    )
    copied: list[str] = []
    unresolved: set[str] = set()
    visited: set[Path] = set()

    while queue:
        importer = queue.popleft()
        resolved_importer = importer.resolve()
        if resolved_importer in visited:
            continue
        visited.add(resolved_importer)
        for dependency in imports_for(importer):
            if dependency in bundled:
                queue.append(bundled[dependency])
                continue
            if dependency in system_dlls or dependency.startswith(_API_SET_PREFIXES):
                continue
            source = wheel_dlls.get(dependency)
            if source is None:
                unresolved.add(dependency)
                continue
            if source.is_relative_to(wheel_roots[0]):
                relative = source.relative_to(wheel_roots[0])
                target = distribution / "PySide6" / relative
            else:
                relative = source.relative_to(wheel_roots[1])
                target = distribution / "shiboken6" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            bundled[dependency] = target
            copied.append(str(target.relative_to(distribution)))
            queue.append(target)

    # Nuitka/dumpbin may flatten unused Qt modules into the root. Their presence
    # must not make them roots of the dependency graph. Fail without pruning if
    # the graph is incomplete, and only remove files inside the validated tree.
    removed: list[str] = []
    if not unresolved:
        for path in files:
            if path.suffix.lower() == ".dll" and path.resolve() not in visited:
                path.unlink()
                removed.append(str(path.relative_to(distribution)))

    return {
        "copied_count": len(copied),
        "copied": sorted(copied),
        "unresolved_non_system": sorted(unresolved),
        "removed_count": len(removed),
        "removed": sorted(removed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("distribution", type=Path)
    parser.add_argument("site_packages", type=Path)
    args = parser.parse_args()
    report = resolve(args.distribution.resolve(), args.site_packages.resolve())
    print(json.dumps(report, indent=2))
    return 1 if report["unresolved_non_system"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
