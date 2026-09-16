from __future__ import annotations

from netconfiglint import analyze
from netconfiglint.vendors import detect_vendor_plugin, get_vendor_plugin
from netconfiglint.vendors.h3c.detector import H3CDetector
from netconfiglint.vendors.h3c.rules import H3C_RULES

H3C_BANNER = "H3C Comware Software, Version 7.1.070, Release 6715P06"


def test_h3c_detector_requires_comware_specific_evidence() -> None:
    shared = H3CDetector().detect("sysname LAB\nip route-static 0.0.0.0 0 192.0.2.1")
    assert shared.vendor == "Unknown"
    assert 0 < shared.confidence < 0.5

    detected = H3CDetector().detect(f"{H3C_BANNER}\nH3C S6850-56HF")
    assert detected.vendor == "H3C"
    assert detected.platform_family == "Comware 7"
    assert detected.model == "S6850-56HF"
    assert "RELEASE 6715P06" in detected.version
    assert detected.profile_id == "h3c-comware7-generic"


def test_auto_detection_selects_h3c_without_stealing_huawei() -> None:
    selected = detect_vendor_plugin(f"{H3C_BANNER}\nport trunk permit vlan 10")
    assert selected is not None
    assert selected[0].key == "h3c"
    assert selected[1].vendor == "H3C"

    selected = detect_vendor_plugin("Huawei Versatile Routing Platform\nport trunk allow-pass vlan 10")
    assert selected is not None
    assert selected[0].key == "huawei"


def test_h3c_registry_exposes_comware_alias_and_unique_rules() -> None:
    assert get_vendor_plugin("comware7").key == "h3c"
    identifiers = [rule.metadata.rule_id for rule in H3C_RULES]
    assert len(identifiers) >= 40
    assert len(identifiers) == len(set(identifiers))
    assert all(identifier.startswith("H3C-") for identifier in identifiers)


def test_h3c_parser_normalizes_supported_commands_and_preserves_original_text() -> None:
    source = "\n".join(
        (
            H3C_BANNER,
            "#",
            "vlan 10",
            "#",
            "interface Bridge-Aggregation1",
            " port link-type trunk",
            " port trunk permit vlan 10",
            "#",
            "interface GigabitEthernet1/0/1",
            " port link-aggregation group 1",
            "#",
            "bgp 65000",
            " peer 192.0.2.2 as-number 65001",
            " address-family ipv4 unicast",
            "  peer 192.0.2.2 enable",
            "#",
            "ospf 1",
            " area 0.0.0.0",
            "  network 10.0.0.0 0.0.0.255",
            "#",
            "interface Vlan-interface10",
            " ip address 10.0.0.1 255.255.255.0",
            " ospf 1 area 0.0.0.0",
            "#",
        )
    )
    result = analyze(source, "full", "auto")

    assert result.detection.vendor == "H3C"
    assert result.config.source_lines == tuple(source.splitlines())
    assert result.config.interfaces["GigabitEthernet1/0/1"].eth_trunk == "1"
    assert result.config.interfaces["Bridge-Aggregation1"].allowed_vlans == {10}
    assert result.config.interfaces["Vlan-interface10"].ospf_bindings == [
        ("1", "0.0.0.0", result.config.interfaces["Vlan-interface10"].ospf_bindings[0][2])
    ]
    assert result.config.bgp is not None
    assert result.config.bgp.address_families[0].name == "ipv4-family unicast"
    bridge_block = next(
        block for block in result.config.blocks if block.header == "interface Bridge-Aggregation1"
    )
    assert [command.text for command in bridge_block.commands] == [
        "port link-type trunk",
        "port trunk permit vlan 10",
    ]
    assert not result.config.unsupported_lines
    assert result.coverage["complete"] is True


def test_every_unmodeled_h3c_command_is_source_mapped_and_explicitly_unknown() -> None:
    source = (
        f"{H3C_BANNER}\ntelemetry\n sensor-group SYNTHETIC\n  sensor-path fake/path\n#\n"
        "ssh server enable\nauthorization-attribute user-role network-admin\n"
    )
    result = analyze(source, "full", "h3c")

    unknown_lines = [item.source.line for item in result.diagnostics if item.rule_id == "H3C-CMD-001"]
    assert unknown_lines == [2, 3, 4, 6, 7]
    assert result.coverage["unsupported_lines"] == [2, 3, 4, 6, 7]
    assert result.coverage["complete"] is True
    assert result.coverage["semantic_complete"] is False
    summary = next(item for item in result.diagnostics if item.rule_id == "H3C-CMD-002")
    assert "5 command line(s)" in summary.message


def test_h3c_structural_and_management_checks_use_comware_syntax() -> None:
    source = "\n".join(
        (
            H3C_BANNER,
            "vlan 10",
            "interface GigabitEthernet1/0/1",
            " port link-type trunk",
            " port trunk permit vlan 10 30",
            " port link-aggregation group 2",
            "interface Vlan-interface20",
            " ip address 999.0.0.1 255.255.255.0",
            "local-user admin class manage",
            " password simple synthetic-password",
            " service-type ssh telnet",
            "telnet server enable",
            "snmp-agent community read simple synthetic-community",
        )
    )
    result = analyze(source, "full", "h3c")
    identifiers = {item.rule_id for item in result.diagnostics}

    assert {
        "H3C-VLAN-001",
        "H3C-IF-003",
        "H3C-IF-005",
        "H3C-IF-006",
        "H3C-SEC-002",
        "H3C-SEC-004",
        "H3C-SEC-005",
        "H3C-SEC-008",
    } <= identifiers
    assert "HUA-SEC-002" not in identifiers


def test_h3c_snippet_missing_references_remain_unknown() -> None:
    result = analyze("interface GigabitEthernet1/0/1\n port trunk permit vlan 200\n", "snippet", "h3c")
    item = next(item for item in result.diagnostics if item.rule_id == "H3C-VLAN-001")
    assert item.severity.value == "UNKNOWN"
