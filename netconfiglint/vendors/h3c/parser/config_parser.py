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
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser

_ACCOUNTED_TEXT = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^(?:H3C|HPE|HP)\b.*(?:Comware|Software)",
        r"^Comware Software,?\s+Version\b",
        r"^!Software Version\b",
        r"^local-user\s+\S+\s+class\s+(?:manage|network)\b",
        r"^password\s+(?:simple|cipher|hash)\b",
        r"^service-type\s+",
        r"^(?:telnet|ftp)\s+server\s+(?:enable|disable)$",
        r"^snmp-agent\s+community\b",
        r"^ntp-service\s+",
        r"^protocol\s+inbound\s+",
        r"^authentication-mode\s+",
        r"^stp\s+(?:edged-port|bpdu-protection)\b",
    )
)


def _normalize_body(body: str) -> str:
    """Translate only documented Comware spellings that share normalized semantics."""
    substitutions = (
        (r"^port trunk permit vlan\b", "port trunk allow-pass vlan"),
        (r"^undo port trunk permit vlan\b", "undo port trunk allow-pass vlan"),
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


def _accounted(text: str) -> bool:
    return any(pattern.search(text) for pattern in _ACCOUNTED_TEXT)


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
        normalized = _normalize_source(source)
        config = self._normalized.parse(
            normalized,
            mode,
            detection,
            initial_view=_normalize_body(initial_view) if initial_view is not None else None,
        )
        originals = tuple(source.splitlines())
        config.vendor = "H3C"
        config.source_lines = originals
        config.metadata["profile_id"] = detection.profile_id
        config.metadata["command_accounting"] = "source-preserving"

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

        accounted_lines = {number for number, line in enumerate(originals, 1) if _accounted(line.strip())}
        config.unparsed_lines = [item for item in config.unparsed_lines if item.line not in accounted_lines]
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
                    "H3C-CMD-001",
                    SourceRange(item.line),
                    original_text.split(maxsplit=1)[0] if original_text else "Configuration",
                    "This H3C command is preserved, but its effective semantics are not verified.",
                    "No Comware semantic checker is registered for this exact command or view.",
                    "Confirm the command against the matching H3C model/release reference before "
                    "changing it.",
                    Confidence.LOW,
                )
            )
        return config
