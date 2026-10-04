"""Final coverage labels and saved workspace layout use the rendered application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint import analyze
from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore
from netconfiglint.gui.preferences import Preferences


def wait_for(predicate: Callable[[], bool]) -> None:
    for _ in range(200):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate()


def items(item: QQuickItem) -> list[QQuickItem]:
    return [item] + [child for direct in item.childItems() for child in items(direct)]


def find(window: QQuickWindow, name: str) -> QQuickItem:
    candidate = window.findChild(QQuickItem, name)
    if candidate is None:
        candidate = next(item for item in items(window.contentItem()) if item.objectName() == name)
    return candidate


def click(window: QQuickWindow, name: str) -> None:
    item = find(window, name)
    ancestor = item.parentItem()
    while ancestor is not None:
        if ancestor.metaObject().indexOfProperty("contentY") >= 0:
            point = item.mapToItem(ancestor, QPointF(item.width() / 2, item.height() / 2))
            scroll = ancestor.property("contentY") + point.y() - ancestor.height() / 2
            limit = max(0, ancestor.property("contentHeight") - ancestor.height())
            ancestor.setProperty("contentY", max(0, min(limit, scroll)))
        ancestor = ancestor.parentItem()
    QTest.qWait(30)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    assert 0 <= point.x() < window.width() and 0 <= point.y() < window.height()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)


def open_desktop(tmp_path: Path, width: int = 1600) -> list:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.show()
    window.requestActivate()
    assert QTest.qWaitForWindowExposed(window, 2000)
    assert QTest.qWaitForWindowActive(window, 2000)
    window.setWidth(width)
    wait_for(lambda: find(window, "configurationEditor").width() > 200)
    QTest.qWait(200)
    return [window, engine, controller]


@pytest.fixture
def desktop(qapp: object, tmp_path: Path):
    Preferences().setValue("windowWidth", 1600)
    session = open_desktop(tmp_path)
    yield session
    dispose_engine(qapp, session[1], session[2])


def test_saved_panel_dimensions_and_reset_are_configuration_free(qapp: object) -> None:
    preferences = Preferences()
    preferences.setValue("themeColor", "teal")
    preferences.setValue("panelWidths", [700, 310, 270])
    preferences.setValue("panelHeights", [500, 600, 400])
    preferences.setValue("panelOrder", ["temporary", "configuration", "diagnostics"])
    preferences.setValue("panels", ["configuration"])
    restored = Preferences()
    assert restored.values["panelWidths"] == [700, 310, 270]
    assert restored.values["panelHeights"] == [500, 600, 400]
    for invalid in ([1, 2, 3], [540, float("nan"), 300], [540, "configuration text", 300], [True, 340, 300]):
        restored.setValue("panelWidths", invalid)
    assert restored.values["panelWidths"] == [700, 310, 270]
    restored.resetWorkspaceLayout()
    after_reset = Preferences()
    for key in ("panels", "panelOrder", "panelWidths", "panelHeights"):
        assert after_reset.values[key] == Preferences.DEFAULTS[key]
    assert after_reset.values["themeColor"] == "teal"


@pytest.mark.parametrize("width", [1600, 640])
def test_real_splitter_drag_is_saved_and_reset_menu_restores_layout(
    desktop: list, qapp: object, tmp_path: Path, width: int
) -> None:
    window, engine, _ = desktop
    window.setWidth(width)
    QTest.qWait(200)
    preferences = engine.rootContext().contextProperty("preferences")
    configuration = find(window, "configurationEditor")
    diagnostics = find(window, "analysisPanel")
    wait_for(lambda: diagnostics.width() >= 240)
    narrow = width == 640
    before = configuration.height() if narrow else diagnostics.width()
    point = QPointF(100, configuration.height() + 8) if narrow else QPointF(configuration.width() + 8, 100)
    if narrow:
        flickable = find(window, "workspaceScrollView").property("contentItem")
        handle_y = configuration.mapToItem(flickable, point).y()
        flickable.setProperty("contentY", flickable.property("contentY") + handle_y - flickable.height() / 2)
        QTest.qWait(50)
    handle = configuration.mapToScene(point).toPoint()
    assert 0 <= handle.x() < window.width() and 0 <= handle.y() < window.height(), handle
    offset = QPointF(0, -45).toPoint() if narrow else QPointF(-45, 0).toPoint()
    QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=handle)
    assert find(window, "workspaceSplitView").property("resizing"), (
        handle,
        configuration.height(),
        diagnostics.height(),
        configuration.y(),
        diagnostics.y(),
    )
    QTest.mouseMove(window, handle + offset, delay=30)
    QTest.qWait(30)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=handle + offset)
    dimension = "panelHeights" if narrow else "panelWidths"
    saved_index = 0 if narrow else 1

    def current_size() -> float:
        return configuration.height() if narrow else diagnostics.width()

    wait_for(lambda: abs(current_size() - before) > 20)
    wait_for(lambda: abs(preferences.values[dimension][saved_index] - current_size()) < 2)
    saved_size = current_size()
    assert Preferences().values[dimension] == preferences.values[dimension]
    window.close()
    dispose_engine(qapp, engine, desktop[2])
    desktop[:] = open_desktop(tmp_path, width)
    window, engine, _ = desktop
    preferences = engine.rootContext().contextProperty("preferences")
    configuration = find(window, "configurationEditor")
    diagnostics = find(window, "analysisPanel")
    wait_for(lambda: abs(current_size() - saved_size) < 2)
    preferences.setValue("panelOrder", ["temporary", "configuration", "diagnostics"])
    preferences.setValue("panels", ["configuration"])
    wait_for(lambda: not diagnostics.isVisible())
    click(window, "panelsButton")
    wait_for(lambda: find(window, "resetLayoutButton").isVisible())
    click(window, "resetLayoutButton")
    default_size = 480 if narrow else 340
    wait_for(lambda: diagnostics.isVisible() and abs(current_size() - default_size) < 2)
    assert preferences.values["panelOrder"] == Preferences.DEFAULTS["panelOrder"]
    assert preferences.values["panelWidths"] == Preferences.DEFAULTS["panelWidths"]
    if not narrow:
        assert find(window, "configurationEditor").x() < find(window, "analysisPanel").x()


@pytest.mark.parametrize(
    "language,expected", [("zh_CN", "仅识别命令族"), ("en", "Command family recognized only")]
)
def test_pending_dialog_translates_actual_catalogued_status(
    desktop: tuple, language: str, expected: str
) -> None:
    window, engine, controller = desktop
    engine.rootContext().contextProperty("i18n").setProperty("language", language)
    controller.vendor = "h3c"
    controller.sourceText = "lldp timer nonsense\n"
    controller.analyzeConfig()
    assert controller.coverage["pending_line_details"][0]["status"] == "catalogued_only"
    button = find(window, "pendingLinesButton")
    wait_for(button.isVisible)
    click(window, "pendingLinesButton")
    wait_for(lambda: window.findChild(QObject, "pendingLinesDialog").property("visible"))
    wait_for(lambda: expected in str(find(window, "pendingLine-1").property("text")))


def test_context_only_pending_is_counted_and_can_be_located(desktop: tuple) -> None:
    window, _, controller = desktop
    controller.vendor = "h3c"
    controller.sourceText = "sysname LAB\n"
    controller.analyzeConfig()
    result = analyze(controller.sourceText, vendor="h3c")
    result.config.context_unknown_lines.append(SourceRange(1))
    assert result.coverage["pending"] == 1
    assert not any(result.coverage[key] for key in ("catalogued", "unparsed", "unsupported"))
    find(window, "analysisPanel").setProperty("coverage", result.coverage)
    button = find(window, "pendingLinesButton")
    wait_for(button.isVisible)
    assert "(1)" in str(button.property("text"))
    click(window, "pendingLinesButton")
    wait_for(lambda: "context_required" not in str(find(window, "pendingLine-1").property("text")))
