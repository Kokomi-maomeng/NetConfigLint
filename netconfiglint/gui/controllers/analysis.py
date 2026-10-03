from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
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
from netconfiglint.core.input import DecodedNetworkText, read_network_text
from netconfiglint.gui.exporting import render_report
from netconfiglint.gui.i18n import TranslationController
from netconfiglint.gui.models import DiagnosticListModel, HistoryListModel, HistoryStore
from netconfiglint.gui.models.history import HistoryEntry, default_temporary_path, local_timestamp
from netconfiglint.vendors import registry

Analyzer = Callable[[str, str, str], AnalysisResult]


@dataclass(frozen=True)
class _LoadedInput:
    path: Path
    decoded: DecodedNetworkText
    preview: tuple[str, dict[int, int]] | None
    revision: int


@dataclass(frozen=True)
class _CompletedAnalysis:
    result: AnalysisResult
    entries: list[HistoryEntry] | None
    history_error: bool
    history_epoch: int


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
    _fileLoaded = Signal(object)
    _fileFailed = Signal(int, str)
    workspaceChanged = Signal()
    unsavedRequested = Signal()
    saveAsRequested = Signal(str)
    closeApproved = Signal()

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
        self._file_path: Path | None = None
        self._saved_source = ""
        self._source_identity = "new"
        self._initial_view = ""
        self._running_initial_view = ""
        self._pending_action: tuple[str, str] | None = None
        self._pending_save_scopes: list[str] = []
        self._example_snapshot: tuple[str, str, str, Path | None, str, str, str, str] | None = None
        self._revision = 0
        self._loading = False
        self._load_revision = -1
        self._history_epoch = 0
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
                contents = saved.read(16_000_001)
            self._temporary_text = (
                contents.decode("utf-8").replace("\r\n", "\n") if len(contents) <= 16_000_000 else ""
            )
        except (OSError, UnicodeError):
            self._temporary_text = ""
        self._saved_temporary = self._temporary_text
        self._result_timestamp = ""
        self._fileLoaded.connect(self._apply_loaded_input)
        self._fileFailed.connect(self._apply_file_error)
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
        self.workspaceChanged.emit()
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
        self._saved_temporary = value
        self.workspaceChanged.emit()
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
            self.workspaceChanged.emit()

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
            self._history_epoch += 1
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
        self._file_path = None
        self._saved_source = ""
        self._source_identity = "new"
        self.workspaceChanged.emit()
        self.fileNameChanged.emit()
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        self._set_status("")

    @staticmethod
    def _read_input_file(path: Path, revision: int) -> _LoadedInput:
        decoded = read_network_text(path, AnalysisLimits())
        return _LoadedInput(path, decoded, registry.extract_configuration_preview(decoded.text), revision)

    @Slot(str)
    def loadFile(self, value: str) -> None:
        path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
        if not self._async_enabled:
            try:
                self._apply_loaded_input(self._read_input_file(path, self._revision))
            except (OSError, UnicodeError, ValueError, AnalysisLimitReached) as error:
                self.toastRequested.emit(self._input_error_key(error))
            return
        self._revision += 1
        self._loading = True
        self._set_busy(True)
        revision = self._revision
        self._load_revision = revision
        future = self._executor.submit(self._read_input_file, path, revision)
        future.add_done_callback(lambda item: self._file_done(item, revision))

    def _file_done(self, future: Future[_LoadedInput], revision: int) -> None:
        if self._closing:
            return
        try:
            self._fileLoaded.emit(future.result())
        except Exception as error:  # Input boundary: never log source paths or values.
            self._fileFailed.emit(revision, self._input_error_key(error))

    @Slot(int, str)
    def _apply_file_error(self, revision: int, key: str = "file.open_error") -> None:
        if revision != self._load_revision:
            return
        if revision != self._revision:
            if self._loading:
                self._loading = False
                self._set_busy(False)
            return
        self._loading = False
        self._set_busy(False)
        self.toastRequested.emit(key)

    @Slot(object)
    def _apply_loaded_input(self, item: object) -> None:
        if isinstance(item, _LoadedInput) and self._async_enabled and item.revision != self._load_revision:
            return
        if not isinstance(item, _LoadedInput) or item.revision != self._revision:
            self._loading = False
            self._set_busy(False)
            return
        decoded, preview = item.decoded, item.preview
        self._active_history_id = None
        if preview is None:
            self._set_source_text(decoded.text)
        else:
            self._source_text = decoded.text
            self._invalidate()
            self.sourceTextChanged.emit()
            self._set_editor_text(preview[0], read_only=True, line_map=preview[1])
            self._bundle_configuration = preview[0]
        self._input_metadata = {
            "encoding": decoded.encoding,
            "newline_style": decoded.newline_style,
            "recovered_bytes": decoded.recovered_bytes,
        }
        self._file_name = item.path.name
        self._file_path = item.path
        self._saved_source = self._source_text
        self._source_identity = "file"
        self.workspaceChanged.emit()
        self._loading = False
        self._set_busy(False)
        self.fileNameChanged.emit()
        if decoded.recovered:
            self.toastRequested.emit("file.encoding_recovered")
        if preview is not None:
            self.toastRequested.emit("file.bundle_preview")

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
        self._running_initial_view = self._initial_view if self._mode == "snippet" else ""
        self._cancellation = CancellationToken()
        self._set_busy(True)
        self._set_status("analysis.running")
        if not self._async_enabled:
            self._run_synchronously()
            return
        future = self._executor.submit(
            self._analyze_and_persist,
            self._source_text,
            self._mode,
            self._vendor,
            self._cancellation,
            self._active_history_id,
            self._history_epoch,
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

    def _worker_done(self, future: Future[_CompletedAnalysis]) -> None:
        if self._closing:
            return
        try:
            self._workerSucceeded.emit(future.result())
        except AnalysisCancelled:
            self._workerFailed.emit("cancelled")
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._workerFailed.emit(str(exc))

    def _analyze_and_persist(
        self,
        source: str,
        mode: str,
        vendor: str,
        cancellation: CancellationToken,
        active_history_id: str | None,
        epoch: int,
    ) -> _CompletedAnalysis:
        result = self._analyze_input(source, mode, vendor, cancellation)
        if cancellation.cancelled:
            raise AnalysisCancelled()
        entries = None
        error = False
        if self._history_store.enabled and active_history_id is None:
            store = HistoryStore(
                self._history_store.path,
                enabled=True,
                persist_settings=False,
                limit=self._history_store.limit,
                retention=self._history_store.retention,
            )
            try:
                store.append(
                    result,
                    source,
                    vendor,
                    title=self._file_name,
                    initial_view=self._running_initial_view,
                    guard=lambda: epoch == self._history_epoch and not cancellation.cancelled,
                )
                entries = list(store.entries)
            except OSError:
                error = True
        return _CompletedAnalysis(result, entries, error, epoch)

    def _analyze_input(
        self, source: str, mode: str, vendor: str, cancellation: CancellationToken
    ) -> AnalysisResult:
        if self._analyzer is analyze:
            return analyze(
                source,
                mode,
                vendor,
                cancellation=cancellation,
                initial_view=self._running_initial_view or None,
            )
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
        completed = result if isinstance(result, _CompletedAnalysis) else None
        if completed is not None:
            result = completed.result
        if self._loading:
            return
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
        if self._running_initial_view:
            self._input_metadata["initial_view"] = self._running_initial_view
        else:
            self._input_metadata.pop("initial_view", None)
        self._detection = {"vendor": result.detection.vendor}
        self._result_current = True
        self._extend_bundle_preview(result)
        self.resultCurrentChanged.emit()
        self.workspaceChanged.emit()
        counts = Counter(item.severity.value for item in result.diagnostics)
        self._summary = {key: counts[key] for key in self._summary}
        try:
            if completed is not None:
                if completed.history_error:
                    raise OSError("Background history write failed")
                if completed.entries is not None and completed.history_epoch == self._history_epoch:
                    self._history_store.entries = completed.entries
                    if completed.entries:
                        self._active_history_id = completed.entries[0].entry_id
            elif self._active_history_id is None:
                self._history_store.append(
                    result,
                    self._source_text,
                    self._vendor,
                    title=self._file_name,
                    initial_view=self._running_initial_view,
                )
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
        if self._loading:
            return
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
        self._history_epoch += 1
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
        if entry is not None and not entry.source_text:
            self.toastRequested.emit("history.summary_only")
            return
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
        self._set_source_text(entry.source_text)
        self._bundle_configuration = ""
        self._input_metadata = {"initial_view": entry.initial_view} if entry.initial_view else {}
        self._file_name = entry.title
        self._file_path = None
        self._saved_source = ""
        self._source_identity = "history"
        self._initial_view = entry.initial_view
        self.workspaceChanged.emit()
        self.fileNameChanged.emit()
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
        self._history_epoch += 1
        try:
            self._history_store.remove_ids(set(entry_ids))
            self._history_model.replace(self._history_store.entries)
            if self._active_history_id in entry_ids:
                self._active_history_id = None
        except OSError:
            self.toastRequested.emit("history.clear_error")

    @staticmethod
    def _input_error_key(error: Exception) -> str:
        if isinstance(error, AnalysisLimitReached):
            return "file.limit_error"
        if isinstance(error, OSError):
            return "file.access_error"
        if isinstance(error, UnicodeError) or "UTF-32" in str(error):
            return "file.encoding_error"
        return "file.binary_error"

    sourceDirty = Property(
        bool, lambda self: self._source_text != self._saved_source, notify=workspaceChanged
    )
    temporaryDirty = Property(
        bool, lambda self: self._temporary_text != self._saved_temporary, notify=workspaceChanged
    )
    filePath = Property(str, lambda self: str(self._file_path or ""), notify=workspaceChanged)
    sourceIdentity = Property(str, lambda self: self._source_identity, notify=workspaceChanged)
    temporaryPath = Property(str, lambda self: str(self._temporary_path), constant=True)
    historyPath = Property(str, lambda self: str(self._history_store.path), constant=True)

    @Slot(str)
    def updateTemporaryText(self, value: str) -> None:
        if self._temporary_text != value:
            self._temporary_text = value
            self.workspaceChanged.emit()

    def _set_initial_view(self, value: str) -> None:
        if value != self._initial_view and len(value) <= 160 and "\n" not in value:
            self._initial_view = value.strip()
            self._active_history_id = None
            self._invalidate()
            self.workspaceChanged.emit()

    initialView = Property(str, lambda self: self._initial_view, _set_initial_view, notify=workspaceChanged)

    def _markers(self) -> list[dict[str, Any]]:
        if not self._result_current:
            return []
        return [
            {
                "line": self._display_line_map.get(d.source.line, d.source.line),
                "end_line": self._display_line_map.get(
                    d.source.end_line or d.source.line, d.source.end_line or d.source.line
                ),
                "column": d.source.column,
                "end_column": d.source.end_column,
                "severity": d.severity.value,
                "confidence": d.confidence.value,
                "message": self.translator.diagnostic(d.message),
                "rule_id": d.rule_id,
            }
            for d in self._diagnostics.items
        ]

    diagnosticMarkers = Property("QVariantList", _markers, notify=resultCurrentChanged)  # type: ignore[arg-type]

    @Slot(str, str)
    def requestAction(self, action: str, argument: str = "") -> None:
        if (self._busy and action != "close") or action not in {
            "load",
            "history",
            "clear",
            "example",
            "close",
            "scratch",
            "undo_example",
        }:
            return
        if action == "history":
            entry = self._history_store.get(argument)
            if entry is not None and (
                self._active_history_id == argument
                and self._result_current
                and entry.source_text == self._source_text
                and entry.mode == self._mode
                and entry.selected_vendor == self._vendor
                and entry.initial_view == self._initial_view
            ):
                return
        self._pending_action = (action, argument)
        self._pending_save_scopes = []
        if self._source_text != self._saved_source:
            self._pending_save_scopes.append("configuration")
        if action == "close" and self._temporary_text != self._saved_temporary:
            self._pending_save_scopes.append("temporary")
        if self._pending_save_scopes:
            self.unsavedRequested.emit()
        else:
            self._finish_pending_action()

    @Slot(str)
    def resolveUnsaved(self, decision: str) -> None:
        if decision == "cancel":
            self._pending_action = None
            self._pending_save_scopes = []
        elif decision == "discard":
            self._pending_save_scopes = []
            self._finish_pending_action()
        elif decision == "save":
            self._save_next_pending()

    def _save_next_pending(self) -> None:
        if not self._pending_save_scopes:
            self._finish_pending_action()
            return
        scope = self._pending_save_scopes[0]
        if scope == "temporary":
            self.saveTemporaryText(self._temporary_text)
            if self._saved_temporary == self._temporary_text:
                self._pending_save_scopes.pop(0)
                self._save_next_pending()
        elif self._file_path is not None:
            self.saveSourceFile(str(self._file_path))
        else:
            self.saveAsRequested.emit("configuration")

    def _finish_pending_action(self) -> None:
        pending, self._pending_action = self._pending_action, None
        if pending is None:
            return
        action, argument = pending
        if action == "load":
            self.loadFile(argument)
        elif action == "history":
            self.openHistory(argument)
        elif action == "clear":
            self.clear()
        elif action == "example":
            self._example_snapshot = (
                self._source_text,
                self._saved_source,
                self._file_name,
                self._file_path,
                self._source_identity,
                self._vendor,
                self._mode,
                self._initial_view,
            )
            self.clear()
            self._set_vendor("h3c")
            self._set_mode("snippet")
            self._set_initial_view("")
            self._set_source_text(
                "sysname LAB-SW\n# Synthetic example\nvlan 10\n"
                "interface GigabitEthernet 1/0/1\n port link-type access\n port access vlan 10\n#\n"
            )
        elif action == "scratch":
            self.clear()
            self._set_source_text(self._temporary_text)
        elif action == "undo_example" and self._example_snapshot is not None:
            text, saved, name, path, identity, vendor, mode, initial_view = self._example_snapshot
            self._set_vendor(vendor)
            self._set_mode(mode)
            self._set_initial_view(initial_view)
            self._set_source_text(text)
            self._saved_source, self._file_name = saved, name
            self._file_path, self._source_identity = path, identity
            self._example_snapshot = None
            self.fileNameChanged.emit()
            self.workspaceChanged.emit()
        elif action == "close":
            self.closeApproved.emit()

    @Slot()
    def saveConfiguration(self) -> None:
        if self._file_path is None:
            self.saveAsRequested.emit("configuration")
        else:
            self.saveSourceFile(str(self._file_path))

    exampleAvailable = Property(
        bool, lambda self: self._example_snapshot is not None, notify=workspaceChanged
    )

    @Slot(str, result=bool)
    def saveSourceFile(self, value: str) -> bool:
        path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(self._source_text)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            self.toastRequested.emit("file.save_error")
            return False
        self._file_path = path
        self._file_name = path.name
        self._source_identity = "file"
        self._saved_source = self._source_text
        self.fileNameChanged.emit()
        self.workspaceChanged.emit()
        self.toastRequested.emit("file.saved")
        if self._pending_save_scopes and self._pending_save_scopes[0] == "configuration":
            self._pending_save_scopes.pop(0)
            self._save_next_pending()
        return True

    @Slot(str, result=bool)
    def exportTemporaryFile(self, value: str) -> bool:
        path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
        try:
            path.write_text(self._temporary_text, encoding="utf-8", newline="")
        except OSError:
            self.toastRequested.emit("file.save_error")
            return False
        self.toastRequested.emit("file.saved")
        return True

    historyRetention = Property(str, lambda self: self._history_store.retention, notify=historyEnabledChanged)

    @Slot(str)
    def setHistoryRetention(self, value: str) -> None:
        if value in {"summary", "full"}:
            self._history_epoch += 1
            try:
                self._history_store.set_retention(value)
            except OSError:
                self.toastRequested.emit("history.clear_error")
                return
            self._history_model.replace(self._history_store.entries)
            self.historyEnabledChanged.emit()

    @Slot(str)
    def filterHistory(self, value: str) -> None:
        self._history_model.set_filter(value)

    def _support_summary(self) -> dict[str, Any]:
        from netconfiglint.core.support import support_scope

        return support_scope()

    supportSummary = Property("QVariantMap", _support_summary, constant=True)  # type: ignore[arg-type]

    @Slot(str, result=bool)
    def exportSupportInventory(self, value: str) -> bool:
        from netconfiglint.core.support import export_support_inventory

        path = QUrl(value).toLocalFile() if value.startswith("file:") else value
        try:
            export_support_inventory(path)
        except (OSError, ValueError):
            self.toastRequested.emit("file.save_error")
            return False
        self.toastRequested.emit("file.saved")
        return True

    def close(self) -> None:
        self._closing = True
        self._cancellation.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
