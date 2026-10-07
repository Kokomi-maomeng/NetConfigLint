"""Qt completion bridge; persists only the chosen vendor keys."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from threading import Event, Lock
from typing import Any

from PySide6.QtCore import Property, QObject, QSettings, QTimer, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtQuick import QQuickTextDocument

from netconfiglint.commands.completion import (
    VENDORS,
    CompletionCancelled,
    complete,
    interactive_requires_async,
)


@dataclass(frozen=True)
class _CompletionTask:
    owner: str
    serial: int
    kind: str
    source: str
    cursor: int
    vendors: tuple[str, ...]
    key: str
    cancelled: Event


class _CompletionState:
    """Pure Python worker state: it must never retain a QObject or bound signal."""

    def __init__(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="command-query")
        self.jobs: dict[tuple[str, str], tuple[int, Event]] = {}
        self.results: SimpleQueue[tuple[str, int, str, dict[str, Any]]] = SimpleQueue()
        self._pending = 0
        self._pending_lock = Lock()

    def count_pending(self, change: int = 0) -> int:
        with self._pending_lock:
            self._pending += change
            return self._pending

    def close(self) -> None:
        for _, cancelled in self.jobs.values():
            cancelled.set()
        self.pool.shutdown(wait=False, cancel_futures=True)


def _run_completion(task: _CompletionTask, state: _CompletionState) -> None:
    """Run without any Qt wrappers, including signal objects, on this thread."""
    try:
        try:
            result: dict[str, Any] = complete(
                task.source,
                task.cursor,
                task.vendors,
                include_details=task.kind == "detail",
                detail_key=task.key,
                cancelled=task.cancelled.is_set,
            )
            if task.kind == "detail":
                result = next(
                    (
                        row
                        for row in [*result["items"], *result["argumentDetails"]]
                        if row.get("detailKey") == task.key
                    ),
                    {},
                )
        except CompletionCancelled:
            return
        except Exception:
            result = {"error": True, "items": [], "arguments": []}
        if not task.cancelled.is_set():
            state.results.put((task.owner, task.serial, task.kind, result))
    finally:
        state.count_pending(-1)


class CommandCompletion(QObject):
    changed = Signal()
    queryReady = Signal(str, int, dict)
    detailReady = Signal(str, int, dict)

    def __init__(self, parent: QObject | None = None, *, persist: bool = True) -> None:
        super().__init__(parent)
        self._persist = persist
        saved = QSettings().value("completion/vendors", []) if persist else []
        self._vendors = [key for key in VENDORS if isinstance(saved, list) and key in saved]
        self._state = _CompletionState()
        self._jobs = self._state.jobs
        self._detail_cache: dict[str, dict[str, Any]] = {}
        self._serial = 0
        self._poll = QTimer(self)
        self._poll.setInterval(15)
        self._poll.timeout.connect(self._drain)
        # The callback retains pure Python state, rather than a lambda retaining
        # this QObject. Workers can release their last references on any thread.
        self.destroyed.connect(self._state.close)

    @Slot()
    def _drain(self) -> None:
        while True:
            try:
                result = self._state.results.get_nowait()
            except Empty:
                break
            self._deliver(*result)
        if not self._jobs and not self._state.count_pending():
            self._poll.stop()

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
        return complete(source, cursor, tuple(self._vendors), include_details=False)

    @Slot(str, str, int, result="QVariantMap")
    def requestInteractive(self, owner: str, source: str, cursor: int) -> dict[str, Any]:
        self.cancelQuery(owner)
        if interactive_requires_async(source, cursor):
            return {"pending": True, "requestId": self.queryAsync(owner, source, cursor)}
        return self.request(source, cursor)

    def _start(self, owner: str, source: str, cursor: int, kind: str, key: str = "") -> int:
        self._cancel(owner, kind)
        self._serial += 1
        serial, cancelled = self._serial, Event()
        self._jobs[(owner, kind)] = (serial, cancelled)
        task = _CompletionTask(owner, serial, kind, source, cursor, tuple(self._vendors), key, cancelled)
        self._state.count_pending(1)
        self._state.pool.submit(_run_completion, task, self._state)
        self._poll.start()
        return serial

    @Slot(str, str, int, result=int)
    def queryAsync(self, owner: str, source: str, cursor: int) -> int:
        return self._start(owner, source, cursor, "query")

    @Slot(str, str, int, str, result=int)
    def requestDetails(self, owner: str, source: str, cursor: int, key: str) -> int:
        self._detail_cache.pop(owner, None)
        return self._start(owner, source, cursor, "detail", key)

    def _cancel(self, owner: str, kind: str) -> None:
        previous = self._jobs.pop((owner, kind), None)
        if previous:
            previous[1].set()

    @Slot(str)
    def cancelQuery(self, owner: str) -> None:
        self._cancel(owner, "query")

    @Slot(str)
    def cancelDetails(self, owner: str) -> None:
        self._cancel(owner, "detail")
        self._detail_cache.pop(owner, None)

    @Slot(str, int, str, object)
    def _deliver(self, owner: str, serial: int, kind: str, result: dict[str, Any]) -> None:
        current = self._jobs.get((owner, kind))
        if current is None or current[0] != serial or current[1].is_set():
            return
        self._jobs.pop((owner, kind), None)
        if kind == "query":
            self.queryReady.emit(owner, serial, result)
        else:
            self._detail_cache[owner] = result
            self.detailReady.emit(owner, serial, self.detailPage(owner, "", 0))

    @Slot(str, str, int, result="QVariantMap")
    def detailPage(self, owner: str, query: str, page: int) -> dict[str, Any]:
        """Only a bounded page crosses into QML, including when filtering all rows."""
        detail = self._detail_cache.get(owner, {})
        rows = detail.get("syntaxDetails", [])
        if not rows:
            rows = [
                {
                    "syntax": syntax,
                    "sources": detail.get("sources", []),
                    "views": detail.get("views", []),
                    "scopes": detail.get("scopes", []),
                    "annotations": detail.get("annotations", []),
                }
                for syntax in detail.get("syntaxes", [])
            ]
        if query.strip():
            needle = query.casefold().strip()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    [
                        row["syntax"],
                        *row.get("sources", []),
                        *row.get("views", []),
                        *row.get("scopes", []),
                        *row.get("annotations", []),
                    ]
                ).casefold()
            ]
        page_size = 40
        pages = max(1, (len(rows) + page_size - 1) // page_size)
        safe_page = max(0, min(page, pages - 1))
        # Avoid transferring the unbounded syntaxes/sourceDetails arrays as header.
        header = {
            key: detail.get(key, "" if key in {"text", "token", "description", "status"} else [])
            for key in ("text", "token", "description", "status", "vendors", "aliases")
        }
        visible_rows = rows[safe_page * page_size : (safe_page + 1) * page_size]
        header.update(
            rows=visible_rows,
            syntaxDetails=visible_rows,
            syntaxes=list(dict.fromkeys(row["syntax"] for row in visible_rows)),
            sources=list(dict.fromkeys(url for row in visible_rows for url in row.get("sources", []))),
            views=list(dict.fromkeys(view for row in visible_rows for view in row.get("views", []))),
            total=len(rows),
            page=safe_page,
            pages=pages,
            error=detail.get("error", False),
        )
        return header

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
