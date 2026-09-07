from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from netconfiglint import analyze
from netconfiglint.core.analyzer import AnalysisResult
from netconfiglint.gui.exporting import render_report
from netconfiglint.gui.i18n import TranslationController
from netconfiglint.gui.models import DiagnosticListModel, HistoryListModel, HistoryStore
from netconfiglint.vendors import registry

Analyzer = Callable[[str, str, str], AnalysisResult]


class AnalysisController(QObject):
    sourceTextChanged = Signal()
    modeChanged = Signal()
    vendorChanged = Signal()
    busyChanged = Signal()
    statusMessageChanged = Signal()
    detectionChanged = Signal()
    summaryChanged = Signal()
    fileNameChanged = Signal()
    historyEnabledChanged = Signal()
    resultCurrentChanged = Signal()
    analysisFinished = Signal()
    analysisFailed = Signal(str)
    jumpToLine = Signal(int, int)
    toastRequested = Signal(str)
    _workerSucceeded = Signal(object)
    _workerFailed = Signal(str)

    def __init__(
        self,
        analyzer: Analyzer = analyze,
        *,
        async_enabled: bool = True,
        history_store: HistoryStore | None = None,
    ) -> None:
        super().__init__()
        self._analyzer = analyzer
        self._async_enabled = async_enabled
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="netconfiglint")
        self._source_text = ""
        self._mode = "full"
        self._vendor = "auto"
        self._busy = False
        self._status_message = ""
        self._file_name = ""
        self._revision = 0
        self._running_revision = -1
        self._result_current = False
        self._export_payload: str | None = None
        self._closing = False
        self.translator = TranslationController(persist_settings=False)
        self._detection: dict[str, Any] = self._empty_detection()
        self._summary: dict[str, int] = {key: 0 for key in ("ERROR", "WARNING", "INFO", "UNKNOWN")}
        self._diagnostics = DiagnosticListModel()
        self._history_store = history_store or HistoryStore()
        self._history_model = HistoryListModel(self._history_store.entries)
        self._workerSucceeded.connect(self._apply_result)
        self._workerFailed.connect(self._apply_error)

    @staticmethod
    def _empty_detection() -> dict[str, Any]:
        return {"vendor": "Unknown"}

    def _invalidate(self) -> None:
        self._revision += 1
        had_result = self._result_current
        self._result_current = False
        self._diagnostics.replace(())
        self._detection = self._empty_detection()
        self._summary = {key: 0 for key in self._summary}
        self.resultCurrentChanged.emit()
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        if not self._source_text.strip():
            self._set_status("")
        elif had_result or self._status_message in {"analysis.failed", "analysis.unsupported"}:
            self._set_status("analysis.changed")

    def _get_result_current(self) -> bool:
        return self._result_current

    resultCurrent = Property(bool, _get_result_current, notify=resultCurrentChanged)

    def _get_vendor_options(self) -> list[dict[str, str]]:
        return [{"value": "auto", "label": "auto"}] + [
            {"value": plugin.key, "label": plugin.vendor_name} for plugin in registry.VENDOR_PLUGINS
        ]

    vendorOptions = Property("QVariantList", _get_vendor_options, constant=True)  # type: ignore[arg-type]

    def _get_source_text(self) -> str:
        return self._source_text

    def _set_source_text(self, value: str) -> None:
        if value != self._source_text:
            self._source_text = value
            self._invalidate()
            self.sourceTextChanged.emit()

    sourceText = Property(str, _get_source_text, _set_source_text, notify=sourceTextChanged)

    def _get_mode(self) -> str:
        return self._mode

    def _set_mode(self, value: str) -> None:
        if value in {"snippet", "full", "snapshot"} and value != self._mode:
            self._mode = value
            self._invalidate()
            self.modeChanged.emit()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)

    def _get_vendor(self) -> str:
        return self._vendor

    def _set_vendor(self, value: str) -> None:
        if value in {"auto", *(p.key for p in registry.VENDOR_PLUGINS)} and value != self._vendor:
            self._vendor = value
            self._invalidate()
            self.vendorChanged.emit()

    vendor = Property(str, _get_vendor, _set_vendor, notify=vendorChanged)

    def _get_busy(self) -> bool:
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_status_message(self) -> str:
        return self._status_message

    statusMessage = Property(str, _get_status_message, notify=statusMessageChanged)

    def _get_file_name(self) -> str:
        return self._file_name

    fileName = Property(str, _get_file_name, notify=fileNameChanged)

    def _get_detection(self) -> dict[str, Any]:
        return self._detection

    detection = Property("QVariantMap", _get_detection, notify=detectionChanged)  # type: ignore[arg-type]

    def _get_summary(self) -> dict[str, int]:
        return self._summary

    summary = Property("QVariantMap", _get_summary, notify=summaryChanged)  # type: ignore[arg-type]

    def _get_diagnostics_model(self) -> QObject:
        return self._diagnostics

    diagnosticsModel = Property(QObject, _get_diagnostics_model, constant=True)

    def _get_history_model(self) -> QObject:
        return self._history_model

    historyModel = Property(QObject, _get_history_model, constant=True)

    def _get_history_enabled(self) -> bool:
        return self._history_store.enabled

    def _set_history_enabled(self, value: bool) -> None:
        if value != self._history_store.enabled:
            self._history_store.set_enabled(value)
            self.historyEnabledChanged.emit()

    historyEnabled = Property(bool, _get_history_enabled, _set_history_enabled, notify=historyEnabledChanged)

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _set_status(self, value: str) -> None:
        if value != self._status_message:
            self._status_message = value
            self.statusMessageChanged.emit()

    @Slot()
    def clear(self) -> None:
        if self._busy:
            return
        self._set_source_text("")
        self._diagnostics.replace(())
        self._detection = self._empty_detection()
        self._summary = {key: 0 for key in self._summary}
        self._file_name = ""
        self.fileNameChanged.emit()
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        self._set_status("")

    @Slot(str)
    def loadFile(self, value: str) -> None:
        try:
            path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
            self._set_source_text(path.read_text(encoding="utf-8-sig"))
            self._file_name = path.name
            self.fileNameChanged.emit()
        except (OSError, UnicodeError):
            self.toastRequested.emit("file.open_error")

    @Slot(str, str, bool, result=bool)
    def prepareExport(self, scope: str, format: str, diagnostics_first: bool) -> bool:
        self._export_payload = None
        if not self._source_text.strip() or (scope != "configuration" and not self._result_current):
            return False
        try:
            items = self._diagnostics.items
            self._export_payload = render_report(
                self._source_text,
                items,
                scope=scope,
                format=format,
                diagnostics_first=diagnostics_first,
                mode=self._mode,
                vendor=self._detection["vendor"],
                text=self.translator.text,
                translate=self.translator.diagnostic,
            )
        except ValueError:
            return False
        return True

    @Slot()
    def cancelExport(self) -> None:
        self._export_payload = None

    @Slot(str)
    def exportReport(self, value: str) -> None:
        if self._export_payload is None:
            return
        try:
            path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
            path.write_text(self._export_payload, encoding="utf-8", newline="")
            self.toastRequested.emit("export.saved")
        except OSError:
            self.toastRequested.emit("export.error")
        finally:
            self.cancelExport()

    @Slot()
    def analyzeConfig(self) -> None:
        if self._busy:
            return
        if not self._source_text.strip():
            return
        self._running_revision = self._revision
        self._set_busy(True)
        self._set_status("analysis.running")
        if not self._async_enabled:
            self._run_synchronously()
            return
        future = self._executor.submit(self._analyzer, self._source_text, self._mode, self._vendor)
        future.add_done_callback(self._worker_done)

    def _run_synchronously(self) -> None:
        try:
            self._apply_result(self._analyzer(self._source_text, self._mode, self._vendor))
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._apply_error(str(exc))

    def _worker_done(self, future: Future[AnalysisResult]) -> None:
        if self._closing:
            return
        try:
            self._workerSucceeded.emit(future.result())
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._workerFailed.emit(str(exc))

    @Slot(object)
    def _apply_result(self, result: object) -> None:
        if not isinstance(result, AnalysisResult):
            self._apply_error("invalid_result")
            return
        if self._running_revision != self._revision:
            self._set_busy(False)
            self._set_status("analysis.changed" if self._source_text.strip() else "")
            return
        self._diagnostics.replace(result.diagnostics)
        self._detection = {"vendor": result.detection.vendor}
        self._result_current = True
        self.resultCurrentChanged.emit()
        counts = Counter(item.severity.value for item in result.diagnostics)
        self._summary = {key: counts[key] for key in self._summary}
        try:
            self._history_store.append(result)
            self._history_model.replace(self._history_store.entries)
        except OSError:
            self.toastRequested.emit("history.write_error")
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        self._set_busy(False)
        self._set_status("analysis.completed")
        self.analysisFinished.emit()

    @Slot(str)
    def _apply_error(self, message: str) -> None:
        self._set_busy(False)
        if self._running_revision != self._revision:
            self._set_status("analysis.changed" if self._source_text.strip() else "")
            return
        self._invalidate()
        key = (
            "analysis.unsupported"
            if "Could not identify a supported vendor" in message
            else "analysis.failed"
        )
        self._set_status(key)
        self.analysisFailed.emit(key)

    @Slot(int)
    def requestJump(self, row: int) -> None:
        item = self._diagnostics.item_at(row)
        if item is not None:
            self.jumpToLine.emit(item.source.line, item.source.end_line or item.source.line)

    @Slot()
    def clearHistory(self) -> None:
        try:
            self._history_store.clear()
            self._history_model.replace([])
            self.toastRequested.emit("history.cleared")
        except OSError:
            self.toastRequested.emit("history.clear_error")

    def close(self) -> None:
        self._closing = True
        self._executor.shutdown(wait=False, cancel_futures=True)
