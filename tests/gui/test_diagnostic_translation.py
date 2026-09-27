from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.gui.i18n.diagnostics import translate_diagnostic


def _static_prose(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            "".join(part.value if isinstance(part, ast.Constant) else "SYNTHETIC" for part in node.values)
        ]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [left + right for left in _static_prose(node.left) for right in _static_prose(node.right)]
    if isinstance(node, ast.IfExp):
        return _static_prose(node.body) + _static_prose(node.orelse)
    return []


def test_source_diagnostic_prose_has_chinese_templates() -> None:
    root = Path(__file__).parents[2] / "netconfiglint"
    checked = 0
    for path in root.rglob("*.py"):
        if "i18n" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id == "Diagnostic":
                fields = call.args[4:7]
            elif call.func.id == "missing_reference_diagnostic":
                fields = [
                    keyword.value
                    for keyword in call.keywords
                    if keyword.arg in {"full_message", "snippet_message", "explanation", "suggested_fix"}
                ]
            else:
                continue
            for field in fields:
                for value in _static_prose(field):
                    if len(value.split()) < 3 or value.startswith("SYNTHETIC"):
                        continue
                    assert translate_diagnostic(value) != value, (path.name, value)
                    checked += 1
    assert checked >= 200


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
