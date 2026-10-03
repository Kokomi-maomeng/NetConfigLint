"""Source mapping and conservative semantic regressions for the v3 UX audit."""

from __future__ import annotations

import json

import pytest

from netconfiglint import analyze
from netconfiglint.core.diagnostics import Severity
from netconfiglint.core.lexer import lex_lines, normalize_cli_line
from netconfiglint.vendors.huawei.parser.snapshot_parser import HuaweiSnapshotParser
from netconfiglint.vendors.registry import detect_vendor_plugin


@pytest.mark.parametrize(
    "source",
    [
        "sysname SW\ninterface GigabitEthernet1/0/1\n port access vlan 10\n",
        "version 7.1.070, Release 6715\nsysname SW\n",
        "stp global enable\nstp mode mstp\n",
        "acl basic 2000\n",
    ],
)
def test_distinctive_comware_inputs_are_detected(source: str) -> None:
    result = analyze(source)
    assert result.detection.vendor == "H3C"
    assert result.detection.model == "Unknown"
    assert result.detection.evidence


@pytest.mark.parametrize("source", ["sysname SW", "stp mode mstp", "interface GigabitEthernet1/0/1"])
def test_shared_inputs_stay_uncertain(source: str) -> None:
    assert detect_vendor_plugin(source) is None
    with pytest.raises(ValueError, match="Could not identify"):
        analyze(source)


def test_distinctive_mixed_vendor_inputs_stay_uncertain() -> None:
    source = "port access vlan 10\nport default vlan 20\n"
    assert detect_vendor_plugin(source) is None
    with pytest.raises(ValueError, match="Could not identify"):
        analyze(source)
    for banner in ("Huawei Versatile Routing Platform", "H3C Comware Software, Version 7.1.070"):
        assert detect_vendor_plugin(banner + "\n" + source) is None


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_terminal_prompts_preserve_arguments_and_source_lines(vendor: str) -> None:
    prefix = "[SW]" if vendor == "h3c" else "[~SW]"
    child = "[SW-GigabitEthernet1/0/1]" if vendor == "h3c" else "[*SW-GigabitEthernet1/0/1]"
    source = (
        f"{prefix} sysname SW\n{prefix} interface GigabitEthernet 1/0/1\n"
        f'{child} description "[unchanged] # as argument"\n'
        f"{child} ip address 999.1.1.1 255.255.255.0\n# human note\n"
    )
    result = analyze(source, "snippet", vendor)
    assert result.config.source_lines == tuple(source.splitlines())
    interface = result.config.interfaces["GigabitEthernet1/0/1"]
    assert interface.description == '"[unchanged] # as argument"'
    assert interface.ip_addresses[0][2].line == 4
    assert 5 not in result.coverage["pending_lines"]
    assert not result.coverage["pending_lines"]
    assert any(item.rule_id.endswith("IF-005") and item.source.line == 4 for item in result.diagnostics)


def test_terminal_normalization_has_exact_character_offset() -> None:
    raw = "  [SW-GigabitEthernet1/0/1] port trunk p "
    cleaned, offset = normalize_cli_line(raw)
    assert cleaned == "port trunk p "
    assert raw[offset:] == cleaned
    line = lex_lines(raw)[0]
    assert line.raw == raw
    assert line.prompt == "[SW-GigabitEthernet1/0/1]"
    for value in ['description "[SW] text"', 'peer 2001:db8::1 description "<x>"', "[2001:db8::1] x"]:
        assert normalize_cli_line(value)[0] == value


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_catalogued_unknown_and_unparsed_have_pending_line_inventory(vendor: str) -> None:
    source = "lldp timer nonsense\ninfo-center loghost 999.1.1.1\nunknown-protocol true\n"
    result = analyze(source, "snippet", vendor)
    assert not result.coverage["semantic_complete"]
    assert result.coverage["pending_lines"] == [1, 2, 3]
    assert result.coverage["pending"] == 3
    assert [item["line"] for item in result.coverage["pending_line_details"]] == [1, 2, 3]
    assert all("text" not in item for item in result.coverage["pending_line_details"])


def test_pending_inventory_does_not_copy_secrets_into_coverage() -> None:
    result = analyze("password cipher SYNTHETIC-SECRET", "snippet", "huawei")
    assert "SYNTHETIC-SECRET" not in json.dumps(result.coverage)


@pytest.mark.parametrize(
    ("vendor", "header", "command", "reset", "default", "active"),
    [
        (
            "h3c",
            "Bridge-Aggregation1",
            "link-aggregation mode dynamic",
            "undo link-aggregation mode",
            "static",
            "dynamic",
        ),
        ("huawei", "Eth-Trunk1", "mode lacp-static", "undo mode", "manual load-balance", "lacp-static"),
    ],
)
def test_aggregation_mode_last_value_reset_and_local_peer_uncertainty(
    vendor: str, header: str, command: str, reset: str, default: str, active: str
) -> None:
    source = f"interface {header}\n {command}\n"
    result = analyze(source, "full", vendor)
    assert result.config.interfaces[header].aggregation_mode == active
    assert result.coverage["pending"] == 0
    assert any(
        item.rule_id.endswith("IF-007") and item.severity == Severity.UNKNOWN for item in result.diagnostics
    )
    reset_result = analyze(source + f" {reset}\n", "full", vendor)
    interface = reset_result.config.interfaces[header]
    assert interface.aggregation_mode == default
    assert interface.aggregation_mode_origin == "reference_default"
    assert not any(item.rule_id.endswith("IF-007") for item in reset_result.diagnostics)
    restored = analyze(source + f" {reset}\n {command}\n", "full", vendor)
    assert restored.config.interfaces[header].aggregation_mode == active
    assert restored.config.interfaces[header].command_sources["aggregation_mode"].line == 4


@pytest.mark.parametrize(
    "vendor,command", [("h3c", "link-aggregation mode dynamic"), ("huawei", "mode lacp-static")]
)
def test_aggregation_mode_in_physical_interface_is_not_normalized(vendor: str, command: str) -> None:
    result = analyze(f"interface GigabitEthernet1/0/1\n {command}\n", "full", vendor)
    assert result.config.interfaces["GigabitEthernet1/0/1"].aggregation_mode is None
    assert 2 in result.coverage["pending_lines"]


def test_comware_routed_member_references_route_aggregation_separately() -> None:
    source = (
        "interface Route-Aggregation1\n link-aggregation mode dynamic\n#\n"
        "interface GigabitEthernet1/0/1\n port link-mode route\n port link-aggregation group 1\n#\n"
    )
    result = analyze(source, "full", "h3c")
    assert not any(item.rule_id == "H3C-IF-003" for item in result.diagnostics)
    assert result.config.interfaces["Route-Aggregation1"].aggregation_mode == "dynamic"
    assert any(item.rule_id == "H3C-IF-007" for item in result.diagnostics)
    mismatch = analyze(source.replace("Route-Aggregation1", "Bridge-Aggregation1"), "full", "h3c")
    assert any(item.rule_id == "H3C-IF-003" for item in mismatch.diagnostics)


def test_comware_static_keyword_outside_scoped_6715_syntax_remains_pending() -> None:
    result = analyze("interface Bridge-Aggregation1\n link-aggregation mode static\n", "full", "h3c")
    assert 2 in result.coverage["pending_lines"]


@pytest.mark.parametrize("interface_type", ["10GE", "25GE", "40GE", "100GE"])
def test_scoped_numeric_interface_types_share_spelling_and_vlan_checks(interface_type: str) -> None:
    variants = [f"{interface_type} 1/0/1", f"{interface_type}1/0/1", f"{interface_type.lower()}1/0/1"]
    for variant in variants:
        result = analyze(
            f"interface {variant}\n port link-type access\n port default vlan 10\n", "full", "huawei"
        )
        assert set(result.config.interfaces) == {f"{interface_type}1/0/1"}
        assert result.coverage["pending"] == 0
        assert any(item.rule_id == "HUA-VLAN-002" and item.source.line == 3 for item in result.diagnostics)
    for variant in variants:
        route = analyze(f"ip route-static 192.0.2.0 24 {variant}\n", "full", "huawei")
        assert route.config.static_routes[0].next_hop == f"{interface_type}1/0/1"
        snapshot = HuaweiSnapshotParser._interface(f"{variant} 192.0.2.1/24 up up", 7)
        assert snapshot is not None and snapshot.name == f"{interface_type}1/0/1"
        assert snapshot.source.line == 7


@pytest.mark.parametrize("header", ["10GE 1/0/1 unknown-view", "Foo 1/0/1", "100 10GE1/0/1", "200GE 1/0/1"])
def test_unknown_interface_heads_do_not_invent_a_model(header: str) -> None:
    result = analyze(f"interface {header}\n port default vlan 10\n", "full", "huawei")
    assert not result.config.interfaces
    assert result.coverage["pending_lines"] == [1, 2]
