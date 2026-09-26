from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def _items(item: QQuickItem) -> list[QQuickItem]:
    children = item.childItems()
    return children + [descendant for child in children for descendant in _items(child)]


def _find(window: QQuickWindow, name: str) -> QQuickItem:
    return next(item for item in _items(window.contentItem()) if item.objectName() == name)


def _click(window: QQuickWindow, name: str) -> None:
    item = _find(window, name)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)


def test_v23_editor_search_selection_and_card_width(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1600)
    QTest.qWait(280)

    surface = _find(window, "workspaceSurface")
    assert all(
        surface.property(name) == 28
        for name in ("topLeftRadius", "topRightRadius", "bottomLeftRadius", "bottomRightRadius")
    )

    for section in ("general", "display", "color", "privacy"):
        assert not window.findChild(QObject, section + "SettingsSection").property("expanded")
    assert window.minimumWidth() > 960
    window.setWidth(window.minimumWidth())
    QTest.qWait(80)
    for card_name, editor_name in (
        ("configurationEditor", "configurationTextArea"),
        ("temporaryEditor", "temporaryTextArea"),
    ):
        card = _find(window, card_name)
        assert card.width() >= card.property("headerMinimumWidth") - 1
        assert _find(window, editor_name + "HeaderDetail").isVisible()
        assert card.mapToScene(QPointF(card.width(), 0)).x() <= window.width() + 1
    window.setWidth(1600)
    QTest.qWait(80)
    _click(window, "settingsButton")
    _click(window, "displaySettingsSection-header")
    settings = window.findChild(QObject, "settingsDialog")
    settings.close()
    QTest.qWait(250)
    _click(window, "settingsButton")
    assert window.findChild(QObject, "displaySettingsSection").property("expanded")
    settings.close()
    QTest.qWait(250)

    for card_name, editor_name in (
        ("configurationEditor", "configurationTextArea"),
        ("temporaryEditor", "temporaryTextArea"),
    ):
        card = _find(window, card_name)
        editor = _find(window, editor_name)
        editor.setProperty("text", "Alpha\n\n   \nBeta\n" + "tail\n" * 80)
        editor.forceActiveFocus()
        scroll = _find(window, editor_name + "ScrollView")
        flickable = scroll.property("contentItem")
        QTest.qWait(60)
        flickable.setProperty("contentY", 150)
        QTest.qWait(30)
        before = flickable.property("contentY")
        QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(70)
        assert editor.property("selectedText") == editor.property("text"), editor_name
        assert abs(flickable.property("contentY") - before) < 2, editor_name
        highlights = [
            item for item in _items(window.contentItem()) if item.objectName() == "selectedBlankLine"
        ]
        assert len(highlights) == 2

        original_minimum = card.property("headerMinimumWidth")
        card.setProperty("currentLine", 123456)
        QTest.qWait(20)
        assert card.property("headerMinimumWidth") > original_minimum
        editor.forceActiveFocus()
        QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(50)
        assert _find(window, "editorSearchCard").isVisible()
        assert card.property("searchActive")
        if _find(window, "editorMatchCase").property("checked"):
            _click(window, "editorMatchCase")
        if _find(window, "editorRegex").property("checked"):
            _click(window, "editorRegex")
        field = _find(window, "editorSearchField")
        field.setProperty("text", "alpha")
        QTest.qWait(30)
        status = _find(window, "editorSearchStatus").property("text")
        assert status == "1 处匹配", (editor_name, status)
        _click(window, "editorFindNext")
        assert editor.property("selectedText") == "Alpha"
        _click(window, "editorMatchCase")
        _click(window, "editorFindNext")
        assert editor.property("selectedText") == "Alpha"  # A failed find preserves selection.
        field.setProperty("text", "Alpha|Beta")
        _click(window, "editorRegex")
        _click(window, "editorFindNext")
        assert editor.property("selectedText") in ("Alpha", "Beta")
        _click(window, "editorSearchOpacityButton")
        slider = _find(window, "editorOpacitySlider")
        assert slider.property("from") > 0
        _click(window, "editorSearchClose")
        assert not card.property("searchActive")
        flickable.setProperty("contentY", 0)
        QTest.qWait(30)
        menu_point = editor.mapToScene(QPointF(80, 80)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=menu_point)
        QTest.qWait(50)
        _click(window, "editorClearMenuItem")
        QTest.qWait(180)
        assert editor.property("text") == ""

    window.close()
    QTest.qWait(200)
    controller.close()
