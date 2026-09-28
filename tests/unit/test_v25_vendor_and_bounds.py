"""Counterexamples for vendor isolation, live evidence and input bounds."""

from __future__ import annotations

import ast
from pathlib import Path
from time import perf_counter

import pytest

from netconfiglint import analyze
from netconfiglint.core.analyzer.control import AnalysisLimits
from netconfiglint.core.diagnostics import Confidence, Severity
from netconfiglint.core.input import decode_network_bytes
from netconfiglint.vendors.h3c.parser.snapshot_parser import _sections

ROOT = Path(__file__).resolve().parents[2]


def test_vendor_implementation_has_no_foreign_vendor_imports() -> None:
    for vendor in ("h3c", "huawei"):
        for path in (ROOT / "netconfiglint/vendors" / vendor).rglob("*.py"):
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                modules = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [item.name for item in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                for module in modules:
                    if module.startswith("netconfiglint.vendors."):
                        assert module.startswith(f"netconfiglint.vendors.{vendor}."), (path, module)
    assert not (ROOT / "netconfiglint/vendors/h3c/rules/adapter.py").exists()
    dispatcher = (ROOT / "netconfiglint/core/analyzer/views.py").read_text("utf-8")
    assert "plugin.key" not in dispatcher
    assert "vendors.h3c" not in dispatcher and "vendors.huawei" not in dispatcher


def test_h3c_1100_issues_are_charged_once() -> None:
    source = "sysname SYNTHETIC\n" + "".join(
        f"interface GigabitEthernet1/0/{index}\n port access vlan 99\n#\n" for index in range(1, 1101)
    )
    result = analyze(source, "full", "h3c")
    assert result.coverage["complete"]
    issues = [item for item in result.diagnostics if item.rule_id == "H3C-VLAN-002"]
    assert len(issues) == 1100
    assert len({item.source.line for item in issues}) == 1100
    assert all(not item.rule_id.startswith("HUA-") for item in result.diagnostics)


def test_full_checks_complete_huawei_operational_evidence() -> None:
    source = (
        "sysname SYNTHETIC\nbgp 65000\n peer 192.0.2.2 as-number 65001\n"
        " ipv4-family unicast\n  network 198.51.100.0 24\n#\n"
        "<SYNTHETIC>display bgp peer\n"
        "Peer V AS MsgRcvd MsgSent OutQ Up/Down State PrefRcv\n"
        "192.0.2.2 4 65001 0 0 0 00:00:01 Idle 0\n"
        "<SYNTHETIC>display ip routing-table\nRouting Tables: Public\n"
        "Destinations : 0 Routes : 0\n<SYNTHETIC>\n"
    )
    result = analyze(source, "full", "huawei")
    absent = next(item for item in result.diagnostics if item.rule_id == "HUA-BGP-002")
    assert (absent.severity, absent.confidence) == (Severity.ERROR, Confidence.VERIFIED)
    assert any(item.rule_id == "HUA-BGP-003" for item in result.diagnostics)


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_unknown_views_never_claim_semantic_completion(vendor: str) -> None:
    result = analyze("<SYNTHETIC>display unsupported\n% Unrecognized command\n", "view", vendor)
    assert not result.coverage["semantic_complete"]
    assert result.coverage["unparsed"] > 0
    assert all(item.severity == Severity.UNKNOWN for item in result.diagnostics)


@pytest.mark.parametrize("state_first", [True, False])
def test_two_way_without_local_role_context_is_unknown(state_first: bool) -> None:
    tail = "2-Way/DROther Vlan10" if state_first else "Vlan10 2-Way/DROther"
    result = analyze(f"<SYNTHETIC>display ospf peer\n192.0.2.2 192.0.2.2 1 30 {tail}\n", "view", "h3c")
    assert not any(item.rule_id == "H3C-OPS-008" for item in result.diagnostics)
    assert any(
        item.rule_id == "H3C-OPS-014" and item.severity == Severity.UNKNOWN for item in result.diagnostics
    )


def test_vty_class_and_range_are_both_evaluated() -> None:
    source = (
        "sysname SYNTHETIC\nline class vty\n protocol inbound telnet\n"
        " authentication-mode none\n#\nline vty 0 4\n protocol inbound ssh\n"
        " authentication-mode scheme\n#\n"
    )
    result = analyze(source, "full", "h3c")
    issues = [item for item in result.diagnostics if item.rule_id in {"H3C-SEC-009", "H3C-SEC-010"}]
    assert {item.rule_id for item in issues} == {"H3C-SEC-009", "H3C-SEC-010"}
    assert all(item.severity == Severity.UNKNOWN for item in issues)
    assert all("capacity unknown" in item.object_name for item in issues)


def test_vty_range_inherits_disabled_authentication() -> None:
    result = analyze(
        "line class vty\n authentication-mode none\n#\nline vty 5 15\n protocol inbound ssh\n#\n",
        "full",
        "h3c",
    )
    assert any(
        item.rule_id == "H3C-SEC-010"
        and item.object_name == "line vty 5 15"
        and item.severity == Severity.ERROR
        for item in result.diagnostics
    )


def test_ospf_silence_and_authentication_do_not_cross_scopes() -> None:
    source = (
        "sysname SYNTHETIC\nospf 1\n silent-interface all\n area 0.0.0.0\n"
        "  authentication-mode md5\n  network 192.0.2.0 0.0.0.255\n#\n"
        "ospf 2\n area 0.0.0.1\n  network 198.51.100.0 0.0.0.255\n#\n"
    )
    result = analyze(source, "full", "h3c")
    exposed = [item for item in result.diagnostics if item.rule_id == "H3C-OSPF-004"]
    unauthenticated = [item for item in result.diagnostics if item.rule_id == "H3C-OSPF-005"]
    assert exposed and unauthenticated
    assert all("OSPF 2" in item.object_name for item in [*exposed, *unauthenticated])
    undone = analyze(
        source.replace(" silent-interface all", " silent-interface all\n undo silent-interface all"),
        "full",
        "h3c",
    )
    assert any(item.rule_id == "H3C-OSPF-004" and "OSPF 1" in item.object_name for item in undone.diagnostics)


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_invalid_prefix_and_acl_parameters_are_not_verified(vendor: str) -> None:
    head = "ip prefix-list" if vendor == "h3c" else "ip ip-prefix"
    result = analyze(
        f"{head} BAD index 10 permit 999.999.999.999 999\n"
        "acl number 3000\n rule 5 permit tcp destination-port eq 999999\n#\n",
        "full",
        vendor,
    )
    assert any(item.rule_id.endswith("PARSE-PREFIX") for item in result.diagnostics)
    acl = next(iter(result.config.acls.values()))
    assert not next(iter(acl.rules.values())).syntax_known


def test_invalid_h3c_command_shapes_are_not_semantically_recognized() -> None:
    result = analyze("snmp-agent totally-invalid\nntp-service nonsense\nclock timezone\n", "full", "h3c")
    assert result.coverage["recognized"] == 0
    assert not result.coverage["semantic_complete"]


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_giant_numeric_input_returns_incomplete_result(vendor: str) -> None:
    name = "Vlan-interface" if vendor == "h3c" else "Vlanif"
    result = analyze("interface " + name + "9" * 5000 + "\n", "full", vendor)
    assert result.diagnostics
    assert any(item.severity in {Severity.ERROR, Severity.UNKNOWN} for item in result.diagnostics)


def test_section_scan_is_linear_and_budget_is_cooperative() -> None:
    source = "".join(f"=====display unsupported-{index}=====\nrow\n" for index in range(4000))
    started = perf_counter()
    sections = _sections(source)
    assert len(sections) == 4000
    assert all(len(rows) == 1 for _line, rows in sections.values())
    assert perf_counter() - started < 1.0
    result = analyze(source, "view", "h3c", limits=AnalysisLimits(max_work=100))
    assert not result.coverage["complete"]


@pytest.mark.parametrize("encoding,bom", [("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")])
def test_utf16_bom_exports_are_decoded_exactly(encoding: str, bom: bytes) -> None:
    result = decode_network_bytes(bom + "sysname 测试\r\n#\r\n".encode(encoding))
    assert result.text == "sysname 测试\n#\n"
    assert result.encoding == encoding and not result.recovered


def test_binary_and_utf32_input_are_rejected() -> None:
    for data in (b"sysname\x00bad", "sysname 测试".encode("utf-32")):
        with pytest.raises(ValueError):
            decode_network_bytes(data)
