import json

from netconfiglint.core.analyzer import AnalysisMode, VendorDetection
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser

DETECTION = VendorDetection("Huawei", "VRP", "Unknown", "Unknown", "Unknown", 0.9)


def test_parser_builds_normalized_model_and_line_mapping() -> None:
    source = """sysname LAB
vlan batch 10 20 to 21
interface GigabitEthernet1/0/1
 description uplink
 port link-type trunk
 port trunk allow-pass vlan 10 20 to 21
 ip address 192.0.2.1 255.255.255.0
"""
    config = HuaweiConfigParser().parse(source, AnalysisMode.FULL, DETECTION)

    assert set(config.vlans) == {10, 20, 21}
    interface = config.interfaces["GigabitEthernet1/0/1"]
    assert interface.allowed_vlans == {10, 20, 21}
    assert interface.command_sources["allowed_vlans"].line == 6
    assert config.metadata["sysname"] == "<redacted>"


def test_parser_keeps_unknown_source_lines() -> None:
    config = HuaweiConfigParser().parse("sysname LAB\nunsupported command here", AnalysisMode.FULL, DETECTION)
    assert config.unparsed_lines[0].line == 2


def test_parser_does_not_store_sensitive_values_in_metadata() -> None:
    config = HuaweiConfigParser().parse(
        "sysname LAB\n password cipher TOPSECRET", AnalysisMode.FULL, DETECTION
    )
    assert config.sensitive_lines[0].line == 2
    assert "TOPSECRET" not in repr(config.metadata)


def test_parser_tracks_each_ospf_network_area() -> None:
    source = """ospf 1
 area 0.0.0.0
  network 192.0.2.0 0.0.0.255
 area 0.0.0.1
  network 198.51.100.0 0.0.0.255
"""
    config = HuaweiConfigParser().parse(source, AnalysisMode.FULL, DETECTION)

    ospf = config.ospf_processes["1"]
    assert ospf.areas == {"0.0.0.0", "0.0.0.1"}
    assert [network.area for network in ospf.networks] == ["0.0.0.0", "0.0.0.1"]


def test_device_config_to_dict_is_json_serializable() -> None:
    source = """vlan batch 20 10
interface GigabitEthernet1/0/1
 port link-type trunk
 port trunk allow-pass vlan 20 10
"""
    config = HuaweiConfigParser().parse(source, AnalysisMode.FULL, DETECTION)

    serialized = config.to_dict()
    assert serialized["interfaces"]["GigabitEthernet1/0/1"]["allowed_vlans"] == [10, 20]
    json.dumps(serialized)
