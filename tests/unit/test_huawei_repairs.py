"""Synthetic business regressions for the v1.5 Huawei specialization."""

import pytest

from netconfiglint import analyze
from netconfiglint.core.diagnostics import Severity


def check(source: str, rule: str, mode: str = "full") -> list:
    return [d for d in analyze(source, mode, "huawei").diagnostics if d.rule_id == rule]


def test_separated_interface_names_share_reference_and_runtime_identity() -> None:
    source = (
        "interface Eth-Trunk 7\n#\ninterface GigabitEthernet 0/0/1\n eth-trunk 7\n#\n"
        "interface Vlanif 10\n ip address 192.0.2.1 24\n#\nvlan 10\n"
    )
    config = analyze(source, "full", "huawei").config
    assert set(config.interfaces) == {"Eth-Trunk7", "GigabitEthernet0/0/1", "Vlanif10"}
    assert not check(source, "HUA-IF-003") and not check(source, "HUA-IF-006")
    assert check(source.replace("interface Eth-Trunk 7\n#\n", ""), "HUA-IF-003")


def test_indented_separators_and_reentered_bgp_views_keep_correct_af() -> None:
    source = (
        "bgp 65000\n #\n ipv4-family vpn-instance BLUE\n  network 192.0.2.0 24\n #\n"
        " ipv6-family unicast\n  network 2001:db8:: 64\n#\n"
        "bgp 65000\n network 198.51.100.0 24\n"
    )
    families = analyze(source, "full", "huawei").config.bgp.address_families
    assert [(f.vpn_instance, f.networks[0][0]) for f in families] == [
        ("BLUE", "192.0.2.0"),
        (None, "2001:db8::"),
        (None, "198.51.100.0"),
    ]
    assert not check(source, "HUA-PARSE-BGP")


def test_quit_and_unknown_nested_views_do_not_leak_into_supported_context() -> None:
    source = (
        "bgp 65000\n ipv4-family vpn-instance BLUE\n  network 192.0.2.0 24\n quit\n"
        " network 198.51.100.0 24\n quit\n network 203.0.113.0 24\n#\n"
        "interface Vlanif1\n unfamiliar-view\n  ip address 10.0.0.1 24\n#\n"
        "interface Vlanif2\n ip route-static 10.0.0.0 24 NULL0\n"
    )
    config = analyze(source, "full", "huawei").config
    assert [n[0] for f in config.bgp.address_families for n in f.networks] == ["192.0.2.0", "198.51.100.0"]
    assert not config.interfaces["Vlanif1"].ip_addresses and not config.static_routes
    assert {7, 11, 14} <= {line.line for line in config.unparsed_lines}


@pytest.mark.parametrize("family", ["ipv4", "ipv6"])
def test_vpn_peers_do_not_inherit_public_or_other_vpn_remote_as(family: str) -> None:
    address = "192.0.2.1" if family == "ipv4" else "2001:db8::1"
    source = (
        f"bgp 65000\n peer {address} as-number 65001\n"
        f" {family}-family vpn-instance BLUE\n  peer {address} as-number 65002\n"
        f" {family}-family vpn-instance RED\n  peer {address} group EDGE\n"
    )
    assert len(check(source, "HUA-BGP-005")) == 1
    assert len(check(source, "HUA-BGP-004")) == 1
    good = source + "  group EDGE external\n  peer EDGE as-number 65003\n"
    assert not check(good, "HUA-BGP-005") and not check(good, "HUA-BGP-004")


def test_public_address_family_peers_inherit_transport_as_and_group() -> None:
    source = (
        "bgp 65000\n group EDGE internal\n peer 192.0.2.1 group EDGE\n"
        " ipv4-family unicast\n  peer 192.0.2.1 enable\n"
        " ipv6-family unicast\n  peer 192.0.2.1 enable\n"
    )
    assert not check(source, "HUA-BGP-005") and not check(source, "HUA-BGP-004")
    assert check(source.replace(" group EDGE internal\n", ""), "HUA-BGP-004")


def test_unknown_peer_extension_does_not_invent_a_peer_or_remote_as_error() -> None:
    source = "bgp 65000\n peer 192.0.2.1 unfamiliar-option VALUE\n"
    assert not check(source, "HUA-BGP-005")
    assert analyze(source, vendor="huawei").coverage["unparsed_lines"] == [2]
    described = "bgp 65000\n peer 192.0.2.1 description SYNTHETIC\n"
    assert check(described, "HUA-BGP-005")
    assert not check(described + " undo peer 192.0.2.1 description\n", "HUA-BGP-005")


def test_bgp_network_and_policy_undo_are_scoped_and_source_mapped() -> None:
    source = (
        "bgp 65000\n ipv4-family vpn-instance BLUE\n"
        "  network 192.0.2.0 24 route-policy OLD\n  undo network 192.0.2.0 255.255.255.0\n"
        " ipv4-family vpn-instance RED\n  network 192.0.2.0 24 route-policy ACTIVE\n"
    )
    assert [d.source.line for d in check(source, "HUA-BGP-001")] == [6]
    assert [d.source.line for d in check(source, "HUA-BGP-002")] == [6]


@pytest.mark.parametrize(
    "definition,reference",
    [
        ("ip ip-prefix SAME permit 192.0.2.0 24", "if-match ipv6 address prefix-list SAME"),
        ("ip ipv6-prefix SAME permit 2001:db8:: 64", "if-match ip-prefix SAME"),
    ],
)
def test_prefix_names_are_address_family_specific(definition: str, reference: str) -> None:
    source = f"{definition}\nroute-policy EXPORT permit node 10\n {reference}\n"
    assert check(source, "HUA-RPOL-001")
    both = source + "#\nip ip-prefix SAME permit 192.0.2.0 24\nip ipv6-prefix SAME permit 2001:db8:: 64\n"
    assert not check(both, "HUA-RPOL-001")


@pytest.mark.parametrize("field", ["address", "next-hop", "route-source"])
def test_official_ipv6_route_policy_acl_and_prefix_forms(field: str) -> None:
    source = f"route-policy EXPORT permit node 10\n if-match ipv6 {field} acl 2000\n"
    assert check(source, "HUA-ACL-001")
    assert not check("acl ipv6 2000\n#\n" + source, "HUA-ACL-001")
    assert not check(source + f" undo if-match ipv6 {field}\n", "HUA-ACL-001")


def test_policy_node_undo_does_not_remove_another_node_or_family() -> None:
    source = (
        "route-policy EXPORT permit node 10\n if-match ip-prefix REMOVED\n#\n"
        "route-policy EXPORT permit node 20\n if-match ip-prefix ACTIVE\n#\n"
        "undo route-policy EXPORT permit node 10\n"
    )
    assert len(check(source, "HUA-RPOL-001")) == 1
    assert "ACTIVE" in check(source, "HUA-RPOL-001")[0].message


@pytest.mark.parametrize(
    "command,undo,rule",
    [
        ("eth-trunk 7", "undo eth-trunk", "HUA-IF-003"),
        ("ospf enable 7 area 0", "undo ospf enable 7", "HUA-OSPF-003"),
        ("isis enable 7", "undo isis enable 7", "HUA-ISIS-001"),
        ("traffic-policy EDGE inbound", "undo traffic-policy EDGE inbound", "HUA-POL-002"),
        ("traffic-filter inbound acl 3000", "undo traffic-filter inbound acl 3000", "HUA-ACL-001"),
        ("ip address INVALID 24", "undo ip address", "HUA-IF-005"),
        ("ipv6 address INVALID 64", "undo ipv6 address", "HUA-IPV6-002"),
    ],
)
def test_interface_undo_removes_only_effective_reference(command: str, undo: str, rule: str) -> None:
    root = f"interface GigabitEthernet0/0/1\n {command}\n"
    assert check(root, rule)
    assert not check(root + f" {undo}\n", rule)
    assert check(root + f"#\ninterface GigabitEthernet0/0/2\n {undo}\n", rule)


@pytest.mark.parametrize(
    "family,address,network",
    [
        ("ip", "192.0.2.1 24", "192.0.2.0 24"),
        ("ipv6", "2001:db8::1 64", "2001:db8:: 64"),
    ],
)
def test_vpn_binding_clears_prior_l3_candidate_but_retains_later_address(
    family: str, address: str, network: str
) -> None:
    af = "ipv4" if family == "ip" else "ipv6"
    source = (
        f"interface Vlanif1\n {family} address {address}\n ip binding vpn-instance BLUE\n#\n"
        f"bgp 65000\n {af}-family vpn-instance BLUE\n  network {network}\n"
    )
    assert check(source, "HUA-BGP-002")
    source = source.replace(
        " ip binding vpn-instance BLUE\n", f" ip binding vpn-instance BLUE\n {family} address {address}\n"
    )
    assert not check(source, "HUA-BGP-002")


def test_ospf_network_and_explicit_binding_require_same_vpn() -> None:
    root = "interface Vlanif1\n ip binding vpn-instance RED\n ip address 192.0.2.1 24\n"
    ospf = "#\nospf 7 vpn-instance BLUE\n area 0\n  network 192.0.2.0 0.0.0.255\n"
    assert check(root + ospf, "HUA-OSPF-002")
    assert not check((root + ospf).replace("vpn-instance RED", "vpn-instance BLUE"), "HUA-OSPF-002")
    assert check(root + " ospf enable 7 area 0\n" + ospf, "HUA-OSPF-003")


@pytest.mark.parametrize(
    "before,after,rule",
    [
        ("telnet server enable", "undo telnet server enable", "HUA-SEC-002"),
        ("ftp server enable", "undo ftp server enable", "HUA-SEC-003"),
        ("ssh server-source all-interface", "ssh server-source -i Vlanif1", "HUA-SEC-007"),
        ("user-interface vty 0 4\n protocol inbound all", " protocol inbound ssh", "HUA-SEC-009"),
        ("user-interface vty 0 4\n authentication-mode password", " authentication-mode aaa", "HUA-SEC-010"),
        (
            "aaa\n local-user SYNTHETIC password simple SYNTHETIC",
            " local-user SYNTHETIC password irreversible-cipher SYNTHETIC",
            "HUA-SEC-004",
        ),
        ("aaa\n local-user SYNTHETIC service-type telnet", " undo local-user SYNTHETIC", "HUA-SEC-008"),
    ],
)
def test_effective_security_state_replaces_stale_risks(before: str, after: str, rule: str) -> None:
    assert check(before, rule)
    assert not check(before + "\n" + after, rule)


def test_removed_bpdu_protection_and_reentered_isis_net_are_effective() -> None:
    source = (
        "stp bpdu-protection\nundo stp bpdu-protection\n"
        "interface GigabitEthernet0/0/1\n stp edged-port enable\n"
    )
    assert check(source, "HUA-STP-001")
    assert not check(source + " stp edged-port disable\n", "HUA-STP-001")
    isis = "isis 7\n network-entity 49.0001.0000.0000.0007.00\n#\nisis 7\n#\n"
    assert not check(isis, "HUA-ISIS-002")
    assert check(isis + "isis 7\n undo network-entity 49.0001.0000.0000.0007.00\n", "HUA-ISIS-002")


def test_acl_unsupported_rule_is_not_an_empty_acl() -> None:
    source = "acl 3000\n rule permit ip\n#\ninterface Vlanif1\n traffic-filter inbound acl 3000\n"
    assert not check(source, "HUA-ACL-003")
    assert check(source.replace(" rule permit ip\n", ""), "HUA-ACL-003")
    assert 2 in analyze(source, vendor="huawei").coverage["unparsed_lines"]


def test_vni_replacement_undo_and_views_avoid_false_duplicate_binding() -> None:
    source = "bridge-domain 10\n vxlan vni 100\n#\nbridge-domain 20\n vxlan vni 100\n"
    assert check(source, "HUA-EVPN-003")
    assert not check(source + " undo vxlan vni\n", "HUA-EVPN-003")
    assert not check(source + " vxlan vni 200\n", "HUA-EVPN-003")
    assert not check("interface Vlanif1\n vxlan vni 99999999\n", "HUA-EVPN-001")


@pytest.mark.parametrize(
    "command",
    ["port trunk allow-pass vlan all", "port hybrid tagged vlan all", "ipv6 address 2001:db8::1 64"],
)
def test_shutdown_business_detection_includes_all_vlan_and_ipv6(command: str) -> None:
    root = f"interface GigabitEthernet0/0/1\n {command}\n shutdown\n"
    assert check(root, "HUA-IF-001")
    assert not check(root + " undo shutdown\n", "HUA-IF-001")


def test_unknown_model_version_stays_generic_and_case_does_not_create_conflicts() -> None:
    source = "Huawei Versatile Routing Platform\nS7706 V200R019C10\ns7706 v200r019c10\nstelnet server enable"
    assert check(source, "HUA-SEC-007")[0].severity == Severity.WARNING
    assert check(source.replace("019", "099"), "HUA-SEC-007")[0].severity == Severity.UNKNOWN


@pytest.mark.parametrize("family,prefix", [("ip", "192.0.2.0 24"), ("ipv6", "2001:db8:: 64")])
def test_static_route_undo_retains_other_vpn_and_other_next_hop(family: str, prefix: str) -> None:
    root = (
        f"{family} route-static vpn-instance BLUE {prefix} NULL0\n"
        f"{family} route-static vpn-instance RED {prefix} NULL0\n"
        f"undo {family} route-static vpn-instance BLUE {prefix} NULL0\n"
    )
    config = analyze(root, "full", "huawei").config
    routes = config.static_routes if family == "ip" else config.ipv6_static_routes
    assert [r.vpn_instance for r in routes] == ["RED"]
    diagnostics = check(root, "HUA-ROUTE-003")
    assert len(diagnostics) == 1 and "RED" in diagnostics[0].message


def test_static_next_hop_vpn_does_not_change_network_scope_or_parse_description_as_reference() -> None:
    source = (
        "ip vpn-instance BLUE\n#\nip vpn-instance RED\n#\n"
        "ip route-static vpn-instance BLUE 192.0.2.0 24 vpn-instance RED 198.51.100.1 "
        "description vpn-instance TEXT\n"
        "bgp 65000\n ipv4-family vpn-instance BLUE\n  network 192.0.2.0 24\n"
        " ipv4-family vpn-instance RED\n  network 192.0.2.0 24\n"
    )
    assert not check(source, "HUA-ROUTE-001") and not check(source, "HUA-ROUTE-003")
    assert [d.source.line for d in check(source, "HUA-BGP-002")] == [10]
    assert check(source.replace("ip vpn-instance RED\n#\n", ""), "HUA-ROUTE-003")


def test_static_default_preference_is_not_a_route_and_unknown_extension_cannot_prove_bgp() -> None:
    source = "ip route-static default-preference 60\nipv6 route-static default-preference 80\n"
    assert not check(source, "HUA-ROUTE-001") and not check(source, "HUA-IPV6-001")
    source += "ip route-static 192.0.2.0 24 NULL0 unfamiliar-flag\nbgp 65000\n network 192.0.2.0 24\n"
    assert check(source, "HUA-ROUTE-001")[0].severity == Severity.UNKNOWN
    assert check(source, "HUA-BGP-002")


def test_named_numbered_acl_undo_works_across_alias_views_only_in_its_family() -> None:
    source = (
        "acl name WEB advanced number 3000\n rule 5 permit ip\n#\n"
        "acl ipv6 3000\n rule 5 permit ipv6\n#\nacl number 3000\n undo rule 5\n#\n"
        "interface Vlanif1\n traffic-filter inbound acl name WEB\n"
    )
    assert len(check(source, "HUA-ACL-002")) == 1
    assert check(source, "HUA-ACL-003") and not check(source, "HUA-ACL-001")
    assert not check(source + "#\nundo acl 3000\n", "HUA-ACL-003")
    assert check(source + "#\nundo acl 3000\n", "HUA-ACL-001")


def test_undo_wrong_selector_does_not_remove_effective_command() -> None:
    source = (
        "interface GigabitEthernet0/0/1\n eth-trunk 7\n undo eth-trunk 8\n"
        " traffic-policy ACTIVE inbound\n undo traffic-policy OTHER inbound\n"
    )
    assert check(source, "HUA-IF-003") and check(source, "HUA-POL-002")


@pytest.mark.parametrize(
    "link_type,command",
    [
        ("access", "port trunk allow-pass vlan all"),
        ("trunk", "port hybrid tagged vlan all"),
        ("hybrid", "port trunk allow-pass vlan 10"),
    ],
)
def test_link_type_conflicts_include_all_and_hybrid(link_type: str, command: str) -> None:
    assert check(f"interface GigabitEthernet0/0/1\n port link-type {link_type}\n {command}", "HUA-IF-002")
    assert not check(f"interface GigabitEthernet0/0/1\n {command}", "HUA-IF-002")


@pytest.mark.parametrize(
    "row",
    [
        "192.0.2.0/24 garbage garbage garbage",
        "192.0.2.0/24 Static 60 0 RD INVALID Vlanif10",
        "192.0.2.0/24 Static 60 0 RD 2001:db8::1 Vlanif10",
    ],
)
def test_malformed_rib_rows_cannot_prove_presence_or_absence(row: str) -> None:
    source = (
        "bgp 65000\n network 192.0.2.0 24\n#\n<SYNTHETIC> display ip routing-table\n"
        f"Destination/Mask Proto Pre Cost Flags NextHop Interface\n{row}\n<SYNTHETIC>\n"
    )
    assert check(source, "HUA-BGP-002", "snapshot")[0].severity == Severity.UNKNOWN


@pytest.mark.parametrize("broken", ["bad-prefix", "wrong-family", "missing-hop", "invalid-hop"])
def test_incomplete_ipv6_detail_cannot_prove_network(broken: str) -> None:
    row = (
        "Destination : 2001:db8:: PrefixLength : 64\nNextHop : 2001:db8:1::1 Preference : 60\n"
        "Protocol : Static\nInterface : Vlanif1 Flags : D\n"
    )
    if broken == "bad-prefix":
        row = row.replace("2001:db8::", "INVALID")
    elif broken == "wrong-family":
        row = row.replace("2001:db8::", "192.0.2.0").replace("PrefixLength : 64", "PrefixLength : 24")
    elif broken == "missing-hop":
        row = row.replace("NextHop : 2001:db8:1::1 Preference : 60\n", "")
    else:
        row = row.replace("2001:db8:1::1", "INVALID")
    source = (
        "bgp 65000\n ipv6-family unicast\n  network 2001:db8:: 64\n#\n"
        "<SYNTHETIC> display ipv6 routing-table\n" + row + "<SYNTHETIC>\n"
    )
    assert check(source, "HUA-BGP-002", "snapshot")[0].severity == Severity.UNKNOWN


@pytest.mark.parametrize("table", ["ip", "physical"])
def test_interface_snapshot_column_layouts_and_failed_captures(table: str) -> None:
    root = "interface GigabitEthernet 0/0/1\n ip address 192.0.2.1 24\n#\n"
    if table == "ip":
        capture = (
            "<SYNTHETIC> display ip interface brief\nInterface IP Address/Mask Physical Protocol VPN\n"
            "GigabitEthernet0/0/1 192.0.2.1/24 down down --\n"
        )
    else:
        capture = (
            "<SYNTHETIC> display interface brief\nInterface PHY Protocol InUti OutUti inErrors outErrors\n"
            "GigabitEthernet 0/0/1 down down 0% 0% 0 0\n"
        )
    assert check(root + capture, "HUA-IF-004", "snapshot")
    assert not check(root + capture.replace("down down", "up up(s)"), "HUA-IF-004", "snapshot")
    assert not check(root + capture + "Error: capture failed\n", "HUA-IF-004", "snapshot")
    assert not check(root + capture + capture.replace("down down", "up up"), "HUA-IF-004", "snapshot")


def test_failed_and_conflicting_bgp_snapshots_do_not_report_verified_state() -> None:
    root = "bgp 65000\n peer 192.0.2.1 as-number 65001\n#\n"
    capture = (
        "<SYNTHETIC> display bgp peer\nPeer V AS MsgRcvd MsgSent OutQ Up/Down State PrefRcv\n"
        "192.0.2.1 4 65001 0 0 0 00:00:10 Active 0\n"
    )
    assert check(root + capture, "HUA-BGP-003", "snapshot")
    assert not check(root + capture + "Error: capture failed\n", "HUA-BGP-003", "snapshot")
    assert not check(root + capture + capture.replace("Active", "Established"), "HUA-BGP-003", "snapshot")


def test_classifier_retains_multiple_acls_and_selective_undo() -> None:
    source = "traffic classifier EDGE operator or\n if-match acl 3000\n if-match acl 3001\n"
    assert len(check(source, "HUA-ACL-001")) == 2
    remaining = check(source + " undo if-match acl 3000\n", "HUA-ACL-001")
    assert len(remaining) == 1 and "3001" in remaining[0].message


def test_ospf_secondary_only_match_does_not_prove_participation() -> None:
    source = (
        "interface Vlanif1\n ip address 198.51.100.1 24\n ip address 192.0.2.1 24 sub\n#\n"
        "ospf 7\n area 0\n  network 192.0.2.0 0.0.0.255\n"
    )
    assert check(source, "HUA-OSPF-002")
    assert not check(source.replace("24 sub", "24"), "HUA-OSPF-002")


def test_primary_address_replacement_and_mask_equivalent_undo_change_bgp_candidate() -> None:
    source = (
        "interface Vlanif1\n ip address 192.0.2.1 24\n ip address 198.51.100.1 24\n#\n"
        "bgp 65000\n network 192.0.2.0 24\n network 198.51.100.0 24\n"
    )
    assert [d.object_name for d in check(source, "HUA-BGP-002")] == ["192.0.2.0/24"]
    source += "#\ninterface Vlanif1\n undo ip address 198.51.100.1 255.255.255.0\n"
    assert len(check(source, "HUA-BGP-002")) == 2


@pytest.mark.parametrize("address", ["2001:db8::/64", "2001:db8:: 64"])
def test_acl6_prefix_forms_are_normalized_without_claiming_any(address: str) -> None:
    source = f"acl ipv6 3000\n rule 5 permit ipv6 source {address} destination any\n"
    config = analyze(source, "full", "huawei").config
    rule = config.acls["ipv6:number:3000"].rules["5"]
    assert rule.syntax_known and rule.source_match == ("2001:db8::/64",)
    assert not check(source, "HUA-ACL-002")
    assert check(source.replace(address, "any"), "HUA-ACL-002")


def test_acl_zero_host_wildcard_and_partial_rule_edits_are_conservative() -> None:
    source = "acl 3000\n rule 5 permit ip source 192.0.2.1 0\n"
    config = analyze(source, "full", "huawei").config
    assert config.acls["ipv4:number:3000"].rules["5"].source_match == ("192.0.2.1", "0.0.0.0")
    edited = source + " rule 5 permit ip destination any\n"
    assert not check(edited, "HUA-ACL-002")
    assert not analyze(edited, "full", "huawei").config.acls["ipv4:number:3000"].rules["5"].syntax_known
    assert check(source + " undo rule 5\n rule 5 permit ip\n", "HUA-ACL-002")


def test_bgp_peer_deletion_removes_public_af_references_but_not_vpn_peer() -> None:
    source = (
        "bgp 65000\n peer 192.0.2.1 as-number 65001\n ipv4-family unicast\n"
        "  peer 192.0.2.1 route-policy REMOVED export\n"
        " ipv4-family vpn-instance BLUE\n  peer 192.0.2.1 as-number 65002\n"
        "  peer 192.0.2.1 route-policy ACTIVE export\n quit\n undo peer 192.0.2.1\n"
    )
    assert not check(source, "HUA-BGP-005")
    policies = check(source, "HUA-BGP-001")
    assert len(policies) == 1 and "ACTIVE" in policies[0].message


def test_vni_mixed_configuration_styles_are_not_definitive_missing_errors() -> None:
    source = "vni 100\n#\nbridge-domain 10\n vxlan vni 200\n"
    assert check(source, "HUA-EVPN-002")[0].severity == Severity.UNKNOWN
    assert not check(source.replace("vni 100\n#\n", ""), "HUA-EVPN-002")


def test_profile_requires_vendor_and_platform_consistency() -> None:
    from netconfiglint.core.analyzer import VendorDetection
    from netconfiglint.vendors.huawei.profiles import ProfileDatabase

    database = ProfileDatabase()
    for vendor, platform in [("Unknown", "S-Series"), ("Huawei", "Unknown")]:
        result = database.resolve(VendorDetection(vendor, platform, "S7706", "V200R019C10", 0.9))
        assert result.profile.profile_id == "huawei-vrp-base" and result.confidence == "GENERIC"


def test_unsupported_bgp_instance_does_not_merge_into_public_process() -> None:
    source = "bgp 65000 instance OTHER\n network 192.0.2.0 24\n#\nbgp 65000\n network 198.51.100.0 24\n"
    config = analyze(source, "full", "huawei").config
    assert [n[0] for f in config.bgp.address_families for n in f.networks] == ["198.51.100.0"]
    assert {1, 2} <= {item.line for item in config.unparsed_lines}


@pytest.mark.parametrize(
    "process,enable,rule",
    [
        ("ospf", "ospf enable 7 area 0", "HUA-OSPF-003"),
        ("isis", "isis enable 7", "HUA-ISIS-001"),
    ],
)
def test_process_reentry_keeps_vpn_binding(process: str, enable: str, rule: str) -> None:
    source = (
        f"{process} 7 vpn-instance BLUE\n#\n{process} 7\n#\n"
        f"interface Vlanif1\n ip binding vpn-instance BLUE\n {enable}\n"
    )
    assert not check(source, rule)
    assert check(source.replace("ip binding vpn-instance BLUE", "ip binding vpn-instance RED"), rule)


def test_noncontiguous_ospf_wildcard_is_unknown_not_reinterpreted_as_netmask() -> None:
    source = "ospf 7\n area 0\n  network 192.0.2.0 255.255.255.0\n"
    assert check(source, "HUA-OSPF-001")[0].severity == Severity.UNKNOWN
    assert not check(source.replace("255.255.255.0", "0.0.0.255"), "HUA-OSPF-001")
    assert check(source.replace("255.255.255.0", "0.0.0.999"), "HUA-OSPF-001")[0].severity == Severity.ERROR


@pytest.mark.parametrize("group", ["group EDGE", "group EDGE listen internal", "group EDGE unfamiliar"])
def test_unsupported_group_semantics_do_not_become_definitive_missing_as(group: str) -> None:
    source = f"bgp 65000\n {group}\n peer 192.0.2.1 group EDGE\n"
    assert check(source, "HUA-BGP-005")[0].severity == Severity.UNKNOWN
    assert 2 in analyze(source, vendor="huawei").coverage["unparsed_lines"]
    assert not check(source.replace(group, "group EDGE internal"), "HUA-BGP-005")
