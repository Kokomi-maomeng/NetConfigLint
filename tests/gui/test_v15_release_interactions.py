"""End-to-end release interactions across QML filtering, navigation and export."""

import json
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController


def descendants(item: QQuickItem) -> list[QQuickItem]:
    return item.childItems() + [child for parent in item.childItems() for child in descendants(parent)]


def test_filtered_card_click_jumps_to_original_source_and_export_keeps_all(
    qapp: object, tmp_path: Path
) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    controller.mode = "full"
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.setWidth(1440)
    window.setHeight(900)
    try:
        controller.sourceText = (
            "sysname SYNTHETIC\ninterface GigabitEthernet1/0/1\n port link-type trunk\n"
            " port trunk allow-pass vlan 100\n#\ntelnet server enable\n"
        )
        controller.analyzeConfig()
        QTest.qWait(300)
        items = descendants(window.contentItem())
        chip = next(item for item in items if item.objectName() == "severityFilter-WARNING")
        point = chip.mapToScene(QPointF(chip.width() / 2, chip.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        QTest.qWait(200)
        card = next(
            item
            for item in descendants(window.contentItem())
            if item.objectName() == "diagnosticIssueCard"
            and item.isVisible()
            and item.property("ruleIdentifier") == "HUA-SEC-002"
        )
        button = next(item for item in descendants(card) if str(item.property("text")).endswith("↗"))
        jumps = []
        controller.jumpToLine.connect(lambda start, end: jumps.append((start, end)))
        point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        QTest.qWait(100)
        assert jumps == [(6, 6)]
        editor = next(
            item for item in descendants(window.contentItem()) if item.objectName() == "configurationTextArea"
        )
        cursor = editor.property("cursorPosition")
        assert controller.sourceText[:cursor].count("\n") + 1 == 6
        assert controller.prepareExport("diagnostics", "json", True)
        target = tmp_path / "report.json"
        controller.exportReport(str(target))
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert {item["rule_id"] for item in payload["diagnostics"]} >= {"HUA-VLAN-001", "HUA-SEC-002"}
    finally:
        window.close()
        controller.close()
