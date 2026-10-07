"""Cancel-safe workers and bounded, navigable QML command/reference views."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any
from weakref import ref

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QEvent, QMetaObject, QObject, Qt, QTimer
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

import netconfiglint.gui.completion as completion_module
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.completion import CommandCompletion
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def descendants(item: QQuickItem) -> list[QQuickItem]:
    return [item] + [child for direct in item.childItems() for child in descendants(direct)]


def find(window: Any, name: str) -> Any:
    obj = window.findChild(QObject, name)
    return obj or next(child for child in descendants(window.contentItem()) if child.objectName() == name)


def value(obj: Any, name: str) -> Any:
    result = obj.property(name)
    return result.toVariant() if hasattr(result, "toVariant") else result


def wait_for(predicate: Any) -> None:
    for _ in range(500):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def desktop(qapp: Any, tmp_path: Path):
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.setWidth(960)
    QTest.qWait(100)
    yield window, engine
    dispose_engine(qapp, engine, controller)


def test_worker_preserves_gui_heartbeat_and_rejects_superseded_or_cancelled_results(
    qapp: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started, release = Event(), Event()

    def delayed(source: str, _cursor: int, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        if source == "slow":
            started.set()
            release.wait(10)
        return {"items": [{"text": source}], "argumentDetails": []}

    monkeypatch.setattr(completion_module, "complete", delayed)
    bridge = CommandCompletion(persist=False)
    delivered: list[tuple[Any, ...]] = []
    bridge.queryReady.connect(lambda *args: delivered.append(args))
    ticks: list[bool] = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    try:
        bridge.queryAsync("test", "slow", 4)
        wait_for(started.is_set)
        ticks.clear()
        wait_for(lambda: len(ticks) >= 3)
        assert len(ticks) >= 3 and not delivered
        serial = bridge.queryAsync("test", "latest", 6)
        release.set()
        wait_for(lambda: bool(delivered))
        QTest.qWait(30)
        assert len(delivered) == 1 and delivered[0][1] == serial
        assert delivered[0][2]["items"][0]["text"] == "latest"
        bridge.queryAsync("closed", "cancelled", 9)
        bridge.cancelQuery("closed")
        QTest.qWait(60)
        assert len(delivered) == 1
    finally:
        release.set()
        timer.stop()
        bridge.deleteLater()
        qapp.processEvents()


def test_engine_owned_bridge_is_released_before_its_worker_finishes(
    qapp: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The last Qt wrapper reference must never live in a worker callback."""
    import gc

    started, release, finished = Event(), Event(), Event()

    def delayed(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        started.set()
        release.wait(3)
        # Exercise worker-side collection after the Qt parent was disposed.
        gc.collect()
        finished.set()
        return {"items": [], "argumentDetails": []}

    monkeypatch.setattr(completion_module, "complete", delayed)
    parent = QObject()
    bridge = CommandCompletion(parent, persist=False)
    weak_bridge = ref(bridge)
    bridge.queryAsync("disposed", "synthetic", 9)
    wait_for(started.is_set)
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del bridge, parent
    try:
        assert weak_bridge() is None
    finally:
        release.set()
        wait_for(finished.is_set)


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_empty_tab_can_be_cancelled_or_typed_through_while_worker_is_pending(
    desktop: tuple,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, engine = desktop
    original = completion_module.complete
    started, release = Event(), Event()

    def delayed(source: str, cursor: int, *args: Any, **kwargs: Any) -> dict[str, Any]:
        started.set()
        release.wait(3)
        return original(source, cursor, *args, **kwargs)

    monkeypatch.setattr(completion_module, "complete", delayed)
    editor = find(window, name)
    card = find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    popup = find(window, name + "CompletionPopup")
    editor.setProperty("text", "")
    editor.forceActiveFocus()
    try:
        QTest.keyClick(window, Qt.Key.Key_Tab)
        wait_for(started.is_set)
        assert card.property("completionBusy")
        QTest.keyClick(window, Qt.Key.Key_Escape)
        assert not card.property("completionBusy")
        QTest.keyClick(window, Qt.Key.Key_Tab)
        assert card.property("completionBusy")
        QTest.keyClick(window, Qt.Key.Key_A)
        assert editor.property("text") == "a"
        assert not card.property("completionBusy")
        release.set()
        QTest.qWait(300)
        assert editor.property("text") == "a" and not popup.property("visible")
        bridge = engine.rootContext().contextProperty("commandCompletion")
        assert (name + "-completion", "query") not in bridge._jobs
    finally:
        release.set()


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_rehighlight_preserves_pending_completion_until_text_or_cursor_changes(
    desktop: tuple,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, engine = desktop
    original = completion_module.complete
    started, release = Event(), Event()

    def delayed(source: str, cursor: int, *args: Any, **kwargs: Any) -> dict[str, Any]:
        started.set()
        release.wait(3)
        return original(source, cursor, *args, **kwargs)

    monkeypatch.setattr(completion_module, "complete", delayed)
    monkeypatch.setattr(completion_module, "interactive_requires_async", lambda *_args: True)
    editor = find(window, name)
    card = find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    popup = find(window, name + "CompletionPopup")
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    editor.forceActiveFocus()
    try:
        QTest.keyClick(window, Qt.Key.Key_Tab)
        wait_for(started.is_set)
        assert card.property("completionBusy")
        document = editor.property("textDocument").textDocument()
        highlighter = next(
            item
            for item in engine.rootContext().contextProperty("syntaxHighlighter")._highlighters
            if item.document() is document
        )
        notifications: list[str] = []
        editor.textChanged.connect(lambda: notifications.append(editor.property("text")))
        highlighter.rehighlight()
        QTest.qWait(30)
        assert notifications and set(notifications) == {"sys"}
        assert card.property("completionBusy") and popup.property("visible")
        release.set()
        wait_for(lambda: not card.property("completionBusy"))
        assert popup.property("visible") and find(window, name + "CompletionList").property("count") >= 2
        editor.setProperty("cursorPosition", 2)
        wait_for(lambda: not popup.property("visible"))
    finally:
        release.set()


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
@pytest.mark.parametrize("source", ["sysname ", "ip binding vpn-instance "])
def test_query_parameter_only_input_has_references_without_editing_source(
    desktop: tuple, name: str, source: str
):
    window, engine = desktop
    engine.rootContext().contextProperty("commandCompletion").toggleVendor("huawei")
    editor = find(window, name)
    editor.setProperty("text", "SYNTHETIC_ORIGINAL")
    card = find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    QMetaObject.invokeMethod(card, "openCommandQuery")
    query = find(window, name + "CommandQuery")
    find(window, name + "CommandQueryField").setProperty("text", source)
    wait_for(
        lambda: not query.property("busy") and find(window, name + "CommandQueryList").property("count") > 0
    )
    result = value(query, "queryResult")
    assert not result["items"] and result["argumentDetails"]
    QMetaObject.invokeMethod(card, "showQueryDetail", Q_ARG("QVariant", 0))
    detail = find(window, name + "CompletionDetails")
    wait_for(lambda: detail.property("visible") and not detail.property("busy"))
    assert value(detail, "detail")["rows"][0]["sources"]
    assert find(window, name + "CompletionParameterDescription").property("text")
    assert editor.property("text") == "SYNTHETIC_ORIGINAL"


def test_worst_detail_group_is_paged_searchable_and_close_is_app_translated(desktop: tuple) -> None:
    window, engine = desktop
    name = "configurationTextArea"
    card = find(window, "configurationEditor")
    QMetaObject.invokeMethod(card, "openCommandQuery")
    query = find(window, name + "CommandQuery")
    find(window, name + "CommandQueryField").setProperty("text", "undo")
    wait_for(
        lambda: not query.property("busy") and find(window, name + "CommandQueryList").property("count") > 0
    )
    QMetaObject.invokeMethod(card, "showQueryDetail", Q_ARG("QVariant", 0))
    detail = find(window, name + "CompletionDetails")
    wait_for(lambda: detail.property("visible") and not detail.property("busy"))
    page = value(detail, "detail")
    assert page["total"] > 20_000 and len(page["rows"]) == 40 and page["pages"] > 500
    assert find(window, name + "CompletionDetailList").property("count") == 40
    assert len(descendants(window.contentItem())) < 2500
    QMetaObject.invokeMethod(detail, "page", Q_ARG("QVariant", page["pages"] - 1))
    assert value(detail, "detail")["page"] == page["pages"] - 1
    row = value(detail, "detail")["rows"][-1]
    find(window, name + "CompletionDetailFilter").setProperty("text", row["syntax"])
    wait_for(lambda: value(detail, "detail")["page"] == 0 and value(detail, "detail")["total"] < 20_000)
    assert any(item["syntax"] == row["syntax"] for item in value(detail, "detail")["rows"])
    i18n = engine.rootContext().contextProperty("i18n")
    for language, label in (("en", "Close"), ("zh_CN", "关闭")):
        i18n.language = language
        QTest.qWait(10)
        assert find(window, name + "CommandQueryClose").property("text") == label
        assert find(window, name + "CompletionDetailsClose").property("text") == label
    QTest.keyClick(window, Qt.Key.Key_Escape)
    wait_for(lambda: not detail.property("visible"))
    assert name not in engine.rootContext().contextProperty("commandCompletion")._detail_cache
