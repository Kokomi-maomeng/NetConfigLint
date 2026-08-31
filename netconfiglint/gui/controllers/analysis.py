from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from netconfiglint import analyze
from netconfiglint.core.analyzer import AnalysisResult
from netconfiglint.gui.models import DiagnosticListModel
from netconfiglint.vendors.huawei.rules import HUAWEI_RULES

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
    analysisFinished = Signal()
    analysisFailed = Signal(str)
    jumpToLine = Signal(int, int)
    toastRequested = Signal(str)
    _workerSucceeded = Signal(object)
    _workerFailed = Signal(str)

    def __init__(self, analyzer: Analyzer = analyze, *, async_enabled: bool = True) -> None:
        super().__init__()
        self._analyzer = analyzer
        self._async_enabled = async_enabled
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="netconfiglint")
        self._source_text = ""
        self._mode = "full"
        self._vendor = "auto"
        self._busy = False
        self._status_message = "Ready"
        self._file_name = "Untitled configuration"
        self._detection: dict[str, Any] = self._empty_detection()
        self._summary: dict[str, int] = {key: 0 for key in ("ERROR", "WARNING", "INFO", "UNKNOWN")}
        self._diagnostics = DiagnosticListModel()
        self._workerSucceeded.connect(self._apply_result)
        self._workerFailed.connect(self._apply_error)

    @staticmethod
    def _empty_detection() -> dict[str, Any]:
        return {
            "vendor": "Unknown",
            "os": "Unknown",
            "platform_family": "Unknown",
            "model": "Unknown",
            "version": "Unknown",
            "confidence": 0.0,
        }

    def _get_source_text(self) -> str:
        return self._source_text

    def _set_source_text(self, value: str) -> None:
        if value != self._source_text:
            self._source_text = value
            self.sourceTextChanged.emit()

    sourceText = Property(str, _get_source_text, _set_source_text, notify=sourceTextChanged)

    def _get_mode(self) -> str:
        return self._mode

    def _set_mode(self, value: str) -> None:
        if value in {"snippet", "full", "snapshot"} and value != self._mode:
            self._mode = value
            self.modeChanged.emit()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)

    def _get_vendor(self) -> str:
        return self._vendor

    def _set_vendor(self, value: str) -> None:
        if value in {"auto", "huawei"} and value != self._vendor:
            self._vendor = value
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

    def _get_rule_catalog(self) -> list[dict[str, str]]:
        return [
            {
                "ruleId": rule.metadata.rule_id,
                "title": rule.metadata.title,
                "severity": rule.metadata.default_severity.value,
                "vendor": rule.metadata.vendor,
            }
            for rule in HUAWEI_RULES
        ]

    ruleCatalog = Property("QVariantList", _get_rule_catalog, constant=True)  # type: ignore[arg-type]

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
        self._file_name = "Untitled configuration"
        self.fileNameChanged.emit()
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        self._set_status("Ready")

    @Slot(str)
    def loadFile(self, value: str) -> None:
        try:
            path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
            self._set_source_text(path.read_text(encoding="utf-8-sig"))
            self._file_name = path.name
            self.fileNameChanged.emit()
            self._set_status(f"Loaded {path.name}")
        except (OSError, UnicodeError) as exc:
            self._apply_error(f"Could not open file: {exc}")

    @Slot(str)
    def exportReport(self, value: str) -> None:
        try:
            path = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
            payload = {
                "file": self._file_name,
                "mode": self._mode,
                "detection": self._detection,
                "diagnostics": [
                    self._diagnostics.item_at(row).to_dict()  # type: ignore[union-attr]
                    for row in range(self._diagnostics.rowCount())
                ],
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.toastRequested.emit(f"Report exported to {path.name}")
        except OSError as exc:
            self._apply_error(f"Could not export report: {exc}")

    @Slot()
    def analyzeConfig(self) -> None:
        if self._busy:
            return
        if not self._source_text.strip():
            self._apply_error("Paste or open a configuration before analyzing.")
            return
        self._set_busy(True)
        self._set_status("Analyzing locally…")
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
        try:
            self._workerSucceeded.emit(future.result())
        except Exception as exc:  # analyzer boundary: surfaced without source text
            self._workerFailed.emit(str(exc))

    @Slot(object)
    def _apply_result(self, result: object) -> None:
        if not isinstance(result, AnalysisResult):
            self._apply_error("Analyzer returned an invalid result")
            return
        self._diagnostics.replace(result.diagnostics)
        self._detection = result.detection.to_dict()
        counts = Counter(item.severity.value for item in result.diagnostics)
        self._summary = {key: counts[key] for key in self._summary}
        self.detectionChanged.emit()
        self.summaryChanged.emit()
        self._set_busy(False)
        self._set_status(f"Completed in {result.elapsed_ms:.1f} ms")
        self.analysisFinished.emit()

    @Slot(str)
    def _apply_error(self, message: str) -> None:
        self._set_busy(False)
        self._set_status("Analysis error")
        self.analysisFailed.emit(message)
        self.toastRequested.emit(message)

    @Slot(int)
    def requestJump(self, row: int) -> None:
        item = self._diagnostics.item_at(row)
        if item is not None:
            self.jumpToLine.emit(item.source.line, item.source.end_line or item.source.line)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
