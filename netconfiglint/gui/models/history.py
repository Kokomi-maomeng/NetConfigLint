from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    QSettings,
    QStandardPaths,
    Qt,
)

from netconfiglint.core.analyzer import AnalysisResult

_INVALID_INDEX = QModelIndex()


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    entry_id: str
    timestamp: str
    mode: str
    vendor: str
    platform: str
    diagnostic_count: int
    source_line_count: int
    summary: dict[str, int]
    rule_ids: tuple[str, ...]

    @classmethod
    def from_result(cls, result: AnalysisResult) -> HistoryEntry:
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        summary = {key: 0 for key in ("ERROR", "WARNING", "INFO", "UNKNOWN")}
        for diagnostic in result.diagnostics:
            summary[diagnostic.severity.value] += 1
        return cls(
            entry_id=timestamp,
            timestamp=timestamp,
            mode=result.mode.value,
            vendor=result.detection.vendor,
            platform=result.detection.platform_family,
            diagnostic_count=len(result.diagnostics),
            source_line_count=result.source_line_count,
            summary=summary,
            rule_ids=tuple(sorted({item.rule_id for item in result.diagnostics})),
        )


class HistoryStore:
    def __init__(
        self,
        path: Path | None = None,
        *,
        enabled: bool | None = None,
        persist_settings: bool = True,
        limit: int = 100,
    ) -> None:
        data_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.path = path or data_root / "history.json"
        self.limit = limit
        self._persist_settings = persist_settings
        configured = QSettings().value("privacy/historyEnabled", False, type=bool)
        self.enabled = bool(configured if enabled is None else enabled)
        self.entries = self._load()

    def _load(self) -> list[HistoryEntry]:
        if not self.path.exists():
            return []
        try:
            raw: list[dict[str, Any]] = json.loads(self.path.read_text(encoding="utf-8"))
            return [
                HistoryEntry(
                    entry_id=item["entry_id"],
                    timestamp=item["timestamp"],
                    mode=item["mode"],
                    vendor=item["vendor"],
                    platform=item["platform"],
                    diagnostic_count=int(item["diagnostic_count"]),
                    source_line_count=int(item["source_line_count"]),
                    summary={str(key): int(value) for key, value in item["summary"].items()},
                    rule_ids=tuple(item["rule_ids"]),
                )
                for item in raw
            ]
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if self._persist_settings:
            QSettings().setValue("privacy/historyEnabled", enabled)

    def append(self, result: AnalysisResult) -> None:
        if not self.enabled:
            return
        self.entries.insert(0, HistoryEntry.from_result(result))
        del self.entries[self.limit :]
        self._write()

    def clear(self) -> None:
        self.entries.clear()
        if self.path.exists():
            self.path.unlink()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(entry) for entry in self.entries]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class HistoryRole(IntEnum):
    TIMESTAMP = Qt.ItemDataRole.UserRole + 1
    MODE = Qt.ItemDataRole.UserRole + 2
    VENDOR = Qt.ItemDataRole.UserRole + 3
    PLATFORM = Qt.ItemDataRole.UserRole + 4
    DIAGNOSTIC_COUNT = Qt.ItemDataRole.UserRole + 5
    SOURCE_LINE_COUNT = Qt.ItemDataRole.UserRole + 6
    SUMMARY = Qt.ItemDataRole.UserRole + 7
    RULE_IDS = Qt.ItemDataRole.UserRole + 8


class HistoryListModel(QAbstractListModel):
    _ROLE_NAMES: ClassVar[dict[HistoryRole, bytes]] = {
        HistoryRole.TIMESTAMP: b"timestamp",
        HistoryRole.MODE: b"mode",
        HistoryRole.VENDOR: b"vendor",
        HistoryRole.PLATFORM: b"platform",
        HistoryRole.DIAGNOSTIC_COUNT: b"diagnosticCount",
        HistoryRole.SOURCE_LINE_COUNT: b"sourceLineCount",
        HistoryRole.SUMMARY: b"summary",
        HistoryRole.RULE_IDS: b"ruleIds",
    }

    def __init__(self, entries: list[HistoryEntry] | None = None) -> None:
        super().__init__()
        self._items = list(entries or ())

    def roleNames(self) -> dict[int, QByteArray]:
        return {int(key): QByteArray(value) for key, value in self._ROLE_NAMES.items()}

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        values: dict[int, Any] = {
            HistoryRole.TIMESTAMP: item.timestamp,
            HistoryRole.MODE: item.mode,
            HistoryRole.VENDOR: item.vendor,
            HistoryRole.PLATFORM: item.platform,
            HistoryRole.DIAGNOSTIC_COUNT: item.diagnostic_count,
            HistoryRole.SOURCE_LINE_COUNT: item.source_line_count,
            HistoryRole.SUMMARY: item.summary,
            HistoryRole.RULE_IDS: list(item.rule_ids),
        }
        return values.get(role)

    def replace(self, entries: list[HistoryEntry]) -> None:
        self.beginResetModel()
        self._items = list(entries)
        self.endResetModel()
