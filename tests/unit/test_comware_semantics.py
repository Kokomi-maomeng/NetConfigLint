"""Comware input boundaries and changes of effective configuration state."""

from __future__ import annotations

import pytest

from netconfiglint import analyze


@pytest.mark.parametrize(
    "tail,valid,known",
    [
        ("192.0.2.0 24 198.51.100.1", True, True),
        ("192.0.2.0 24 NULL0", True, True),
        ("192.0.2.0 24 GigabitEthernet 1/0/1 198.51.100.1", True, True),
        ("192.0.2.0 24 Bridge-Aggregation1", True, True),
        ("192.0.2.0 24 Vlan-interface10 preference 10 tag 42", True, True),
        ("vpn-instance BLUE 192.0.2.0 24 198.51.100.1 public", True, True),
        ("192.0.2.0 24 vpn-instance BLUE 198.51.100.1", True, True),
        ("192.0.2.0 24 vpn-instance BLUE", False, False),
        ("192.0.2.0 24 vpn-instance", False, True),
        ("192.0.2.0 24", False, True),
        ("192.0.2.0 24 2001:db8::1", False, True),
        ("192.0.2.0 24 999.1.1.1", False, True),
        ("192.0.2.0 24 UNSUPPORTED_INTERFACE", False, False),
        ("192.0.2.0 24 GigabitEthernet1/0/1 999.1.1.1", False, True),
        ("192.0.2.0 24 GigabitEthernet1/0/1 2001:db8::1", False, True),
        ("192.0.2.0 24 198.51.100.1 preference 0", False, True),
        ("192.0.2.0 24 198.51.100.1 preference 10 preference 20", False, True),
        ("192.0.2.0 24 198.51.100.1 UNKNOWN_EXTENSION", False, False),
        ("192.0.2.0 24 198.51.100.1 description SYNTHETIC ONLY", True, True),
        ("192.0.2.0 24 198.51.100.1 description", False, True),
        ("vpn-instance BLUE", False, True),
    ],
)
def test_static_route_argument_boundaries(tail: str, valid: bool, known: bool) -> None:
    result = analyze("ip route-static " + tail, "full", "h3c")
    route = result.config.static_routes[0]
    assert route.parse_valid == valid and route.syntax_known == known
    issues = [item for item in result.diagnostics if item.rule_id == "H3C-ROUTE-001"]
    assert bool(issues) != valid
    if not known:
        assert all(item.severity.value == "UNKNOWN" for item in issues)


@pytest.mark.parametrize(
    "rule,known",
    [
        ("rule 5 permit ip", True),
        ("rule 5 permit tcp source any destination any destination-port eq 443", True),
        ("rule 5 permit udp source 192.0.2.0 0.0.0.255 destination-port range 53 54", True),
        ("rule 5 permit tcp destination-port eq 0", True),
        ("rule 5 permit tcp destination-port eq 65535", True),
        ("rule 5 permit tcp destination-port eq 65536", False),
        ("rule 5 permit tcp destination-port range 443 80", False),
        ("rule 5 permit tcp destination-port BETWEEN 80", False),
        ("rule 5 permit tcp source", False),
        ("rule 5 permit tcp source 999.0.0.1 0.0.0.0", False),
        ("rule 5 permit tcp source 192.0.2.1 0.0.5.255", True),
        ("rule 5 permit tcp source any source any", False),
        ("rule 5 permit tcp destination-port eq", False),
        ("rule 5 permit tcp destination-port range 80", False),
        ("rule 5 permit tcp UNKNOWN_EXTENSION", False),
    ],
)
def test_acl_parameter_evidence_is_conservative(rule: str, known: bool) -> None:
    result = analyze("acl advanced 3000\n " + rule + "\n#\n", "full", "h3c")
    acl = next(iter(result.config.acls.values()))
    assert acl.rules["5"].syntax_known == known
    if not known:
        assert not result.coverage["semantic_complete"]


@pytest.mark.parametrize(
    "rule,known",
    [
        ("rule 5 permit ipv6 source 2001:db8::/64 destination any", True),
        ("rule 5 permit ipv6 source 2001:db8:: 64", True),
        ("rule 5 permit ipv6 source 2001:db8::zz/64", False),
        ("rule 5 permit ipv6 source ::/0", False),
    ],
)
def test_ipv6_acl_scope(rule: str, known: bool) -> None:
    result = analyze("acl ipv6 advanced 3000\n " + rule, "full", "h3c")
    assert next(iter(result.config.acls.values())).rules["5"].syntax_known == known


@pytest.mark.parametrize(
    "network,valid",
    [
        ("192.0.2.0 24", True),
        ("192.0.2.0 255.255.255.0", True),
        ("10.0.0.0", True),
        ("999.1.1.0 24", False),
        ("2001:db8:: 64", False),
        ("192.0.2.0 24 UNKNOWN", False),
        ("192.0.2.0 24 route-policy EXPORT", True),
    ],
)
def test_bgp_network_native_family(network: str, valid: bool) -> None:
    result = analyze("bgp 65000\n address-family ipv4 unicast\n  network " + network, "full", "h3c")
    assert result.config.bgp is not None
    assert bool(result.config.bgp.address_families[0].networks) == valid
    assert any(item.rule_id == "H3C-PARSE-BGP" for item in result.diagnostics) != valid


def test_reentered_views_and_undo_remove_only_selected_facts() -> None:
    source = (
        "vlan 10 to 20\n#\nundo vlan 20\n"
        "interface GigabitEthernet1/0/1\n port trunk permit vlan 10 to 20\n"
        " undo port trunk permit vlan 20\n port hybrid vlan 10 tagged\n"
        " undo port hybrid vlan 10 tagged\n#\n"
        "interface GigabitEthernet1/0/1\n ip address 192.0.2.1 255.255.255.0\n"
        " ip address 192.0.2.2 255.255.255.0\n#\n"
        "bgp 65000\n address-family ipv4 unicast\n  network 192.0.2.0 24\n"
        "  undo network 192.0.2.0 24\n#\n"
        "ip route-static 198.51.100.0 24 192.0.2.1\n"
        "undo ip route-static 198.51.100.0 24 192.0.2.1\n"
    )
    result = analyze(source, "full", "h3c")
    interface = result.config.interfaces["GigabitEthernet1/0/1"]
    assert 20 not in result.config.vlans and 20 not in interface.allowed_vlans
    assert not interface.hybrid_tagged_vlans
    assert [item[0] for item in interface.ip_addresses] == ["192.0.2.2"]
    assert not result.config.static_routes
    assert result.config.bgp is not None and not result.config.bgp.address_families[0].networks


def test_acl_name_alias_and_separate_ipv6_prefix_consumers() -> None:
    source = (
        "acl advanced name WEB number 3000\n rule 5 permit tcp destination-port eq 443\n#\n"
        "interface GigabitEthernet1/0/1\n packet-filter name WEB inbound\n#\n"
        "ipv6 prefix-list V6 index 10 permit 2001:db8:: 32 greater-equal 48 less-equal 64\n"
        "route-policy EXPORT permit node 10\n if-match ipv6 address prefix-list V6\n#\n"
        "traffic classifier WEB\n if-match acl name WEB\n#\n"
        "traffic behavior FORWARD\n#\nqos policy EDGE\n classifier WEB behavior FORWARD\n#\n"
    )
    result = analyze(source, "full", "h3c")
    assert "V6" in result.config.ipv6_prefix_lists
    assert not any(
        item.rule_id in {"H3C-ACL-001", "H3C-RPOL-001", "H3C-POL-001"} for item in result.diagnostics
    )
    assert result.config.acl_references and result.config.traffic_classifiers["WEB"].acl_references


def test_snippet_starting_view_and_unknown_nested_context() -> None:
    known = analyze("port access vlan 99", "snippet", "h3c", initial_view="interface GigabitEthernet1/0/1")
    assert any(
        item.rule_id == "H3C-VLAN-002" and item.severity.value == "UNKNOWN" for item in known.diagnostics
    )
    with pytest.raises(ValueError):
        analyze("port access vlan 99", "full", "h3c", initial_view="interface GigabitEthernet1/0/1")
    unknown = analyze("return\n UNSUPPORTED_NATIVE_EXTENSION", "snippet", "h3c")
    assert not unknown.coverage["semantic_complete"]


@pytest.mark.parametrize("vendor,interface", [("huawei", "Eth-Trunk1"), ("h3c", "Bridge-Aggregation1")])
def test_compact_interface_cannot_absorb_an_invalid_next_hop(vendor: str, interface: str) -> None:
    result = analyze(f"ip route-static 192.0.2.0 24 {interface} 999.1.1.1", "full", vendor)
    assert not result.config.static_routes[0].parse_valid
    assert any(item.rule_id.endswith("ROUTE-001") for item in result.diagnostics)


def test_native_interface_facts_and_vlan_all_are_modeled() -> None:
    result = analyze(
        "interface GigabitEthernet1/0/1\n port link-mode route\n"
        " arp filter source 192.0.2.1 255.255.255.255\n ospf network-type p2p\n"
        " port trunk permit vlan all\n undo port trunk permit vlan all\n"
        " port hybrid vlan all tagged\n undo port hybrid vlan all tagged\n"
        " ipv6 address 2001:db8::1 64\n ipv6 address 2001:db8::2/64 eui-64\n#\n",
        "full",
        "h3c",
    )
    interface = result.config.interfaces["GigabitEthernet1/0/1"]
    assert interface.link_mode == "route" and interface.ospf_network_type == "p2p"
    assert interface.arp_filter_sources[0][:2] == ("192.0.2.1", "255.255.255.255")
    assert not interface.vlan_all
    assert len(interface.ipv6_addresses) == 2


def test_native_bgp_group_inheritance_and_family_policies() -> None:
    source = (
        "bgp 65000\n group EDGE external\n peer EDGE as-number 65001\n"
        " peer 192.0.2.2 group EDGE\n address-family ipv4 unicast\n"
        "  peer 192.0.2.2 enable\n  peer EDGE route-policy EXPORT export\n"
        "  network 192.0.2.0 24 route-policy EXPORT\n#\n"
        "route-policy EXPORT permit node 10\n#\n"
    )
    result = analyze(source, "full", "h3c")
    assert not any(
        item.rule_id in {"H3C-BGP-001", "H3C-BGP-004", "H3C-BGP-005"} for item in result.diagnostics
    )
    assert result.config.bgp is not None
    assert result.config.bgp.groups["EDGE"].remote_as == "65001"
    assert result.config.bgp.address_families[0].groups["EDGE"].export_policies
