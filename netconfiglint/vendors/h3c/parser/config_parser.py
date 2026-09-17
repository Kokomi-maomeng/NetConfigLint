"""Source-preserving H3C Comware parser built on the cross-vendor normalized model.

Every non-empty configuration line is retained.  Commands with an implemented
normalizer are checked structurally; other commands receive an explicit UNKNOWN
diagnostic instead of being silently accepted or interpreted as Huawei VRP.
"""

from __future__ import annotations

import re
from dataclasses import replace

from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.model import DeviceConfig
from netconfiglint.vendors.h3c.parser.diagnostic_bundle import extract_h3c_diagnostic_bundle
from netconfiglint.vendors.h3c.parser.snapshot_parser import H3CSnapshotParser
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser

_SEMANTIC_PATTERNS = tuple(
    (family, re.compile(pattern, re.IGNORECASE))
    for family, pattern in (
        ("system", r"^(?:version\s+\S+.*|mdc\s+\S+\s+id\s+\d+|sysname\s+\S+|tcsm)$"),
        ("clock", r"^clock\s+(?:timezone|protocol)\b.*$"),
        ("management_server", r"^(?:telnet|ftp|ssh|sftp)\s+server\s+(?:enable|disable)$"),
        ("ip_services", r"^(?:ip\s+(?:unreachables|ttl-expires)\s+enable|dhcp\s+enable)$"),
        ("lldp", r"^lldp\s+global\s+enable$"),
        ("stp", r"^stp\s+(?:instance|port-log|bpdu-protection|global|edged-port)\b.*$"),
        ("m_lag", r"^(?:port\s+m-lag\s+peer-link|m-lag\s+(?:mad|role|system|keepalive)\b).*$"),
        ("mac_check", r"^undo\s+mac-address\s+static\s+source-check\s+enable$"),
        ("scheduler", r"^scheduler\s+logfile\s+size\s+\d+$"),
        (
            "terminal",
            r"^(?:line\s+(?:class\s+)?(?:console|con|vty)\b.*|authentication-mode\s+\S+|protocol\s+inbound\s+.*|user-role\s+.*)$",
        ),
        ("logging", r"^info-center\s+loghost\s+\S+$"),
        ("snmp", r"^snmp-agent(?:\s+.*)?$"),
        ("arp_protection", r"^arp\s+(?:ip-conflict|user-ip-conflict)\b.*$"),
        ("ntp", r"^ntp-service\s+.*$"),
        ("aaa_domain", r"^domain(?:\s+default\s+enable)?\s+\S+$"),
        ("rbac", r"^(?:role\s+name\s+\S+|user-group\s+\S+|authorization-attribute\s+user-role\s+.*)$"),
        (
            "local_user",
            r"^(?:local-user\s+\S+\s+class\s+(?:manage|network)|password\s+(?:simple|cipher|hash)\b.*|service-type\s+.*)$",
        ),
        ("security", r"^(?:security-enhanced\s+level\s+\d+|undo\s+ssl\s+(?:renegotiation|version)\b.*)$"),
        ("interface_mode", r"^port\s+link-mode\s+(?:bridge|route)$"),
        ("interface_arp", r"^arp\s+filter\s+source\s+\S+(?:\s+\S+)?$"),
        ("interface_ospf", r"^ospf\s+network-type\s+\S+$"),
        ("multicast", r"^undo\s+multicast\s+forwarding-mode$"),
    )
)
_PLATFORM_SPECIFIC = re.compile(r"^(?:system-working-mode\b|xbar\b|ftth\b|onu\b)", re.IGNORECASE)


def _normalize_body(body: str) -> str:
    """Translate only documented Comware spellings that share normalized semantics."""
    substitutions = (
        (r"^port trunk permit vlan\b", "port trunk allow-pass vlan"),
        (r"^undo port trunk permit vlan\b", "undo port trunk allow-pass vlan"),
        (r"^port access vlan\b", "port default vlan"),
        (r"^undo port access vlan\b", "undo port default vlan"),
        (r"^port hybrid vlan (.+) tagged$", r"port hybrid tagged vlan \1"),
        (r"^port hybrid vlan (.+) untagged$", r"port hybrid untagged vlan \1"),
        (r"^undo port hybrid vlan (.+) tagged$", r"undo port hybrid tagged vlan \1"),
        (r"^undo port hybrid vlan (.+) untagged$", r"undo port hybrid untagged vlan \1"),
        (r"^port link-aggregation group (\d+)$", r"eth-trunk \1"),
        (r"^undo port link-aggregation group(?: \d+)?$", "undo eth-trunk"),
        (r"^ospf (\d+) area (\S+)$", r"ospf enable \1 area \2"),
        (r"^undo ospf (\d+) area (\S+)$", r"undo ospf enable \1 area \2"),
        (r"^address-family ipv4 unicast$", "ipv4-family unicast"),
        (r"^address-family ipv6 unicast$", "ipv6-family unicast"),
        (r"^undo address-family ipv4 unicast$", "undo ipv4-family unicast"),
        (r"^undo address-family ipv6 unicast$", "undo ipv6-family unicast"),
        (r"^ip prefix-list\b", "ip ip-prefix"),
        (r"^undo ip prefix-list\b", "undo ip ip-prefix"),
        (r"^if-match ip address prefix-list\b", "if-match ip-prefix"),
        (r"^packet-filter (\S+) (inbound|outbound)$", r"traffic-filter \2 acl \1"),
        (r"^packet-filter ipv6 (\S+) (inbound|outbound)$", r"traffic-filter \2 ipv6 acl \1"),
    )
    for pattern, replacement in substitutions:
        if re.search(pattern, body, re.IGNORECASE):
            return re.sub(pattern, replacement, body, flags=re.IGNORECASE)
    if re.match(r"^(?:H3C|HPE|HP)\b.*(?:Comware|Software)", body, re.IGNORECASE):
        return "description " + body
    if re.match(r"^Comware Software,?\s+Version", body, re.IGNORECASE):
        return "description " + body
    if re.match(r"^(?:H3C )?Software Version\b", body, re.IGNORECASE):
        return "!Software Version " + body
    return body


def _normalize_source(source: str) -> str:
    result = []
    for line in source.splitlines():
        leading = line[: len(line) - len(line.lstrip())]
        result.append(leading + _normalize_body(line.strip()))
    return "\n".join(result) + ("\n" if source.endswith(("\n", "\r")) else "")


def _semantic_family(text: str) -> str | None:
    return next((family for family, pattern in _SEMANTIC_PATTERNS if pattern.fullmatch(text)), None)


class H3CConfigParser:
    """Parse the documented common Comware 7 configuration subset."""

    def __init__(self) -> None:
        self._normalized = HuaweiConfigParser()

    def parse(
        self,
        source: str,
        mode: AnalysisMode,
        detection: VendorDetection,
        *,
        initial_view: str | None = None,
    ) -> DeviceConfig:
        bundle = extract_h3c_diagnostic_bundle(source)
        parser_source = bundle.masked_configuration if bundle is not None else source
        normalized = _normalize_source(parser_source)
        delegate_mode = AnalysisMode.FULL if bundle is not None else mode
        config = self._normalized.parse(
            normalized,
            delegate_mode,
            detection,
            initial_view=_normalize_body(initial_view) if initial_view is not None else None,
        )
        originals = tuple(source.splitlines())
        config.vendor = "H3C"
        config.source_lines = originals
        config.metadata["profile_id"] = detection.profile_id
        config.metadata["command_accounting"] = "source-preserving"
        if bundle is not None:
            config.analysis_lines = set(bundle.analysis_lines)
            config.metadata["diagnostic_bundle_sections"] = str(bundle.section_count)
            config.metadata["saved_configuration_present"] = str(bundle.saved_present).lower()
            config.metadata["saved_configuration_matches"] = (
                "unknown"
                if bundle.saved_matches_current is None
                else str(bundle.saved_matches_current).lower()
            )
            config.snapshot = H3CSnapshotParser().parse(source)

        # The normalized model is already populated. Restore the exact Comware text for
        # exports, textual rules, auditability, and future vendor-specific extensions.
        for block in config.blocks:
            if block.source.line <= len(originals):
                block.header = originals[block.source.line - 1].strip()
            block.commands = [
                replace(command, text=originals[command.source.line - 1].strip())
                if command.source.line <= len(originals)
                else command
                for command in block.commands
            ]

        semantic_lines: set[int] = set()
        command_families: dict[str, list[int]] = {}
        for block in config.blocks:
            commands = [(block.header, block.source), *((item.text, item.source) for item in block.commands)]
            interface = None
            if block.header.lower().startswith("interface "):
                interface = config.interfaces.get(block.header[10:].strip())
            for _text, item_source in commands:
                original_text = originals[item_source.line - 1].strip()
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
        config.unsupported_lines = sorted(
            {*(item for item in config.unsupported_lines), *config.unparsed_lines},
            key=lambda item: item.line,
        )
        config.parse_issues = [
            replace(
                issue,
                rule_id=issue.rule_id.replace("HUA-", "H3C-"),
                explanation=issue.explanation.replace("Huawei", "H3C Comware"),
            )
            for issue in config.parse_issues
        ]
        existing_issue_lines = {item.source.line for item in config.parse_issues}
        for item in config.unsupported_lines:
            if item.line in existing_issue_lines or item.line > len(originals):
                continue
            original_text = originals[item.line - 1].strip()
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
