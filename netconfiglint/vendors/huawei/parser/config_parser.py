"""Huawei VRP configuration parser.

The parser is intentionally bounded. It normalizes supported constructs and retains unknown
lines instead of guessing at unsupported command semantics.
"""

from __future__ import annotations

import ipaddress
import re
import textwrap
from dataclasses import asdict

from netconfiglint.core.analyzer.control import charge_vlan_memberships, checkpoint
from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.lexer import SourceLine, lex_lines
from netconfiglint.core.model import (
    ACL,
    BGPAddressFamily,
    BGPGroup,
    BGPPeer,
    BGPProcess,
    ConfigBlock,
    ConfigCommand,
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
from netconfiglint.vendors.huawei.parser.acl_identity import parse_acl_identity
from netconfiglint.vendors.huawei.parser.semantics import acl_rule, bgp_network, route_arguments, vlan_list
from netconfiglint.vendors.huawei.parser.snapshot_parser import HuaweiSnapshotParser
from netconfiglint.vendors.huawei.profiles import ProfileDatabase

_SENSITIVE = re.compile(r"\b(password|cipher|community|pre-shared-key|secret|private-key)\b", re.IGNORECASE)


class HuaweiConfigParser:
    def parse(
        self, source: str, mode: AnalysisMode, detection: VendorDetection, *, initial_view: str | None = None
    ) -> DeviceConfig:
        lines = lex_lines(textwrap.dedent(source) if mode == AnalysisMode.SNIPPET else source)
        config = DeviceConfig(vendor=detection.vendor, source_lines=tuple(source.splitlines()))
        if initial_view is not None:
            if (
                mode != AnalysisMode.SNIPPET
                or re.fullmatch(
                    r"aaa|user-interface (?:vty|console) \d+(?: \d+)?|interface \S+|ospf \d+|bgp \d+|acl .+",
                    initial_view,
                    re.I,
                )
                is None
            ):
                raise ValueError("Unsupported initial view; use a supported snippet view header")
            lines = tuple(SourceLine(line.number, " " + line.raw, line.text, line.tokens) for line in lines)
        config.blocks = self._index_blocks(lines, initial_view)
        config.metadata["profile_id"] = detection.profile_id
        database = ProfileDatabase()
        resolution = database.resolve(detection)
        if resolution.match_level == "model+version":
            config.feature_facts = {
                fact.feature: asdict(fact)
                for fact in database.effective_features(resolution.profile.profile_id)
            }
        context: tuple[str, object] | None = None
        if initial_view is not None:
            context = self._start_block(
                config, SourceLine(1, initial_view, initial_view, tuple(initial_view.split()))
            )

        for line in lines:
            checkpoint()
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
            if not line.raw[:1].isspace():
                context = None
            if self._parse_global(config, line):
                continue
            if context is not None and self._parse_context(config, line, context):
                continue
            if lower.startswith(("description ", "!software version", "huawei versatile routing platform")):
                config.ignored_lines.append(SourceRange(line.number))
                continue
            config.unparsed_lines.append(SourceRange(line.number))
            if lower.startswith(("undo ", "ospfv3")):
                config.unsupported_lines.append(SourceRange(line.number))
        for block in config.blocks:
            checkpoint()
            if not block.context_known:
                config.context_unknown_lines.extend(command.source for command in block.commands)
        config.acl_references = [
            (config.acl_aliases.get(key, key), obj, source) for key, obj, source in config.acl_references
        ]
        consumers: list[RoutePolicy | TrafficClassifier] = [
            *config.route_policies.values(),
            *config.traffic_classifiers.values(),
        ]
        for consumer in consumers:
            consumer.acl_references = [
                (config.acl_aliases.get(key, key), source) for key, source in consumer.acl_references
            ]
        if mode == AnalysisMode.SNAPSHOT:
            config.snapshot = HuaweiSnapshotParser().parse(source)
        return config

    @staticmethod
    def _index_blocks(lines: tuple[SourceLine, ...], initial_view: str | None = None) -> list[ConfigBlock]:
        """Build a lossless-enough block index for rules outside the normalized core model."""
        active = ConfigBlock(initial_view, SourceRange(1)) if initial_view is not None else None
        blocks: list[ConfigBlock] = [active] if active is not None else []
        for line in lines:
            checkpoint()
            text = line.text
            if not text or text.lower() == "return":
                continue
            if text == "#":
                active = None
                continue
            if not line.raw[:1].isspace():
                active = ConfigBlock(text, SourceRange(line.number))
                blocks.append(active)
                continue
            if active is None:
                active = ConfigBlock("Unknown context", SourceRange(line.number), context_known=False)
                blocks.append(active)
            active.commands.append(ConfigCommand(text, SourceRange(line.number)))
        return blocks

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
        if tokens and tokens[0].lower() == "ospf":
            if len(tokens) >= 2 and tokens[1].lower() == "process":
                return None
            process_id = tokens[1] if len(tokens) >= 2 and tokens[1].isdigit() else "1"
            process = config.ospf_processes.setdefault(process_id, OSPFProcess(process_id, source))
            return ("ospf", process)
        if lower.startswith("acl ") and self._parse_global(config, line):
            identity = parse_acl_identity(tokens[1:])
            if identity is not None:
                return ("acl", config.acls[config.acl_aliases.get(identity.key, identity.key)])
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
        if tokens and tokens[0].lower() == "vlan":
            try:
                values = tokens[2:] if len(tokens) > 1 and tokens[1].lower() == "batch" else tokens[1:]
                if len(tokens) > 1 and tokens[1].lower() != "batch" and len(values) != 1:
                    raise ValueError("A single VLAN declaration requires one VLAN ID")
                for vlan_id in vlan_list(values)[0]:
                    checkpoint()
                    config.vlans.setdefault(vlan_id, Vlan(vlan_id, source))
            except ValueError as exc:
                self._issue(config, line, "HUA-PARSE-VLAN", "VLAN", str(exc))
            return True
        if lower == "ip route-static" or lower.startswith("ip route-static "):
            config.static_routes.append(self._parse_static_route(line))
            return True
        if lower == "ipv6 route-static" or lower.startswith("ipv6 route-static "):
            config.ipv6_static_routes.append(self._parse_ipv6_static_route(line))
            return True
        if lower.startswith("ip ip-prefix ") and len(tokens) >= 3:
            config.prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("ip ipv6-prefix ") and len(tokens) >= 3:
            config.prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("acl ") and len(tokens) >= 2:
            identity = parse_acl_identity(tokens[1:])
            if identity is None:
                return False
            acl_type = "unknown"
            if identity.kind == "number":
                number = int(identity.value) if len(identity.value) <= 4 else 0
                acl_type = (
                    "basic" if 2000 <= number <= 2999 else "advanced" if 3000 <= number <= 3999 else "unknown"
                )
            elif any(word.lower() in {"advanced", "advance"} for word in tokens):
                acl_type = "advanced"
            elif "basic" in (word.lower() for word in tokens):
                acl_type = "basic"
            keys = [identity.key]
            words = [token.lower() for token in tokens]
            if identity.kind == "name" and "number" in words:
                index = words.index("number")
                if index + 1 < len(tokens) and tokens[index + 1].isdigit():
                    value = tokens[index + 1].lstrip("0") or "0"
                    number = int(value) if value.isascii() and len(value) <= 4 else 0
                    keys.append(f"{identity.family}:number:{value}")
                    acl_type = (
                        "basic"
                        if 2000 <= number <= 2999
                        else "advanced"
                        if 3000 <= number <= 3999
                        else "unknown"
                    )
            existing = {
                config.acl_aliases.get(key, key)
                for key in keys
                if config.acl_aliases.get(key, key) in config.acls
            }
            if len(existing) > 1:
                self._issue(config, line, "HUA-PARSE-ACL", "ACL", "Conflicting ACL name/number aliases")
                return False
            canonical = next(iter(existing), identity.key)
            config.acls.setdefault(
                canonical, ACL(identity.value, source, identity.family, identity.kind, acl_type)
            )
            for key in keys:
                config.acl_aliases[key] = canonical
            return True
        if lower.startswith("traffic-filter ") and not line.raw[:1].isspace():
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
            return self._parse_bgp(config, line, value)
        if kind == "acl" and isinstance(value, ACL):
            if line.tokens[:2] == ("undo", "rule") and len(line.tokens) == 3:
                value.rules.pop(line.tokens[2], None)
                return True
            rule = acl_rule(line.tokens, SourceRange(line.number), value.acl_type, value.family)
            if rule is not None:
                value.rules[rule.rule_id] = rule
                return rule.syntax_known
            return False
        if kind == "ospf" and isinstance(value, OSPFProcess):
            return self._parse_ospf(line, value)
        if kind == "route_policy" and isinstance(value, RoutePolicy):
            return self._parse_route_policy(line, value)
        if kind == "traffic_classifier" and isinstance(value, TrafficClassifier):
            return self._parse_traffic_classifier(line, value)
        if kind == "traffic_policy" and isinstance(value, TrafficPolicy):
            return self._parse_traffic_policy(line, value)
        return False

    def _parse_interface(self, config: DeviceConfig, line: SourceLine, interface: Interface) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        interface.raw_commands.append((line.text, source))
        vlan_command = lower.removeprefix("undo ")
        undo = lower.startswith("undo ")
        lists = {
            "port trunk allow-pass vlan": "allowed_vlans",
            "port hybrid tagged vlan": "hybrid_tagged_vlans",
            "port hybrid untagged vlan": "hybrid_untagged_vlans",
        }
        for prefix, key in lists.items():
            checkpoint()
            if vlan_command == prefix or vlan_command.startswith(prefix + " "):
                try:
                    values, all_vlans = vlan_list(tokens[(5 if undo else 4) :], allow_all=True)
                except ValueError as exc:
                    self._issue(config, line, "HUA-PARSE-VLAN", interface.name, str(exc))
                    return True
                charge_vlan_memberships(len(values))
                existing: set[int] = getattr(interface, key)
                sources = interface.vlan_sources.setdefault(key, {})
                excluded = interface.vlan_exclusions.setdefault(key, set())
                if all_vlans:
                    existing.clear()
                    sources.clear()
                    excluded.clear()
                    if undo:
                        interface.vlan_all.discard(key)
                    else:
                        interface.vlan_all.add(key)
                elif undo:
                    existing.difference_update(values)
                    for vlan_id in values:
                        checkpoint()
                        sources.pop(vlan_id, None)
                    if key in interface.vlan_all:
                        excluded.update(values)
                else:
                    existing.update(values)
                    excluded.difference_update(values)
                    for vlan_id in values:
                        checkpoint()
                        sources.setdefault(vlan_id, source)
                interface.command_sources[key] = source
                return True
        singles = {
            "port default vlan": "access_vlan",
            "port trunk pvid vlan": "pvid_vlan",
            "port hybrid pvid vlan": "pvid_vlan",
        }
        for prefix, key in singles.items():
            checkpoint()
            if vlan_command == prefix or vlan_command.startswith(prefix + " "):
                single_values = vlan_command.split()[len(prefix.split()) :]
                if undo and not single_values:
                    setattr(interface, key, None)
                else:
                    try:
                        if len(single_values) != 1:
                            raise ValueError("Expected one VLAN ID")
                        vlan_id = next(iter(vlan_list(single_values)[0]))
                        setattr(interface, key, None if undo else vlan_id)
                    except ValueError as exc:
                        self._issue(config, line, "HUA-PARSE-VLAN", interface.name, str(exc))
                interface.command_sources[key] = source
                return True
        if lower.startswith("description "):
            interface.description = line.text[len("description ") :]
        elif lower.startswith("port link-type ") and len(tokens) >= 3:
            interface.link_type = tokens[2].lower()
            interface.command_sources["link_type"] = source
        elif lower.startswith("ip address ") and len(tokens) >= 3:
            if tokens[2].lower() not in {"dhcp-alloc", "negotiated", "ppp-negotiate", "unnumbered"}:
                interface.ip_addresses.append((tokens[2], tokens[3] if len(tokens) >= 4 else None, source))
            interface.command_sources["ip_address"] = source
        elif lower.startswith("ipv6 address ") and len(tokens) >= 3:
            if tokens[2].lower() != "auto":
                ipv6_prefix = tokens[3] if len(tokens) >= 4 and tokens[3].isdigit() else None
                interface.ipv6_addresses.append((tokens[2], ipv6_prefix, source))
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

    def _parse_bgp(self, config: DeviceConfig, line: SourceLine, bgp: BGPProcess) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("router-id ") and len(tokens) >= 2:
            bgp.router_id = tokens[1]
            return True
        if lower.startswith("group ") and len(tokens) >= 2:
            group = bgp.groups.setdefault(tokens[1], BGPGroup(tokens[1], source))
            group.declared = True
            group.source = source
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
                    peer.group_source = source
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
        if lower == "network" or lower.startswith("network "):
            if not bgp.address_families:
                bgp.address_families.append(BGPAddressFamily("ipv4-family unicast", bgp.source))
            family = bgp.address_families[-1]
            try:
                address, mask, policy = bgp_network(tokens[1:], 6 if family.name.startswith("ipv6") else 4)
                family.networks.append((address, mask, source))
                if policy is not None:
                    family.network_policies.append((policy, source))
            except ValueError as exc:
                self._issue(config, line, "HUA-PARSE-BGP", family.name, str(exc))
            return True
        return False

    def _parse_ospf(self, line: SourceLine, ospf: OSPFProcess) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith("area ") and len(tokens) >= 2:
            ospf.areas.add(tokens[1])
            ospf.area_order.append(tokens[1])
            return True
        if lower.startswith("network ") and len(tokens) >= 3:
            area = ospf.area_order[-1] if ospf.area_order else "Unknown"
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
        if lower.startswith(("if-match acl ", "if-match ipv6 acl ")):
            offset = 3 if tokens[1].lower() == "ipv6" else 2
            identity = parse_acl_identity(tokens[offset:], family="ipv6" if offset == 3 else "ipv4")
            if identity is not None:
                policy.acl_references.append((identity.key, source))
                return True
        return False

    @staticmethod
    def _parse_traffic_classifier(line: SourceLine, classifier: TrafficClassifier) -> bool:
        tokens = line.tokens
        lower_tokens = tuple(token.lower() for token in tokens)
        source = SourceRange(line.number)
        if lower_tokens[:2] == ("if-match", "acl") or lower_tokens[:3] == ("if-match", "ipv6", "acl"):
            offset = 3 if lower_tokens[1] == "ipv6" else 2
            identity = parse_acl_identity(tokens[offset:], family="ipv6" if offset == 3 else "ipv4")
            if identity is not None:
                classifier.acl_references.append((identity.key, source))
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

    @staticmethod
    def _issue(config: DeviceConfig, line: SourceLine, rule_id: str, object_name: str, issue: str) -> None:
        config.parse_issues.append(
            Diagnostic(
                Severity.ERROR,
                rule_id,
                SourceRange(line.number),
                object_name,
                "The command could not be normalized safely.",
                issue,
                "Check the required arguments against the command reference.",
                Confidence.DOCUMENTED,
            )
        )

    @staticmethod
    def _parse_static_route(line: SourceLine) -> StaticRoute:
        destination, mask, hop, vpn, issue, known = route_arguments(line.tokens[2:], 4)
        return StaticRoute(destination, mask, hop, vpn, SourceRange(line.number), not issue, issue, known)

    @staticmethod
    def _parse_ipv6_static_route(line: SourceLine) -> IPv6StaticRoute:
        destination, mask, hop, vpn, issue, known = route_arguments(line.tokens[2:], 6)
        return IPv6StaticRoute(destination, mask, hop, vpn, SourceRange(line.number), not issue, issue, known)

    @staticmethod
    def _is_ip_address(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    @staticmethod
    def _record_acl_reference(config: DeviceConfig, line: SourceLine, object_name: str) -> None:
        tokens = line.tokens
        lower = tuple(token.lower() for token in tokens)
        if "acl" not in lower:
            return
        index = lower.index("acl")
        identity = parse_acl_identity(
            tokens[index + 1 :], family="ipv6" if "ipv6" in lower[:index] else "ipv4"
        )
        if identity is not None:
            config.acl_references.append((identity.key, object_name, SourceRange(line.number)))
