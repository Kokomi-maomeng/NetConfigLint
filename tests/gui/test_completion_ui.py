"""Real QML keyboard/selection/undo completion on both editors."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.completion import CommandCompletion
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def descendants(item: QQuickItem) -> list[QQuickItem]:
    return [item] + [child for direct in item.childItems() for child in descendants(direct)]


def find(window: QQuickWindow, name: str) -> QObject:
    obj = window.findChild(QObject, name)
    return obj or next(child for child in descendants(window.contentItem()) if child.objectName() == name)


@pytest.fixture
def desktop(qapp: object, tmp_path: Path):
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.setWidth(1600)
    QTest.qWait(200)
    yield window, engine, controller
    dispose_engine(qapp, engine, controller)


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_tab_popup_keyboard_accept_and_undo(desktop: tuple, name: str) -> None:
    window, _engine, _ = desktop
    editor = find(window, name)
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    popup = find(window, name + "CompletionPopup")
    assert popup.property("visible")
    assert editor.property("text") == "sys"
    candidate_list = find(window, name + "CompletionList")
    assert candidate_list.property("count") >= 2
    QTest.keyClick(window, Qt.Key.Key_Down)
    assert candidate_list.property("currentIndex") == 1
    QTest.keyClick(window, Qt.Key.Key_Backtab)
    assert candidate_list.property("currentIndex") == 0
    QTest.keyClick(window, Qt.Key.Key_Return)
    for _ in range(50):
        if not popup.property("visible"):
            break
        QTest.qWait(10)
    assert not popup.property("visible")
    assert editor.property("text").endswith(" ")
    assert "\n" not in editor.property("text")
    QMetaObject.invokeMethod(editor, "undo")
    assert editor.property("text") == "sys"


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_unique_middle_and_parameter_completion(desktop: tuple, name: str) -> None:
    window, engine, _ = desktop
    editor = find(window, name)
    bridge = engine.rootContext().contextProperty("commandCompletion")
    bridge.toggleVendor("h3c")
    editor.setProperty("text", "sysnam-old suffix\nnext")
    editor.setProperty("cursorPosition", 5)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert editor.property("text") == "sysname suffix\nnext"
    QMetaObject.invokeMethod(editor, "undo")
    assert editor.property("text") == "sysnam-old suffix\nnext"
    editor.setProperty("text", "peer 192.0.2.1 as-n")
    editor.setProperty("cursorPosition", len(editor.property("text")))
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert editor.property("text") == "peer 192.0.2.1 as-number "


def test_cancellation_selection_readonly_and_stale_candidates(desktop: tuple) -> None:
    window, _, _ = desktop
    editor = find(window, "temporaryTextArea")
    popup = find(window, "temporaryTextAreaCompletionPopup")
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    for _ in range(50):
        if not popup.property("visible"):
            break
        QTest.qWait(10)
    assert editor.property("text") == "sys" and not popup.property("visible")
    QTest.keyClick(window, Qt.Key.Key_Tab)
    QTest.keyClick(window, Qt.Key.Key_A)
    for _ in range(50):
        if not popup.property("visible"):
            break
        QTest.qWait(10)
    assert editor.property("text") == "sysa" and not popup.property("visible")
    QMetaObject.invokeMethod(editor, "selectAll")
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert editor.property("text") == "sysa"
    editor.setProperty("readOnly", True)
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert editor.property("text") == "sysa" and not popup.property("visible")


def test_auto_exclusion_multiselect_persistence_and_toolbar(desktop: tuple) -> None:
    window, engine, controller = desktop
    bridge = engine.rootContext().contextProperty("commandCompletion")
    assert bridge.automatic
    QMetaObject.invokeMethod(find(window, "completionButton"), "clicked")
    dialog = find(window, "completionDialog")
    assert dialog.property("visible")
    bridge.toggleVendor("h3c")
    assert not bridge.automatic and bridge.selectedVendors == ["h3c"]
    bridge.toggleVendor("huawei")
    assert bridge.selectedVendors == ["h3c", "huawei"]
    assert controller.vendor == "auto"
    restored = CommandCompletion()
    assert restored.selectedVendors == ["h3c", "huawei"]
    bridge.toggleVendor("auto")
    assert bridge.automatic and bridge.selectedVendors == []
    dialog.close()
    window.setWidth(640)
    QTest.qWait(100)
    toolbar = find(window, "topConfigToolbar")
    assert toolbar.width() < window.width()


def test_unicode_offset_and_popup_bounds(desktop: tuple) -> None:
    window, engine, _ = desktop
    editor = find(window, "temporaryTextArea")
    engine.rootContext().contextProperty("commandCompletion").toggleVendor("h3c")
    source = "description 🐱 中文\nsysnam"
    editor.setProperty("text", source)
    editor.setProperty("cursorPosition", len(source.encode("utf-16-le")) // 2)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert editor.property("text") == source[:-6] + "sysname "
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    QTest.keyClick(window, Qt.Key.Key_Tab)
    popup = find(window, "temporaryTextAreaCompletionPopup")
    assert popup.property("visible")
    assert popup.property("x") >= 0 and popup.property("y") >= 0
    assert popup.property("x") + popup.property("width") <= window.width()
    assert popup.property("y") + popup.property("height") <= window.height()


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_mouse_accept_and_changed_document_rejects_stale_popup(desktop: tuple, name: str) -> None:
    window, _, _ = desktop
    editor = find(window, name)
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    candidate_list = find(window, name + "CompletionList")
    popup = find(window, name + "CompletionPopup")
    for _ in range(50):
        if popup.property("opened"):
            break
        QTest.qWait(10)
    assert popup.property("opened")
    assert candidate_list.height() > 0
    candidate = next(
        item
        for item in descendants(candidate_list)
        if item.property("index") == 0 and item.property("modelData") is not None
    )
    point = candidate.mapToScene(QPointF(candidate.width() / 2, candidate.height() / 2)).toPoint()
    assert 0 <= point.x() < window.width() and 0 <= point.y() < window.height()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
    assert editor.property("text").endswith(" ")
    editor.setProperty("text", "sys")
    editor.setProperty("cursorPosition", 3)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    editor.setProperty("text", "new document")
    card = find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    assert QMetaObject.invokeMethod(card, "acceptCompletion", Q_ARG("QVariant", 0))
    assert editor.property("text") == "new document"
