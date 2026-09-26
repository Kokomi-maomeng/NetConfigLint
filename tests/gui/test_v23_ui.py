from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
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
        QTest.qWait(130)
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


def test_v23_search_regex_selection_drag_and_menu_style(tmp_path: Path, qapp: object) -> None:
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
    QTest.qWait(260)

    editor = _find(window, "configurationTextArea")
    editor.setProperty("text", "one\r\ntwo\nthree")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(50)
    _click(window, "editorRegex")
    field = _find(window, "editorSearchField")
    field.setProperty("text", r"\r\n")
    QTest.qWait(150)
    assert _find(window, "editorSearchStatus").property("text") == "2 处匹配"
    _click(window, "editorFindNext")
    assert "\n" in editor.property("selectedText")
    field.setProperty("text", "^two$")
    QTest.qWait(150)
    assert _find(window, "editorSearchStatus").property("text") == "1 处匹配"
    field.setProperty("text", r"\b(?:one|three)\b")
    QTest.qWait(150)
    assert _find(window, "editorSearchStatus").property("text") == "2 处匹配"
    field.setProperty("text", r"(?=two)")
    QTest.qWait(150)
    assert _find(window, "editorSearchStatus").property("text") == "1 处匹配"
    field.setProperty("text", "[")
    QTest.qWait(150)
    assert _find(window, "editorSearchStatus").property("text") == "正则表达式无效"

    card = _find(window, "editorSearchCard")
    field.setProperty("text", "one")
    QTest.qWait(120)
    original = QPointF(card.x(), card.y())
    field_point = field.mapToScene(QPointF(field.width() / 2, field.height() / 2)).toPoint()
    QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=field_point)
    QTest.mouseMove(window, field_point + QPoint(55, 25))
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=field_point + QPoint(55, 25))
    QTest.qWait(40)
    assert QPointF(card.x(), card.y()) == original

    grip = _find(window, "editorSearchGrip")
    grip_dot = _find(window, "editorSearchGripDot")
    QTest.mouseMove(window, field_point)
    QTest.qWait(30)
    idle_color = grip_dot.property("color")
    grip_point = grip.mapToScene(QPointF(grip.width() / 2, grip.height() / 2)).toPoint()
    QTest.mouseMove(window, grip_point)
    QTest.qWait(250)
    assert grip_dot.property("color") != idle_color
    grip_tip = window.findChild(QObject, "editorSearchGripTip")
    assert grip_tip is not None
    assert grip_tip.property("background").property("radius") == 10
    assert grip_tip.property("text") == "移动卡片位置"
    end_point = grip_point + QPoint(75, 42)
    QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=grip_point)
    for part in range(1, 7):
        QTest.mouseMove(window, grip_point + (end_point - grip_point) * (part / 6), delay=20)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=end_point)
    QTest.qWait(40)
    assert card.x() > original.x() and card.y() > original.y()
    header_tip = window.findChild(QObject, "configurationTextAreaHeaderToolTip")
    assert header_tip is not None
    assert header_tip.property("background").property("radius") == 10

    _click(window, "editorSearchClose")
    editor.setProperty("text", "alpha+beta\nsecond")
    editor.select(0, 10)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(50)
    assert field.property("text") == "alpha+beta"
    assert not _find(window, "editorRegex").property("checked")
    _click(window, "editorSearchClose")
    editor.select(0, 11)  # A selected line ending must not enter the search field.
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(50)
    assert field.property("text") == "alpha+beta"
    _click(window, "editorSearchClose")
    editor.select(0, len(editor.property("text")))
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(50)
    assert "\n" not in field.property("text")
    _click(window, "editorSearchClose")

    menu_point = editor.mapToScene(QPointF(70, 50)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=menu_point)
    QTest.qWait(70)
    menu_item = _find(window, "editorSearchMenuItem")
    assert menu_item.property("background").property("radius") == 10
    QTest.mouseMove(window, menu_item.mapToScene(QPointF(50, 20)).toPoint())
    QTest.qWait(40)
    assert menu_item.property("hovered")

    window.close()
    QTest.qWait(200)
    controller.close()
