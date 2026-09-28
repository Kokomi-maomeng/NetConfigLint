"""Persistent data, real QML layout and async input regression checks."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from time import perf_counter

import pytest
from PySide6.QtCore import QObject, QSettings
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from netconfiglint import analyze
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers.analysis import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def test_history_size_is_readable_and_two_instances_merge(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "history.json"
    first = HistoryStore(path, enabled=True, persist_settings=False)
    second = HistoryStore(path, enabled=True, persist_settings=False)
    result = analyze("sysname SYNTHETIC\n", vendor="huawei")
    first.append(result, "SYNTHETIC-FIRST")
    second.append(result, "SYNTHETIC-SECOND")
    assert {item.source_text for item in second.entries} == {"SYNTHETIC-FIRST", "SYNTHETIC-SECOND"}
    first.remove_ids({second.entries[0].entry_id})
    assert len(HistoryStore(path, enabled=True, persist_settings=False).entries) == 1
    for _ in range(6):
        first.append(result, "中" * 4_000_000)
    reopened = HistoryStore(path, enabled=True, persist_settings=False)
    assert not reopened.load_warning
    assert len(reopened.entries) == 5
    assert path.stat().st_size <= 64 * 1024 * 1024
    assert all(len(item.source_text) == 4_000_000 for item in reopened.entries)


def test_history_restore_clears_bundle_and_decoding_metadata(tmp_path: Path, qapp: object) -> None:
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False)
    source = "sysname SYNTHETIC-B\n"
    store.append(analyze(source, vendor="huawei"), source, "huawei")
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller._bundle_configuration = "sysname SYNTHETIC-A\n"
    controller._input_metadata = {"encoding": "SYNTHETIC-OLD"}
    controller._file_name = "SYNTHETIC-A.cfg"
    controller.openHistory(store.entries[0].entry_id)
    assert controller.sourceText == source and controller.editorText == source
    assert not controller._bundle_configuration and not controller._input_metadata and not controller.fileName
    assert controller.prepareExport("configuration", "txt", False)
    assert source in controller._export_payload and "SYNTHETIC-A" not in controller._export_payload
    controller.close()


def test_scratch_unicode_roundtrip(tmp_path: Path, qapp: object) -> None:
    store = HistoryStore(tmp_path / "history" / "history.json", enabled=False, persist_settings=False)
    controller = AnalysisController(async_enabled=False, history_store=store)
    text = "中" * 1_500_000
    controller.saveTemporaryText(text)
    controller.close()
    reopened = AnalysisController(async_enabled=False, history_store=store)
    assert reopened.temporaryText == text
    reopened.close()


def _item(window: QObject, name: str) -> QQuickItem:
    result = window.findChild(QQuickItem, name)
    assert result is not None, name
    return result


def test_narrow_window_and_expanded_coverage_keep_issues_accessible(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.setWidth(768)
    window.setHeight(408)
    controller.vendor = "huawei"
    controller.sourceText = "vlan batch 10\ninterface GigabitEthernet0/0/1\n port default vlan 99\n#\n"
    controller.analyzeConfig()
    panel = _item(window, "analysisPanel")
    coverage = dict(controller.coverage)
    coverage["catalogued_families"] = [{"family": "synthetic", "count": i} for i in range(14)]
    panel.setProperty("coverage", coverage)
    panel.setProperty("coverageExpanded", True)
    QTest.qWait(200)
    page = _item(window, "configCheckPage")
    assert page.property("narrow")
    split = _item(window, "workspaceSplitView")
    assert split.width() <= page.width()
    assert panel.width() <= page.width()
    metadata = _item(window, "analysisMetadataScroll")
    assert metadata.height() <= panel.height() * 0.5
    lists = panel.findChildren(QQuickItem, "diagnosticIssueList")
    if not lists:
        lists = [
            item
            for item in panel.findChildren(QQuickItem)
            if item.metaObject().className().startswith("QQuickListView")
        ]
    assert lists and lists[0].height() >= 120
    assert window.minimumWidth() <= 768 and window.minimumHeight() <= 408
    preferences = engine.rootContext().contextProperty("preferences")
    preferences.setValue("reduceMotion", True)
    assert preferences.values["reduceMotion"]
    dispose_engine(qapp, engine, controller)


def test_large_file_load_is_async_and_gutter_is_bounded(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "synthetic-large.cfg"
    path.write_text("description SYNTHETIC-ONLY\n" * 40_000, encoding="utf-8")
    controller = AnalysisController(
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False)
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.setWidth(1440)
    started = perf_counter()
    controller.loadFile(str(path))
    assert perf_counter() - started < 0.5
    deadline = perf_counter() + 10
    while controller.busy and perf_counter() < deadline:
        QTest.qWait(20)
    assert not controller.busy and controller.sourceText == path.read_text("utf-8")
    gutter = _item(window, "configurationTextAreaGutter")
    assert len(gutter.childItems()) < 150
    assert gutter.property("firstLine") is not None
    dispose_engine(qapp, engine, controller)


def test_default_full_history_behavior_is_retained(tmp_path: Path, qapp: object) -> None:
    QSettings().remove("privacy/historyEnabled")
    store = HistoryStore(tmp_path / "history.json", persist_settings=False)
    assert store.enabled
    source = "sysname SYNTHETIC\npassword cipher SYNTHETIC_ONLY\n"
    store.append(analyze(source, vendor="huawei"), source)
    assert "SYNTHETIC_ONLY" in store.path.read_text("utf-8")


def _wait_idle(controller: AnalysisController) -> None:
    deadline = perf_counter() + 10
    while controller.busy and perf_counter() < deadline:
        QTest.qWait(20)
    assert not controller.busy


def test_queued_file_load_keeps_latest_request_and_user_edits(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = Event(), Event()
    original = AnalysisController._read_input_file
    paths = [tmp_path / f"synthetic-{i}.cfg" for i in range(3)]
    for i, path in enumerate(paths):
        path.write_text(f"sysname SYNTHETIC-{i}\n", "utf-8")

    def delayed(path: Path, revision: int) -> object:
        if path == paths[0]:
            entered.set()
            assert release.wait(5)
        return original(path, revision)

    monkeypatch.setattr(AnalysisController, "_read_input_file", staticmethod(delayed))
    controller = AnalysisController(
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False)
    )
    controller.loadFile(str(paths[0]))
    assert entered.wait(2)
    controller.loadFile(str(paths[1]))
    controller.loadFile(str(paths[2]))
    release.set()
    _wait_idle(controller)
    assert controller.sourceText == paths[2].read_text("utf-8")
    entered.clear()
    release.clear()
    controller.loadFile(str(paths[0]))
    assert entered.wait(2)
    controller.sourceText = "sysname SYNTHETIC-USER-EDIT\n"
    release.set()
    _wait_idle(controller)
    assert controller.sourceText == "sysname SYNTHETIC-USER-EDIT\n"
    controller.close()


@pytest.mark.parametrize("action", ["clear", "disable"])
def test_background_analysis_cannot_restore_cleared_history(
    tmp_path: Path, qapp: object, action: str
) -> None:
    entered, release = Event(), Event()

    def delayed(source: str, mode: str, vendor: str) -> object:
        entered.set()
        assert release.wait(5)
        return analyze(source, mode, vendor)

    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False)
    controller = AnalysisController(analyzer=delayed, history_store=store)  # type: ignore[arg-type]
    controller.vendor = "h3c"
    controller.sourceText = "sysname SYNTHETIC\n"
    controller.analyzeConfig()
    assert entered.wait(2)
    if action == "clear":
        controller.clearHistory()
    else:
        controller.historyEnabled = False
    release.set()
    _wait_idle(controller)
    assert controller.resultCurrent and not store.entries
    assert not HistoryStore(store.path, enabled=True, persist_settings=False).entries
    controller.close()


def test_large_editor_detaches_highlighting_and_restores_small_document(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    controller.sourceText = "description SYNTHETIC\n" * 40_000
    window = engine.rootObjects()[0]
    editor = _item(window, "configurationTextArea")
    QTest.qWait(30)
    assert editor.property("pagedPreview") and editor.property("readOnly")
    assert len(editor.property("text")) <= 82_768
    assert bridge.fullText(editor) == controller.sourceText
    relative_line = bridge.lineInPreview(editor, 39_990)
    assert 1 <= relative_line <= editor.property("lineCount")
    assert editor.property("previewPage") == editor.property("previewPageCount")
    assert controller.sourceText == "description SYNTHETIC\n" * 40_000
    source_highlighter = next(item for item in bridge._highlighters if item.document() is None)
    assert source_highlighter.document() is None
    controller.sourceText = "sysname SYNTHETIC\n"
    QTest.qWait(30)
    assert source_highlighter.document() is not None
    assert source_highlighter.document().toPlainText() == "sysname SYNTHETIC\n"
    dispose_engine(qapp, engine, controller)


def test_replacing_a_pending_large_editor_load_cannot_append_stale_text(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    controller.sourceText = "description SYNTHETIC-OLD\n" * 40_000
    controller.sourceText = "sysname SYNTHETIC-NEW\n"
    QTest.qWait(100)
    window = engine.rootObjects()[0]
    editor = _item(window, "configurationTextArea")
    assert editor.property("text") == controller.sourceText == "sysname SYNTHETIC-NEW\n"
    assert not editor.property("pagedPreview") and not editor.property("readOnly")
    dispose_engine(qapp, engine, controller)


def test_large_scratch_pagination_keeps_complete_saved_content(tmp_path: Path, qapp: object) -> None:
    store = HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False)
    scratch = tmp_path / "temporary" / "editor.txt"
    scratch.parent.mkdir()
    full_text = "中" * 1_500_000
    scratch.write_text(full_text, "utf-8")
    controller = AnalysisController(async_enabled=False, history_store=store)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    editor = _item(window, "temporaryTextArea")
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    assert editor.property("pagedPreview") and len(editor.property("text")) <= 82_768
    bridge.stepPreviewPage(editor, 1)
    assert editor.property("previewPage") == 2
    controller.saveTemporaryText(bridge.fullText(editor))
    assert scratch.read_text("utf-8") == full_text == controller.temporaryText
    dispose_engine(qapp, engine, controller)
