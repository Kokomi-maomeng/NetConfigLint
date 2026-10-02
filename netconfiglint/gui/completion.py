"""Qt completion bridge; persists only the chosen vendor keys."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtQuick import QQuickTextDocument

from netconfiglint.commands.completion import VENDORS, complete


class CommandCompletion(QObject):
    changed = Signal()

    def __init__(self, parent: QObject | None = None, *, persist: bool = True) -> None:
        super().__init__(parent)
        self._persist = persist
        saved = QSettings().value("completion/vendors", []) if persist else []
        self._vendors = [key for key in VENDORS if isinstance(saved, list) and key in saved]

    def _get_selected(self) -> list[str]:
        return list(self._vendors)

    selectedVendors = Property("QStringList", _get_selected, notify=changed)  # type: ignore[arg-type]
    automatic = Property(bool, lambda self: not self._vendors, notify=changed)

    @Slot(str)
    def toggleVendor(self, vendor: str) -> None:
        if vendor == "auto":
            updated: list[str] = []
        elif vendor in VENDORS:
            updated = [key for key in VENDORS if key in (set(self._vendors) ^ {vendor})]
        else:
            return
        if updated == self._vendors:
            return
        self._vendors = updated
        if self._persist:
            QSettings().setValue("completion/vendors", updated)
        self.changed.emit()

    @Slot(str, int, result="QVariantMap")
    def request(self, source: str, cursor: int) -> dict[str, Any]:
        return complete(source, cursor, tuple(self._vendors))

    @Slot(QObject, int, int, str)
    def replace(self, editor: QObject, start: int, end: int, value: str) -> None:
        if editor.property("readOnly"):
            return
        quick_document = editor.property("textDocument")
        if not isinstance(quick_document, QQuickTextDocument):
            return
        document = quick_document.textDocument()
        if document is None or not 0 <= start <= end < document.characterCount():
            return
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(value)
        cursor.endEditBlock()
        editor.setProperty("cursorPosition", start + len(value.encode("utf-16-le")) // 2)
