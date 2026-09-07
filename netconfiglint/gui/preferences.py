"""Validated, configuration-free desktop preferences."""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot


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
    }

    def __init__(self, parent: QObject | None = None, *, persist: bool = True) -> None:
        super().__init__(parent)
        self._persist = persist
        self._values = dict(self.DEFAULTS)
        if persist:
            for key, default in self.DEFAULTS.items():
                self._assign(key, QSettings().value(f"appearance/{key}", default), save=False)

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
        elif key == "sidebarExpanded":
            value = value is True or value == "true"
        elif key in ("panels", "panelOrder"):
            if not isinstance(value, list) or any(v not in self.DEFAULTS["panels"] for v in value):
                return
            value = list(dict.fromkeys(value))
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
