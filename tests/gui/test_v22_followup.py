from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import QFontDatabase, QFontInfo
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.fonts import load_fonts, make_font
from netconfiglint.gui.models.history import HistoryRole, HistoryStore, local_timestamp


def _items(item: QQuickItem) -> list[QQuickItem]:
    children = item.childItems()
    return children + [descendant for child in children for descendant in _items(child)]


def _find(window: QQuickWindow, name: str) -> QQuickItem:
    return next(item for item in _items(window.contentItem()) if item.objectName() == name)


def _click(window: QQuickWindow, name: str) -> None:
    item = _find(window, name)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)


def test_bundled_fonts_resolve_regular_and_semibold(qapp: object) -> None:
    load_fonts()
    assert {"Regular", "SemiBold"}.issubset(set(QFontDatabase.styles("Noto Sans SC")))
    assert QFontInfo(make_font(15, 400)).styleName() == "Regular"
    assert QFontInfo(make_font(15, 600)).styleName() == "SemiBold"


def test_blank_line_selection_and_keyboard_zoom_in_both_editors(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    QTest.qWait(280)

    for card_name, editor_name in (
        ("configurationEditor", "configurationTextArea"),
        ("temporaryEditor", "temporaryTextArea"),
    ):
        card = _find(window, card_name)
        editor = _find(window, editor_name)
        editor.setProperty("text", "top\n\nbottom")
        editor.forceActiveFocus()
        QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(60)
        highlights = [
            item for item in _items(window.contentItem()) if item.objectName() == "selectedBlankLine"
        ]
        assert len(highlights) == 1
        assert highlights[0].width() > 32 and highlights[0].height() > 0
        assert highlights[0].isVisible()

        original = card.property("editorFontSize")
        QTest.keyClick(window, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(40)
        assert card.property("editorFontSize") == original + 1
        QTest.keyClick(window, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(40)
        assert card.property("editorFontSize") == original

        editor.setProperty("cursorPosition", 0)
        QTest.qWait(40)
        assert not [item for item in _items(window.contentItem()) if item.objectName() == "selectedBlankLine"]

    window.close()
    QTest.qWait(200)
    controller.close()


def test_window_open_maximize_restore_and_close_transitions(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    shell = _find(window, "applicationShell")
    QTest.qWait(35)
    assert 0 < shell.property("opacity") < 1
    QTest.qWait(300)
    assert shell.property("opacity") == 1

    _click(window, "maximizeWindowButton")
    QTest.qWait(45)
    assert shell.property("opacity") < 1
    QTest.qWait(300)
    assert window.visibility() == QQuickWindow.Visibility.Maximized
    assert shell.property("opacity") == 1

    _click(window, "maximizeWindowButton")
    QTest.qWait(300)
    assert window.visibility() == QQuickWindow.Visibility.Windowed
    _click(window, "closeWindowButton")
    QTest.qWait(70)
    assert window.isVisible() and shell.property("opacity") < 1
    QTest.qWait(180)
    assert not window.isVisible()
    controller.close()


def test_portable_scratch_save_and_history_timestamp(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "history" / "history.json"
    store = HistoryStore(path, enabled=True, persist_settings=False)
    controller = AnalysisController(async_enabled=False, history_store=store)
    assert controller.temporaryText == ""
    controller.saveTemporaryText("first\nsecond\n")
    scratch_path = tmp_path / "temporary" / "editor.txt"
    assert scratch_path.read_text(encoding="utf-8") == "first\nsecond\n"

    controller.vendor = "huawei"
    controller.sourceText = "sysname SYNTHETIC\n"
    controller.analyzeConfig()
    assert len(store.entries) == 1
    displayed = controller.historyModel.data(controller.historyModel.index(0, 0), HistoryRole.TIMESTAMP)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", displayed)
    assert displayed == controller.resultTimestamp == local_timestamp(store.entries[0].timestamp)
    controller.openHistory(store.entries[0].entry_id)
    assert controller.resultTimestamp == displayed
    controller.close()

    reopened = AnalysisController(
        async_enabled=False, history_store=HistoryStore(path, enabled=True, persist_settings=False)
    )
    assert reopened.temporaryText == "first\nsecond\n"
    reopened.close()


def test_compact_cards_and_navigation_interactions(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(960)
    window.setHeight(720)
    QTest.qWait(350)

    config = _find(window, "configurationEditor")
    config.setProperty("text", "one\n")
    editor = _find(window, "configurationTextArea")
    editor.forceActiveFocus()
    editor.setProperty("cursorPosition", len(editor.property("text")))
    QTest.keyClick(window, Qt.Key.Key_Return)
    QTest.qWait(80)
    assert config.property("currentLine") == 3
    assert _find(window, "analyzeButton").y() == 12
    assert _find(window, "temporarySaveButton").y() == 12
    scratch_path = tmp_path / "temporary" / "editor.txt"
    scratch_editor = _find(window, "temporaryTextArea")
    point = scratch_editor.mapToScene(QPointF(80, 100)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
    QTest.keyClick(window, Qt.Key.Key_A)
    assert scratch_editor.property("text") == "a"
    _click(window, "temporarySaveButton")
    assert scratch_path.read_text(encoding="utf-8") == "a"

    badges = [_find(window, f"severityFilter-{value}") for value in ("ERROR", "WARNING", "INFO", "UNKNOWN")]
    assert len({round(item.y()) for item in badges}) == 1
    assert len({round(item.height()) for item in badges}) == 1

    _click(window, "sidebarToggle")
    QTest.qWait(320)
    assert _find(window, "navigationRail").width() == 260
    _click(window, "sidebarToggle")
    QTest.qWait(320)
    assert _find(window, "navigationRail").width() == 0
    _click(window, "brandAboutButton")
    assert window.property("currentPage") == 1
    _click(window, "brandAboutButton")
    assert window.property("currentPage") == 0
    window.close()
    controller.close()


def test_maximized_window_returns_maximized_after_minimize(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.showMaximized()
    QTest.qWait(80)
    assert window.visibility() == QQuickWindow.Visibility.Maximized
    window.showMinimized()
    QTest.qWait(80)
    assert window.visibility() == QQuickWindow.Visibility.Minimized
    window.showNormal()  # Windows taskbar activation can surface a normal state.
    QTest.qWait(120)
    assert window.visibility() == QQuickWindow.Visibility.Maximized
    window.close()
    controller.close()


def test_history_switch_reenables_and_clear_confirmation_returns_to_check(
    tmp_path: Path, qapp: object
) -> None:
    path = tmp_path / "history" / "history.json"
    store = HistoryStore(path, enabled=True, persist_settings=False)
    controller = AnalysisController(async_enabled=False, history_store=store)
    controller.vendor = "huawei"
    controller.sourceText = "sysname SYNTHETIC\n"
    controller.analyzeConfig()
    assert path.exists()
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1440)
    QTest.qWait(80)
    _click(window, "settingsButton")
    section = _find(window, "privacySettingsSection")
    section.setProperty("expanded", True)
    QTest.qWait(350)
    scroll = _find(window, "settingsScrollView")
    viewport = scroll.property("contentItem")
    viewport.setProperty("contentY", viewport.property("contentHeight") - viewport.property("height"))
    QTest.qWait(100)
    _click(window, "historySwitch")
    _click(window, "disableHistoryConfirm")
    QTest.qWait(200)
    assert not controller.historyEnabled
    assert not _find(window, "historySwitch").property("checked")
    _click(window, "historySwitch")
    assert controller.historyEnabled
    assert _find(window, "historySwitch").property("checked")

    controller.sourceText = "sysname SECOND\n"
    controller.analyzeConfig()
    assert path.exists()
    _click(window, "clearHistoryButton")
    dialog = window.findChild(QObject, "clearHistoryDialog")
    assert dialog is not None and dialog.property("visible")
    _click(window, "clearHistoryCancel")
    QTest.qWait(150)
    assert path.exists()
    _click(window, "clearHistoryButton")
    _click(window, "clearHistoryConfirm")
    QTest.qWait(180)
    assert not path.exists()
    assert window.property("currentPage") == 0
    settings = window.findChild(QObject, "settingsDialog")
    assert settings is not None and not settings.property("visible")
    window.close()
    controller.close()


def test_settings_section_and_window_controls_animate(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=False, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1440)
    QTest.qWait(100)
    _click(window, "settingsButton")
    body = _find(window, "generalSettingsSection-body")
    assert body.height() == 0
    _click(window, "generalSettingsSection-header")
    QTest.qWait(70)
    midway = body.height()
    QTest.qWait(300)
    assert 0 < midway < body.height()
    settings = window.findChild(QObject, "settingsDialog")
    assert settings is not None
    settings.close()
    QTest.qWait(130)

    shell = _find(window, "applicationShell")
    _click(window, "minimizeWindowButton")
    QTest.qWait(40)
    assert shell.property("opacity") < 1
    QTest.qWait(130)
    assert window.visibility() == QQuickWindow.Visibility.Minimized
    window.showNormal()
    QTest.qWait(120)
    assert shell.property("opacity") == 1

    controller.toastRequested.emit("history.cleared")
    toast = _find(window, "appToast")
    QTest.qWait(200)
    assert toast.isVisible()
    QTest.qWait(3350)
    assert toast.isVisible()  # Fade-out starts before the toast is removed.
    QTest.qWait(350)
    assert not toast.isVisible()
    window.close()
    controller.close()


def test_open_then_analyze_keeps_result_visible(tmp_path: Path, qapp: object) -> None:
    controller = AnalysisController(
        async_enabled=True,
        history_store=HistoryStore(
            tmp_path / "history" / "history.json", enabled=True, persist_settings=False
        ),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    sample = tmp_path / "sample.cfg"
    sample.write_text("Huawei Versatile Routing Platform\nsysname PACKAGED_OPEN_OK\n", encoding="utf-8")
    controller.loadFile(str(sample))
    QTest.qWait(150)
    _click(window, "analyzeButton")
    for _ in range(80):
        if not controller.busy:
            break
        QTest.qWait(100)
    assert controller.resultCurrent, (
        controller.statusMessage,
        controller.sourceText,
        controller.editorText,
        controller.busy,
        len(controller._history_store.entries),
    )
    assert _find(window, "analysisPanel").property("resultCurrent")
    assert controller.resultTimestamp
    window.close()
    controller.close()
