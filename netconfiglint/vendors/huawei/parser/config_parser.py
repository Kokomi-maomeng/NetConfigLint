"""Huawei VRP beta parser.

The parser is intentionally bounded. It normalizes supported constructs and retains unknown
lines instead of guessing at unsupported command semantics.
"""

from __future__ import annotations

import ipaddress
import re

from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.lexer import SourceLine, lex_lines
from netconfiglint.core.model import (
    ACL,
    BGPAddressFamily,
    BGPGroup,
    BGPPeer,
    BGPProcess,
    DeviceConfig,
    Interface,
    IPv6StaticRoute,
    OSPFNetwork,
    OSPFProcess,
    PrefixList,
    RoutePolicy,
    StaticRoute,
    TrafficBehavior,
    TrafficClassifier,
    TrafficPolicy,
    Vlan,
    VpnInstance,
)
from netconfiglint.vendors.huawei.parser.snapshot_parser import HuaweiSnapshotParser

_SENSITIVE = re.compile(r"\b(password|cipher|community|pre-shared-key|secret|private-key)\b", re.IGNORECASE)


class HuaweiConfigParser:
    def __init__(self) -> None:
        self._active_ospf_area: dict[int, str] = {}

    def parse(self, source: str, mode: AnalysisMode, detection: VendorDetection) -> DeviceConfig:
        lines = lex_lines(source)
        self._active_ospf_area = {}
        config = DeviceConfig(vendor=detection.vendor, source_lines=tuple(line.raw for line in lines))
        config.metadata["profile_id"] = detection.profile_id
        context: tuple[str, object] | None = None

        for line in lines:
            text = line.text
            lower = text.lower()
            if not text or text == "#" or lower == "return":
                if text == "#":
                    context = None
                continue
            if _SENSITIVE.search(text):
                config.sensitive_lines.append(SourceRange(line.number))

            started = self._start_block(config, line)
            if started is not None:
                context = started
                continue
            if self._parse_global(config, line):
                continue
            if context is not None and self._parse_context(config, line, context):
                continue
            config.unparsed_lines.append(SourceRange(line.number))
        if mode == AnalysisMode.SNAPSHOT:
            config.snapshot = HuaweiSnapshotParser().parse(source)
        return config

    def _start_block(self, config: DeviceConfig, line: SourceLine) -> tuple[str, object] | None:
        if line.raw[:1].isspace():
            return None
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if len(tokens) >= 2 and lower.startswith("interface "):
            if tokens[1].lower() == "ip" and "address/mask" in lower:
                return None
            interface = config.interfaces.setdefault(tokens[1], Interface(tokens[1], source))
            return ("interface", interface)
        if len(tokens) >= 2 and lower.startswith("bgp "):
            if lower.startswith("bgp local router id"):
                return None
            config.bgp = config.bgp or BGPProcess(tokens[1], source)
            return ("bgp", config.bgp)
        if lower.startswith("ospf"):
            if len(tokens) >= 2 and tokens[1].lower() == "process":
                return None
            process_id = tokens[1] if len(tokens) >= 2 and tokens[1].isdigit() else "1"
            process = config.ospf_processes.setdefault(process_id, OSPFProcess(process_id, source))
            return ("ospf", process)
        if len(tokens) >= 4 and lower.startswith("route-policy "):
            route_policy = config.route_policies.setdefault(tokens[1], RoutePolicy(tokens[1], source))
            return ("route_policy", route_policy)
        if len(tokens) >= 3 and lower.startswith("ip vpn-instance "):
            vpn = config.vpn_instances.setdefault(tokens[2], VpnInstance(tokens[2], source))
            return ("vpn", vpn)
        if len(tokens) >= 3 and lower.startswith("traffic classifier "):
            classifier = config.traffic_classifiers.setdefault(
                tokens[2], TrafficClassifier(tokens[2], source)
            )
            return ("traffic_classifier", classifier)
        if len(tokens) >= 3 and lower.startswith("traffic behavior "):
            behavior = config.traffic_behaviors.setdefault(tokens[2], TrafficBehavior(tokens[2], source))
            return ("traffic_behavior", behavior)
        if len(tokens) >= 3 and lower.startswith("traffic policy "):
            traffic_policy = config.traffic_policies.setdefault(tokens[2], TrafficPolicy(tokens[2], source))
            return ("traffic_policy", traffic_policy)
        return None

    def _parse_global(self, config: DeviceConfig, line: SourceLine) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if len(tokens) >= 2 and tokens[0].lower() == "vlan" and tokens[1].isdigit():
            config.vlans[int(tokens[1])] = Vlan(int(tokens[1]), source)
            return True
        if lower.startswith("vlan batch "):
            for vlan_id in self._expand_vlans(tokens[2:]):
                config.vlans.setdefault(vlan_id, Vlan(vlan_id, source))
            return True
        if lower.startswith("ip route-static "):
            config.static_routes.append(self._parse_static_route(line))
            return True
        if lower.startswith("ipv6 route-static "):
            config.ipv6_static_routes.append(self._parse_ipv6_static_route(line))
            return True
        if lower.startswith("ip ip-prefix ") and len(tokens) >= 3:
            config.prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("ip ipv6-prefix ") and len(tokens) >= 3:
            config.prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("acl ") and len(tokens) >= 2:
            if len(tokens) >= 4 and tokens[1].lower() == "ipv6" and tokens[2].lower() in {"name", "number"}:
                name = tokens[3]
            else:
                name = (
                    tokens[2] if len(tokens) >= 3 and tokens[1].lower() in {"name", "number"} else tokens[1]
                )
            config.acls.setdefault(name, ACL(name, source))
            return True
        if lower.startswith("traffic-filter "):
            self._record_acl_reference(config, line, object_name="global")
            return True
        if lower.startswith("sysname "):
            config.metadata["sysname"] = "<redacted>"
            return True
        return False

    def _parse_context(self, config: DeviceConfig, line: SourceLine, context: tuple[str, object]) -> bool:
        kind, value = context
        if kind == "interface" and isinstance(value, Interface):
            return self._parse_interface(config, line, value)
        if kind == "bgp" and isinstance(value, BGPProcess):
            return self._parse_bgp(line, value)
        if kind == "ospf" and isinstance(value, OSPFProcess):
            return self._parse_ospf(line, value)
        if kind == "route_policy" and isinstance(value, RoutePolicy):
            return self._parse_route_policy(line, value)
        if kind == "traffic_classifier" and isinstance(value, TrafficClassifier):
            return self._parse_traffic_classifier(line, value)
        if kind == "traffic_policy" and isinstance(value, TrafficPolicy):
            return self._parse_traffic_policy(line, value)
        if kind == "traffic_behavior":
            return True
        return kind == "vpn"

    def _parse_interface(self, config: DeviceConfig, line: SourceLine, interface: Interface) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        interface.raw_commands.append((line.text, source))
        if lower.startswith("description "):
            interface.description = line.text[len("description ") :]
        elif lower.startswith("port link-type ") and len(tokens) >= 3:
            interface.link_type = tokens[2].lower()
            interface.command_sources["link_type"] = source
        elif lower.startswith("port default vlan ") and len(tokens) >= 4 and tokens[3].isdigit():
            interface.access_vlan = int(tokens[3])
            interface.command_sources["access_vlan"] = source
        elif lower.startswith("port trunk allow-pass vlan "):
            interface.allowed_vlans.update(self._expand_vlans(tokens[4:]))
            interface.command_sources["allowed_vlans"] = source
        elif lower.startswith("ip address ") and len(tokens) >= 3:
            interface.ip_addresses.append((tokens[2], tokens[3] if len(tokens) >= 4 else None, source))
            interface.command_sources["ip_address"] = source
        elif lower.startswith("ipv6 address ") and len(tokens) >= 3:
            interface.ipv6_addresses.append((tokens[2], tokens[3] if len(tokens) >= 4 else None, source))
            interface.command_sources["ipv6_address"] = source
        elif lower.startswith("ospf enable ") and "area" in tuple(token.lower() for token in tokens):
            area_index = tuple(token.lower() for token in tokens).index("area")
            process_id = tokens[2] if len(tokens) > 2 and tokens[2].isdigit() else "1"
            if area_index + 1 < len(tokens):
                interface.ospf_bindings.append((process_id, tokens[area_index + 1], source))
                interface.command_sources["ospf_enable"] = source
        elif lower.startswith("traffic-policy ") and len(tokens) >= 2:
            direction = tokens[2].lower() if len(tokens) >= 3 else "unknown"
            interface.traffic_policies.append((tokens[1], direction, source))
        elif lower == "shutdown":
            interface.shutdown = True
            interface.command_sources["shutdown"] = source
        elif lower == "undo shutdown":
            interface.shutdown = False
            interface.command_sources["shutdown"] = source
        elif lower.startswith("eth-trunk ") and len(tokens) >= 2:
            interface.eth_trunk = tokens[1]
            interface.command_sources["eth_trunk"] = source
        elif lower.startswith("ip binding vpn-instance ") and len(tokens) >= 4:
            interface.vpn_instance = tokens[3]
            interface.command_sources["vpn_instance"] = source
        elif lower.startswith("traffic-filter "):
            self._record_acl_reference(config, line, object_name=interface.name)
        else:
            return False
        return True

    def _parse_bgp(self, line: SourceLine, bgp: BGPProcess) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("router-id ") and len(tokens) >= 2:
            bgp.router_id = tokens[1]
            return True
        if lower.startswith("group ") and len(tokens) >= 2:
            group = bgp.groups.setdefault(tokens[1], BGPGroup(tokens[1], source))
            if len(tokens) >= 3:
                group.group_type = tokens[2].lower()
            return True
        if lower.startswith("peer ") and len(tokens) >= 3:
            target_name = tokens[1]
            is_address = self._is_ip_address(target_name)
            if is_address:
                peer = bgp.peers.setdefault(target_name, BGPPeer(target_name, source))
                if tokens[2].lower() == "as-number" and len(tokens) >= 4:
                    peer.remote_as = tokens[3]
                elif tokens[2].lower() == "group" and len(tokens) >= 4:
                    peer.group = tokens[3]
                elif tokens[2].lower() == "route-policy" and len(tokens) >= 5:
                    target = peer.import_policies if tokens[4].lower() == "import" else peer.export_policies
                    target.append((tokens[3], source))
            else:
                group = bgp.groups.setdefault(target_name, BGPGroup(target_name, source))
                if tokens[2].lower() == "as-number" and len(tokens) >= 4:
                    group.remote_as = tokens[3]
                elif tokens[2].lower() == "route-policy" and len(tokens) >= 5:
                    target = group.import_policies if tokens[4].lower() == "import" else group.export_policies
                    target.append((tokens[3], source))
            return True
        if lower.startswith(("ipv4-family ", "ipv6-family ")):
            vpn_name = tokens[2] if len(tokens) >= 3 and tokens[1].lower() == "vpn-instance" else None
            bgp.address_families.append(BGPAddressFamily(line.text, source, vpn_name))
            return True
        if lower.startswith("network ") and len(tokens) >= 2:
            if not bgp.address_families:
                bgp.address_families.append(BGPAddressFamily("ipv4-family unicast", bgp.source))
            bgp.address_families[-1].networks.append(
                (tokens[1], tokens[2] if len(tokens) >= 3 else None, source)
            )
            return True
        return False

    def _parse_ospf(self, line: SourceLine, ospf: OSPFProcess) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("area ") and len(tokens) >= 2:
            ospf.areas.add(tokens[1])
            self._active_ospf_area[id(ospf)] = tokens[1]
            return True
        if lower.startswith("network ") and len(tokens) >= 3:
            area = self._active_ospf_area.get(id(ospf), "Unknown")
            ospf.networks.append(OSPFNetwork(area, tokens[1], tokens[2], source))
            return True
        return False

    def _parse_route_policy(self, line: SourceLine, policy: RoutePolicy) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("if-match ip-prefix ") and len(tokens) >= 3:
            policy.prefix_references.append((tokens[2], source))
            return True
        if lower.startswith("if-match acl ") and len(tokens) >= 3:
            policy.acl_references.append((tokens[2], source))
            return True
        return False

    @staticmethod
    def _parse_traffic_classifier(line: SourceLine, classifier: TrafficClassifier) -> bool:
        tokens = line.tokens
        lower_tokens = tuple(token.lower() for token in tokens)
        source = SourceRange(line.number)
        if lower_tokens[:2] == ("if-match", "acl") and len(tokens) >= 3:
            classifier.acl_references.append((tokens[2], source))
            return True
        if lower_tokens[:3] == ("if-match", "ipv6", "acl") and len(tokens) >= 4:
            classifier.acl_references.append((tokens[3], source))
            return True
        return False

    @staticmethod
    def _parse_traffic_policy(line: SourceLine, policy: TrafficPolicy) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("classifier ") and len(tokens) >= 4 and tokens[2].lower() == "behavior":
            policy.classifier_bindings.append((tokens[1], tokens[3], source))
            return True
        return False

    def _parse_static_route(self, line: SourceLine) -> StaticRoute:
        tokens = list(line.tokens[2:])
        source = SourceRange(line.number)
        vpn = None
        if len(tokens) >= 2 and tokens[0].lower() == "vpn-instance":
            vpn = tokens[1]
            tokens = tokens[2:]
        if len(tokens) < 2:
            return StaticRoute("", None, "", vpn, source, False, "Too few arguments")
        destination = tokens[0]
        mask: str | None = None
        next_hop_index = 1
        if len(tokens) >= 3 and (self._looks_like_mask(tokens[1]) or tokens[1].isdigit()):
            mask = tokens[1]
            next_hop_index = 2
        if next_hop_index >= len(tokens):
            return StaticRoute(destination, mask, "", vpn, source, False, "Missing next hop")
        return StaticRoute(destination, mask, tokens[next_hop_index], vpn, source)

    def _parse_ipv6_static_route(self, line: SourceLine) -> IPv6StaticRoute:
        tokens = list(line.tokens[2:])
        source = SourceRange(line.number)
        vpn = None
        if len(tokens) >= 2 and tokens[0].lower() == "vpn-instance":
            vpn = tokens[1]
            tokens = tokens[2:]
        if len(tokens) < 2:
            return IPv6StaticRoute("", None, "", vpn, source, False, "Too few arguments")
        destination = tokens[0]
        prefix_length = None
        next_hop_index = 1
        if "/" not in destination and len(tokens) >= 3 and tokens[1].isdigit():
            prefix_length = tokens[1]
            next_hop_index = 2
        if next_hop_index >= len(tokens):
            return IPv6StaticRoute(destination, prefix_length, "", vpn, source, False, "Missing next hop")
        return IPv6StaticRoute(destination, prefix_length, tokens[next_hop_index], vpn, source)

    @staticmethod
    def _is_ip_address(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    @staticmethod
    def _looks_like_mask(token: str) -> bool:
        return bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", token))

    @staticmethod
    def _expand_vlans(tokens: tuple[str, ...] | list[str]) -> set[int]:
        result: set[int] = set()
        index = 0
        while index < len(tokens):
            token = tokens[index].lower()
            if token.isdigit():
                start = int(token)
                if (
                    index + 2 < len(tokens)
                    and tokens[index + 1].lower() == "to"
                    and tokens[index + 2].isdigit()
                ):
                    end = int(tokens[index + 2])
                    if 1 <= start <= end <= 4094:
                        result.update(range(start, end + 1))
                    index += 3
                    continue
                if 1 <= start <= 4094:
                    result.add(start)
            index += 1
        return result

    @staticmethod
    def _record_acl_reference(config: DeviceConfig, line: SourceLine, object_name: str) -> None:
        tokens = line.tokens
        for marker in ("acl", "name"):
            if marker in tuple(token.lower() for token in tokens):
                index = tuple(token.lower() for token in tokens).index(marker)
                if index + 1 < len(tokens):
                    config.acl_references.append((tokens[index + 1], object_name, SourceRange(line.number)))
                return
