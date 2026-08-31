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


def imports_for(path: Path) -> set[str]:
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    except pefile.PEFormatError:
        return set()
    try:
        return {
            entry.dll.decode("ascii", errors="ignore").lower()
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", ())
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
    wheel_roots = (site_packages / "PySide6", site_packages / "shiboken6")
    wheel_dlls = _index_dlls(wheel_roots)
    system_root = Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32"
    system_dlls = _index_dlls((system_root,), (".dll", ".drv", ".cpl"))
    bundled = _index_dlls((distribution,))
    queue = deque(
        path
        for path in distribution.rglob("*")
        if path.is_file() and path.suffix.lower() in {".exe", ".pyd", ".dll"}
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
            if dependency in bundled or dependency in system_dlls or dependency.startswith(_API_SET_PREFIXES):
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

    return {
        "copied_count": len(copied),
        "copied": sorted(copied),
        "unresolved_non_system": sorted(unresolved),
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
