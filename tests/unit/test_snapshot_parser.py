from netconfiglint import analyze
from netconfiglint.core.diagnostics import Confidence, Severity


def test_snapshot_parses_rib_peer_and_interface_sections() -> None:
    source = """sysname SYNTHETIC-LAB
<SYNTHETIC-LAB> display ip routing-table
Destination/Mask Proto Pre Cost Flags NextHop Interface
10.10.10.0/24 Static 60 0 RD 192.0.2.2 Vlanif10
<SYNTHETIC-LAB> display bgp peer
Peer V AS MsgRcvd MsgSent OutQ Up/Down State PrefRcv
192.0.2.2 4 65001 10 9 0 00:10:00 Established 4
<SYNTHETIC-LAB> display ip interface brief
Interface IP Address/Mask Physical Protocol
Vlanif10 192.0.2.1/24 up up
"""
    config = analyze(source, "snapshot", "huawei").config
    snapshot = config.snapshot
    assert snapshot.ipv4_rib_present
    assert snapshot.routes[0].prefix == "10.10.10.0/24"
    assert snapshot.bgp_peers["192.0.2.2"].state == "Established"
    assert snapshot.interfaces["vlanif10"].protocol_state == "up"
    assert "IP" not in config.interfaces


def test_snapshot_rib_absence_is_verified_error_for_bgp_network() -> None:
    source = """sysname SYNTHETIC-LAB
bgp 65000
 ipv4-family unicast
  network 10.10.10.0 255.255.255.0
#
<SYNTHETIC-LAB> display ip routing-table
Destination/Mask Proto Pre Cost Flags NextHop Interface
192.0.2.0/24 Direct 0 0 D 192.0.2.1 Vlanif10
<SYNTHETIC-LAB>
"""
    diagnostic = next(
        item for item in analyze(source, "snapshot", "huawei").diagnostics if item.rule_id == "HUA-BGP-002"
    )
    assert diagnostic.severity == Severity.ERROR
    assert diagnostic.confidence == Confidence.VERIFIED
    assert "absent" in diagnostic.message


def test_snapshot_exact_rib_route_proves_bgp_network() -> None:
    source = """sysname SYNTHETIC-LAB
bgp 65000
 ipv4-family unicast
  network 10.10.10.0 255.255.255.0
#
<SYNTHETIC-LAB> display ip routing-table
Destination/Mask Proto Pre Cost Flags NextHop Interface
10.10.10.0/24 Static 60 0 RD 192.0.2.2 Vlanif10
"""
    assert "HUA-BGP-002" not in {item.rule_id for item in analyze(source, "snapshot", "huawei").diagnostics}


def test_snapshot_huawei_ipv6_detail_route_proves_bgp_network() -> None:
    source = """sysname SYNTHETIC-LAB
bgp 65000
 ipv6-family unicast
  network 2001:db8:10:: 64
#
<SYNTHETIC-LAB> display ipv6 routing-table
Routing Table : Public
Destination  : 2001:db8:10::                         PrefixLength : 64
NextHop      : 2001:db8:20::2                        Preference   : 60
Cost         : 0                                     Protocol     : Static
RelayNextHop : ::                                    TunnelID     : 0x0
Interface    : Vlanif20                              Flags        : D
"""
    result = analyze(source, "snapshot", "huawei")
    assert result.config.snapshot.ipv6_rib_present
    assert result.config.snapshot.routes[0].prefix == "2001:db8:10::/64"
    assert "HUA-BGP-002" not in {item.rule_id for item in result.diagnostics}
