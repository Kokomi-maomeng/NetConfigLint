from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QLockFile,
    QModelIndex,
    QPersistentModelIndex,
    QSettings,
    QStandardPaths,
    Qt,
)

from netconfiglint.core.analyzer import AnalysisResult
from netconfiglint.gui.secure_storage import atomic_write_private, has_link_ancestor, make_private_directory

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


def safe_history_title(title: str, source: str, vendor: str) -> str:
    """Keep a short local label; never put paths or secret-looking values in the title."""
    import hashlib

    label = Path(title).name.strip()
    device = re.search(r"(?mi)^\s*sysname\s+([A-Za-z0-9_.-]{1,40})\s*$", source)
    if device:
        suffix = f" · {device[1]}"
        while label.endswith(suffix):
            label = label[: -len(suffix)].rstrip()
        label = f"{label[: 80 - len(suffix)].rstrip()}{suffix}" if label and label != device[1] else device[1]
    else:
        label = label[:80]
    if not label or re.search(r"(?i)@|password|secret|token|api.?key|\b(?:\d{1,3}\.){3}\d{1,3}\b", label):
        label = (
            f"{vendor} · {len(source.splitlines())} lines · {hashlib.sha256(source.encode()).hexdigest()[:8]}"
        )
    return label


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
    title: str = ""
    initial_view: str = ""

    @classmethod
    def from_result(
        cls,
        result: AnalysisResult,
        source_text: str = "",
        selected_vendor: str = "auto",
        *,
        title: str = "",
        initial_view: str = "",
        retention: str = "full",
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
            source_text=source_text if retention == "full" else "",
            selected_vendor=selected_vendor,
            diagnostics=tuple(item.to_dict() for item in result.diagnostics) if retention == "full" else (),
            coverage=result.coverage if retention == "full" else None,
            title=safe_history_title(title, source_text, result.detection.vendor),
            initial_view=initial_view if retention == "full" else "",
        )


class HistoryStore:
    def __init__(
        self,
        path: Path | None = None,
        *,
        enabled: bool | None = None,
        persist_settings: bool = True,
        limit: int = 100,
        retention: str | None = None,
    ) -> None:
        self.path = path or default_history_path()
        self.limit = limit
        self._persist_settings = persist_settings
        self._privacy_revision = "initial"
        self._loaded_signature: tuple[int, int, int, int] | None = None
        configured_retention = QSettings().value("privacy/historyRetention", "summary")
        self.retention = retention or ("full" if enabled is not None else str(configured_retention))
        if self.retention not in {"summary", "full"}:
            self.retention = "summary"
        configured = QSettings().value("privacy/historyEnabled", True, type=bool)
        self.enabled = bool(configured if enabled is None else enabled)
        self.load_warning = False
        if self.enabled:
            try:
                self._refresh_privacy()
            except OSError:
                self.enabled = False
                self.load_warning = True
        self.entries = self._load() if self.enabled else []
        if (
            retention is None
            and enabled is None
            and not self._policy_path.exists()
            and not QSettings().contains("privacy/historyRetention")
            and any(entry.source_text for entry in self.entries)
        ):
            # Preserve existing recovery data, and describe its actual scope truthfully.
            self.retention = "full"
            if self._persist_settings:
                QSettings().setValue("privacy/historyRetention", "full")
        if self.retention == "summary":
            self.entries = self._summaries(self.entries)

    def _load(self) -> list[HistoryEntry]:
        try:
            with self.path.open("rb") as stream:
                data = stream.read(64 * 1024 * 1024 + 1)
                metadata = os.fstat(stream.fileno())
                self._loaded_signature = (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                )
            if len(data) > 64 * 1024 * 1024:
                raise ValueError("History size limit")
            raw = json.loads(data)
            if isinstance(raw, dict):
                if raw.get("schema_version") not in {1, 2, 3}:
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
        from netconfiglint.vendors.registry import VENDOR_PLUGINS

        if selected_vendor not in {"auto", *(plugin.key for plugin in VENDOR_PLUGINS)}:
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
            safe_history_title(str(item.get("title", "")), source_text, item["vendor"]),
            str(item.get("initial_view", ""))[:160],
        )

    def set_retention(self, value: str) -> None:
        if value not in {"summary", "full"}:
            return
        with self._transaction():
            self._refresh_privacy()
            if value == self.retention and value == "full":
                return
            self._save_privacy(self.enabled, value)
            if value == "summary" and self.enabled:
                self._refresh_for_write()
                self._write()

    def set_enabled(self, enabled: bool) -> None:
        with self._transaction():
            self._refresh_privacy()
            if enabled == self.enabled and enabled:
                return
            self._save_privacy(enabled, self.retention)
            if enabled:
                self.entries = self._load()
            else:
                self.path.unlink(missing_ok=True)
                self.entries.clear()
                self.load_warning = False

    @property
    def _policy_path(self) -> Path:
        # Keep the revocation record after disabling removes history.json.
        # Workers that intentionally do not write QSettings still consult it.
        return self.path.with_name(self.path.name + ".privacy.json")

    def _refresh_privacy(self) -> None:
        if has_link_ancestor(self._policy_path):
            raise OSError("History privacy policy cannot use linked or redirected paths")
        try:
            raw = json.loads(self._policy_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if self._persist_settings:
                settings = QSettings()
                settings.sync()
                if settings.status() != QSettings.Status.NoError:
                    raise OSError("History privacy preference could not be read") from None
                if settings.contains("privacy/historyEnabled"):
                    self.enabled = bool(settings.value("privacy/historyEnabled", False, type=bool))
                if settings.contains("privacy/historyRetention"):
                    configured = str(settings.value("privacy/historyRetention"))
                    self.retention = configured if configured in {"summary", "full"} else "summary"
            return
        except (OSError, ValueError, RecursionError) as exc:
            raise OSError("Invalid history privacy policy; history write refused") from exc
        if (
            not isinstance(raw, dict)
            or type(raw.get("enabled")) is not bool
            or raw.get("retention") not in {"summary", "full"}
            or not isinstance(raw.get("revision"), str)
        ):
            raise OSError("Invalid history privacy policy; history write refused")
        self.enabled = raw["enabled"]
        self.retention = raw["retention"]
        self._privacy_revision = raw["revision"]
        if not self.enabled:
            self.entries = []
        elif self.retention == "summary" and hasattr(self, "entries"):
            self.entries = self._summaries(self.entries)

    @staticmethod
    def _summaries(entries: list[HistoryEntry]) -> list[HistoryEntry]:
        return [replace(e, source_text="", diagnostics=(), coverage=None, initial_view="") for e in entries]

    def _save_privacy(self, enabled: bool, retention: str) -> None:
        revision = uuid4().hex
        # Commit the permission first. If scrubbing/deleting or settings sync
        # then fails, another instance must still respect the revocation.
        atomic_write_private(
            self._policy_path,
            json.dumps({"enabled": enabled, "retention": retention, "revision": revision}),
        )
        self.enabled, self.retention, self._privacy_revision = enabled, retention, revision
        if self._persist_settings:
            settings = QSettings()
            settings.sync()
            settings.setValue("privacy/historyEnabled", enabled)
            settings.setValue("privacy/historyRetention", retention)
            settings.sync()
            if settings.status() != QSettings.Status.NoError:
                raise OSError("History privacy preference could not be saved")

    def privacy_token(self) -> str:
        """Capture at analysis submission, and pass back to append after work."""
        with self._transaction():
            self._refresh_privacy()
            return self._privacy_revision

    def refresh(self) -> None:
        """Refresh other-window privacy and entries before display or restore."""
        with self._transaction():
            self._refresh_privacy()
            if not self.enabled:
                self.entries = []
                self._loaded_signature = None
            else:
                try:
                    metadata = self.path.stat()
                    signature = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
                except FileNotFoundError:
                    signature = None
                if signature != self._loaded_signature:
                    self.entries = self._load()
            if self.retention == "summary":
                self.entries = self._summaries(self.entries)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        make_private_directory(self.path.parent)
        lock = QLockFile(str(self.path) + ".lock")
        lock.setStaleLockTime(30_000)
        if not lock.tryLock(1000):
            raise OSError("History is busy in another application instance")
        previous = list(self.entries)
        try:
            yield
        except OSError:
            self.entries = previous if self.enabled else []
            if self.retention == "summary":
                self.entries = self._summaries(self.entries)
            raise
        finally:
            lock.unlock()

    def _refresh_for_write(self) -> None:
        self.entries = self._load()
        if self.load_warning:
            raise OSError("Damaged history preserved; recover or explicitly clear it before saving")
        if self.retention == "summary":
            self.entries = self._summaries(self.entries)

    def append(
        self,
        result: AnalysisResult,
        source_text: str = "",
        selected_vendor: str = "auto",
        *,
        guard: Callable[[], bool] | None = None,
        title: str = "",
        initial_view: str = "",
        privacy_token: str | None = None,
    ) -> str | None:
        if len(source_text) > 4_000_000:
            raise OSError("History source exceeds per-entry limit")
        with self._transaction():
            self._refresh_privacy()
            if not self.enabled or (privacy_token is not None and privacy_token != self._privacy_revision):
                return None
            self._refresh_for_write()
            if guard is not None and not guard():
                return None
            entry = HistoryEntry.from_result(
                result,
                source_text,
                selected_vendor,
                title=title,
                initial_view=initial_view,
                retention=self.retention,
            )
            self.entries.insert(0, entry)
            del self.entries[self.limit :]
            self._write()
            return entry.entry_id

    def clear(self) -> None:
        with self._transaction():
            try:
                self._refresh_privacy()
            except OSError:
                # Explicit clearing can recover a bad policy without granting
                # source retention or re-enabling a previously unknown policy.
                self.enabled, self.retention = False, "summary"
            self._save_privacy(self.enabled, self.retention)
            self.path.unlink(missing_ok=True)
            self.entries.clear()
            self._loaded_signature = None
            self.load_warning = False

    def remove_ids(self, ids: set[str]) -> None:
        with self._transaction():
            self._refresh_privacy()
            if not self.enabled:
                return
            self._refresh_for_write()
            self.entries = [entry for entry in self.entries if entry.entry_id not in ids]
            self._write()

    def get(self, entry_id: str) -> HistoryEntry | None:
        self.refresh()
        return next((item for item in self.entries if item.entry_id == entry_id), None)

    def _write(self) -> None:
        # The aggregate UTF-8 quota matches the reader, including JSON overhead.
        prefix = b'{"schema_version":2,"entries":['
        encoded: list[bytes] = []
        retained: list[HistoryEntry] = []
        size = len(prefix) + 2
        for entry in self.entries:
            data = json.dumps(asdict(entry), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            additional = len(data) + bool(encoded)
            if size + additional > 64 * 1024 * 1024:
                if not encoded:
                    raise OSError("History entry exceeds aggregate storage limit")
                break
            encoded.append(data)
            retained.append(entry)
            size += additional
        atomic_write_private(self.path, prefix + b",".join(encoded) + b"]}")
        self.entries = retained
        metadata = self.path.stat()
        self._loaded_signature = (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)


class HistoryRole(IntEnum):
    TIMESTAMP = Qt.ItemDataRole.UserRole + 1
    MODE = Qt.ItemDataRole.UserRole + 2
    VENDOR = Qt.ItemDataRole.UserRole + 3
    DIAGNOSTIC_COUNT = Qt.ItemDataRole.UserRole + 4
    SOURCE_LINE_COUNT = Qt.ItemDataRole.UserRole + 5
    SUMMARY = Qt.ItemDataRole.UserRole + 6
    RULE_IDS = Qt.ItemDataRole.UserRole + 7
    ENTRY_ID = Qt.ItemDataRole.UserRole + 8
    TITLE = Qt.ItemDataRole.UserRole + 9
    RESTORABLE = Qt.ItemDataRole.UserRole + 10


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
        HistoryRole.TITLE: b"entryTitle",
        HistoryRole.RESTORABLE: b"restorable",
    }

    def __init__(self, entries: list[HistoryEntry] | None = None) -> None:
        super().__init__()
        self._all_items = list(entries or ())
        self._items = list(self._all_items)
        self._query = ""

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
            HistoryRole.TITLE: item.title,
            HistoryRole.RESTORABLE: bool(item.source_text),
        }
        return values.get(role)

    def replace(self, entries: list[HistoryEntry]) -> None:
        self.beginResetModel()
        self._all_items = list(entries)
        self._items = [e for e in self._all_items if self._query in (e.title + " " + e.vendor).casefold()]
        self.endResetModel()

    def set_filter(self, value: str) -> None:
        self._query = value.strip().casefold()
        self.replace(self._all_items)

    def ids_between(self, first: int, last: int) -> list[str]:
        start, end = sorted((first, last))
        return [item.entry_id for item in self._items[max(0, start) : end + 1]]
