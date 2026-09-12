"""Synthetic counterexamples and adjacent cases for F06-F14/F19-F22."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest

from netconfiglint import analyze
from netconfiglint.core.analyzer import AnalysisMode, VendorDetection
from netconfiglint.core.analyzer.control import AnalysisCancelled, AnalysisLimits, CancellationToken
from netconfiglint.core.diagnostics import Confidence, Severity
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser


def issues(source: str, rule: str, mode: str = "full") -> list:
    return [d for d in analyze(source, mode, "huawei").diagnostics if d.rule_id == rule]


@pytest.mark.parametrize(
    "command,broad",
    [
        ("permit ip", True),
        ("permit ip source any destination any", True),
        ("permit ip source any", True),
        ("permit ip destination any", True),
        ("permit ip source 0.0.0.0 255.255.255.255", True),
        ("permit ip source 192.0.2.0 0.0.0.255", False),
        ("permit ip destination 192.0.2.0 0.0.0.255", False),
        ("permit tcp source any destination any destination-port eq 443", False),
        ("permit udp destination-port range 100 200", False),
        ("permit ip time-range BUSINESS", False),
        ("deny ip", False),
    ],
)
def test_f06_acl_normalized_matching(command: str, broad: bool) -> None:
    source = f"acl 3000\n rule 5 {command}\n#\ninterface Vlanif10\n traffic-filter inbound acl 3000\n"
    assert bool(issues(source, "HUA-ACL-002")) == broad


def test_acl_aliases_and_repeated_blocks_share_rule_inventory() -> None:
    source = (
        "acl name WEB advanced number 3000\n rule 5 permit ip\n#\nacl number 3000\n#\n"
        "interface Vlanif10\n traffic-filter inbound acl 3000\n"
        " traffic-filter outbound acl name WEB\n"
    )
    result = analyze(source, vendor="huawei")
    assert not {"HUA-ACL-001", "HUA-ACL-003"} & {d.rule_id for d in result.diagnostics}
    assert len(result.config.acls) == 1
    assert result.config.acl_references[0][0] == result.config.acl_references[1][0]


@pytest.mark.parametrize("address,prefix", [("10.0.0.0", "8"), ("172.16.0.0", "16"), ("192.0.2.0", "24")])
@pytest.mark.parametrize("suffix", ["", " route-policy EXPORT"])
def test_f07_classful_defaults_equal_explicit(address: str, prefix: str, suffix: str) -> None:
    source = f"ip route-static {address} {prefix} NULL0\nbgp 65000\n network {address}{suffix}\n"
    result = analyze(source, vendor="huawei")
    assert not issues(source, "HUA-BGP-002")
    assert result.config.bgp.address_families[0].networks[0][:2] == (address, prefix)


@pytest.mark.parametrize(
    "command",
    [
        "network",
        "network garbage",
        "network 192.0.2.0 mask 24",
        "network 192.0.2.0 33",
        "network 192.0.2.0 255.0.255.0",
        "network 192.0.2.1 24",
        "network 192.0.2.0 route-policy",
        "network 192.0.2.0 24 unexpected",
    ],
)
def test_f07_bad_network_is_not_silently_lost(command: str) -> None:
    result = analyze(f"bgp 65000\n {command}\n", vendor="huawei")
    assert any(d.rule_id == "HUA-PARSE-BGP" and d.source.line == 2 for d in result.diagnostics)
    assert not result.config.bgp.address_families[0].networks


@pytest.mark.parametrize(
    "command,valid",
    [
        ("network 2001:db8:: 64", True),
        ("network 2001:db8::", False),
        ("network 2001:db8:: 129", False),
        ("network 192.0.2.0 24", False),
    ],
)
def test_f07_ipv6_requires_matching_prefix(command: str, valid: bool) -> None:
    result = analyze(f"bgp 65000\n ipv6-family unicast\n  {command}", vendor="huawei")
    assert bool(result.config.bgp.address_families[0].networks) == valid


@pytest.mark.parametrize(
    "declaration,properties,override,missing_group,missing_as",
    [
        ("", "peer EDGE as-number 65001", "", True, True),
        ("group EDGE external", "", "", False, True),
        ("group EDGE external", "peer EDGE as-number 65001", "", False, False),
        ("group EDGE internal", "", "", False, False),
        ("group EDGE external", "", "peer 192.0.2.1 as-number 65002", False, False),
    ],
)
def test_f08_group_declaration_and_effective_as(
    declaration: str, properties: str, override: str, missing_group: bool, missing_as: bool
) -> None:
    source = f"bgp 65000\n {declaration}\n {properties}\n peer 192.0.2.1 group EDGE\n {override}\n"
    assert bool(issues(source, "HUA-BGP-004")) == missing_group
    assert bool(issues(source, "HUA-BGP-005")) == missing_as
    for item in issues(source, "HUA-BGP-005", "snippet"):
        assert item.severity == Severity.UNKNOWN and item.confidence != Confidence.VERIFIED


@pytest.mark.parametrize(
    "header,missing",
    [("ospf 10", False), ("ospfv3 10", True), ("ospf-like 10", True), ("ospfv3 10\n#\nospf 10", False)],
)
def test_f09_ospf_protocols_do_not_satisfy_each_other(header: str, missing: bool) -> None:
    assert (
        bool(issues(header + "\n#\ninterface Vlanif10\n ospf enable 10 area 0\n", "HUA-OSPF-003")) == missing
    )


@pytest.mark.parametrize("kind", ["trunk allow-pass", "hybrid tagged", "hybrid untagged"])
def test_f10_f11_f13_vlan_all_sources_overlap_and_undo(kind: str) -> None:
    root = "vlan 200\ninterface GigabitEthernet1/0/1\n"
    rule = "HUA-VLAN-001" if kind.startswith("trunk") else "HUA-VLAN-004"
    assert not issues(root + f" port {kind} vlan all\n", "HUA-VLAN-003")
    source = root + f" port {kind} vlan 100 to 102\n port {kind} vlan 102 200\n"
    diagnostics = issues(source, rule)
    assert len(diagnostics) == 1 and diagnostics[0].source.line == 3
    assert "100-102" in diagnostics[0].message
    assert not issues(source + f" undo port {kind} vlan 100 to 102\n", rule)
    assert issues(root + f" port {kind} vlan all\n undo port {kind} vlan 200\n", "HUA-VLAN-003")


@pytest.mark.parametrize(
    "command",
    [
        "vlan 5000",
        "vlan batch 0",
        "vlan batch 20 to 10",
        "vlan batch 20 to",
        "vlan batch 10 nonsense",
        "vlan",
        "vlan 10 20",
        "interface Vlanif1\n port default vlan 5000",
        "interface Vlanif1\n port trunk allow-pass vlan 10 to 5000",
    ],
)
def test_f12_invalid_vlan_is_explicit(command: str) -> None:
    assert issues(command, "HUA-PARSE-VLAN")


@pytest.mark.parametrize(
    "command",
    [
        "ip route-static 192.0.2.0 24",
        "ip route-static 192.0.2.0 24 999.999.999.999",
        "ip route-static 192.0.2.0 24 24",
        "ip route-static 192.0.2.0 24 NULL0 preference 500",
        "ip route-static 192.0.2.0 24 NULL0 preference 10 preference 20",
        "ipv6 route-static 2001:db8:: 64",
        "ipv6 route-static 2001:db8:: 64 192.0.2.1",
        "ipv6 route-static 2001:db8:: 129 NULL0",
    ],
)
def test_f12_bad_routes_are_diagnosed(command: str) -> None:
    assert any(
        d.rule_id in {"HUA-ROUTE-001", "HUA-IPV6-001"} and d.severity == Severity.ERROR
        for d in analyze(command, vendor="huawei").diagnostics
    )


@pytest.mark.parametrize(
    "hop", ["NULL0", "GigabitEthernet0/0/1", "GigabitEthernet 0/0/1 192.0.2.1", "192.0.2.1"]
)
def test_f12_legal_next_hop_branches(hop: str) -> None:
    assert not issues(f"ip route-static 198.51.100.0 24 {hop}", "HUA-ROUTE-001")


def test_f12_unknown_interface_stays_unknown_and_is_not_a_bgp_candidate() -> None:
    source = "ip route-static 192.0.2.0 24 Unfamiliar0\nbgp 65000\n network 192.0.2.0 24"
    assert issues(source, "HUA-ROUTE-001")[0].severity == Severity.UNKNOWN
    assert issues(source, "HUA-BGP-002")


@pytest.mark.parametrize("indent", ["", " ", "    ", "\t"])
def test_f13_f14_password_snippet_not_lost(indent: str) -> None:
    source = indent + "local-user SYNTHETIC password simple SYNTHETIC-VALUE"
    assert issues(source, "HUA-SEC-004", "snippet")
    result = analyze(source, "snippet", "huawei", initial_view="aaa")
    diagnostic = next(d for d in result.diagnostics if d.rule_id == "HUA-SEC-004")
    assert diagnostic.object_name == "aaa" and diagnostic.confidence == Confidence.DOCUMENTED
    assert result.config.source_lines == (source,)


def test_f14_description_and_console_are_not_vty_password_risks() -> None:
    assert not issues(
        "interface Vlanif10\n description Do not use password simple in production", "HUA-SEC-004"
    )
    assert not issues("user-interface console 0\n authentication-mode password", "HUA-SEC-010")
    diagnostic = issues("user-interface vty 0 4\n authentication-mode password", "HUA-SEC-010")[0]
    assert diagnostic.object_name == "user-interface vty 0 4"
    assert not issues("interface Vlanif10\n telnet server enable", "HUA-SEC-002")


def test_f19_shared_parser_parallel_calls_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = HuaweiConfigParser()
    original = parser._parse_ospf
    paused, resume = Event(), Event()

    def interleave(line, ospf):
        result = original(line, ospf)
        if line.text == "area 11":
            paused.set()
            assert resume.wait(3)
        return result

    monkeypatch.setattr(parser, "_parse_ospf", interleave)
    detection = VendorDetection("Huawei", "Unknown", "Unknown", "Unknown", 1)
    with ThreadPoolExecutor(2) as executor:
        first = executor.submit(
            parser.parse, "ospf 1\n area 11\n  network 192.0.2.0 0.0.0.255", AnalysisMode.FULL, detection
        )
        assert paused.wait(3)
        second = parser.parse(
            "ospf 1\n area 22\n  network 198.51.100.0 0.0.0.255", AnalysisMode.FULL, detection
        )
        resume.set()
        assert first.result().ospf_processes["1"].networks[0].area == "11"
        assert second.ospf_processes["1"].networks[0].area == "22"


@pytest.mark.parametrize(
    "limits",
    [
        replace(AnalysisLimits(), max_characters=10),
        replace(AnalysisLimits(), max_lines=2),
        replace(AnalysisLimits(), max_line_length=10),
        replace(AnalysisLimits(), max_work=5),
        replace(AnalysisLimits(), max_vlan_memberships=10),
    ],
)
def test_f20_input_and_work_limits_never_look_complete(limits: AnalysisLimits) -> None:
    source = "interface GigabitEthernet1/0/1\n port trunk allow-pass vlan 1 to 4094\n#\n"
    result = analyze(source, vendor="huawei", limits=limits)
    assert not result.coverage["complete"]
    assert any(d.rule_id == "SYS-LIMIT-001" for d in result.diagnostics)


def test_f20_diagnostic_limit_retains_partial_results_and_marker() -> None:
    source = "\n".join(f"interface Vlanif{i}\n ip address INVALID 24\n#" for i in range(1, 30))
    result = analyze(source, vendor="huawei", limits=replace(AnalysisLimits(), max_diagnostics=7))
    assert len(result.diagnostics) == 8 and not result.coverage["complete"]
    assert sum(d.rule_id == "SYS-LIMIT-001" for d in result.diagnostics) == 1


def test_f20_cancelled_analysis_does_not_return_success() -> None:
    token = CancellationToken()
    token.cancel()
    with pytest.raises(AnalysisCancelled):
        analyze("sysname SYNTHETIC", vendor="huawei", cancellation=token)
    assert analyze("sysname SYNTHETIC", vendor="huawei").coverage["complete"]


def test_f21_coverage_is_present_without_config_or_diagnostics() -> None:
    supported = analyze("sysname SYNTHETIC\n#", vendor="huawei")
    partial = analyze("sysname SYNTHETIC\nunsupported thing\nospfv3 10", vendor="huawei")
    unknown = analyze("something unknown", vendor="huawei")
    assert supported.coverage["recognized"] == 1 and supported.coverage["unparsed"] == 0
    assert partial.to_dict()["coverage"]["unparsed_lines"] == [2]
    assert partial.coverage["unsupported_lines"] == [3]
    assert unknown.coverage["recognized"] == 0 and unknown.coverage["unparsed"] == 1
    assert not partial.diagnostics and "config" not in partial.to_dict()


@pytest.mark.parametrize(
    "version,severity",
    [("V200R019C10", Severity.WARNING), ("V200R021C10", None), ("V200R099C00", Severity.UNKNOWN)],
)
def test_f22_exact_profile_changes_ssh_default_check(version: str, severity: Severity | None) -> None:
    source = f"Huawei Versatile Routing Platform\nS7706 {version}\nsysname SYNTHETIC\nstelnet server enable\n"
    diagnostics = issues(source, "HUA-SEC-007")
    if severity is None:
        assert not diagnostics
    else:
        assert diagnostics[0].severity == severity
    result = analyze(source, vendor="huawei")
    assert bool(result.config.feature_facts) == (version != "V200R099C00")


@pytest.mark.parametrize("version", ["V200R019C10", "V200R021C10"])
def test_f22_other_model_does_not_inherit_s7700_default(version: str) -> None:
    source = f"Huawei Versatile Routing Platform\nS5700 {version}\nstelnet server enable"
    assert issues(source, "HUA-SEC-007")[0].severity == Severity.UNKNOWN


@pytest.mark.parametrize(
    "banner,description,expected",
    [
        ("S5700 V200R021C10", "S7706 V200R021C10", "S5700"),
        ("S7706 V200R019C10", "S5700 V200R021C10", "S7706"),
        ("", "S7706 V200R021C10", "Unknown"),
    ],
)
def test_f22_free_text_cannot_activate_or_override_profile(
    banner: str, description: str, expected: str
) -> None:
    source = (
        f"Huawei Versatile Routing Platform\n{banner}\nsysname SYNTHETIC\n"
        f"interface GigabitEthernet1/0/1\n description uplink {description}\n#\nstelnet server enable"
    )
    result = analyze(source, vendor="huawei")
    assert result.detection.model == expected
    assert issues(source, "HUA-SEC-007")
    if expected != "S7706":
        assert not result.config.feature_facts


def test_public_analyzer_wrapper_accepts_all_control_options() -> None:
    from netconfiglint.core.analyzer import analyze as lazy_analyze

    token = CancellationToken()
    for entry in (analyze, lazy_analyze):
        result = entry(
            "local-user SYNTHETIC password simple VALUE",
            "snippet",
            "huawei",
            limits=AnalysisLimits(),
            cancellation=token,
            initial_view="aaa",
        )
        assert next(d for d in result.diagnostics if d.rule_id == "HUA-SEC-004").object_name == "aaa"


def test_snapshot_device_name_and_conflicting_captures_are_not_proof() -> None:
    config = "sysname DEVICE-A\nbgp 65000\n network 192.0.2.0 24\n#\n"
    positive = (
        "display ip routing-table\nDestination/Mask Proto Pre Cost Flags NextHop Interface\n"
        "192.0.2.0/24 Static 60 0 RD 198.51.100.1 Vlanif10\n"
    )
    mismatch = config + "<DEVICE-B> " + positive + "<DEVICE-B>\n"
    assert issues(mismatch, "HUA-BGP-002", "snapshot")[0].severity == Severity.UNKNOWN
    for order in (0, 1):
        captures = ["<DEVICE-A> " + positive, "<DEVICE-A> display ip routing-table\nDestinations : 0\n"]
        if order:
            captures.reverse()
        source = config + "".join(captures) + "<DEVICE-A>\n"
        assert issues(source, "HUA-BGP-002", "snapshot")[0].severity == Severity.UNKNOWN


@pytest.mark.parametrize("mode,severity", [("full", Severity.ERROR), ("snippet", Severity.UNKNOWN)])
def test_f07_network_route_policy_reference_retains_line(mode: str, severity: Severity) -> None:
    source = "bgp 65000\n network 192.0.2.0 route-policy SYNTHETIC\n#"
    d = issues(source, "HUA-BGP-001", mode)[0]
    assert d.source.line == 2 and d.severity == severity
    assert not issues(source + "\nroute-policy SYNTHETIC permit node 10", "HUA-BGP-001", mode)


def test_f20_compact_vlan_amplification_has_bounded_peak_memory() -> None:
    import tracemalloc

    source = "\n".join(
        f"interface GigabitEthernet1/0/{i}\n port trunk allow-pass vlan 1 to 4094\n#" for i in range(100)
    )
    tracemalloc.start()
    try:
        result = analyze(
            source, vendor="huawei", limits=replace(AnalysisLimits(), max_vlan_memberships=20_000)
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert not result.coverage["complete"] and peak < 12 * 1024 * 1024
    assert result.diagnostics[-1].rule_id == "SYS-LIMIT-001"


def test_f20_parser_diagnostics_obey_the_same_budget() -> None:
    source = "vlan batch 9999\n" * 100
    result = analyze(source, vendor="huawei", limits=replace(AnalysisLimits(), max_diagnostics=7))
    assert not result.coverage["complete"] and len(result.diagnostics) <= 8


@pytest.mark.parametrize(
    "template",
    [
        "acl number {}",
        "acl name SYNTHETIC number {}",
        "ip route-static 192.0.2.0 24 NULL0 tag {}",
        "bgp 65000\n peer 192.0.2.1 as-number {}",
    ],
)
def test_f12_large_numeric_fields_never_crash(template: str) -> None:
    result = analyze(template.format("9" * 5000), vendor="huawei")
    assert result.coverage["complete"]
