from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, qInstallMessageHandler
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint import analyze
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def controller_at(path: Path) -> AnalysisController:
    return AnalysisController(
        async_enabled=False, history_store=HistoryStore(path / "history.json", enabled=False)
    )


def test_cancel_and_save_before_replace_and_close(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    requests: list[str] = []
    closes: list[bool] = []
    controller.unsavedRequested.connect(lambda: requests.append("prompt"))
    controller.saveAsRequested.connect(requests.append)
    controller.closeApproved.connect(lambda: closes.append(True))
    next_file = tmp_path / "next.cfg"
    next_file.write_text("sysname NEXT\n", encoding="utf-8")
    controller.sourceText = "sysname BEFORE\n"
    controller.requestAction("load", str(next_file))
    assert requests == ["prompt"]
    controller.resolveUnsaved("cancel")
    assert controller.sourceText == "sysname BEFORE\n"
    controller.requestAction("load", str(next_file))
    controller.resolveUnsaved("save")
    assert requests[-1] == "configuration"
    saved = tmp_path / "saved.cfg"
    assert controller.saveSourceFile(str(saved))
    assert saved.read_text(encoding="utf-8") == "sysname BEFORE\n"
    assert controller.sourceText == "sysname NEXT\n"
    assert not controller.sourceDirty
    assert controller.fileName == "next.cfg"
    controller.updateTemporaryText("UNSAVED SCRATCH\n")
    assert controller.temporaryDirty
    controller.requestAction("close", "")
    controller.resolveUnsaved("cancel")
    assert not closes and controller.temporaryDirty
    controller.requestAction("close", "")
    controller.resolveUnsaved("save")
    assert closes and not controller.temporaryDirty
    assert Path(controller.temporaryPath).read_text(encoding="utf-8") == "UNSAVED SCRATCH\n"
    controller.close()


def test_failed_save_keeps_source_and_pending_action(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    closes: list[bool] = []
    controller.closeApproved.connect(lambda: closes.append(True))
    controller.sourceText = "sysname KEEP\n"
    controller.requestAction("close", "")
    controller.resolveUnsaved("save")
    assert not controller.saveSourceFile(str(tmp_path / "missing" / "file.cfg"))
    assert controller.sourceDirty and not closes
    assert controller.sourceText == "sysname KEEP\n"
    controller.resolveUnsaved("cancel")
    controller.close()


def test_unsaved_scratch_and_source_are_separate(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    controller.sourceText = "sysname SOURCE\n"
    controller.updateTemporaryText("SCRATCH\n")
    controller.saveTemporaryText("SCRATCH\n")
    assert controller.sourceDirty and not controller.temporaryDirty
    controller.requestAction("scratch", "")
    controller.resolveUnsaved("cancel")
    assert controller.sourceText == "sysname SOURCE\n"
    controller.requestAction("scratch", "")
    controller.resolveUnsaved("discard")
    assert controller.sourceText == "SCRATCH\n"
    controller.close()


def test_example_can_be_undone_without_saving_over_open_file(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    source = tmp_path / "original.cfg"
    source.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller.loadFile(str(source))
    controller.requestAction("example", "")
    assert "LAB-SW" in controller.sourceText
    controller.requestAction("undo_example", "")
    controller.resolveUnsaved("discard")
    assert controller.sourceText == "sysname ORIGINAL\n"
    assert controller.fileName == "original.cfg"
    assert not controller.sourceDirty
    controller.close()


def test_context_and_marker_invalidation_and_export(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    controller.vendor = "h3c"
    controller.initialView = "bgp 65000"
    controller.sourceText = "peer 192.0.2.1 as-number 65001\n"
    controller.analyzeConfig()
    assert controller.coverage["recognized"] >= 1
    assert controller.prepareExport("diagnostics", "json", False)
    report = tmp_path / "report.json"
    controller.exportReport(str(report))
    assert json.loads(report.read_text(encoding="utf-8"))["input"]["initial_view"] == "bgp 65000"
    controller.initialView = ""
    controller.sourceText = "interface GigabitEthernet1/0/1\n ip address 999.1.1.1 255.255.255.0\n"
    controller.analyzeConfig()
    assert any(marker["severity"] == "ERROR" for marker in controller.diagnosticMarkers)
    controller.sourceText += "# Changed\n"
    assert controller.diagnosticMarkers == []
    controller.close()


def test_history_summary_retention_and_full_to_summary(tmp_path: Path, qapp: object) -> None:
    source = "sysname LAB-ONE\npassword cipher SYNTHETIC-SECRET\n"
    result = analyze(source, vendor="huawei")
    store = HistoryStore(tmp_path / "history.json", enabled=True, retention="summary")
    store.append(result, source, title="one.cfg")
    data = store.path.read_text(encoding="utf-8")
    assert "SYNTHETIC-SECRET" not in data
    assert store.entries[0].source_text == "" and "one.cfg" in store.entries[0].title
    store.set_retention("full")
    store.append(result, source, title="two.cfg", initial_view="bgp 65000")
    assert store.entries[0].source_text == source
    store.set_retention("summary")
    assert "SYNTHETIC-SECRET" not in store.path.read_text(encoding="utf-8")
    assert all(not e.source_text and not e.diagnostics for e in store.entries)


@pytest.mark.parametrize("kind,key", [("absent", "access"), ("binary", "binary"), ("utf32", "encoding")])
def test_file_error_categories_preserve_content(tmp_path: Path, qapp: object, kind: str, key: str) -> None:
    controller = controller_at(tmp_path)
    messages: list[str] = []
    controller.toastRequested.connect(messages.append)
    controller.sourceText = "KEEP"
    path = tmp_path / "input.cfg"
    if kind == "binary":
        path.write_bytes(b"abc\x00def")
    elif kind == "utf32":
        path.write_bytes("abc".encode("utf-32"))
    controller.loadFile(str(path))
    assert messages[-1] == f"file.{key}_error"
    assert controller.sourceText == "KEEP"
    controller.close()


def test_utf16_and_history_search(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    path = tmp_path / "utf16.cfg"
    path.write_bytes("sysname UTF16\n".encode("utf-16"))
    controller.loadFile(str(path))
    assert controller.sourceText == "sysname UTF16\n" and not controller.sourceDirty
    controller.historyEnabled = True
    controller.vendor = "huawei"
    controller.analyzeConfig()
    controller.filterHistory("UTF16")
    assert controller.historyModel.rowCount() == 1
    controller.filterHistory("MISSING")
    assert controller.historyModel.rowCount() == 0
    controller.close()


def test_same_text_history_restores_its_context_and_result(tmp_path: Path, qapp: object) -> None:
    source = "peer 192.0.2.1 as-number 65001\n"
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False, retention="full")
    store.append(
        analyze(source, vendor="h3c", initial_view="bgp 65000"), source, "h3c", initial_view="bgp 65000"
    )
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller.vendor = "h3c"
    path = tmp_path / "same.cfg"
    path.write_text(source, encoding="utf-8")
    controller.loadFile(str(path))
    controller.initialView = "bgp 65200"
    controller.requestAction("history", store.entries[0].entry_id)
    assert controller.initialView == "bgp 65000"
    assert controller.resultCurrent and controller.sourceIdentity == "history"
    controller.close()


def test_history_export_retains_the_user_provided_context(tmp_path: Path, qapp: object) -> None:
    source = "peer 192.0.2.1 as-number 65001\n"
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False, retention="full")
    store.append(
        analyze(source, vendor="h3c", initial_view="bgp 65000"), source, "h3c", initial_view="bgp 65000"
    )
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller.openHistory(store.entries[0].entry_id)
    assert controller.prepareExport("diagnostics", "json", False)
    payload = json.loads(controller._export_payload or "{}")
    assert payload["input"]["initial_view"] == "bgp 65000"
    controller.close()


def test_changed_history_context_creates_a_new_analysis_entry(tmp_path: Path, qapp: object) -> None:
    source = "peer 192.0.2.1 as-number 65001\n"
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False, retention="full")
    store.append(
        analyze(source, vendor="h3c", initial_view="bgp 65000"), source, "h3c", initial_view="bgp 65000"
    )
    old_id = store.entries[0].entry_id
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller.openHistory(old_id)
    controller.initialView = "bgp 65200"
    assert controller._active_history_id is None and not controller.resultCurrent
    controller.analyzeConfig()
    assert len(store.entries) == 2 and controller._active_history_id != old_id
    assert store.entries[0].initial_view == "bgp 65200"
    controller.close()


def test_bundle_load_after_history_uses_a_new_history_identity(tmp_path: Path, qapp: object) -> None:
    source = "sysname PREVIOUS\n"
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False, retention="full")
    store.append(analyze(source, vendor="h3c"), source, "h3c")
    old_id = store.entries[0].entry_id
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller.openHistory(old_id)
    bundle = "===== display current-configuration =====\nsysname BUNDLE\n#\n=====\n"
    path = tmp_path / "bundle.txt"
    path.write_text(bundle, encoding="utf-8")
    controller.loadFile(str(path))
    assert controller.editorReadOnly and controller._active_history_id is None
    controller.analyzeConfig()
    assert len(store.entries) == 2 and controller._active_history_id != old_id
    assert store.entries[0].source_text == bundle
    controller.close()


def test_full_history_title_is_stable_across_loads_and_writes(tmp_path: Path, qapp: object) -> None:
    source = "sysname LAB-STABLE\n"
    result = analyze(source, vendor="h3c")
    path = tmp_path / "history.json"
    store = HistoryStore(path, enabled=True, persist_settings=False, retention="full")
    store.append(result, source, "h3c", title="sample.cfg")
    title = store.entries[0].title
    for _ in range(3):
        store = HistoryStore(path, enabled=True, persist_settings=False, retention="full")
        assert all(entry.title == title for entry in store.entries)
        store.append(result, source, "h3c", title="sample.cfg")
    assert title.count("LAB-STABLE") == 1


def test_undo_example_restores_vendor_mode_context_and_dirty_baseline(tmp_path: Path, qapp: object) -> None:
    controller = controller_at(tmp_path)
    source = tmp_path / "huawei.cfg"
    source.write_text("sysname ORIGINAL\n", encoding="utf-8")
    controller.vendor = "huawei"
    controller.mode = "full"
    controller.initialView = "bgp 65000"
    controller.loadFile(str(source))
    controller.requestAction("example", "")
    controller.requestAction("undo_example", "")
    controller.resolveUnsaved("discard")
    assert (controller.vendor, controller.mode, controller.initialView) == ("huawei", "full", "bgp 65000")
    assert controller.sourceText == "sysname ORIGINAL\n" and not controller.sourceDirty
    assert controller.filePath == str(source)
    controller.close()


@pytest.mark.parametrize("width", [640, 1000, 1440])
def test_toolbar_and_pending_warning_are_accessible(tmp_path: Path, qapp: object, width: int) -> None:
    controller = controller_at(tmp_path)
    controller.vendor = "h3c"
    controller.sourceText = "lldp timer nonsense\ninfo-center loghost 999.1.1.1\n"
    controller.analyzeConfig()
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda mode, context, message: messages.append(message))
    engine = create_engine(controller)
    try:
        assert engine.rootObjects()
        window = engine.rootObjects()[0]
        assert isinstance(window, QQuickWindow)
        window.setWidth(width)
        QTest.qWait(200)
        for name in (
            "openButton",
            "modeSelectionField",
            "vendorSelectionField",
            "completionButton",
            "panelsButton",
        ):
            control = window.findChild(QObject, name)
            assert control is not None
            assert control.property("visible")
            assert (
                float(control.property("x")) + float(control.property("width"))
                <= float(control.parent().property("width")) + 1
            )
        assert window.findChild(QObject, "pendingLinesButton") is not None
        assert not any("ReferenceError" in message or "TypeError" in message for message in messages), (
            messages
        )
    finally:
        qInstallMessageHandler(previous)
        dispose_engine(qapp, engine, controller)
