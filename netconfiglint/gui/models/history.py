from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

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


def default_history_path() -> Path:
    """Use an adjacent portable store or the platform user-data directory."""
    executable = Path(sys.executable).resolve()
    if executable.stem.lower() in {"netconfiglint", "deploy_main"}:
        root = executable.parent
        if (root / "portable.flag").is_file():
            return root / "history" / "history.json"
    else:
        root = Path(__file__).resolve().parents[3]
        if (root / "portable.flag").is_file():
            return root / "history" / "history.json"
    data_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(data_root) / "history" / "history.json"


def default_temporary_path() -> Path:
    """Use the same application-owned root as portable history."""
    return default_history_path().parent.parent / "temporary" / "editor.txt"


def local_timestamp(value: str) -> str:
    """Render persisted ISO timestamps in the machine's current local timezone."""
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    entry_id: str
    timestamp: str
    mode: str
    vendor: str
    diagnostic_count: int
    source_line_count: int
    summary: dict[str, int]
    rule_ids: tuple[str, ...]
    source_text: str = ""
    selected_vendor: str = "auto"
    diagnostics: tuple[dict[str, Any], ...] = ()
    coverage: dict[str, Any] | None = None

    @classmethod
    def from_result(
        cls, result: AnalysisResult, source_text: str = "", selected_vendor: str = "auto"
    ) -> HistoryEntry:
        timestamp = datetime.now(UTC).isoformat(timespec="microseconds")
        summary = {key: 0 for key in ("ERROR", "WARNING", "INFO", "UNKNOWN")}
        for diagnostic in result.diagnostics:
            summary[diagnostic.severity.value] += 1
        return cls(
            entry_id=uuid4().hex,
            timestamp=timestamp,
            mode=result.mode.value,
            vendor=result.detection.vendor,
            diagnostic_count=len(result.diagnostics),
            source_line_count=result.source_line_count,
            summary=summary,
            rule_ids=tuple(sorted({item.rule_id for item in result.diagnostics})),
            source_text=source_text,
            selected_vendor=selected_vendor,
            diagnostics=tuple(item.to_dict() for item in result.diagnostics),
            coverage=result.coverage,
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
        self.path = path or default_history_path()
        self.limit = limit
        self._persist_settings = persist_settings
        configured = QSettings().value("privacy/historyEnabled", True, type=bool)
        self.enabled = bool(configured if enabled is None else enabled)
        self.load_warning = False
        self.entries = self._load() if self.enabled else []

    def _load(self) -> list[HistoryEntry]:
        try:
            with self.path.open("rb") as stream:
                data = stream.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise ValueError("History size limit")
            raw = json.loads(data)
            if isinstance(raw, dict):
                if raw.get("schema_version") not in {1, 2}:
                    raise ValueError("Unsupported history schema")
                raw = raw.get("entries")
            if not isinstance(raw, list) or len(raw) > 1000:
                raise ValueError("Invalid history root or record count")
            entries = []
            for item in raw:
                try:
                    entries.append(self._entry(item))
                except (ValueError, KeyError, TypeError, OverflowError):
                    self.load_warning = True
            return sorted(entries, key=lambda item: item.timestamp, reverse=True)[: self.limit]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, TypeError, RecursionError):
            self.load_warning = True
            return []

    @staticmethod
    def _entry(item: Any) -> HistoryEntry:
        if not isinstance(item, dict):
            raise ValueError("Invalid history entry")
        for key in ("entry_id", "timestamp", "mode", "vendor"):
            if not isinstance(item[key], str) or not 1 <= len(item[key]) <= 128:
                raise ValueError("Invalid history string")
        datetime.fromisoformat(item["timestamp"])
        if item["mode"] not in {"snippet", "message", "view", "full", "snapshot"}:
            raise ValueError("Invalid history mode")
        for key in ("diagnostic_count", "source_line_count"):
            if type(item[key]) is not int or not 0 <= item[key] <= 1000000:
                raise ValueError("Invalid history count")
        summary = item["summary"]
        if not isinstance(summary, dict) or set(summary) != {"ERROR", "WARNING", "INFO", "UNKNOWN"}:
            raise ValueError("Invalid history summary")
        if any(type(value) is not int or not 0 <= value <= 1000000 for value in summary.values()):
            raise ValueError("Invalid summary counts")
        if sum(summary.values()) != item["diagnostic_count"]:
            raise ValueError("Inconsistent history counts")
        ids = item["rule_ids"]
        if (
            not isinstance(ids, list)
            or len(ids) > 1000
            or any(
                not isinstance(value, str) or re.fullmatch(r"[A-Z0-9-]{1,80}", value) is None for value in ids
            )
        ):
            raise ValueError("Invalid history rule list")
        source_text = item.get("source_text", "")
        if not isinstance(source_text, str) or len(source_text) > 4_000_000:
            raise ValueError("Invalid history source")
        diagnostics = item.get("diagnostics", [])
        if (
            not isinstance(diagnostics, list)
            or len(diagnostics) > 10000
            or any(not isinstance(d, dict) for d in diagnostics)
        ):
            raise ValueError("Invalid history diagnostics")
        selected_vendor = item.get("selected_vendor", "auto")
        if selected_vendor not in {"auto", "h3c", "huawei"}:
            raise ValueError("Invalid selected vendor")
        coverage = item.get("coverage")
        if coverage is not None and not isinstance(coverage, dict):
            raise ValueError("Invalid history coverage")
        return HistoryEntry(
            item["entry_id"],
            item["timestamp"],
            item["mode"],
            item["vendor"],
            item["diagnostic_count"],
            item["source_line_count"],
            dict(summary),
            tuple(ids),
            source_text,
            selected_vendor,
            tuple(diagnostics),
            coverage,
        )

    def set_enabled(self, enabled: bool) -> None:
        if enabled and not self.enabled:
            self.entries = self._load()
        if not enabled and self.enabled:
            self.clear()
        self.enabled = enabled
        if self._persist_settings:
            QSettings().setValue("privacy/historyEnabled", enabled)

    def append(self, result: AnalysisResult, source_text: str = "", selected_vendor: str = "auto") -> None:
        if not self.enabled:
            return
        if self.load_warning:
            raise OSError("Damaged history preserved; recover or explicitly clear it before saving")
        previous = list(self.entries)
        if len(source_text) > 4_000_000:
            raise OSError("History source exceeds per-entry limit")
        self.entries.insert(0, HistoryEntry.from_result(result, source_text, selected_vendor))
        del self.entries[self.limit :]
        try:
            self._write()
        except OSError:
            self.entries = previous
            raise

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.entries.clear()
        self.load_warning = False

    def remove_ids(self, ids: set[str]) -> None:
        previous = list(self.entries)
        self.entries = [entry for entry in self.entries if entry.entry_id not in ids]
        try:
            self._write()
        except OSError:
            self.entries = previous
            raise

    def get(self, entry_id: str) -> HistoryEntry | None:
        return next((item for item in self.entries if item.entry_id == entry_id), None)

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 2, "entries": [asdict(entry) for entry in self.entries]}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class HistoryRole(IntEnum):
    TIMESTAMP = Qt.ItemDataRole.UserRole + 1
    MODE = Qt.ItemDataRole.UserRole + 2
    VENDOR = Qt.ItemDataRole.UserRole + 3
    DIAGNOSTIC_COUNT = Qt.ItemDataRole.UserRole + 4
    SOURCE_LINE_COUNT = Qt.ItemDataRole.UserRole + 5
    SUMMARY = Qt.ItemDataRole.UserRole + 6
    RULE_IDS = Qt.ItemDataRole.UserRole + 7
    ENTRY_ID = Qt.ItemDataRole.UserRole + 8


class HistoryListModel(QAbstractListModel):
    _ROLE_NAMES: ClassVar[dict[HistoryRole, bytes]] = {
        HistoryRole.TIMESTAMP: b"timestamp",
        HistoryRole.MODE: b"mode",
        HistoryRole.VENDOR: b"vendor",
        HistoryRole.DIAGNOSTIC_COUNT: b"diagnosticCount",
        HistoryRole.SOURCE_LINE_COUNT: b"sourceLineCount",
        HistoryRole.SUMMARY: b"summary",
        HistoryRole.RULE_IDS: b"ruleIds",
        HistoryRole.ENTRY_ID: b"entryId",
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
            HistoryRole.TIMESTAMP: local_timestamp(item.timestamp),
            HistoryRole.MODE: item.mode,
            HistoryRole.VENDOR: item.vendor,
            HistoryRole.DIAGNOSTIC_COUNT: item.diagnostic_count,
            HistoryRole.SOURCE_LINE_COUNT: item.source_line_count,
            HistoryRole.SUMMARY: item.summary,
            HistoryRole.RULE_IDS: list(item.rule_ids),
            HistoryRole.ENTRY_ID: item.entry_id,
        }
        return values.get(role)

    def replace(self, entries: list[HistoryEntry]) -> None:
        self.beginResetModel()
        self._items = list(entries)
        self.endResetModel()

    def ids_between(self, first: int, last: int) -> list[str]:
        start, end = sorted((first, last))
        return [item.entry_id for item in self._items[max(0, start) : end + 1]]
