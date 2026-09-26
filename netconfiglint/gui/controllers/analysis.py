from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from netconfiglint import analyze
from netconfiglint.core.analyzer import AnalysisResult
from netconfiglint.core.analyzer.control import (
    AnalysisCancelled,
    AnalysisLimitReached,
    AnalysisLimits,
    CancellationToken,
)
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.input import read_network_text
from netconfiglint.gui.exporting import render_report
from netconfiglint.gui.i18n import TranslationController
from netconfiglint.gui.models import DiagnosticListModel, HistoryListModel, HistoryStore
from netconfiglint.gui.models.history import default_temporary_path, local_timestamp
from netconfiglint.vendors import registry
from netconfiglint.vendors.h3c.parser.diagnostic_bundle import extract_h3c_diagnostic_bundle

Analyzer = Callable[[str, str, str], AnalysisResult]


class AnalysisController(QObject):
    sourceTextChanged = Signal()
    editorTextChanged = Signal()
    editorReadOnlyChanged = Signal()
    modeChanged = Signal()
    vendorChanged = Signal()
    busyChanged = Signal()
    statusMessageChanged = Signal()
    detectionChanged = Signal()
    summaryChanged = Signal()
    fileNameChanged = Signal()
    historyEnabledChanged = Signal()
    temporaryTextChanged = Signal()
    resultTimestampChanged = Signal()
    historyOpened = Signal()
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
        self._editor_text = ""
        self._editor_read_only = False
        self._display_line_map: dict[int, int] = {}
        self._bundle_configuration = ""
        self._mode = "snippet"
        self._vendor = "auto"
        self._busy = False
        self._status_message = ""
        self._file_name = ""
        self._revision = 0
        self._running_revision = -1
        self._result_current = False
        self._export_payload: str | None = None
        self._closing = False
        self._cancellation = CancellationToken()
        self._coverage: dict[str, Any] = {}
        self._input_metadata: dict[str, Any] = {}
        self.translator = TranslationController(persist_settings=False)
        self._detection: dict[str, Any] = self._empty_detection()
        self._summary: dict[str, int] = {key: 0 for key in ("ERROR", "WARNING", "INFO", "UNKNOWN")}
        self._diagnostics = DiagnosticListModel()
        self._history_store = history_store or HistoryStore()
        self._history_model = HistoryListModel(self._history_store.entries)
        self._active_history_id: str | None = None
        history_parent = self._history_store.path.parent
        storage_root = history_parent.parent if history_parent.name == "history" else history_parent
        self._temporary_path = (
            storage_root / "temporary" / "editor.txt"
            if history_store is not None
            else default_temporary_path()
        )
        try:
            with self._temporary_path.open("rb") as saved:
                contents = saved.read(4_000_001)
            self._temporary_text = (
                contents.decode("utf-8").replace("\r\n", "\n") if len(contents) <= 4_000_000 else ""
            )
        except (OSError, UnicodeError):
            self._temporary_text = ""
        self._result_timestamp = ""
        self._workerSucceeded.connect(self._apply_result)
        self._workerFailed.connect(self._apply_error)

    @staticmethod
    def _empty_detection() -> dict[str, Any]:
        return {"vendor": "Unknown"}

    def _invalidate(self) -> None:
        self._cancellation.cancel()
        self._coverage = {}
        self._revision += 1
        had_result = self._result_current
        self._result_current = False
        self._set_result_timestamp("")
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

    def _get_temporary_text(self) -> str:
        return self._temporary_text

    temporaryText = Property(str, _get_temporary_text, notify=temporaryTextChanged)

    @Slot(str)
    def saveTemporaryText(self, value: str) -> None:
        if len(value) > 4_000_000:
            self.toastRequested.emit("temporary.save_error")
            return
        try:
            self._temporary_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._temporary_path.with_suffix(".tmp")
            temporary.write_text(value, encoding="utf-8", newline="")
            temporary.replace(self._temporary_path)
        except OSError:
            self.toastRequested.emit("temporary.save_error")
            return
        self._temporary_text = value
        self.temporaryTextChanged.emit()
        self.toastRequested.emit("temporary.saved")

    def _get_result_timestamp(self) -> str:
        return self._result_timestamp

    resultTimestamp = Property(str, _get_result_timestamp, notify=resultTimestampChanged)

    def _set_result_timestamp(self, value: str) -> None:
        if value != self._result_timestamp:
            self._result_timestamp = value
            self.resultTimestampChanged.emit()

    def _get_coverage(self) -> dict[str, Any]:
        return self._coverage

    coverage = Property("QVariantMap", _get_coverage, notify=resultCurrentChanged)  # type: ignore[arg-type]

    def _get_vendor_options(self) -> list[dict[str, str]]:
        return [{"value": "auto", "label": "auto"}] + [
            {"value": plugin.key, "label": plugin.vendor_name} for plugin in registry.VENDOR_PLUGINS
        ]

    vendorOptions = Property("QVariantList", _get_vendor_options, constant=True)  # type: ignore[arg-type]

    def _get_source_text(self) -> str:
        return self._source_text

    def _set_source_text(self, value: str) -> None:
        if value != self._source_text:
            self._active_history_id = None
            self._source_text = value
            self._set_editor_text(value, read_only=False)
            self._bundle_configuration = ""
            self._input_metadata = {}
            self._invalidate()
            self.sourceTextChanged.emit()

    sourceText = Property(str, _get_source_text, _set_source_text, notify=sourceTextChanged)

    def _set_editor_text(
        self, value: str, *, read_only: bool, line_map: dict[int, int] | None = None
    ) -> None:
        if read_only != self._editor_read_only:
            self._editor_read_only = read_only
            self.editorReadOnlyChanged.emit()
        if value != self._editor_text:
            self._editor_text = value
            self.editorTextChanged.emit()
        self._display_line_map = line_map or {}

    def _get_editor_text(self) -> str:
        return self._editor_text

    editorText = Property(str, _get_editor_text, notify=editorTextChanged)

    def _get_editor_read_only(self) -> bool:
        return self._editor_read_only

    editorReadOnly = Property(bool, _get_editor_read_only, notify=editorReadOnlyChanged)

    def _get_mode(self) -> str:
        return self._mode

    def _set_mode(self, value: str) -> None:
        if value in {"snippet", "message", "view", "full", "snapshot"} and value != self._mode:
            self._active_history_id = None
            self._mode = value
            self._invalidate()
            self.modeChanged.emit()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)

    def _get_vendor(self) -> str:
        return self._vendor

    def _set_vendor(self, value: str) -> None:
        if value in {"auto", *(p.key for p in registry.VENDOR_PLUGINS)} and value != self._vendor:
            self._active_history_id = None
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
            try:
                self._history_store.set_enabled(value)
            except OSError:
                self.toastRequested.emit("history.clear_error")
                return
            self._history_model.replace(self._history_store.entries)
            if not value:
                self._active_history_id = None
            self.historyEnabledChanged.emit()

    historyEnabled = Property(bool, _get_history_enabled, _set_history_enabled, notify=historyEnabledChanged)

    def _get_history_warning(self) -> bool:
        return self._history_store.load_warning

    historyLoadWarning = Property(bool, _get_history_warning, notify=historyEnabledChanged)

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
        self._active_history_id = None
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
            decoded = read_network_text(path, AnalysisLimits())
            bundle = extract_h3c_diagnostic_bundle(decoded.text)
            if bundle is None:
                self._set_source_text(decoded.text)
            else:
                self._source_text = decoded.text
                self._invalidate()
                self.sourceTextChanged.emit()
                lines = decoded.text.splitlines()
                selected = sorted(bundle.analysis_lines)
                preview = "\n".join(lines[number - 1] for number in selected)
                if preview and decoded.text.endswith("\n"):
                    preview += "\n"
                self._set_editor_text(
                    preview,
                    read_only=True,
                    line_map={source_line: index for index, source_line in enumerate(selected, 1)},
                )
                self._bundle_configuration = preview
            self._input_metadata = {
                "encoding": decoded.encoding,
                "newline_style": decoded.newline_style,
                "recovered_bytes": decoded.recovered_bytes,
            }
            self._file_name = path.name
            self.fileNameChanged.emit()
            if decoded.recovered:
                self.toastRequested.emit("file.encoding_recovered")
            if bundle is not None:
                self.toastRequested.emit("file.bundle_preview")
        except (OSError, UnicodeError, AnalysisLimitReached):
            self.toastRequested.emit("file.open_error")

    @Slot(str, str, bool, result=bool)
    def prepareExport(self, scope: str, format: str, diagnostics_first: bool) -> bool:
        self._export_payload = None
        if not self._source_text.strip() or (scope != "configuration" and not self._result_current):
            return False
        try:
            items = self._diagnostics.items
            self._export_payload = render_report(
                self._bundle_configuration
                if scope == "configuration" and self._bundle_configuration
                else self._source_text,
                items,
                scope=scope,
                format=format,
                diagnostics_first=diagnostics_first,
                mode=self._mode,
                vendor=self._detection["vendor"],
                text=self.translator.text,
                translate=self.translator.diagnostic,
                coverage=self._coverage,
                input_metadata=self._input_metadata,
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
        self._cancellation = CancellationToken()
        self._set_busy(True)
        self._set_status("analysis.running")
        if not self._async_enabled:
            self._run_synchronously()
            return
        future = self._executor.submit(
            self._analyze_input, self._source_text, self._mode, self._vendor, self._cancellation
        )
        future.add_done_callback(self._worker_done)

    def _run_synchronously(self) -> None:
        try:
            self._apply_result(
                self._analyze_input(self._source_text, self._mode, self._vendor, self._cancellation)
            )
        except AnalysisCancelled:
            self._apply_error("cancelled")
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._apply_error(str(exc))

    def _worker_done(self, future: Future[AnalysisResult]) -> None:
        if self._closing:
            return
        try:
            self._workerSucceeded.emit(future.result())
        except AnalysisCancelled:
            self._workerFailed.emit("cancelled")
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._workerFailed.emit(str(exc))

    def _analyze_input(
        self, source: str, mode: str, vendor: str, cancellation: CancellationToken
    ) -> AnalysisResult:
        if self._analyzer is analyze:
            return analyze(source, mode, vendor, cancellation=cancellation)
        # Third-party injected analyzers retain their existing three-argument contract.
        if cancellation.cancelled:
            raise AnalysisCancelled()
        result = self._analyzer(source, mode, vendor)
        if cancellation.cancelled:
            raise AnalysisCancelled()
        return result

    @Slot()
    def cancelAnalysis(self) -> None:
        self._cancellation.cancel()

    @Slot(object)
    def _apply_result(self, result: object) -> None:
        if self._busy and self._cancellation.cancelled:
            self._apply_error("cancelled")
            return
        if not isinstance(result, AnalysisResult):
            self._apply_error("invalid_result")
            return
        if self._running_revision != self._revision:
            self._set_busy(False)
            self._set_status("analysis.changed" if self._source_text.strip() else "")
            return
        self._diagnostics.replace(result.diagnostics)
        self._coverage = result.coverage
        self._detection = {"vendor": result.detection.vendor}
        self._result_current = True
        self._extend_bundle_preview(result)
        self.resultCurrentChanged.emit()
        counts = Counter(item.severity.value for item in result.diagnostics)
        self._summary = {key: counts[key] for key in self._summary}
        try:
            if self._active_history_id is None:
                self._history_store.append(result, self._source_text, self._vendor)
                if self._history_store.enabled and self._history_store.entries:
                    self._active_history_id = self._history_store.entries[0].entry_id
            active_entry = (
                self._history_store.get(self._active_history_id) if self._active_history_id else None
            )
            self._set_result_timestamp(
                local_timestamp(active_entry.timestamp)
                if active_entry
                else datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            )
            self._history_model.replace(self._history_store.entries)
        except OSError:
            self._set_result_timestamp(datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"))
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
        if message == "cancelled":
            self._set_status("analysis.cancelled")
            return
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
            start = self._display_line_map.get(item.source.line, item.source.line)
            source_end = item.source.end_line or item.source.line
            end = self._display_line_map.get(source_end, start)
            self.jumpToLine.emit(start, end)

    def _extend_bundle_preview(self, result: AnalysisResult) -> None:
        if not self._editor_read_only or not result.config.analysis_lines:
            return
        source_lines = result.config.source_lines
        selected = sorted(result.config.analysis_lines)
        preview = [source_lines[number - 1] for number in selected]
        line_map = {source_line: index for index, source_line in enumerate(selected, 1)}
        evidence_lines = sorted(
            {
                item.source.line
                for item in result.diagnostics
                if item.source.line not in result.config.analysis_lines
                and 1 <= item.source.line <= len(source_lines)
            }
        )
        for source_line in evidence_lines:
            start = max(1, source_line - 1)
            end = min(len(source_lines), source_line + 1)
            preview.extend(("", f"===== Source lines {start}-{end} ====="))
            for number in range(start, end + 1):
                if number == source_line:
                    line_map[number] = len(preview) + 1
                preview.append(source_lines[number - 1])
        self._set_editor_text("\n".join(preview) + "\n", read_only=True, line_map=line_map)

    @Slot()
    def clearHistory(self) -> None:
        try:
            self._history_store.clear()
            self._active_history_id = None
            self._history_model.replace([])
            self.historyEnabledChanged.emit()
            self.toastRequested.emit("history.cleared")
        except OSError:
            self.toastRequested.emit("history.clear_error")

    @Slot(str)
    def openHistory(self, entry_id: str) -> None:
        entry = self._history_store.get(entry_id)
        if entry is None or not entry.source_text or self._busy:
            return
        try:
            restored = tuple(
                Diagnostic(
                    Severity(item["severity"]),
                    str(item["rule_id"]),
                    SourceRange(**item["source"]),
                    str(item["object_name"]),
                    str(item["message"]),
                    str(item["explanation"]),
                    str(item["suggested_fix"]),
                    Confidence(item["confidence"]),
                )
                for item in entry.diagnostics
            )
        except (KeyError, TypeError, ValueError):
            self.toastRequested.emit("history.recovery_warning")
            return
        self._source_text = entry.source_text
        self._set_editor_text(entry.source_text, read_only=False)
        self._invalidate()
        self._mode = entry.mode
        self._vendor = entry.selected_vendor
        self._diagnostics.replace(restored)
        self._coverage = dict(entry.coverage or {})
        self._summary = dict(entry.summary)
        self._detection = {"vendor": entry.vendor}
        self._result_current = True
        self._active_history_id = entry_id
        self._set_result_timestamp(local_timestamp(entry.timestamp))
        self._set_status("analysis.completed")
        for signal in (
            self.sourceTextChanged,
            self.modeChanged,
            self.vendorChanged,
            self.resultCurrentChanged,
            self.detectionChanged,
            self.summaryChanged,
        ):
            signal.emit()
        self.historyOpened.emit()

    @Slot(str)
    def removeHistory(self, entry_id: str) -> None:
        self.removeHistories([entry_id])

    @Slot(int, int, result="QVariantList")
    def historyIdsBetween(self, first: int, last: int) -> list[str]:
        return self._history_model.ids_between(first, last)

    @Slot("QVariantList")
    def removeHistories(self, entry_ids: list[str]) -> None:
        try:
            self._history_store.remove_ids(set(entry_ids))
            self._history_model.replace(self._history_store.entries)
            if self._active_history_id in entry_ids:
                self._active_history_id = None
        except OSError:
            self.toastRequested.emit("history.clear_error")

    def close(self) -> None:
        self._closing = True
        self._cancellation.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
