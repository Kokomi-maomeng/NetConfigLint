"""Prune pyside6-deploy's broad Qt payload before resolving PE dependencies."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

_PYSIDE_MODULES = {
    "QtCore.pyd",
    "QtGui.pyd",
    "QtNetwork.pyd",
    "QtOpenGL.pyd",
    "QtQml.pyd",
    "QtQuick.pyd",
    "QtQuickControls2.pyd",
    "QtWidgets.pyd",
}
_QML_MODULES = {"QtCore", "QtNetwork", "QtQml", "QtQuick"}
_QTQUICK_MODULES = {"Controls", "Dialogs", "Layouts", "Templates", "Window"}
_CONTROL_STYLES = {"Basic", "Material", "impl"}
_QTQML_MODULES = {"Models", "WorkerScript"}
_QT_PLUGIN_GROUPS = {
    "iconengines",
    "imageformats",
    "platforms",
}
_PLUGIN_FILES = {
    "iconengines": {"qsvgicon.dll"},
    "imageformats": {"qsvg.dll"},
    "platforms": {"qwindows.dll"},
}


def _prune_children(root: Path, allowed: set[str], distribution: Path) -> list[str]:
    removed: list[str] = []
    if root.is_dir():
        for path in root.iterdir():
            if path.is_dir() and path.name not in allowed:
                shutil.rmtree(path)
                removed.append(str(path.relative_to(distribution)))
    return removed


def prune(distribution: Path) -> dict[str, object]:
    pyside = distribution / "PySide6"
    if not pyside.is_dir() or distribution.parent.name != "dist":
        raise ValueError("Refusing to prune outside a dist/*.dist directory")

    removed: list[str] = []
    for duplicate_name in ("gui", "resources", "vendors"):
        duplicate = distribution / duplicate_name
        packaged = distribution / "netconfiglint" / duplicate_name
        if duplicate.is_dir() and packaged.is_dir():
            shutil.rmtree(duplicate)
            removed.append(str(duplicate.relative_to(distribution)))
    for path in pyside.glob("Qt*.pyd"):
        if path.name.lower() not in {name.lower() for name in _PYSIDE_MODULES}:
            path.unlink()
            removed.append(str(path.relative_to(distribution)))
    for path in pyside.glob("Qt6*.dll"):
        path.unlink()
        removed.append(str(path.relative_to(distribution)))

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
                if path.is_file() and path.name.lower() not in allowed_files:
                    path.unlink()
                    removed.append(str(path.relative_to(distribution)))

    return {"removed_count": len(removed), "removed": sorted(removed)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("distribution", type=Path)
    args = parser.parse_args()
    print(json.dumps(prune(args.distribution.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
