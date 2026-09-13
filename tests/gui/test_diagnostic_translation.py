from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.gui.i18n.diagnostics import translate_diagnostic


def test_every_fixture_diagnostic_has_translated_prose() -> None:
    root = Path(__file__).parents[1] / "fixtures" / "huawei"
    checked = 0
    for path in root.rglob("*.cfg"):
        source = path.read_text(encoding="utf-8")
        for mode in ("full", "snippet", "snapshot"):
            for diagnostic in analyze(source, mode=mode, vendor="huawei").diagnostics:
                for value in (diagnostic.message, diagnostic.explanation, diagnostic.suggested_fix):
                    assert translate_diagnostic(value) != value, (path.name, diagnostic.rule_id, value)
                    checked += 1
    assert checked > 300


@pytest.mark.parametrize("next_table", ["vpn-instance", "vpn-instance BLUE", "vpn-instance BLUE unknown"])
def test_huawei_next_table_parser_diagnostics_are_localized(next_table: str) -> None:
    result = analyze(f"ip route-static 192.0.2.0 24 {next_table}", mode="full", vendor="huawei")
    diagnostics = [item for item in result.diagnostics if item.rule_id == "HUA-ROUTE-001"]
    assert diagnostics
    for item in diagnostics:
        for prose in (item.message, item.explanation, item.suggested_fix):
            assert translate_diagnostic(prose) != prose


def test_template_placeholders_are_preserved_exactly() -> None:
    path = Path(__file__).parents[2] / "netconfiglint/gui/i18n/diagnostics_zh.json"
    templates = json.loads(path.read_text(encoding="utf-8"))
    for source, translated in templates.items():
        assert sorted(re.findall(r"\{\d+\}", source)) == sorted(re.findall(r"\{\d+\}", translated))
    name = "SPECIAL-{1}-命令-10.0.0.1"
    value = f"Route-policy references undefined ip-prefix {name}."
    assert name in translate_diagnostic(value)
    assert translate_diagnostic("port trunk allow-pass vlan 100") == "port trunk allow-pass vlan 100"
