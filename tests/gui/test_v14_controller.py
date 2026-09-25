from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.i18n import TranslationController
from netconfiglint.gui.preferences import Preferences
from netconfiglint.vendors import registry

SOURCE = "sysname SYNTHETIC-LAB\ninterface GigabitEthernet1/0/1\n port trunk allow-pass vlan 100\n"


def test_empty_input_never_starts_a_worker_or_reports_failure(qapp: object) -> None:
    calls: list[str] = []
    controller = AnalysisController(async_enabled=False)
    controller.analysisFailed.connect(calls.append)
    for source in ("", " \n\t "):
        controller.sourceText = source
        controller.analyzeConfig()
        assert not controller.busy
        assert controller.statusMessage == ""
        assert not controller.resultCurrent
    assert not calls
    controller.close()


@pytest.mark.parametrize(
    "field,value", [("sourceText", SOURCE + "# changed"), ("mode", "full"), ("vendor", "huawei")]
)
def test_edits_invalidate_diagnostics_and_block_mismatched_export(
    qapp: object, field: str, value: str
) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.sourceText = SOURCE
    controller.analyzeConfig()
    assert controller.resultCurrent
    setattr(controller, field, value)
    assert not controller.resultCurrent
    assert controller.diagnosticsModel.rowCount() == 0
    assert controller.statusMessage == "analysis.changed"
    assert not controller.prepareExport("full", "json", False)
    assert controller.prepareExport("configuration", "txt", False)
    controller.close()


def test_outdated_worker_result_and_error_do_not_replace_current_input(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.sourceText = SOURCE
    controller._running_revision = controller._revision
    controller.sourceText = "sysname OTHER\n"
    result = analyze(SOURCE)
    controller._apply_result(result)
    assert not controller.resultCurrent
    assert controller.diagnosticsModel.rowCount() == 0
    controller._apply_error("sensitive source should never appear")
    assert controller.statusMessage == "analysis.changed"
    assert not controller.busy
    controller.close()


def test_worker_exception_has_localizable_failure_without_source_leak(qapp: object) -> None:
    def broken(source: str, mode: str, vendor: str) -> object:
        raise RuntimeError(source)

    controller = AnalysisController(analyzer=broken, async_enabled=False)  # type: ignore[arg-type]
    messages: list[str] = []
    controller.analysisFailed.connect(messages.append)
    controller.sourceText = SOURCE
    controller.analyzeConfig()
    assert messages == ["analysis.failed"]
    assert controller.statusMessage == "analysis.failed"
    assert SOURCE not in "".join(messages)
    assert not controller.resultCurrent
    controller.sourceText = SOURCE + "# edited\n"
    assert controller.statusMessage == "analysis.changed"
    controller.sourceText = ""
    assert controller.statusMessage == ""
    controller.close()


@pytest.mark.parametrize("scope", ["full", "configuration", "diagnostics"])
@pytest.mark.parametrize("format", ["json", "md", "txt"])
@pytest.mark.parametrize("first", [False, True])
def test_export_combinations_use_matching_snapshot(
    qapp: object, tmp_path: Path, scope: str, format: str, first: bool
) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.mode = "full"
    controller.translator = TranslationController(system_locale="zh_CN", persist_settings=False)
    controller.sourceText = SOURCE
    controller.analyzeConfig()
    assert controller.prepareExport(scope, format, first)
    controller.sourceText = "sysname CHANGED-AFTER-CONFIRM\n"
    path = tmp_path / f"report.{format}"
    controller.exportReport(str(path))
    output = path.read_text(encoding="utf-8")
    assert "CHANGED-AFTER-CONFIRM" not in output
    if format == "json":
        payload = json.loads(output)
        assert ("configuration" in payload) == (scope != "diagnostics")
        assert ("diagnostics" in payload) == (scope != "configuration")
        if scope != "diagnostics":
            assert payload["configuration"] == SOURCE
        if scope == "full" and first:
            assert payload["annotated_lines"][2]["counts"] == {"ERROR": 1}
    else:
        assert ("sysname SYNTHETIC-LAB" in output) == (scope != "diagnostics")
        assert ("HUA-VLAN-001" in output) == (scope != "configuration")
        if scope == "full":
            assert (output.index("诊断结果") < output.index("sysname")) == first
            assert ("[ERROR 1]" in output) == first
    controller.close()


def test_cancel_and_invalid_export_do_not_write_files(qapp: object, tmp_path: Path) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.sourceText = SOURCE
    assert controller.prepareExport("configuration", "txt", False)
    controller.cancelExport()
    path = tmp_path / "cancelled.txt"
    controller.exportReport(str(path))
    assert not path.exists()
    assert not controller.prepareExport("invalid", "json", False)
    assert not controller.prepareExport("configuration", "html", False)
    controller.close()


def test_preferences_validate_and_persist_without_configuration(qapp: object) -> None:
    preferences = Preferences()
    preferences.setValue("panelTitle", "  Synthetic Panel  ")
    preferences.setValue("themeColor", "teal")
    preferences.setValue("themeMode", 2)
    preferences.setValue("panels", [])
    preferences.setValue("panelOrder", ["temporary", "configuration", "diagnostics"])
    restored = Preferences()
    assert restored.values["panelTitle"] == "Synthetic Panel"
    assert restored.values["themeColor"] == "teal"
    assert restored.values["panels"] == ["configuration"]
    assert restored.values["panelOrder"] == ["temporary", "configuration", "diagnostics"]
    restored.setValue("themeMode", 99)
    restored.setValue("themeColor", "invalid")
    restored.setValue("panelOrder", ["temporary"])
    restored.setValue("sourceText", SOURCE)
    assert restored.values == preferences.values


def test_new_vendor_registration_reaches_controller_without_gui_conditionals(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = replace(registry.VENDOR_PLUGINS[0], key="synthetic_vendor", vendor_name="Synthetic Vendor")
    monkeypatch.setattr(registry, "VENDOR_PLUGINS", (*registry.VENDOR_PLUGINS, plugin))
    controller = AnalysisController(async_enabled=False)
    assert {"value": "synthetic_vendor", "label": "Synthetic Vendor"} in controller.vendorOptions
    controller.vendor = "synthetic_vendor"
    assert controller.vendor == "synthetic_vendor"
    controller.sourceText = SOURCE
    result = analyze(SOURCE)
    controller._running_revision = controller._revision
    controller._apply_result(replace(result, detection=replace(result.detection, vendor="Synthetic Vendor")))
    assert controller.detection == {"vendor": "Synthetic Vendor"}
    controller.close()
