from netconfiglint import analyze
from netconfiglint.core.diagnostics import Severity

SOURCE = """sysname LAB
interface GigabitEthernet1/0/1
 port link-type trunk
 port trunk allow-pass vlan 100
"""


def test_full_mode_asserts_missing_reference() -> None:
    diagnostic = next(item for item in analyze(SOURCE, "full").diagnostics if item.rule_id == "HUA-VLAN-001")
    assert diagnostic.severity == Severity.ERROR
    assert diagnostic.source.line == 4


def test_snippet_mode_is_conservative() -> None:
    diagnostic = next(
        item for item in analyze(SOURCE, "snippet").diagnostics if item.rule_id == "HUA-VLAN-001"
    )
    assert diagnostic.severity == Severity.UNKNOWN
    assert "full configuration" in diagnostic.explanation.lower()
