from __future__ import annotations

from pathlib import Path

from netconfiglint.gui.controllers import AnalysisController

SOURCE = """sysname SYNTHETIC-LAB
interface GigabitEthernet1/0/1
 port link-type trunk
 port trunk allow-pass vlan 100
"""


def test_controller_calls_shared_analyzer_and_updates_models(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.sourceText = SOURCE
    controller.mode = "full"
    controller.analyzeConfig()

    assert controller.detection["vendor"] == "Huawei"
    assert set(controller.detection) == {"vendor"}
    assert controller.summary["ERROR"] == 1
    assert controller.diagnosticsModel.rowCount() == 1
    assert controller.statusMessage == "analysis.completed"
    controller.close()


def test_controller_jump_target_uses_diagnostic_source_line(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    captured: list[tuple[int, int]] = []
    controller.jumpToLine.connect(lambda start, end: captured.append((start, end)))
    controller.sourceText = SOURCE
    controller.analyzeConfig()
    controller.requestJump(0)

    assert captured == [(4, 4)]
    controller.close()


def test_controller_loads_utf8_file(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "synthetic.cfg"
    path.write_text("sysname SYNTHETIC-LAB\n", encoding="utf-8")
    controller = AnalysisController(async_enabled=False)
    controller.loadFile(str(path))

    assert controller.sourceText == "sysname SYNTHETIC-LAB\n"
    assert controller.fileName == "synthetic.cfg"
    controller.close()
