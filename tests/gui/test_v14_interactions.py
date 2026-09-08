from __future__ import annotations

from collections.abc import Callable, Iterator
from itertools import pairwise

import pytest
from PySide6.QtCore import QCoreApplication, QElapsedTimer, QMetaObject, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QContextMenuEvent, QWheelEvent
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController


def descendants(item: QQuickItem) -> list[QQuickItem]:
    return item.childItems() + [c for child in item.childItems() for c in descendants(child)]


def find(window: QQuickWindow, name: str) -> QQuickItem:
    return next(i for i in descendants(window.contentItem()) if i.objectName() == name)


def center(item: QQuickItem) -> QPoint:
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


def click(window: QQuickWindow, name: str) -> None:
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=center(find(window, name)))
    QTest.qWait(320)


def wait_until(predicate: Callable[[], bool]) -> None:
    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < 3000:
        QTest.qWait(20)
    assert predicate(), "UI did not settle into its expected state"


@pytest.fixture
def gui(qapp: object) -> Iterator[tuple[QQuickWindow, AnalysisController, object]]:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1440)
    window.setHeight(900)
    QTest.qWait(400)
    yield window, controller, engine
    window.close()
    controller.close()


def test_empty_analyze_disabled_and_results_live_in_panel(gui: tuple) -> None:
    window, controller, _ = gui
    assert not find(window, "analyzeButton").isEnabled()
    controller.sourceText = " \n\t"
    QCoreApplication.processEvents()
    assert not find(window, "analyzeButton").isEnabled()
    controller.sourceText = "sysname SYNTHETIC\ntelnet server enable\n"
    click(window, "analyzeButton")
    assert controller.resultCurrent
    assert find(window, "analysisStatus").isVisible()
    assert not find(window, "activeSeverityFilter").isVisible()
    click(window, "severityFilter-WARNING")
    assert find(window, "activeSeverityFilter").isVisible()
    click(window, "severityFilter-WARNING")
    assert not find(window, "activeSeverityFilter").isVisible()


def test_settings_is_modal_and_sidebar_collapses(gui: tuple) -> None:
    window, _, engine = gui
    click(window, "sidebarToggle")
    assert engine.rootContext().contextProperty("preferences").values["sidebarExpanded"] is False
    click(window, "settingsButton")
    dialog = window.findChild(QObject, "settingsDialog")
    assert dialog.property("visible")
    assert dialog.property("modal")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.qWait(200)
    assert not dialog.property("visible")
    assert window.property("currentPage") == 0


def test_compact_sidebar_expands_over_workspace_and_dismisses(gui: tuple) -> None:
    window, _, _ = gui
    window.setWidth(960)
    QTest.qWait(350)
    rail = find(window, "navigationRail")
    editor = find(window, "configurationEditor")
    wait_until(lambda: rail.width() == 80 and rail.parentItem().width() == 80)
    editor_position = editor.mapToScene(QPointF(0, 0))
    assert rail.width() == 80
    click(window, "sidebarToggle")
    wait_until(lambda: rail.width() == 260)
    assert rail.width() == 260
    assert editor.mapToScene(QPointF(0, 0)) == editor_position
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(940, 100))
    wait_until(lambda: rail.width() == 80)
    assert rail.width() == 80
    click(window, "sidebarToggle")
    click(window, "navigation-2")
    wait_until(lambda: rail.width() == 80)
    assert window.property("currentPage") == 2
    assert rail.width() == 80


def test_hide_and_restore_all_panels_preserves_both_editors(gui: tuple) -> None:
    window, controller, engine = gui
    controller.sourceText = "sysname SOURCE\n"
    scratch = find(window, "temporaryTextArea")
    scratch.setProperty("text", "scratch text only")
    preferences = engine.rootContext().contextProperty("preferences")
    for key in ("configuration", "diagnostics", "temporary"):
        click(window, "panelsButton")
        click(window, "panelToggle-" + key)
    assert preferences.values["panels"] == []
    for name in ("configurationEditor", "analysisPanel", "temporaryEditor"):
        assert not find(window, name).isVisible()
    preferences.setValue("panels", ["configuration", "diagnostics", "temporary"])
    QTest.qWait(300)
    assert scratch.property("text") == "scratch text only"
    assert controller.sourceText == "sysname SOURCE\n"


def test_real_header_drag_reorders_cards_without_rebuilding_editor(gui: tuple) -> None:
    window, controller, engine = gui
    controller.sourceText = "sysname SOURCE\n"
    editor = find(window, "configurationTextArea")
    start = center(find(window, "configurationTextAreaHeaderGrip"))
    end = center(find(window, "temporaryTextAreaHeaderGrip"))
    QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=start)
    for part in range(1, 11):
        position = start + (end - start) * (part / 10)
        QTest.mouseMove(window, position, delay=25)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=end)
    QTest.qWait(400)
    order = engine.rootContext().contextProperty("preferences").values["panelOrder"]
    assert order == ["diagnostics", "temporary", "configuration"]
    assert find(window, "configurationTextArea") is editor
    assert editor.property("text") == "sysname SOURCE\n"


def test_gutter_grows_by_digits_and_wheel_changes_only_target_editor(gui: tuple) -> None:
    window, controller, _ = gui
    gutter = find(window, "configurationTextAreaGutter")
    widths = []
    for lines in (1, 10, 100, 1000, 10000):
        controller.sourceText = "\n" * (lines - 1)
        QTest.qWait(30)
        widths.append(gutter.width())
    assert widths[0] < 30
    assert all(b > a for a, b in pairwise(widths))
    editor = find(window, "configurationEditor")
    original = editor.property("editorFontSize")
    viewport = find(window, "configurationTextAreaViewport")
    position = QPointF(center(viewport))
    event = QWheelEvent(
        position,
        position,
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QCoreApplication.sendEvent(window, event)
    QTest.qWait(100)
    assert editor.property("editorFontSize") == original + 1
    assert find(window, "temporaryEditor").property("editorFontSize") == original
    assert editor.property("zoomModified")
    assert QMetaObject.invokeMethod(editor, "resetZoom")
    assert editor.property("editorFontSize") == original
    assert not editor.property("zoomModified")


def test_click_anywhere_clears_previous_selection(gui: tuple) -> None:
    window, _, _ = gui
    title = find(window, "checkPageTitle")
    title.forceActiveFocus()
    assert QMetaObject.invokeMethod(title, "selectAll")
    assert title.property("selectedText")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(window.width() - 10, 100))
    QTest.qWait(50)
    assert title.property("selectedText") == ""


def test_editor_context_menu_is_chinese_and_reset_is_last(gui: tuple) -> None:
    window, controller, engine = gui
    engine.rootContext().contextProperty("i18n").language = "zh_CN"
    controller.sourceText = "sysname CONTEXT\n"
    panel = find(window, "configurationEditor")
    panel.setProperty("zoomModified", True)
    editor = find(window, "configurationTextArea")
    position = center(find(window, "configurationTextAreaViewport"))
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, position, position)
    QCoreApplication.sendEvent(window, event)
    QTest.qWait(250)
    reset = find(window, "resetEditorZoom")
    assert reset.isVisible()
    assert reset.property("text") == "恢复默认大小"
    items = [
        item.property("text")
        for item in descendants(window.contentItem())
        if item.isVisible() and item.property("text") in ("复制", "撤销", "粘贴")
    ]
    assert set(items) == {"复制", "撤销", "粘贴"}
    click(window, "resetEditorZoom")
    assert not panel.property("zoomModified")
    assert editor.property("text") == controller.sourceText


def test_export_cancel_and_outside_click_never_open_save_dialog(gui: tuple) -> None:
    window, controller, _ = gui
    controller.sourceText = "sysname EXPORT\n"
    controller.analyzeConfig()
    click(window, "exportButton")
    dialog = window.findChild(QObject, "exportOptionsDialog")
    assert dialog.property("visible")
    click(window, "exportCancel")
    assert not dialog.property("visible")
    assert controller._export_payload is None
    click(window, "exportButton")
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.qWait(200)
    assert not dialog.property("visible")
    assert controller._export_payload is None


def test_confirm_export_opens_system_save_flow(gui: tuple) -> None:
    window, controller, _ = gui
    controller.sourceText = "sysname EXPORT-CONFIRM\n"
    controller.analyzeConfig()
    click(window, "exportButton")
    click(window, "exportConfirm")
    save = window.findChild(QObject, "exportSaveDialog")
    assert save.property("visible")
    assert controller._export_payload is not None
    QMetaObject.invokeMethod(save, "reject")
    QTest.qWait(200)
    assert controller._export_payload is None


def test_actual_font_and_theme_bindings_are_valid(gui: tuple) -> None:
    window, _, engine = gui
    preferences = engine.rootContext().contextProperty("preferences")
    preferences.setValue("themeMode", 1)
    preferences.setValue("panelTitle", "Synthetic Panel Title")
    QTest.qWait(100)
    assert window.title() == "Synthetic Panel Title"
    title_font = find(window, "checkPageTitle").property("font")
    assert title_font.families()[:2] == ["Roboto", "Noto Sans SC"]
    expression = QQmlExpression(qmlContext(window), window, "Colors.primaryForeground")
    value, _ = expression.evaluate()
    assert value == QColor("#ffffff")
    preferences.setValue("themeColor", "teal")
    expression = QQmlExpression(qmlContext(window), window, "Colors.primary")
    value, _ = expression.evaluate()
    assert value == QColor("#006a6a")


@pytest.mark.parametrize("width", [960, 1280, 1920])
def test_workspace_cards_and_toolbar_fit_multiple_widths(gui: tuple, width: int) -> None:
    window, controller, engine = gui
    engine.rootContext().contextProperty("i18n").language = "en"
    controller.sourceText = "sysname WIDTH\ntelnet server enable\n"
    controller.analyzeConfig()
    window.setWidth(width)
    QTest.qWait(500)
    split = find(window, "workspaceSplitView")
    for name in ("configurationEditor", "analysisPanel", "temporaryEditor"):
        card = find(window, name)
        assert card.x() >= 0
        assert card.x() + card.width() <= split.width() + 1
    analyze_button = find(window, "analyzeButton")
    assert analyze_button.mapToScene(QPointF(analyze_button.width(), 0)).x() <= window.width()
