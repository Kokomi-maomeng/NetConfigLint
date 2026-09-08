"""Cross-vendor normalized configuration objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from netconfiglint.core.diagnostics import SourceRange


def _json_compatible(value: Any) -> Any:
    """Convert dataclass output into deterministic JSON-compatible values."""
    if isinstance(value, dict):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, set):
        return [_json_compatible(item) for item in sorted(value, key=str)]
    return value


@dataclass(slots=True)
class Vlan:
    vlan_id: int
    source: SourceRange


@dataclass(frozen=True, slots=True)
class ConfigCommand:
    """A source-mapped command inside a vendor configuration block."""

    text: str
    source: SourceRange


@dataclass(slots=True)
class ConfigBlock:
    """A generic configuration block retained for vendor rules not yet normalized."""

    header: str
    source: SourceRange
    commands: list[ConfigCommand] = field(default_factory=list)


@dataclass(slots=True)
class Interface:
    name: str
    source: SourceRange
    description: str = ""
    link_type: str | None = None
    access_vlan: int | None = None
    pvid_vlan: int | None = None
    allowed_vlans: set[int] = field(default_factory=set)
    hybrid_tagged_vlans: set[int] = field(default_factory=set)
    hybrid_untagged_vlans: set[int] = field(default_factory=set)
    ip_addresses: list[tuple[str, str | None, SourceRange]] = field(default_factory=list)
    ipv6_addresses: list[tuple[str, str | None, SourceRange]] = field(default_factory=list)
    ospf_bindings: list[tuple[str, str, SourceRange]] = field(default_factory=list)
    traffic_policies: list[tuple[str, str, SourceRange]] = field(default_factory=list)
    shutdown: bool = False
    eth_trunk: str | None = None
    vpn_instance: str | None = None
    command_sources: dict[str, SourceRange] = field(default_factory=dict)
    raw_commands: list[tuple[str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class StaticRoute:
    destination: str
    mask: str | None
    next_hop: str
    vpn_instance: str | None
    source: SourceRange
    parse_valid: bool = True
    parse_issue: str = ""


@dataclass(slots=True)
class IPv6StaticRoute:
    destination: str
    prefix_length: str | None
    next_hop: str
    vpn_instance: str | None
    source: SourceRange
    parse_valid: bool = True
    parse_issue: str = ""


@dataclass(slots=True)
class BGPPeer:
    address: str
    source: SourceRange
    remote_as: str | None = None
    group: str | None = None
    import_policies: list[tuple[str, SourceRange]] = field(default_factory=list)
    export_policies: list[tuple[str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class BGPGroup:
    name: str
    source: SourceRange
    group_type: str | None = None
    remote_as: str | None = None
    import_policies: list[tuple[str, SourceRange]] = field(default_factory=list)
    export_policies: list[tuple[str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class BGPAddressFamily:
    name: str
    source: SourceRange
    vpn_instance: str | None = None
    networks: list[tuple[str, str | None, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class BGPProcess:
    local_as: str
    source: SourceRange
    router_id: str | None = None
    peers: dict[str, BGPPeer] = field(default_factory=dict)
    groups: dict[str, BGPGroup] = field(default_factory=dict)
    address_families: list[BGPAddressFamily] = field(default_factory=list)


@dataclass(slots=True)
class OSPFNetwork:
    area: str
    address: str
    wildcard: str
    source: SourceRange


@dataclass(slots=True)
class OSPFProcess:
    process_id: str
    source: SourceRange
    areas: set[str] = field(default_factory=set)
    networks: list[OSPFNetwork] = field(default_factory=list)


@dataclass(slots=True)
class ACL:
    name: str
    source: SourceRange
    family: str = "ipv4"
    kind: str = "number"


@dataclass(slots=True)
class PrefixList:
    name: str
    source: SourceRange


@dataclass(slots=True)
class RoutePolicy:
    name: str
    source: SourceRange
    prefix_references: list[tuple[str, SourceRange]] = field(default_factory=list)
    acl_references: list[tuple[str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class TrafficClassifier:
    name: str
    source: SourceRange
    acl_references: list[tuple[str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class TrafficBehavior:
    name: str
    source: SourceRange


@dataclass(slots=True)
class TrafficPolicy:
    name: str
    source: SourceRange
    classifier_bindings: list[tuple[str, str, SourceRange]] = field(default_factory=list)


@dataclass(slots=True)
class VpnInstance:
    name: str
    source: SourceRange


@dataclass(frozen=True, slots=True)
class SnapshotRoute:
    prefix: str
    protocol: str
    next_hop: str
    interface: str
    source: SourceRange
    vpn_instance: str | None = None
    scope_known: bool = True


@dataclass(slots=True)
class RibCapture:
    """A single capture; presence alone never proves the absence of a route."""

    family: int
    source: SourceRange
    vpn_instance: str | None = None
    scope_known: bool = True
    unfiltered: bool = True
    header_seen: bool = False
    terminated: bool = False
    failed: bool = False
    truncated: bool = False
    expected_count: int | None = None
    routes: list[SnapshotRoute] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        count_matches = self.expected_count is None or self.expected_count == len(
            {route.prefix for route in self.routes}
        )
        return (
            self.scope_known
            and self.unfiltered
            and self.header_seen
            and self.terminated
            and not self.failed
            and not self.truncated
            and count_matches
        )


@dataclass(frozen=True, slots=True)
class SnapshotBgpPeer:
    address: str
    remote_as: str
    state: str
    received_prefixes: int | None
    source: SourceRange


@dataclass(frozen=True, slots=True)
class SnapshotInterface:
    name: str
    address: str
    physical_state: str
    protocol_state: str
    source: SourceRange


@dataclass(slots=True)
class SnapshotEvidence:
    ipv4_rib_present: bool = False
    ipv6_rib_present: bool = False
    bgp_peer_table_present: bool = False
    interface_table_present: bool = False
    routes: list[SnapshotRoute] = field(default_factory=list)
    bgp_peers: dict[str, SnapshotBgpPeer] = field(default_factory=dict)
    interfaces: dict[str, SnapshotInterface] = field(default_factory=dict)
    rib_captures: list[RibCapture] = field(default_factory=list)


@dataclass(slots=True)
class DeviceConfig:
    vendor: str
    source_lines: tuple[str, ...]
    blocks: list[ConfigBlock] = field(default_factory=list)
    vlans: dict[int, Vlan] = field(default_factory=dict)
    interfaces: dict[str, Interface] = field(default_factory=dict)
    static_routes: list[StaticRoute] = field(default_factory=list)
    ipv6_static_routes: list[IPv6StaticRoute] = field(default_factory=list)
    bgp: BGPProcess | None = None
    ospf_processes: dict[str, OSPFProcess] = field(default_factory=dict)
    acls: dict[str, ACL] = field(default_factory=dict)
    route_policies: dict[str, RoutePolicy] = field(default_factory=dict)
    traffic_classifiers: dict[str, TrafficClassifier] = field(default_factory=dict)
    traffic_behaviors: dict[str, TrafficBehavior] = field(default_factory=dict)
    traffic_policies: dict[str, TrafficPolicy] = field(default_factory=dict)
    prefix_lists: dict[str, PrefixList] = field(default_factory=dict)
    vpn_instances: dict[str, VpnInstance] = field(default_factory=dict)
    acl_references: list[tuple[str, str, SourceRange]] = field(default_factory=list)
    sensitive_lines: list[SourceRange] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    unparsed_lines: list[SourceRange] = field(default_factory=list)
    snapshot: SnapshotEvidence = field(default_factory=SnapshotEvidence)

    def to_dict(self) -> dict[str, Any]:
        data = _json_compatible(asdict(self))
        if not isinstance(data, dict):  # pragma: no cover - defensive type narrowing
            raise TypeError("DeviceConfig serialization did not produce an object")
        return data
