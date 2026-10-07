"""Explicit, bounded removal of NetConfigLint user data for uninstallers."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths

from netconfiglint.gui.secure_storage import has_link_ancestor, is_link_or_reparse


def _absolute(path: Path) -> Path:
    # abspath normalizes . and .. without dereferencing a link first.
    return Path(os.path.abspath(path))


def _safe_user_path(path: Path, user_home: Path | None = None, *, app_names: set[str] | None = None) -> bool:
    candidate = _absolute(path)
    home = _absolute(user_home or Path.home())
    if candidate == home or home not in candidate.parents or has_link_ancestor(candidate):
        return False
    names = app_names or {"netconfiglint"}
    # Ownership is a complete final component, or one recognized child directly
    # inside it. Product-looking usernames, ancestors and backups prove nothing.
    return candidate.name.casefold() in names or (
        candidate.parent.name.casefold() in names
        and candidate.name.casefold() in {"data", "history", "temporary", "cache", "config"}
    )


def _remove_tree_without_following_links(path: Path) -> None:
    if is_link_or_reparse(path):
        # Junctions require rmdir on Windows; neither operation traverses them.
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
        else:
            path.unlink()
    elif path.is_dir():
        for child in path.iterdir():
            _remove_tree_without_following_links(child)
        path.rmdir()
    else:
        path.unlink()


def _remove_empty_app_parents(path: Path, user_home: Path) -> None:
    """Remove only now-empty parent folders that are explicitly NetConfigLint-owned."""
    current = _absolute(path.parent)
    while _safe_user_path(current, user_home) and current.name.casefold() == "netconfiglint":
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
    settings_file = Path(settings.fileName()) if sys.platform != "win32" else None
    if settings_file is None or not has_link_ancestor(settings_file):
        settings.clear()
        settings.sync()
        _remove_windows_settings_key()
    home = _absolute(user_home or Path.home())
    app_names = {
        value.casefold()
        for value in (
            QCoreApplication.organizationName(),
            QCoreApplication.applicationName(),
            "NetConfigLint",
        )
        if value
    }

    candidates = set(user_paths or ())
    if user_paths is None:
        standard_locations = {
            Path(QStandardPaths.writableLocation(location))
            for location in (
                QStandardPaths.StandardLocation.AppDataLocation,
                QStandardPaths.StandardLocation.AppConfigLocation,
                QStandardPaths.StandardLocation.CacheLocation,
            )
        }
        candidates.update(standard_locations)
        # With both organization and application set to NetConfigLint, Unix Qt
        # paths can end in NetConfigLint/NetConfigLint. The outer directory is
        # still exclusively application-owned and must not survive a delete-all
        # uninstall with stale or future-version files inside it.
        candidates.update(
            path.parent
            for path in standard_locations
            if path.name.lower() in app_names and path.parent.name.lower() in app_names
        )
        if settings_file is not None:
            candidates.add(settings_file)
            if settings_file.parent.name.lower() in app_names:
                candidates.add(settings_file.parent)
    app_root = _absolute(application_dir)
    adjacent_history = app_root / "history"
    adjacent_temporary = app_root / "temporary"
    candidates.update((adjacent_history, adjacent_temporary))
    exact_settings_file = _absolute(settings_file) if settings_file else None
    for path in candidates:
        candidate = _absolute(path)
        if not candidate.exists() or has_link_ancestor(candidate):
            continue
        if candidate == app_root or candidate in app_root.parents:
            continue
        if app_root in candidate.parents and candidate not in {adjacent_history, adjacent_temporary}:
            continue
        owned_settings = (
            candidate == exact_settings_file
            and home in candidate.parents
            and candidate.parent.name.casefold() in app_names
        )
        if (
            candidate in {adjacent_history, adjacent_temporary}
            or owned_settings
            or _safe_user_path(candidate, home, app_names=app_names)
        ):
            _remove_tree_without_following_links(candidate)
            _remove_empty_app_parents(candidate, home)
