"""Public entry points use conservative fragment semantics unless explicitly changed."""

import json
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.cli.main import main
from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.analyzer.api import analyze as analyze_direct
from netconfiglint.core.diagnostics import Severity

SOURCE = "interface GigabitEthernet1/0/1\n port default vlan 100\n"


@pytest.mark.parametrize("entrypoint", [analyze, analyze_direct])
def test_api_default_does_not_report_omitted_vlan_as_error(entrypoint: object) -> None:
    default = entrypoint(SOURCE, vendor="huawei")  # type: ignore[operator]
    complete = entrypoint(SOURCE, "full", "huawei")  # type: ignore[operator]
    assert default.mode == AnalysisMode.SNIPPET
    assert default.diagnostics
    assert all(item.severity != Severity.ERROR for item in default.diagnostics)
    assert any(
        item.rule_id == "HUA-VLAN-002" and item.severity == Severity.ERROR for item in complete.diagnostics
    )


def test_cli_default_is_snippet_in_result_and_exit_status(tmp_path: Path, capsys: object) -> None:
    source = tmp_path / "fragment.cfg"
    source.write_text(SOURCE, encoding="utf-8")
    assert main(["check", str(source), "--vendor", "huawei", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert payload["mode"] == "snippet"
    assert payload["diagnostics"]
    assert all(item["severity"] != "ERROR" for item in payload["diagnostics"])
