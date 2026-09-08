from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QMetaObject, QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine, qml_root
from netconfiglint.gui.controllers import AnalysisController


def _descendants(item: QQuickItem) -> list[QQuickItem]:
    children = item.childItems()
    return children + [grandchild for child in children for grandchild in _descendants(child)]


def _visual_by_name(window: QQuickWindow, name: str) -> QQuickItem:
    return next(item for item in _descendants(window.contentItem()) if item.objectName() == name)


def test_main_qml_loads_offscreen(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    assert engine.rootObjects(), "Main.qml failed to create an ApplicationWindow"
    controller.close()


def test_diagnostic_delegate_maps_model_roles_to_visible_card(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    controller.sourceText = "sysname SYNTHETIC-LAB\ntelnet server enable\n"
    controller.analyzeConfig()
    QCoreApplication.processEvents()
    QTest.qWait(100)

    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)

    cards = [
        child for child in _descendants(window.contentItem()) if child.objectName() == "diagnosticIssueCard"
    ]
    telnet = next(card for card in cards if card.property("ruleIdentifier") == "HUA-SEC-002")
    assert telnet.property("severityValue") == "WARNING"
    assert telnet.property("sourceLine") == 2
    assert telnet.property("diagnosticMessage") == "The Telnet server is enabled."
    controller.close()


def test_workspace_is_three_resizable_columns_with_visible_editor_viewports(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1280)
    window.setHeight(800)
    QCoreApplication.processEvents()
    QTest.qWait(100)

    configuration = _visual_by_name(window, "configurationEditor")
    diagnostics = _visual_by_name(window, "analysisPanel")
    temporary = _visual_by_name(window, "temporaryEditor")
    assert configuration.parentItem() is diagnostics.parentItem() is temporary.parentItem()
    assert configuration.x() + configuration.width() + 8 <= diagnostics.x()
    assert diagnostics.x() + diagnostics.width() + 8 <= temporary.x()
    assert min(configuration.width(), diagnostics.width(), temporary.width()) >= 240

    header = _visual_by_name(window, "configurationTextAreaHeader")
    viewport = _visual_by_name(window, "configurationTextAreaViewport")
    editor = _visual_by_name(window, "configurationTextArea")
    assert header.height() >= 60
    assert viewport.y() >= header.height()
    assert editor.width() >= viewport.width()
    assert editor.height() >= viewport.height()

    controller.sourceText = "sysname TEST\n" + "description " + "x" * 100
    QCoreApplication.processEvents()
    QTest.qWait(50)
    assert editor.width() > viewport.width()
    controller.close()


def test_severity_badges_replace_combobox_and_toggle_filter(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    controller.sourceText = "sysname SYNTHETIC-LAB\ntelnet server enable\n"
    controller.analyzeConfig()
    QCoreApplication.processEvents()
    QTest.qWait(100)

    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    panel = _visual_by_name(window, "analysisPanel")
    chips = {
        item.objectName() for item in _descendants(panel) if item.objectName().startswith("severityFilter-")
    }
    assert chips == {
        "severityFilter-ERROR",
        "severityFilter-WARNING",
        "severityFilter-INFO",
        "severityFilter-UNKNOWN",
    }
    card = next(
        item
        for item in _descendants(panel)
        if item.objectName() == "diagnosticIssueCard" and item.property("ruleIdentifier") == "HUA-SEC-002"
    )
    empty_state = _visual_by_name(panel.window(), "analysisEmptyState")
    panel.setProperty("severityFilter", "ERROR")
    QCoreApplication.processEvents()
    assert not card.parentItem().isVisible()
    assert empty_state.isVisible()
    panel.setProperty("severityFilter", "WARNING")
    QCoreApplication.processEvents()
    QTest.qWait(100)
    assert any(
        item.objectName() == "diagnosticIssueCard" and item.isVisible() for item in _descendants(panel)
    )
    assert not empty_state.isVisible()

    warning_chip = _visual_by_name(window, "severityFilter-WARNING")
    panel.setProperty("severityFilter", "ALL")
    position = warning_chip.mapToScene(QPointF(warning_chip.width() / 2, warning_chip.height() / 2))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=position.toPoint())
    QCoreApplication.processEvents()
    assert panel.property("severityFilter") == "WARNING"
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=position.toPoint())
    QCoreApplication.processEvents()
    assert panel.property("severityFilter") == "ALL"
    controller.close()


def test_mode_dialog_stays_inside_window_and_options_have_room(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    dialog = window.findChild(QObject, "modeSelectionDialog")
    assert dialog is not None
    assert QMetaObject.invokeMethod(dialog, "open")
    QCoreApplication.processEvents()
    QTest.qWait(220)

    assert dialog.property("visible") is True
    assert dialog.property("width") <= window.width() - 32
    for value in ("snippet", "full", "snapshot"):
        option = _visual_by_name(window, f"modeOption-{value}")
        assert option.width() > 480
        assert option.height() >= 52
    controller.close()


def test_theme_defines_required_design_tokens() -> None:
    colors = (qml_root() / "theme" / "Colors.qml").read_text(encoding="utf-8")
    spacing = (qml_root() / "theme" / "Spacing.qml").read_text(encoding="utf-8")
    typography = (qml_root() / "theme" / "Typography.qml").read_text(encoding="utf-8")
    analysis = (qml_root() / "analysis" / "AnalysisPanel.qml").read_text(encoding="utf-8")

    for token in ("primary", "surfaceContainer", "error", "warning", "success", "info"):
        assert f"property color {token}" in colors
    for token in ("xxs", "xs", "sm", "md", "lg", "xl", "radiusCard"):
        assert f"property int {token}" in spacing
    assert "fontPalette.fonts" in typography
    assert "ComboBox" not in analysis


def test_qml_resources_are_package_relative() -> None:
    main = (qml_root() / "Main.qml").read_text(encoding="utf-8")
    assert "C:\\Users" not in main
    assert Path(qml_root() / "Main.qml").is_file()
