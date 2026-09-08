from __future__ import annotations

from enum import IntEnum
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Slot,
)

from netconfiglint.core.diagnostics import Diagnostic

_INVALID_INDEX = QModelIndex()


class DiagnosticRole(IntEnum):
    SEVERITY = Qt.ItemDataRole.UserRole + 1
    RULE_ID = Qt.ItemDataRole.UserRole + 2
    LINE = Qt.ItemDataRole.UserRole + 3
    END_LINE = Qt.ItemDataRole.UserRole + 4
    OBJECT_NAME = Qt.ItemDataRole.UserRole + 5
    MESSAGE = Qt.ItemDataRole.UserRole + 6
    EXPLANATION = Qt.ItemDataRole.UserRole + 7
    SUGGESTED_FIX = Qt.ItemDataRole.UserRole + 8
    CONFIDENCE = Qt.ItemDataRole.UserRole + 9
    SOURCE_ROW = Qt.ItemDataRole.UserRole + 10


class DiagnosticListModel(QAbstractListModel):
    _ROLE_NAMES: ClassVar[dict[DiagnosticRole, bytes]] = {
        DiagnosticRole.SEVERITY: b"severity",
        DiagnosticRole.RULE_ID: b"ruleId",
        DiagnosticRole.LINE: b"line",
        DiagnosticRole.END_LINE: b"endLine",
        DiagnosticRole.OBJECT_NAME: b"targetObject",
        DiagnosticRole.MESSAGE: b"message",
        DiagnosticRole.EXPLANATION: b"explanation",
        DiagnosticRole.SUGGESTED_FIX: b"suggestedFix",
        DiagnosticRole.CONFIDENCE: b"confidence",
        DiagnosticRole.SOURCE_ROW: b"sourceRow",
    }

    def __init__(self) -> None:
        super().__init__()
        self._items: tuple[Diagnostic, ...] = ()
        self._rows: tuple[int, ...] = ()
        self._severity_filter = "ALL"

    def roleNames(self) -> dict[int, QByteArray]:
        return {int(key): QByteArray(value) for key, value in self._ROLE_NAMES.items()}

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        source_row = self._rows[index.row()]
        item = self._items[source_row]
        values: dict[int, Any] = {
            DiagnosticRole.SEVERITY: item.severity.value,
            DiagnosticRole.RULE_ID: item.rule_id,
            DiagnosticRole.LINE: item.source.line,
            DiagnosticRole.END_LINE: item.source.end_line or item.source.line,
            DiagnosticRole.OBJECT_NAME: item.object_name,
            DiagnosticRole.MESSAGE: item.message,
            DiagnosticRole.EXPLANATION: item.explanation,
            DiagnosticRole.SUGGESTED_FIX: item.suggested_fix,
            DiagnosticRole.CONFIDENCE: item.confidence.value,
            DiagnosticRole.SOURCE_ROW: source_row,
        }
        return values.get(role)

    def replace(self, items: tuple[Diagnostic, ...]) -> None:
        self.beginResetModel()
        self._items = items
        self._filter_rows()
        self.endResetModel()

    def _filter_rows(self) -> None:
        self._rows = tuple(
            row
            for row, item in enumerate(self._items)
            if self._severity_filter == "ALL" or item.severity.value == self._severity_filter
        )

    @Slot(str)
    def setSeverityFilter(self, value: str) -> None:
        if value not in {"ALL", "ERROR", "WARNING", "INFO", "UNKNOWN"} or value == self._severity_filter:
            return
        self.beginResetModel()
        self._severity_filter = value
        self._filter_rows()
        self.endResetModel()

    def item_at(self, row: int) -> Diagnostic | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    @property
    def items(self) -> tuple[Diagnostic, ...]:
        return self._items
