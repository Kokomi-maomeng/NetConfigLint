"""Validated, configuration-free desktop preferences."""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import Property, QObject, QRect, QSettings, Signal, Slot
from PySide6.QtGui import QGuiApplication


class Preferences(QObject):
    changed = Signal()
    COLORS: ClassVar[tuple[str, ...]] = (
        "violet",
        "blue",
        "green",
        "rose",
        "amber",
        "teal",
        "cyan",
        "indigo",
        "coral",
        "slate",
    )
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "panelTitle": "NetConfigLint",
        "themeMode": 0,
        "themeColor": "violet",
        "sidebarExpanded": True,
        "panels": ["configuration", "diagnostics", "temporary"],
        "panelOrder": ["configuration", "diagnostics", "temporary"],
        "windowWidth": 1440,
        "windowHeight": 900,
        "windowX": -1,
        "windowY": -1,
        "windowPositionSaved": False,
        "windowMaximized": False,
    }

    def __init__(self, parent: QObject | None = None, *, persist: bool = True) -> None:
        super().__init__(parent)
        self._persist = persist
        self._values = dict(self.DEFAULTS)
        if persist:
            for key, default in self.DEFAULTS.items():
                self._assign(key, QSettings().value(f"appearance/{key}", default), save=False)
            if self._values["windowPositionSaved"]:
                saved = QRect(
                    self._values["windowX"],
                    self._values["windowY"],
                    self._values["windowWidth"],
                    self._values["windowHeight"],
                )
                if not any(
                    saved.intersected(screen.availableGeometry()).width() >= 80
                    and saved.intersected(screen.availableGeometry()).height() >= 80
                    for screen in QGuiApplication.screens()
                ):
                    self._values["windowPositionSaved"] = False

    def _get_values(self) -> dict[str, Any]:
        return dict(self._values)

    values = Property("QVariantMap", _get_values, notify=changed)  # type: ignore[arg-type]

    def _assign(self, key: str, value: Any, *, save: bool) -> None:
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        if key == "panelTitle":
            value = str(value).strip()[:40] or "NetConfigLint"
        elif key == "themeMode":
            try:
                value = int(value)
            except (ValueError, TypeError):
                return
            if value not in (0, 1, 2):
                return
        elif key == "themeColor":
            if value not in self.COLORS:
                return
        elif key in ("sidebarExpanded", "windowMaximized", "windowPositionSaved"):
            value = value is True or value == "true"
        elif key in ("windowWidth", "windowHeight", "windowX", "windowY"):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return
            if key in ("windowWidth", "windowHeight") and not 600 <= value <= 10000:
                return
            if key in ("windowX", "windowY") and not -10000 <= value <= 10000:
                return
        elif key in ("panels", "panelOrder"):
            if not isinstance(value, list) or any(v not in self.DEFAULTS["panels"] for v in value):
                return
            value = list(dict.fromkeys(value))
            if key == "panels" and "configuration" not in value:
                value.insert(0, "configuration")
            if key == "panelOrder" and len(value) != 3:
                return
        else:
            return
        if value == self._values.get(key):
            return
        self._values[key] = value
        if save and self._persist:
            QSettings().setValue(f"appearance/{key}", value)
        self.changed.emit()

    @Slot(str, "QVariant")
    def setValue(self, key: str, value: Any) -> None:
        self._assign(key, value, save=True)

    @Slot(int, int, result="QVariantMap")
    def restoreWindowGeometry(self, minimum_width: int, minimum_height: int) -> dict[str, int]:
        """Fit saved geometry to the usable area of the monitor it occupied."""
        desired = QRect(
            int(self._values["windowX"]),
            int(self._values["windowY"]),
            int(self._values["windowWidth"]),
            int(self._values["windowHeight"]),
        )
        screens = QGuiApplication.screens()
        primary = QGuiApplication.primaryScreen()
        area = primary.availableGeometry() if primary else QRect(0, 0, 1440, 900)
        if self._values["windowPositionSaved"] and screens:
            area = max(
                (screen.availableGeometry() for screen in screens),
                key=lambda candidate: (
                    desired.intersected(candidate).width() * desired.intersected(candidate).height()
                ),
            )
        width = min(max(minimum_width, desired.width()), max(minimum_width, area.width()))
        height = min(max(minimum_height, desired.height()), max(minimum_height, area.height()))
        if self._values["windowPositionSaved"]:
            x = max(area.x(), min(desired.x(), area.x() + area.width() - width))
            y = max(area.y(), min(desired.y(), area.y() + area.height() - height))
        else:
            x = area.x() + max(0, (area.width() - width) // 2)
            y = area.y() + max(0, (area.height() - height) // 2)
        return {"x": x, "y": y, "width": width, "height": height}

    @Slot(int, int, int, int, bool)
    def saveWindowGeometry(self, x: int, y: int, width: int, height: int, maximized: bool) -> None:
        self._assign("windowMaximized", maximized, save=True)
        if width >= 960 and height >= 600:
            self._assign("windowPositionSaved", True, save=True)
            for key, value in (
                ("windowX", x),
                ("windowY", y),
                ("windowWidth", width),
                ("windowHeight", height),
            ):
                self._assign(key, value, save=True)
