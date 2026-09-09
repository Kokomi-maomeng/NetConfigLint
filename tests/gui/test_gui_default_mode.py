"""The first GUI analysis uses snippet semantics and mode changes remain explicit."""

from netconfiglint.gui.controllers import AnalysisController


def test_gui_default_and_explicit_complete_configuration(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    try:
        assert controller.mode == "snippet"
        controller.vendor = "huawei"
        controller.sourceText = "interface GigabitEthernet1/0/1\n port default vlan 100\n"
        controller.analyzeConfig()
        assert controller.resultCurrent
        assert controller.summary["ERROR"] == 0
        assert controller.diagnosticsModel.rowCount() > 0
        controller.mode = "full"
        assert not controller.resultCurrent
        controller.analyzeConfig()
        assert controller.summary["ERROR"] == 1
        controller.mode = "snapshot"
        assert not controller.resultCurrent
        controller.mode = "snippet"
        controller.analyzeConfig()
        assert controller.summary["ERROR"] == 0
    finally:
        controller.close()
