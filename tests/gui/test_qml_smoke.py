from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine, qml_root
from netconfiglint.gui.controllers import AnalysisController


def test_main_qml_loads_offscreen(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    assert engine.rootObjects(), "Main.qml failed to create an ApplicationWindow"
    controller.close()


def test_diagnostic_delegate_maps_model_roles_to_visible_card(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    controller.sourceText = "sysname SYNTHETIC-LAB\ntelnet server enable\n"
    controller.analyzeConfig()
    QCoreApplication.processEvents()
    QTest.qWait(100)

    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)

    def descendants(item: QQuickItem) -> list[QQuickItem]:
        children = item.childItems()
        return children + [grandchild for child in children for grandchild in descendants(child)]

    cards = [
        child for child in descendants(window.contentItem()) if child.objectName() == "diagnosticIssueCard"
    ]
    telnet = next(card for card in cards if card.property("ruleIdentifier") == "HUA-SEC-002")
    assert telnet.property("severityValue") == "WARNING"
    assert telnet.property("sourceLine") == 2
    assert telnet.property("diagnosticMessage") == "The Telnet server is enabled."
    controller.close()


def test_theme_defines_required_design_tokens() -> None:
    colors = (qml_root() / "theme" / "Colors.qml").read_text(encoding="utf-8")
    spacing = (qml_root() / "theme" / "Spacing.qml").read_text(encoding="utf-8")
    typography = (qml_root() / "theme" / "Typography.qml").read_text(encoding="utf-8")

    for token in ("primary", "surfaceContainer", "error", "warning", "success", "info"):
        assert f"property color {token}" in colors
    for token in ("xxs", "xs", "sm", "md", "lg", "xl", "radiusCard"):
        assert f"property int {token}" in spacing
    assert "monoFamilies" in typography
    assert "sansFamilies" in typography


def test_qml_resources_are_package_relative() -> None:
    main = (qml_root() / "Main.qml").read_text(encoding="utf-8")
    assert "C:\\Users" not in main
    assert Path(qml_root() / "Main.qml").is_file()
