from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netconfiglint import analyze
from netconfiglint.vendors.huawei.rules import HUAWEI_RULES

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "huawei" / "rules"
RULE_CASES = tuple(sorted(path.name for path in FIXTURE_ROOT.iterdir() if path.is_dir()))


def _read_case(rule_id: str, name: str) -> str:
    return (FIXTURE_ROOT / rule_id / name).read_text(encoding="utf-8")


def _read_expected(rule_id: str) -> list[dict[str, Any]]:
    value = json.loads(_read_case(rule_id, "expected.json"))
    assert isinstance(value, list)
    return value


@pytest.mark.parametrize("rule_id", RULE_CASES)
def test_rule_reports_expected_invalid_diagnostic(rule_id: str) -> None:
    diagnostics = analyze(_read_case(rule_id, "invalid.cfg"), "full").diagnostics
    actual = [item.to_dict() for item in diagnostics if item.rule_id == rule_id]

    expected = _read_expected(rule_id)
    assert len(actual) == len(expected)
    for expected_item, actual_item in zip(expected, actual, strict=True):
        assert {key: actual_item[key] for key in expected_item} == expected_item


@pytest.mark.parametrize("rule_id", RULE_CASES)
def test_rule_accepts_valid_fixture(rule_id: str) -> None:
    diagnostics = analyze(_read_case(rule_id, "valid.cfg"), "full").diagnostics
    assert rule_id not in {item.rule_id for item in diagnostics}


def test_every_registered_rule_has_complete_fixture_set() -> None:
    registered = {rule.metadata.rule_id for rule in HUAWEI_RULES}
    assert set(RULE_CASES) == registered
    assert len(registered) >= 15
    for rule_id in registered:
        assert {path.name for path in (FIXTURE_ROOT / rule_id).iterdir()} == {
            "valid.cfg",
            "invalid.cfg",
            "expected.json",
        }
