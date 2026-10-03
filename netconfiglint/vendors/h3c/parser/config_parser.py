"""H3C Comware configuration parser.

The parser is intentionally bounded. It normalizes supported constructs and retains unknown
lines instead of guessing at unsupported command semantics.
"""

from __future__ import annotations

import ipaddress
import re
import textwrap
from dataclasses import replace

from netconfiglint.commands import catalogued_family, is_annotation
from netconfiglint.core.analyzer.control import charge_vlan_memberships, checkpoint
from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.analyzer.operational_input import mask_operational_output
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.lexer import SourceLine, is_comment_line, lex_lines, normalize_cli_line
from netconfiglint.core.model import (
    ACL,
    BGPAddressFamily,
    BGPGroup,
    BGPPeer,
    BGPProcess,
    ConfigBlock,
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
from netconfiglint.core.parser.numbers import bounded_integer
from netconfiglint.vendors.h3c.parser.acl_identity import parse_acl_identity
from netconfiglint.vendors.h3c.parser.diagnostic_bundle import extract_h3c_diagnostic_bundle
from netconfiglint.vendors.h3c.parser.semantics import acl_rule, bgp_network, route_arguments, vlan_list
from netconfiglint.vendors.h3c.parser.snapshot_parser import H3CSnapshotParser
from netconfiglint.vendors.h3c.parser.views import effective_blocks, index_blocks, interface_name

# Only modeled interface facts or syntax consumed by Comware management rules count here.
# Other documented families stay catalogued until their parameters have a semantic model.
_SEMANTIC_PATTERNS = tuple(
    (family, re.compile(pattern, re.IGNORECASE))
    for family, pattern in (
        ("system", r"^(?:version \S+.*|sysname \S+)$"),
        ("management_server", r"^(?:telnet|ftp|ssh|sftp) server (?:enable|disable)$"),
        (
            "terminal",
            "^(?:line (?:class )?(?:console|con|vty)(?: \\d+(?: \\d+)?)?|authenticati"
            "on-mode (?:none|password|scheme)|protocol inbound (?:all|ssh|telnet|ss"
            "h telnet|telnet ssh)|user-role \\S+)$",
        ),
        (
            "snmp",
            "^snmp-agent(?: community (?:read|write) (?:simple |cipher )?\\S+| sys-i"
            "nfo version (?:v1|v2c|v3)(?: (?:v1|v2c|v3))*)?$",
        ),
        (
            "ntp",
            "^ntp-service (?:authentication enable|(?:unicast-server|unicast-peer) "
            "\\S+(?: authentication-keyid \\d+)?)$",
        ),
        (
            "local_user",
            "^(?:local-user \\S+ class (?:manage|network)|password (?:simple|cipher|"
            "hash) \\S+|service-type (?:ssh|telnet|ftp|http|https|terminal|lan-acces"
            "s)(?: (?:ssh|telnet|ftp|http|https|terminal|lan-access))*)$",
        ),
        ("security", r"^undo ssl version (?:ssl3\.0|tls1\.[01]) disable$"),
        ("interface_mode", r"^port link-mode (?:bridge|route)$"),
        ("interface_arp", r"^arp filter source \S+(?: \S+)?$"),
        ("interface_ospf", r"^ospf network-type (?:broadcast|nbma|p2p|p2mp)$"),
    )
)
_PLATFORM_SPECIFIC = re.compile(r"^(?:system-working-mode\b|xbar\b|ftth\b|onu\b)", re.IGNORECASE)
_IRF_COMMAND = re.compile(
    r"^(?:irf-port\s+\d+/[12]|irf-port-configuration\s+active|"
    r"irf\s+(?:member\s+\d+\s+(?:renumber|priority|description)\b.*|domain\s+\d+|"
    r"mac-address\s+persistent\b.*|auto-update\s+enable|link-delay\s+\d+)|"
    r"(?:undo\s+)?port\s+group\s+interface\s+\S+)$",
    re.I,
)
_SESSION_COMMAND = re.compile(r"^(?:sys|system-view|quit|return|save(?:\s+.*)?)$", re.I)


def _semantic_family(text: str) -> str | None:
    return next((family for family, pattern in _SEMANTIC_PATTERNS if pattern.fullmatch(text)), None)


_SENSITIVE = re.compile(r"\b(password|cipher|community|pre-shared-key|secret|private-key)\b", re.IGNORECASE)


class H3CConfigParser:
    def parse(
        self, source: str, mode: AnalysisMode, detection: VendorDetection, *, initial_view: str | None = None
    ) -> DeviceConfig:
        bundle = extract_h3c_diagnostic_bundle(source)
        parser_source, analysis_scope = (
            mask_operational_output(source)
            if mode in {AnalysisMode.FULL, AnalysisMode.SNAPSHOT}
            else (source, set())
        )
        if bundle is not None:
            parser_source, analysis_scope = bundle.masked_configuration, set(bundle.analysis_lines)
        annotations = {
            number
            for number, line in enumerate(parser_source.splitlines(), 1)
            if is_annotation(line) or (is_comment_line(line) and line.strip() != "#")
        }
        parser_source = "\n".join(
            "" if number in annotations else line for number, line in enumerate(parser_source.splitlines(), 1)
        )
        lines = lex_lines(textwrap.dedent(parser_source) if mode == AnalysisMode.SNIPPET else parser_source)
        config = DeviceConfig(vendor="H3C", source_lines=tuple(source.splitlines()))
        config.ignored_lines.extend(SourceRange(number) for number in annotations)
        if mode in {AnalysisMode.FULL, AnalysisMode.SNAPSHOT}:
            config.analysis_lines = analysis_scope
            config.metadata["analysis_scope_explicit"] = "true"
        if initial_view is not None:
            if (
                mode != AnalysisMode.SNIPPET
                or re.fullmatch(
                    r"line (?:class )?(?:vty|console)(?: \d+(?: \d+)?)?|"
                    r"local-user \S+ class (?:manage|network)|"
                    r"interface \S+(?: \d[\d/.:]*)?|ospf \d+|bgp \d+|acl .+",
                    initial_view,
                    re.I,
                )
                is None
            ):
                raise ValueError("Unsupported initial view; use a supported snippet view header")
            lines = tuple(SourceLine(line.number, " " + line.raw, line.text, line.tokens) for line in lines)
        config.blocks, superseded = effective_blocks(self._index_blocks(lines, initial_view))
        config.ignored_lines.extend(superseded)
        config.metadata["profile_id"] = detection.profile_id
        if bundle is not None:
            config.metadata["diagnostic_bundle_sections"] = str(bundle.section_count)
            config.metadata["saved_configuration_present"] = str(bundle.saved_present).lower()
            config.metadata["saved_configuration_matches"] = (
                "unknown"
                if bundle.saved_matches_current is None
                else str(bundle.saved_matches_current).lower()
            )
        # Sensitive input is inventoried even when the command has since been removed.
        for number, original in enumerate(source.splitlines(), 1):
            checkpoint()
            if _SENSITIVE.search(original):
                config.sensitive_lines.append(SourceRange(number))
        for block in config.blocks:
            checkpoint()
            header = SourceLine(block.source.line, block.header, block.header, tuple(block.header.split()))
            context = self._start_block(config, header) if block.context_known else None
            if context is None and block.context_known and not self._parse_global(config, header):
                self._unparsed(config, header)
            for command in block.commands:
                checkpoint()
                line = SourceLine(
                    command.source.line, " " + command.text, command.text, tuple(command.text.split())
                )
                if context is not None and self._parse_context(config, line, context, command.views):
                    continue
                self._unparsed(config, line)
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
        if mode in {AnalysisMode.SNAPSHOT, AnalysisMode.FULL}:
            config.snapshot = H3CSnapshotParser().parse(source)
        semantic_lines: set[int] = set()
        irf_ports: dict[int, tuple[int, int]] = {}
        irf_bindings: set[int] = set()
        for number, source_text in enumerate(config.source_lines, 1):
            if mode in {AnalysisMode.FULL, AnalysisMode.SNAPSHOT} and number not in analysis_scope:
                continue
            body = normalize_cli_line(source_text)[0].strip()
            if _IRF_COMMAND.fullmatch(body):
                semantic_lines.add(number)
                if match := re.fullmatch(r"irf-port\s+(\d+)/([12])", body, re.I):
                    irf_ports[bounded_integer(match.group(1))] = (bounded_integer(match.group(2)), number)
                elif re.fullmatch(r"port\s+group\s+interface\s+\S+", body, re.I):
                    irf_bindings.add(number)
            elif _SESSION_COMMAND.fullmatch(body) or is_annotation(body):
                config.ignored_lines.append(SourceRange(number))
                semantic_lines.add(number)
        # A two-member sample with both peer ports on the same side cannot form
        # the direct adjacency described by the H3C IRF configuration guide.
        if len(irf_ports) == 2 and len({side for side, _ in irf_ports.values()}) == 1 and irf_bindings:
            members = sorted(irf_ports)
            side, source_line = irf_ports[members[1]]
            config.parse_issues.append(
                Diagnostic(
                    Severity.WARNING,
                    "H3C-IRF-001",
                    SourceRange(source_line),
                    "IRF peer port",
                    f"Members {members[0]} and {members[1]} both use IRF port index {side}.",
                    "If these are the two directly connected peers, their IRF port indices must differ "
                    "(for example 1/2 to 2/1). The supplied text does not prove the cabling topology.",
                    "Verify display irf link and both bindings; connect a /1 port to a peer /2 port.",
                    Confidence.INFERRED,
                )
            )
        command_families: dict[str, list[int]] = {}
        for block in config.blocks:
            commands = [(block.header, block.source), *((item.text, item.source) for item in block.commands)]
            interface = None
            if block.header.lower().startswith("interface "):
                interface = config.interfaces.get(interface_name(block.header[10:]))
            for _text, item_source in commands:
                original_text = normalize_cli_line(config.source_lines[item_source.line - 1])[0].strip()
                family = _semantic_family(original_text)
                if family is None:
                    continue
                semantic_lines.add(item_source.line)
                command_families.setdefault(family, []).append(item_source.line)
                if interface is None:
                    continue
                if match := re.fullmatch(r"port\s+link-mode\s+(bridge|route)", original_text, re.I):
                    interface.link_mode = match.group(1).lower()
                    interface.command_sources["link_mode"] = item_source
                elif match := re.fullmatch(
                    r"arp\s+filter\s+source\s+(\S+)(?:\s+(\S+))?", original_text, re.I
                ):
                    interface.arp_filter_sources.append((match.group(1), match.group(2) or "", item_source))
                elif match := re.fullmatch(r"ospf\s+network-type\s+(\S+)", original_text, re.I):
                    interface.ospf_network_type = match.group(1).lower()
                    interface.command_sources["ospf_network_type"] = item_source
        config.feature_facts["h3c.command_families"] = {
            family: {"count": len(set(lines)), "lines": sorted(set(lines))}
            for family, lines in command_families.items()
        }
        config.unparsed_lines = [item for item in config.unparsed_lines if item.line not in semantic_lines]
        config.unsupported_lines = [
            item for item in config.unsupported_lines if item.line not in semantic_lines
        ]
        config.context_unknown_lines = [
            item for item in config.context_unknown_lines if item.line not in semantic_lines
        ]
        catalogued_families: dict[str, list[int]] = {}
        line_context = {
            command.source.line: (block.header.lower(), command.views)
            for block in config.blocks
            for command in block.commands
        }
        remaining = []
        for item in config.unparsed_lines:
            catalog_family = catalogued_family(
                "h3c", normalize_cli_line(config.source_lines[item.line - 1])[0]
            )
            context = line_context.get(item.line)
            if catalog_family is None or (
                context is not None
                and (
                    context[1]
                    or not context[0].startswith("interface ")
                    or catalog_family.name
                    not in {"stp", "lldp", "interface", "ip", "qos", "multicast", "acl"}
                )
            ):
                remaining.append(item)
                continue
            config.catalogued_lines.append(item)
            catalogued_families.setdefault(catalog_family.name, []).append(item.line)
        config.unparsed_lines = remaining
        catalogued_numbers = {item.line for item in config.catalogued_lines}
        config.unsupported_lines = [
            item for item in config.unsupported_lines if item.line not in catalogued_numbers
        ]
        config.command_catalog = {
            family: {"count": len(numbers), "lines": numbers}
            for family, numbers in catalogued_families.items()
        }
        config.unsupported_lines = sorted(
            {*(item for item in config.unsupported_lines), *config.unparsed_lines},
            key=lambda item: item.line,
        )
        existing_issue_lines = {item.source.line for item in config.parse_issues}
        for item in config.unsupported_lines:
            if item.line in existing_issue_lines or item.line > len(config.source_lines):
                continue
            original_text = config.source_lines[item.line - 1].strip()
            config.parse_issues.append(
                Diagnostic(
                    Severity.UNKNOWN,
                    "H3C-PLATFORM-001" if _PLATFORM_SPECIFIC.match(original_text) else "H3C-CMD-001",
                    SourceRange(item.line),
                    original_text.split(maxsplit=1)[0] if original_text else "Configuration",
                    (
                        "This platform-specific H3C command cannot be verified for an unknown target."
                        if _PLATFORM_SPECIFIC.match(original_text)
                        else "This H3C command is preserved, but its effective semantics are not verified."
                    ),
                    (
                        "The supplied snippet does not prove the target model, Comware release, "
                        "cards, or licenses."
                        if _PLATFORM_SPECIFIC.match(original_text)
                        else "No Comware semantic checker is registered for this exact command or view."
                    ),
                    "Confirm the command against the matching H3C model/release and installed hardware "
                    "reference before applying it.",
                    Confidence.LOW,
                )
            )
        return config

    @staticmethod
    def _index_blocks(lines: tuple[SourceLine, ...], initial_view: str | None = None) -> list[ConfigBlock]:
        return index_blocks(lines, initial_view)

    @staticmethod
    def _unparsed(config: DeviceConfig, line: SourceLine) -> None:
        lower = line.text.lower()
        if lower.startswith(
            (
                "description ",
                "!software version",
                "h3c ",
                "comware software",
                "software version",
                "hpe comware",
            )
        ):
            config.ignored_lines.append(SourceRange(line.number))
        else:
            config.unparsed_lines.append(SourceRange(line.number))
            if lower.startswith(("undo ", "ospfv3")):
                config.unsupported_lines.append(SourceRange(line.number))

    def _start_block(self, config: DeviceConfig, line: SourceLine) -> tuple[str, object] | None:
        if line.raw[:1].isspace():
            return None
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if len(tokens) >= 2 and lower.startswith("interface "):
            if tokens[1].lower() == "ip" and "address/mask" in lower:
                return None
            name = interface_name(line.text[10:])
            if re.match(r"(?:vlanif|eth-trunk)\d", name, re.I):
                return None  # These are VRP interface forms, not Comware interface declarations.
            # Unknown trailing view qualifiers must not become invented interface names.
            if " " in name:
                return None
            if match := re.fullmatch(r"vlan-interface(\d+)", name, re.I):
                value = match.group(1)
                if len(value) > 4 or not 1 <= bounded_integer(value) <= 4094:
                    self._issue(
                        config, line, "H3C-PARSE-INTERFACE", "VLAN interface", "Invalid VLAN interface number"
                    )
                    return None
            interface = config.interfaces.setdefault(name, Interface(name, source))
            if (
                re.fullmatch(r"(?:bridge|route)-aggregation\d+", name, re.I)
                and interface.aggregation_mode is None
            ):
                interface.aggregation_mode = "static"
                interface.aggregation_mode_origin = "reference_default"
            return ("interface", interface)
        if len(tokens) >= 2 and lower.startswith("bgp "):
            if re.fullmatch(r"bgp \d+(?:\.\d+)?", lower) is None:
                return None
            config.bgp = config.bgp or BGPProcess(tokens[1], source)
            return ("bgp", config.bgp)
        if tokens and tokens[0].lower() == "ospf":
            if re.fullmatch(r"ospf(?: \d+)?(?: (?:router-id|vpn-instance) \S+)*", line.text, re.I) is None:
                return None
            process_id = tokens[1] if len(tokens) >= 2 and tokens[1].isdigit() else "1"
            process = config.ospf_processes.setdefault(process_id, OSPFProcess(process_id, source))
            words = [word.lower() for word in tokens]
            if "vpn-instance" in words and words.index("vpn-instance") + 1 < len(tokens):
                process.vpn_instance = tokens[words.index("vpn-instance") + 1]
            return ("ospf", process)
        if re.fullmatch(r"line (?:class )?(?:vty|console|con)(?: \d+(?: \d+)?)?", lower):
            return ("terminal", line.text)
        if re.fullmatch(r"local-user \S+ class (?:manage|network)", line.text, re.I):
            return ("terminal", line.text)
        if lower.startswith("acl ") and self._parse_global(config, line):
            identity = parse_acl_identity(tokens[1:])
            if identity is not None:
                return ("acl", config.acls[config.acl_aliases.get(identity.key, identity.key)])
        if re.fullmatch(r"route-policy \S+ (?:permit|deny) node \d+", line.text, re.I):
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
        if len(tokens) >= 3 and lower.startswith("qos policy "):
            traffic_policy = config.traffic_policies.setdefault(tokens[2], TrafficPolicy(tokens[2], source))
            return ("traffic_policy", traffic_policy)
        return None

    def _parse_global(self, config: DeviceConfig, line: SourceLine) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        if lower.startswith(("ip route-static default-preference ", "ipv6 route-static default-preference ")):
            # A process preference setting is not a route destination.
            return (
                len(tokens) == 4
                and tokens[3].isascii()
                and tokens[3].isdigit()
                and len(tokens[3]) <= 3
                and 1 <= bounded_integer(tokens[3]) <= 255
            )
        if lower.startswith("undo vlan "):
            try:
                values = tokens[3:] if len(tokens) > 2 and tokens[2].lower() == "batch" else tokens[2:]
                for vlan_id in vlan_list(values)[0]:
                    checkpoint()
                    config.vlans.pop(vlan_id, None)
            except ValueError as exc:
                self._issue(config, line, "H3C-PARSE-VLAN", "VLAN", str(exc))
            return True
        if tokens and tokens[0].lower() == "vlan":
            try:
                values = tokens[1:]
                if not re.fullmatch(r"vlan \d+(?: to \d+)?", lower):
                    raise ValueError("Expected a Comware VLAN ID or inclusive 'to' range")
                for vlan_id in vlan_list(values)[0]:
                    checkpoint()
                    config.vlans.setdefault(vlan_id, Vlan(vlan_id, source))
            except ValueError as exc:
                self._issue(config, line, "H3C-PARSE-VLAN", "VLAN", str(exc))
            return True
        if lower == "ip route-static" or lower.startswith("ip route-static "):
            config.static_routes.append(self._parse_static_route(line))
            return True
        if lower == "ipv6 route-static" or lower.startswith("ipv6 route-static "):
            config.ipv6_static_routes.append(self._parse_ipv6_static_route(line))
            return True
        if lower.startswith("ip prefix-list ") and len(tokens) >= 3:
            if not self._valid_prefix(line.tokens, 4):
                self._issue(
                    config, line, "H3C-PARSE-PREFIX", tokens[2], "Invalid prefix, mask, or ge/le range"
                )
                return True
            config.prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("ipv6 prefix-list ") and len(tokens) >= 3:
            if not self._valid_prefix(line.tokens, 6):
                self._issue(
                    config, line, "H3C-PARSE-PREFIX", tokens[2], "Invalid IPv6 prefix, mask, or ge/le range"
                )
                return True
            config.ipv6_prefix_lists.setdefault(tokens[2], PrefixList(tokens[2], source))
            return True
        if lower.startswith("acl ") and len(tokens) >= 2:
            identity = parse_acl_identity(tokens[1:])
            if identity is None:
                return False
            acl_type = "unknown"
            if identity.kind == "number":
                number = bounded_integer(identity.value) if len(identity.value) <= 4 else 0
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
                    number = bounded_integer(value) if value.isascii() and len(value) <= 4 else 0
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
                self._issue(config, line, "H3C-PARSE-ACL", "ACL", "Conflicting ACL name/number aliases")
                return False
            canonical = next(iter(existing), identity.key)
            config.acls.setdefault(
                canonical, ACL(identity.value, source, identity.family, identity.kind, acl_type)
            )
            for key in keys:
                config.acl_aliases[key] = canonical
            return True
        if _semantic_family(line.text) is not None:
            return True
        if lower.startswith("sysname "):
            config.metadata["sysname"] = "<redacted>"
            return True
        return False

    def _parse_context(
        self, config: DeviceConfig, line: SourceLine, context: tuple[str, object], views: tuple[str, ...] = ()
    ) -> bool:
        kind, value = context
        if kind == "terminal" and _semantic_family(line.text) in {"terminal", "local_user", "rbac"}:
            return True
        if views and kind not in {"bgp", "ospf", "vpn"}:
            return False
        if kind == "interface" and isinstance(value, Interface):
            return self._parse_interface(config, line, value)
        if kind == "bgp" and isinstance(value, BGPProcess):
            return self._parse_bgp(config, line, value, views)
        if kind == "acl" and isinstance(value, ACL):
            if line.tokens[:2] == ("undo", "rule") and len(line.tokens) == 3:
                value.rules.pop(line.tokens[2], None)
                return True
            rule = acl_rule(line.tokens, SourceRange(line.number), value.acl_type, value.family)
            if rule is not None:
                if rule.rule_id in value.rules:
                    rule = replace(rule, syntax_known=False)
                value.rules[rule.rule_id] = rule
                return rule.syntax_known
            if line.text.lower().startswith("rule "):
                value.unnormalized_rules = True
            return False
        if kind == "ospf" and isinstance(value, OSPFProcess):
            if views and (len(views) != 1 or not views[0].lower().startswith("area ")):
                return False
            if line.text.lower().startswith("network "):
                value.area_order = [views[0].split()[1]] if views else []
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
        if lower in {
            "link-aggregation mode dynamic",
            "undo link-aggregation mode",
        }:
            if re.fullmatch(r"(?:bridge|route)-aggregation\d+", interface.name, re.I) is None:
                return False
            interface.aggregation_mode = (
                "static" if lower == "undo link-aggregation mode" else lower.rsplit(" ", 1)[1]
            )
            interface.aggregation_mode_origin = (
                "reference_default" if lower == "undo link-aggregation mode" else "explicit"
            )
            interface.command_sources["aggregation_mode"] = source
            return True
        vlan_command = lower.removeprefix("undo ")
        undo = lower.startswith("undo ")
        if vlan_command.startswith("port hybrid vlan "):
            words = vlan_command.split()
            if words[-1] not in {"tagged", "untagged"}:
                return False
            key = "hybrid_tagged_vlans" if words[-1] == "tagged" else "hybrid_untagged_vlans"
            try:
                values, all_vlans = vlan_list(words[3:-1], allow_all=True)
                charge_vlan_memberships(len(values))
                members = getattr(interface, key)
                if all_vlans:
                    members.clear()
                    if undo:
                        interface.vlan_all.discard(key)
                    else:
                        interface.vlan_all.add(key)
                elif undo:
                    members.difference_update(values)
                else:
                    members.update(values)
                interface.command_sources[key] = source
            except ValueError as exc:
                self._issue(config, line, "H3C-PARSE-VLAN", interface.name, str(exc))
            return True
        if re.fullmatch(r"port link-mode (bridge|route)", lower):
            interface.link_mode = tokens[2].lower()
            interface.command_sources["link_mode"] = source
            return True
        if re.fullmatch(r"ospf network-type (broadcast|nbma|p2p|p2mp)", lower):
            interface.ospf_network_type = tokens[2].lower()
            return True
        lists = {
            "port trunk permit vlan": "allowed_vlans",
            "port hybrid tagged vlan": "hybrid_tagged_vlans",
            "port hybrid untagged vlan": "hybrid_untagged_vlans",
        }
        for prefix, key in lists.items():
            checkpoint()
            if vlan_command == prefix or vlan_command.startswith(prefix + " "):
                try:
                    values, all_vlans = vlan_list(tokens[(5 if undo else 4) :], allow_all=True)
                except ValueError as exc:
                    self._issue(config, line, "H3C-PARSE-VLAN", interface.name, str(exc))
                    return True
                charge_vlan_memberships(len(values))
                members = getattr(interface, key)
                sources = interface.vlan_sources.setdefault(key, {})
                excluded = interface.vlan_exclusions.setdefault(key, set())
                if all_vlans:
                    members.clear()
                    sources.clear()
                    excluded.clear()
                    if undo:
                        interface.vlan_all.discard(key)
                    else:
                        interface.vlan_all.add(key)
                elif undo:
                    members.difference_update(values)
                    for vlan_id in values:
                        checkpoint()
                        sources.pop(vlan_id, None)
                    if key in interface.vlan_all:
                        excluded.update(values)
                else:
                    members.update(values)
                    excluded.difference_update(values)
                    for vlan_id in values:
                        checkpoint()
                        sources.setdefault(vlan_id, source)
                interface.command_sources[key] = source
                return True
        singles = {
            "port access vlan": "access_vlan",
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
                        self._issue(config, line, "H3C-PARSE-VLAN", interface.name, str(exc))
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
                if tokens[-1].lower() == "sub":
                    interface.secondary_ipv4_lines.add(source.line)
            interface.command_sources["ip_address"] = source
        elif lower.startswith("ipv6 address ") and len(tokens) >= 3:
            if tokens[2].lower() not in {"auto", "dhcp-alloc"}:
                ipv6_prefix = tokens[3] if len(tokens) >= 4 and tokens[3].isdigit() else None
                if len(tokens) >= 4 and tokens[3].lower() == "link-local":
                    return False  # Link-local addresses cannot supply a unicast BGP candidate.
                if "/" not in tokens[2] and ipv6_prefix is None:
                    return False
                extras = [token.lower() for token in tokens[3 if "/" in tokens[2] else 4 :]]
                if extras and extras != ["eui-64"]:
                    return False
                interface.ipv6_addresses.append((tokens[2], ipv6_prefix, source))
            interface.command_sources["ipv6_address"] = source
        elif re.match(r"ospf \d+ area ", lower) and "area" in tuple(token.lower() for token in tokens):
            area_index = tuple(token.lower() for token in tokens).index("area")
            process_id = tokens[1]
            if area_index + 1 < len(tokens):
                interface.ospf_bindings.append((process_id, tokens[area_index + 1], source))
                interface.command_sources["ospf_enable"] = source
        elif re.fullmatch(r"qos apply policy \S+ (?:inbound|outbound)", lower):
            interface.traffic_policies.append((tokens[3], tokens[4].lower(), source))
        elif lower == "shutdown":
            interface.shutdown = True
            interface.command_sources["shutdown"] = source
        elif lower == "undo shutdown":
            interface.shutdown = False
            interface.command_sources["shutdown"] = source
        elif re.fullmatch(r"port link-aggregation group \d{1,5}", lower):
            interface.eth_trunk = tokens[3]
            interface.command_sources["eth_trunk"] = source
        elif lower.startswith("ip binding vpn-instance ") and len(tokens) >= 4:
            interface.vpn_instance = tokens[3]
            interface.command_sources["vpn_instance"] = source
        elif lower.startswith("undo ip binding vpn-instance"):
            interface.vpn_instance = None
            interface.command_sources["vpn_instance"] = source
        elif lower == "undo port link-type":
            interface.link_type = None
        elif match := re.fullmatch(
            r"packet-filter(?: (ipv6))? ((?:name )?\S+) (inbound|outbound)", line.text, re.I
        ):
            identity = parse_acl_identity(tuple(match[2].split()), family="ipv6" if match[1] else "ipv4")
            if identity is None:
                return False
            config.acl_references.append((identity.key, interface.name, source))
        else:
            return False
        return True

    def _parse_bgp(
        self, config: DeviceConfig, line: SourceLine, bgp: BGPProcess, views: tuple[str, ...] = ()
    ) -> bool:
        tokens = line.tokens
        lower = line.text.lower()
        source = SourceRange(line.number)
        family: BGPAddressFamily | None = None
        if match := re.fullmatch(r"ip vpn-instance (\S+)", line.text, re.I):
            if views:
                return False
            bgp.vpn_scopes.setdefault(match[1], BGPProcess(bgp.local_as, source))
            return True
        if views and (match := re.fullmatch(r"ip vpn-instance (\S+)", views[0], re.I)):
            scope = bgp.vpn_scopes.get(match[1])
            return scope is not None and self._parse_bgp(config, line, scope, views[1:])
        family_names = {
            "address-family ipv4 unicast": "ipv4-family unicast",
            "address-family ipv4 multicast": "ipv4-family multicast",
            "address-family ipv6 unicast": "ipv6-family unicast",
            "address-family ipv6 multicast": "ipv6-family multicast",
            "address-family vpnv4": "ipv4-family vpnv4",
            "address-family vpnv6": "ipv6-family vpnv6",
            "address-family l2vpn evpn": "l2vpn-family evpn",
        }
        if lower.startswith("address-family ") and not views:
            name = family_names.get(lower, "")
            if not name:
                return False
        elif views and len(views) == 1:
            name = family_names.get(views[0].lower(), "")
            if not name:
                return False
        elif views:
            return False
        else:
            name = ""
        if name:
            family = next((item for item in bgp.address_families if item.name == name), None)
            if family is None:
                family = BGPAddressFamily(name, source)
                bgp.address_families.append(family)
            if not views:
                return True
        peers = family.peers if family else bgp.peers
        groups = family.groups if family else bgp.groups
        if lower.startswith("router-id ") and len(tokens) >= 2:
            if family is not None:
                return False
            bgp.router_id = tokens[1]
            return True
        if lower.startswith("group ") and len(tokens) >= 2:
            group = groups.setdefault(tokens[1], BGPGroup(tokens[1], source))
            group.declared = True
            group.source = source
            if len(tokens) >= 3:
                group.group_type = tokens[2].lower()
            group.semantics_known = len(tokens) == 3 and group.group_type in {"internal", "external"}
            return group.semantics_known
        if lower.startswith("peer ") and len(tokens) >= 3:
            operation = tokens[2].lower()
            if operation not in {"as-number", "group", "route-policy", "enable", "description"}:
                return False
            if operation == "description" and len(tokens) < 4:
                return False
            if operation in {"as-number", "group"} and len(tokens) != 4:
                if operation == "as-number" and not self._is_ip_address(tokens[1]):
                    group = groups.setdefault(tokens[1], BGPGroup(tokens[1], source))
                    group.semantics_known = False
                return False
            if operation == "route-policy" and (
                len(tokens) != 5 or tokens[4].lower() not in {"import", "export"}
            ):
                return False
            if operation == "enable" and len(tokens) != 3:
                return False
            target_name = tokens[1]
            is_address = self._is_ip_address(target_name)
            if is_address:
                target_name = str(ipaddress.ip_address(target_name))
                peer = peers.setdefault(target_name, BGPPeer(target_name, source))
                if tokens[2].lower() == "as-number" and len(tokens) >= 4:
                    peer.remote_as = tokens[3]
                elif tokens[2].lower() == "group" and len(tokens) >= 4:
                    peer.group = tokens[3]
                    peer.group_source = source
                elif tokens[2].lower() == "route-policy" and len(tokens) >= 5:
                    target = peer.import_policies if tokens[4].lower() == "import" else peer.export_policies
                    target.append((tokens[3], source))
            else:
                group = groups.setdefault(target_name, BGPGroup(target_name, source))
                if tokens[2].lower() == "as-number" and len(tokens) >= 4:
                    group.remote_as = tokens[3]
                elif tokens[2].lower() == "route-policy" and len(tokens) >= 5:
                    target = group.import_policies if tokens[4].lower() == "import" else group.export_policies
                    target.append((tokens[3], source))
            return True
        if lower == "network" or lower.startswith("network "):
            if family is None:
                family = next((f for f in bgp.address_families if f.name == "ipv4-family unicast"), None)
                if family is None:
                    family = BGPAddressFamily("ipv4-family unicast", bgp.source)
                    bgp.address_families.append(family)
            if not re.fullmatch(r"ipv[46]-family (?:unicast|multicast|vpn-instance \S+)", family.name, re.I):
                return False
            try:
                address, mask, policy = bgp_network(tokens[1:], 6 if family.name.startswith("ipv6") else 4)
                family.networks.append((address, mask, source))
                if policy is not None:
                    family.network_policies.append((policy, source))
            except ValueError as exc:
                self._issue(config, line, "H3C-PARSE-BGP", family.name, str(exc))
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
        if lower.startswith("if-match ip address prefix-list ") and len(tokens) >= 3:
            policy.prefix_references.extend((name, source) for name in tokens[4:])
            return True
        if (
            len(tokens) >= 5
            and tokens[:2] == ("if-match", "ipv6")
            and tokens[2] in {"address", "next-hop", "route-source"}
        ):
            if tokens[3] == "prefix-list" and len(tokens) == 5:
                policy.ipv6_prefix_references.append((tokens[4], source))
                return True
            if tokens[3] == "acl":
                identity = parse_acl_identity(tokens[4:], family="ipv6")
                if identity is not None:
                    policy.acl_references.append((identity.key, source))
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
    def _valid_prefix(tokens: tuple[str, ...], family: int) -> bool:
        try:
            offset = next(i for i, word in enumerate(tokens) if word.lower() in {"permit", "deny"}) + 1
            address, mask = tokens[offset : offset + 2]
            network = ipaddress.ip_network(f"{address}/{mask}", strict=False)
            if network.version != family:
                return False
            lower = network.prefixlen
            upper: int = network.max_prefixlen
            rest = tokens[offset + 2 :]
            if len(rest) % 2:
                return False
            seen: set[str] = set()
            for key, value in zip(rest[::2], rest[1::2], strict=True):
                if (
                    key in seen
                    or key not in {"greater-equal", "less-equal", "ge", "le"}
                    or not value.isascii()
                    or not value.isdigit()
                    or len(value) > 3
                ):
                    return False
                seen.add(key)
                if key in {"greater-equal", "ge"}:
                    lower = bounded_integer(value)
                else:
                    upper = bounded_integer(value)
            return network.prefixlen <= lower <= upper <= network.max_prefixlen
        except (ValueError, IndexError, StopIteration):
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
