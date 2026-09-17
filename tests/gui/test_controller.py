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


def test_controller_uses_bounded_read_only_preview_for_diagnostic_bundle(
    tmp_path: Path, qapp: object
) -> None:
    source = "\n".join(
        (
            "===============display current-configuration===============",
            "#",
            " version 7.1.070, Release 6715P06",
            " telnet server enable",
            "#",
            "return",
            "================================================",
            "===============display logbuffer size 512===============",
            "Overwritten messages: 2",
            "================================================",
        )
    )
    path = tmp_path / "diagnostic.txt"
    path.write_text(source, encoding="utf-8")
    controller = AnalysisController(async_enabled=False)
    jumps: list[tuple[int, int]] = []
    controller.jumpToLine.connect(lambda start, end: jumps.append((start, end)))

    controller.loadFile(str(path))
    assert controller.sourceText == source
    assert controller.editorReadOnly is True
    assert "display logbuffer" not in controller.editorText
    assert controller.prepareExport("configuration", "txt", False)
    configuration_path = tmp_path / "configuration.txt"
    controller.exportReport(str(configuration_path))
    exported = configuration_path.read_text(encoding="utf-8")
    assert "sysname SYNTHETIC" not in exported
    assert "telnet server enable" in exported
    assert "display logbuffer" not in exported
    controller.mode = "snapshot"
    controller.vendor = "h3c"
    controller.analyzeConfig()

    assert "Source lines 8-10" in controller.editorText
    assert controller.prepareExport("full", "txt", False)
    full_path = tmp_path / "full.txt"
    controller.exportReport(str(full_path))
    assert "display logbuffer size 512" in full_path.read_text(encoding="utf-8")
    row = next(
        index for index, item in enumerate(controller.diagnosticsModel.items) if item.rule_id == "H3C-OPS-010"
    )
    controller.requestJump(row)
    assert jumps[-1][0] > 5
    controller.close()
