"""Cross-object counterexamples from the v1.4 audit, using synthetic data only."""

import json

import pytest

from netconfiglint import analyze
from netconfiglint.core.diagnostics import Confidence, Severity
from netconfiglint.vendors.huawei.detector import HuaweiDetector


def bgp_source(family: int = 4, vpn: str | None = None) -> str:
    suffix = f"vpn-instance {vpn}" if vpn else "unicast"
    network = "192.0.2.0 24" if family == 4 else "2001:db8:: 64"
    return f"sysname SYNTHETIC\nbgp 65000\n ipv{family}-family {suffix}\n  network {network}\n#\n"


@pytest.mark.parametrize("family", [4, 6])
@pytest.mark.parametrize("failure", ["denied", "filtered", "paged", "unterminated", "count_mismatch"])
def test_incomplete_rib_never_verifies_absence(family: int, failure: str) -> None:
    command = "ip" if family == 4 else "ipv6"
    args = " 198.51.100.0 24" if failure == "filtered" else ""
    body = "Destinations : 0\n"
    if failure == "denied":
        body += "Error: Permission denied\n"
    if failure == "paged":
        body += "---- More ----\n"
    if failure == "count_mismatch":
        body = "Destinations : 2\nDestination/Mask Proto Pre Cost Flags NextHop Interface\n"
    end = "" if failure == "unterminated" else "<SYNTHETIC>\n"
    result = analyze(
        bgp_source(family) + f"<SYNTHETIC> display {command} routing-table{args}\n{body}{end}",
        "snapshot",
        "huawei",
    )
    issue = next(d for d in result.diagnostics if d.rule_id == "HUA-BGP-002")
    assert issue.severity == Severity.UNKNOWN
    assert issue.confidence != Confidence.VERIFIED


@pytest.mark.parametrize("family", [4, 6])
def test_successful_empty_rib_can_verify_absence(family: int) -> None:
    command = "ip" if family == 4 else "ipv6"
    result = analyze(
        bgp_source(family) + f"<SYNTHETIC> display {command} routing-table\n"
        "Routing Table : Public\nDestinations : 0\n<SYNTHETIC>\n",
        "snapshot",
        "huawei",
    )
    issue = next(d for d in result.diagnostics if d.rule_id == "HUA-BGP-002")
    assert issue.severity == Severity.ERROR
    assert issue.confidence == Confidence.VERIFIED


@pytest.mark.parametrize("family", [4, 6])
@pytest.mark.parametrize("scope", [None, "VPN-A", "VPN-B"])
@pytest.mark.parametrize("candidate_scope", [None, "VPN-A", "VPN-B"])
def test_static_candidates_are_scoped(family: int, scope: str | None, candidate_scope: str | None) -> None:
    vpn = f"vpn-instance {candidate_scope} " if candidate_scope else ""
    route = (
        f"ip route-static {vpn}192.0.2.0 24 NULL0\n"
        if family == 4
        else (f"ipv6 route-static {vpn}2001:db8:: 64 NULL0\n")
    )
    result = analyze(route + bgp_source(family, scope), "full", "huawei")
    assert ("HUA-BGP-002" in {d.rule_id for d in result.diagnostics}) == (scope != candidate_scope)


@pytest.mark.parametrize("scope", [None, "VPN-A", "VPN-B"])
@pytest.mark.parametrize("rib_scope", [None, "VPN-A", "VPN-B"])
def test_rib_routes_are_scoped(scope: str | None, rib_scope: str | None) -> None:
    args = f" vpn-instance {rib_scope}" if rib_scope else ""
    source = bgp_source(4, scope) + f"<SYNTHETIC> display ip routing-table{args}\n"
    source += "Destination/Mask Proto Pre Cost Flags NextHop Interface\n"
    source += "192.0.2.0/24 Static 60 0 RD 198.51.100.1 Vlanif10\n<SYNTHETIC>\n"
    result = analyze(source, "snapshot", "huawei")
    assert ("HUA-BGP-002" in {d.rule_id for d in result.diagnostics}) == (scope != rib_scope)
    if scope != rib_scope:
        assert next(d for d in result.diagnostics if d.rule_id == "HUA-BGP-002").severity == Severity.UNKNOWN


@pytest.mark.parametrize("declaration", ["acl ipv6 3000", "acl ipv6 number 3000"])
def test_acl_families_do_not_satisfy_each_other(declaration: str) -> None:
    source = declaration + "\n rule 5 deny ipv6\n#\nroute-policy TEST permit node 10\n if-match acl 3000\n"
    result = analyze(source, "full", "huawei")
    assert "HUA-ACL-001" in {d.rule_id for d in result.diagnostics}
    assert set(result.config.acls) == {"ipv6:number:3000"}
    json.dumps(result.to_dict(include_config=True))


@pytest.mark.parametrize("family", ["ipv4", "ipv6"])
@pytest.mark.parametrize("kind,value", [("number", "3000"), ("name", "TEST-ACL")])
@pytest.mark.parametrize("consumer", ["interface", "route_policy", "classifier"])
def test_acl_reference_entrypoints(family: str, kind: str, value: str, consumer: str) -> None:
    family_arg = "ipv6 " if family == "ipv6" else ""
    ref = f"{kind} {value}"
    header = {
        "interface": "interface Vlanif10",
        "route_policy": "route-policy TEST permit node 10",
        "classifier": "traffic classifier TEST",
    }[consumer]
    command = (
        f"traffic-filter inbound {family_arg}acl {ref}"
        if consumer == "interface"
        else (f"if-match {family_arg}acl {ref}")
    )
    source = f"acl {family_arg}{ref}\n rule 5 deny ip\n#\n{header}\n {command}\n"
    result = analyze(source, "full", "huawei")
    assert not ({"HUA-ACL-001", "HUA-ACL-003"} & {d.rule_id for d in result.diagnostics})


@pytest.mark.parametrize("banner", ["H3C Comware Software", "HPE Comware Software", "Cisco IOS Software"])
def test_foreign_or_mixed_vendor_requires_explicit_choice(banner: str) -> None:
    for prefix in ["", "Huawei Versatile Routing Platform\n"]:
        source = prefix + banner + "\nsysname SYNTHETIC\n"
        assert HuaweiDetector().detect(source).vendor == "Unknown"
        with pytest.raises(ValueError, match="identify a supported vendor"):
            analyze(source)
        result = analyze(source, vendor="huawei")
        assert "Vendor selected by user" in result.detection.evidence


def test_mixed_device_snapshot_does_not_prove_routes() -> None:
    source = bgp_source() + "<DEVICE-A> display ip routing-table\nDestinations : 0\n<DEVICE-B>\n"
    issue = next(d for d in analyze(source, "snapshot", "huawei").diagnostics if d.rule_id == "HUA-BGP-002")
    assert issue.severity == Severity.UNKNOWN


@pytest.mark.parametrize("family", [4, 6])
@pytest.mark.parametrize("scope", [None, "VPN-A", "VPN-B"])
@pytest.mark.parametrize("interface_scope", [None, "VPN-A", "VPN-B"])
def test_connected_candidates_are_scoped(family: int, scope: str | None, interface_scope: str | None) -> None:
    binding = f" ip binding vpn-instance {interface_scope}\n" if interface_scope else ""
    address = " ip address 192.0.2.1 24\n" if family == 4 else " ipv6 address 2001:db8::1/64\n"
    source = "interface Vlanif10\n" + binding + address + "#\n" + bgp_source(family, scope)
    result = analyze(source, "full", "huawei")
    assert ("HUA-BGP-002" in {d.rule_id for d in result.diagnostics}) == (scope != interface_scope)


def test_explicit_foreign_banner_is_not_hidden_by_shared_commands() -> None:
    source = "H3C Comware Software\nsysname SYNTHETIC\n port trunk allow-pass vlan 100\n"
    with pytest.raises(ValueError, match="identify a supported vendor"):
        analyze(source)


def test_ambiguous_bannerless_snippet_does_not_select_huawei() -> None:
    with pytest.raises(ValueError, match="identify a supported vendor"):
        analyze("sysname SYNTHETIC\nip route-static 192.0.2.0 24 NULL0\n")
