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
    assert unknown_lines == [2, 3, 4]
    assert result.coverage["unsupported_lines"] == [2, 3, 4]
    assert result.coverage["complete"] is True
    assert result.coverage["semantic_complete"] is False
    summary = next(item for item in result.diagnostics if item.rule_id == "H3C-CMD-002")
    assert "3 command line(s)" in summary.message


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


def test_h3c_diagnostic_bundle_scopes_config_and_parses_operational_evidence() -> None:
    source = "\n".join(
        (
            "===============display version===============",
            H3C_BANNER,
            "================================================",
            "===============display current-configuration===============",
            "#",
            " version 7.1.070, Release 6715P06",
            "#",
            " sysname SYNTHETIC",
            "#",
            "return",
            "================================================",
            "===============display saved-configuration===============",
            "#",
            " version 7.1.070, Release 6715P06",
            "#",
            " sysname SYNTHETIC",
            "#",
            "return",
            "================================================",
            "===============display link-aggregation summary===============",
            "BAGG1 S None 8 0 0 Shar",
            "================================================",
            "===============display m-lag summary===============",
            "Peer-link interface state (cause): UP",
            "Keepalive link state (cause): UP",
            "================================================",
            "===============display m-lag system===============",
            "Health level: 0",
            "================================================",
            "===============display ospf peer===============",
            "1.1.1.1 192.0.2.2 1 40 Full/ - HGE1/0/1",
            "================================================",
            "===============display ip routing-table all-routes===============",
            "Destinations : 2 Routes : 3",
            "================================================",
        )
    )
    result = analyze(source, "snapshot", "h3c")

    assert result.coverage["analysis_scope_lines"] == 6
    assert result.coverage["excluded_operational_lines"] == len(source.splitlines()) - 6
    assert result.config.metadata["saved_configuration_matches"] == "true"
    assert result.config.snapshot.operational["ospf"]["neighbors"] == 1
    assert result.config.snapshot.operational["ipv4_routing_table"] == {
        "destinations": 2,
        "routes": 3,
        "line": 34,
    }
    assert any(item.rule_id == "H3C-OPS-000" for item in result.diagnostics)
    assert not result.config.unsupported_lines


def test_h3c_native_security_and_platform_uncertainty() -> None:
    source = "\n".join(
        (
            H3C_BANNER,
            "telnet server enable",
            "ospf 1",
            " area 0.0.0.0",
            "  network 10.0.0.0 0.0.1.255",
            "line vty 0 63",
            " authentication-mode scheme",
            "snmp-agent community read SYNTHETIC-READ",
            "snmp-agent community write SYNTHETIC-WRITE",
            "undo ssl version tls1.0 disable",
            "system-working-mode standard",
        )
    )
    result = analyze(source, "full", "h3c")
    identifiers = [item.rule_id for item in result.diagnostics]

    assert identifiers.count("H3C-SEC-005") == 2
    assert "H3C-SEC-009" in identifiers
    assert "H3C-SEC-011" in identifiers
    assert "H3C-OSPF-004" in identifiers
    assert "H3C-OSPF-005" in identifiers
    assert "H3C-PLATFORM-001" in identifiers


def test_h3c_abnormal_operational_evidence_and_config_mismatch_are_reported() -> None:
    sections = {
        "display current-configuration": ["#", " sysname SYNTHETIC", "#", "return"],
        "display saved-configuration": ["#", " sysname OLD", "#", "return"],
        "display device verbose": [
            "Slot Brd Type Status Subslot Sft Ver Patch Ver",
            "0 SYNTHETIC Fault 0 SYNTHETIC None",
        ],
        "display fan": ["Fan 1 State: Fault"],
        "display environment": [
            "Slot Sensor Temperature Lower Warning Alarm Shutdown",
            "0 hotspot 1 80 0 70 90 100",
        ],
        "display power": ["1 Fault AC 1.0 12.0 12.0 --"],
        "display link-aggregation summary": ["BAGG1 S None 7 1 0 Shar"],
        "display m-lag drcp statistics": ["*BAGG1 UP 10 5/2/0"],
        "display m-lag summary": [
            "Peer-link interface state (cause): DOWN",
            "Keepalive link state (cause): DOWN",
        ],
        "display m-lag system": ["Health level: 1"],
        "display ospf peer": ["1.1.1.1 192.0.2.2 1 40 Init HGE1/0/1"],
        "display transceiver alarm interface": [
            "GigabitEthernet1/0/1 transceiver current alarm information:",
            "High temperature",
        ],
        "display logbuffer size 512": ["Overwritten messages: 2"],
    }
    rows: list[str] = []
    for name, body in sections.items():
        rows.append(f"==============={name}===============")
        rows.extend(body)
        rows.append("================================================")
    result = analyze("\n".join(rows), "snapshot", "h3c")
    identifiers = {item.rule_id for item in result.diagnostics}

    assert {
        "H3C-OPS-001",
        "H3C-OPS-002",
        "H3C-OPS-003",
        "H3C-OPS-004",
        "H3C-OPS-005",
        "H3C-OPS-006",
        "H3C-OPS-007",
        "H3C-OPS-008",
        "H3C-OPS-009",
        "H3C-OPS-010",
        "H3C-OPS-012",
    } <= identifiers


def test_h3c_snapshot_without_operational_output_is_explicitly_unknown() -> None:
    result = analyze(H3C_BANNER, "snapshot", "h3c")
    item = next(item for item in result.diagnostics if item.rule_id == "H3C-OPS-011")
    assert item.severity.value == "UNKNOWN"
