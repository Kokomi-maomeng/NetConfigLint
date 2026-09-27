from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, QPoint, QPointF, Qt
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


def _press_shortcut(window: QQuickWindow, key: Qt.Key) -> None:
    modifier = (
        Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
    )
    QTest.keyClick(window, key, modifier)


def _wait_for_search_status(window: QQuickWindow, expected: str) -> None:
    QTest.qWait(110)  # The card debounces edits before searching.
    for _ in range(50):
        actual = _find(window, "editorSearchStatus").property("text")
        if actual == expected:
            return
        QTest.qWait(20)
    assert actual == expected


def _wait_for_opacity(item: QQuickItem, expected: float) -> None:
    for _ in range(50):
        if abs(item.opacity() - expected) < 0.01:
            return
        QTest.qWait(20)
    assert abs(item.opacity() - expected) < 0.01


def test_v23_editor_search_selection_and_card_width(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    catalog = engine.rootContext().contextProperty("i18n").catalog
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
    assert window.minimumWidth() >= 960
    window.setWidth(window.minimumWidth())
    QTest.qWait(320)
    for card_name, editor_name in (
        ("configurationEditor", "configurationTextArea"),
        ("temporaryEditor", "temporaryTextArea"),
    ):
        card = _find(window, card_name)
        assert card.width() >= card.property("headerMinimumWidth") - 1
        assert _find(window, editor_name + "HeaderDetail").isVisible()
        assert card.mapToScene(QPointF(card.width(), 0)).x() <= window.width() + 1
    window.setWidth(1600)
    QTest.qWait(320)
    _click(window, "settingsButton")
    QTest.qWait(300)
    _click(window, "displaySettingsSection-header")
    settings = window.findChild(QObject, "settingsDialog")
    settings.close()
    QTest.qWait(250)
    _click(window, "settingsButton")
    QTest.qWait(300)
    assert window.findChild(QObject, "displaySettingsSection").property("expanded")
    settings.close()
    QTest.qWait(250)

    for card_name, editor_name in (
        ("configurationEditor", "configurationTextArea"),
        ("temporaryEditor", "temporaryTextArea"),
    ):
        card = _find(window, card_name)
        editor = _find(window, editor_name)
        editor.setProperty("text", "Alpha\n\n   \n\t\nBeta\n" + "tail\n" * 80)
        editor.forceActiveFocus()
        scroll = _find(window, editor_name + "ScrollView")
        flickable = scroll.property("contentItem")
        QTest.qWait(60)
        flickable.setProperty("contentY", 150)
        QTest.qWait(30)
        before = flickable.property("contentY")
        _press_shortcut(window, Qt.Key.Key_A)
        QTest.qWait(70)
        assert editor.property("selectedText") == editor.property("text"), editor_name
        assert abs(flickable.property("contentY") - before) < 2, editor_name
        editor.setProperty("text", "Alpha\n\n   \n\t\nBeta\n")
        editor.selectAll()
        flickable.setProperty("contentY", 0)
        QTest.qWait(180)
        assert flickable.property("contentY") <= 1
        highlights = [
            item for item in _items(window.contentItem()) if item.objectName() == "selectedBlankLine"
        ]
        assert len(highlights) == 1, (
            editor_name,
            editor.property("selectionStart"),
            editor.property("selectionEnd"),
            card.property("selectionWindowStart"),
            card.property("selectionWindowEnd"),
            flickable.property("contentY"),
        )
        blank_rect = editor.positionToRectangle(6)
        expected_origin = editor.mapToScene(QPointF(blank_rect.x(), blank_rect.y()))
        actual_origin = highlights[0].mapToScene(QPointF(0, 0))
        assert abs(actual_origin.y() - expected_origin.y()) < 1
        whitespace = [
            item for item in _items(window.contentItem()) if item.objectName() == "selectedWhitespace"
        ]
        assert any(item.width() > highlights[0].width() for item in whitespace)
        for position in (7, 11):  # Spaces and a tab start on different lines.
            rect = editor.positionToRectangle(position)
            expected = editor.mapToScene(QPointF(rect.x(), rect.y()))
            assert any(
                abs(item.mapToScene(QPointF(0, 0)).x() - expected.x()) < 1
                and abs(item.mapToScene(QPointF(0, 0)).y() - expected.y()) < 1
                for item in whitespace
            )

        original_minimum = card.property("headerMinimumWidth")
        card.setProperty("currentLine", 123456)
        QTest.qWait(20)
        assert card.property("headerMinimumWidth") > original_minimum
        editor.forceActiveFocus()
        _press_shortcut(window, Qt.Key.Key_F)
        QTest.qWait(300)
        assert _find(window, "editorSearchCard").isVisible()
        assert card.property("searchActive")
        if _find(window, "editorMatchCase").property("checked"):
            _click(window, "editorMatchCase")
        if _find(window, "editorRegex").property("checked"):
            _click(window, "editorRegex")
        field = _find(window, "editorSearchField")
        field.setProperty("text", "alpha")
        _wait_for_search_status(window, "1 " + catalog["editor.matches"])
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
        QTest.qWait(300)
        editor.forceActiveFocus()
        assert editor.property("activeFocus")
        assert not _find(window, "editorSearchOverlay").property("opened")
        _press_shortcut(window, Qt.Key.Key_F)
        QTest.qWait(40)
        assert _find(window, "editorSearchOverlay").property("opened")
        _press_shortcut(window, Qt.Key.Key_F)
        assert not _find(window, "editorSearchOverlay").property("opened")
        editor.select(0, 5)
        editor.forceActiveFocus()
        _press_shortcut(window, Qt.Key.Key_F)
        assert field.property("text") == "Alpha"
        beta = editor.property("text").index("Beta")
        editor.forceActiveFocus()
        editor.select(beta, beta + 4)
        _press_shortcut(window, Qt.Key.Key_F)
        assert _find(window, "editorSearchOverlay").property("opened")
        assert field.property("text") == "Beta"
        QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        assert not _find(window, "editorSearchOverlay").property("opened")
        flickable.setProperty("contentY", 0)
        QTest.qWait(30)
        menu_point = editor.mapToScene(QPointF(80, 80)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=menu_point)
        QTest.qWait(50)
        clear_item = _find(window, "editorClearMenuItem")
        assert clear_item.isEnabled()
        if sys.platform == "darwin":
            # Qt's offscreen popup uses a separate window on macOS; dispatch its action.
            assert QMetaObject.invokeMethod(clear_item, "triggered")
        else:
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
    catalog = engine.rootContext().contextProperty("i18n").catalog
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1600)
    QTest.qWait(260)

    editor = _find(window, "configurationTextArea")
    editor.setProperty("text", "one\r\ntwo\nthree")
    editor.forceActiveFocus()
    _press_shortcut(window, Qt.Key.Key_F)
    QTest.qWait(300)
    _click(window, "editorRegex")
    assert _find(window, "editorRegex").property("checked")
    field = _find(window, "editorSearchField")
    field.setProperty("text", r"\r\n")
    _wait_for_search_status(window, "2 " + catalog["editor.matches"])
    _click(window, "editorFindNext")
    assert "\n" in editor.property("selectedText")
    caret = _find(window, "configurationTextAreaSearchCaret")
    assert caret.isVisible() and caret.x() > editor.property("leftPadding")
    _click(window, "editorFindNext")
    assert caret.isVisible() and caret.x() > editor.property("leftPadding")
    field.setProperty("text", "^two$")
    _wait_for_search_status(window, "1 " + catalog["editor.matches"])
    field.setProperty("text", r"\b(?:one|three)\b")
    _wait_for_search_status(window, "2 " + catalog["editor.matches"])
    field.setProperty("text", r"(?=two)")
    _wait_for_search_status(window, "1 " + catalog["editor.matches"])
    field.setProperty("text", "[")
    _wait_for_search_status(window, catalog["editor.invalid_regex"])

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
    assert grip_tip.property("text") == catalog["panels.reorder"]
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
    overlay = _find(window, "editorSearchOverlay")
    assert not overlay.property("opened")
    assert overlay.isVisible()  # The exit animation keeps the card rendered briefly.
    QTest.qWait(300)
    assert not overlay.isEnabled()
    editor.setProperty("text", "alpha+beta\nsecond")
    editor.select(0, 10)
    editor.forceActiveFocus()
    _press_shortcut(window, Qt.Key.Key_F)
    QTest.qWait(50)
    assert field.property("text") == "alpha+beta"
    assert not _find(window, "editorRegex").property("checked")
    _click(window, "editorSearchClose")
    editor.select(0, 11)  # A selected line ending must not enter the search field.
    editor.forceActiveFocus()
    _press_shortcut(window, Qt.Key.Key_F)
    QTest.qWait(50)
    assert field.property("text") == "alpha+beta"
    _click(window, "editorSearchClose")
    editor.select(0, len(editor.property("text")))
    editor.forceActiveFocus()
    _press_shortcut(window, Qt.Key.Key_F)
    QTest.qWait(50)
    assert "\n" not in field.property("text")
    _click(window, "editorSearchClose")

    menu_point = editor.mapToScene(QPointF(70, 50)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=menu_point)
    QTest.qWait(70)
    menu_item = _find(window, "editorSearchMenuItem")
    assert menu_item.property("background").property("radius") == 10
    hover_overlay = next(
        child
        for child in menu_item.property("background").childItems()
        if child.objectName() == "menuItemHoverOverlay"
    )
    undo_item = _find(window, "editorUndoMenuItem")
    QTest.mouseMove(window, undo_item.mapToScene(QPointF(50, 20)).toPoint())
    _wait_for_opacity(hover_overlay, 0)
    QTest.mouseMove(window, menu_item.mapToScene(QPointF(50, 20)).toPoint())
    _wait_for_opacity(hover_overlay, 1)
    assert menu_item.property("hovered")
    assert not undo_item.isEnabled()
    QTest.mouseMove(window, undo_item.mapToScene(QPointF(50, 20)).toPoint())
    _wait_for_opacity(hover_overlay, 0)
    preferences = engine.rootContext().contextProperty("preferences")
    for mode in (1, 2):
        preferences.setValue("themeMode", mode)
        QTest.qWait(50)
        enabled_color = menu_item.property("contentItem").property("color")
        disabled_color = undo_item.property("contentItem").property("color")
        assert abs(enabled_color.lightnessF() - disabled_color.lightnessF()) > 0.25
        for item, expected in ((menu_item, enabled_color), (undo_item, disabled_color)):
            icon = next(
                child for child in item.property("contentItem").childItems() if child.objectName() == "image"
            )
            assert icon.isVisible() and icon.property("color") == expected

    window.close()
    QTest.qWait(200)
    controller.close()


def test_v23_long_selection_draws_only_near_viewport(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    QTest.qWait(200)
    editor = _find(window, "configurationTextArea")
    editor.setProperty("text", "port link-type trunk\n" * 2000)
    editor.selectAll()
    QTest.qWait(80)

    def visible_whitespace_count() -> int:
        return sum(item.objectName() == "selectedWhitespace" for item in _items(window.contentItem()))

    assert 0 < visible_whitespace_count() < 200
    scroll = _find(window, "configurationTextAreaScrollView")
    scroll.property("contentItem").setProperty("contentY", 20000)
    QTest.qWait(80)
    assert 0 < visible_whitespace_count() < 200

    window.close()
    QTest.qWait(200)
    controller.close()
