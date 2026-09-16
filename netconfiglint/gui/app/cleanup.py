"""Explicit, bounded removal of NetConfigLint user data for uninstallers."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, QStandardPaths


def _safe_user_path(path: Path, user_home: Path | None = None) -> bool:
    resolved = path.resolve()
    home = (user_home or Path.home()).resolve()
    return resolved != home and home in resolved.parents and "netconfiglint" in str(resolved).lower()


def _remove_empty_app_parents(path: Path, user_home: Path) -> None:
    """Remove only now-empty parent folders that are explicitly NetConfigLint-owned."""
    current = path.parent.resolve()
    while _safe_user_path(current, user_home) and "netconfiglint" in {part.lower() for part in current.parts}:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _remove_windows_settings_key() -> None:
    if sys.platform != "win32":
        return
    import winreg

    def delete_tree(parent: Any, key_name: str) -> None:
        with suppress(FileNotFoundError):
            with winreg.OpenKey(parent, key_name, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                while True:
                    try:
                        child = winreg.EnumKey(key, 0)
                    except OSError:
                        break
                    delete_tree(key, child)
            winreg.DeleteKey(parent, key_name)

    delete_tree(winreg.HKEY_CURRENT_USER, r"Software\NetConfigLint")


def remove_all_user_data(
    application_dir: Path,
    user_paths: Iterable[Path] | None = None,
    *,
    user_home: Path | None = None,
) -> None:
    """Remove current-user settings/data while refusing broad or unrelated paths.

    ``user_paths`` exists for deterministic installer tests; production callers use
    Qt's platform-specific app-data, app-config, and cache locations.
    """
    settings = QSettings()
    settings.clear()
    settings.sync()
    _remove_windows_settings_key()
    home = (user_home or Path.home()).resolve()

    candidates = set(user_paths or ())
    if user_paths is None:
        candidates.update(
            Path(QStandardPaths.writableLocation(location))
            for location in (
                QStandardPaths.StandardLocation.AppDataLocation,
                QStandardPaths.StandardLocation.AppConfigLocation,
                QStandardPaths.StandardLocation.CacheLocation,
            )
        )
    adjacent_history = application_dir.resolve() / "history"
    if adjacent_history.parent == application_dir.resolve() and adjacent_history.name == "history":
        candidates.add(adjacent_history)
    for path in candidates:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved == application_dir.resolve():
            continue
        if resolved == adjacent_history or _safe_user_path(resolved, home):
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
            _remove_empty_app_parents(resolved, home)
