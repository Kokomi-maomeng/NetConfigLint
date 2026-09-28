from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.h3c.rules.facts import all_commands


class SensitiveConfigurationRule:
    metadata = RuleMetadata("H3C-SEC-001", "Sensitive configuration detected", Severity.INFO, "H3C Comware")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.sensitive_lines:
            return ()
        first = context.config.sensitive_lines[0]
        return (
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                first,
                "Configuration",
                "Sensitive configuration data detected. NetConfigLint processes configuration locally.",
                f"Potentially sensitive keywords occur on {len(context.config.sensitive_lines)} line(s). "
                "Their values are not included in this diagnostic or default logs.",
                "Protect exported reports and configuration files according to your security policy.",
                Confidence.GENERIC,
            ),
        )


def _diagnostic(
    context: RuleContext,
    *,
    rule_id: str,
    pattern: re.Pattern[str],
    severity: Severity,
    message: str,
    explanation: str,
    suggested_fix: str,
) -> tuple[Diagnostic, ...]:
    matches: dict[tuple[str, bool], list[SourceRange]] = {}
    for command, source, block in all_commands(context.config):
        checkpoint()
        if not pattern.search(command):
            continue
        header = block.header.lower()
        unknown = not block.context_known or command == block.header
        if rule_id in {"H3C-SEC-009", "H3C-SEC-010"}:
            if not unknown and not header.startswith("user-interface vty"):
                continue
        elif rule_id in {"H3C-SEC-004", "H3C-SEC-008"}:
            if not unknown and not (header == "aaa" or header.startswith("user-interface ")):
                continue
        elif command != block.header:
            continue  # Server, SNMP, SSH and NTP commands belong to system view.
        else:
            unknown = False
        object_name = (
            "Unknown context" if unknown else ("System view" if command == block.header else block.header)
        )
        matches.setdefault((object_name, unknown), []).append(source)
    return tuple(
        Diagnostic(
            Severity.UNKNOWN if unknown and rule_id in {"H3C-SEC-009", "H3C-SEC-010"} else severity,
            rule_id,
            sources[0],
            object_name,
            "Cannot verify the command's management view."
            if unknown and rule_id in {"H3C-SEC-009", "H3C-SEC-010"}
            else message,
            f"{explanation} Matching configuration lines: {len(sources)}."
            + (" Starting view was not supplied." if unknown else ""),
            suggested_fix,
            Confidence.LOW if unknown else Confidence.DOCUMENTED,
        )
        for (object_name, unknown), sources in matches.items()
    )


class TelnetServerRule:
    metadata = RuleMetadata("H3C-SEC-002", "Telnet server enabled", Severity.WARNING, "H3C Comware")
    _PATTERN = re.compile(r"^telnet(?:\s+(?:ipv4|ipv6))?\s+server\s+enable$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="The Telnet server is enabled.",
            explanation="Telnet does not protect management credentials or session contents in transit.",
            suggested_fix="Use SSH and disable Telnet after confirming the management path.",
        )


class FtpServerRule:
    metadata = RuleMetadata("H3C-SEC-003", "FTP server enabled", Severity.WARNING, "H3C Comware")
    _PATTERN = re.compile(r"^ftp\s+server\s+enable$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="The FTP server is enabled.",
            explanation="H3C Comware documents FTP as a protocol with security risks.",
            suggested_fix="Use SFTP/SCP and disable FTP when it is not explicitly required.",
        )


def _first_match(context: RuleContext, pattern: re.Pattern[str]) -> tuple[SourceRange, int] | None:
    matches = [
        source
        for text, source, block in all_commands(context.config)
        if block.header == text and pattern.search(text)
    ]
    return (matches[0], len(matches)) if matches else None


class UnauthenticatedNtpRule:
    metadata = RuleMetadata("H3C-SEC-006", "NTP without authentication", Severity.WARNING, "H3C Comware")
    _SERVER = re.compile(r"^ntp-service\s+(?:server|unicast-server|unicast-peer)\b", re.IGNORECASE)
    _AUTH = re.compile(r"^ntp-service\s+authentication\s+enable$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        server = _first_match(context, self._SERVER)
        if server is None or _first_match(context, self._AUTH) is not None:
            return ()
        source, count = server
        return (
            Diagnostic(
                Severity.WARNING,
                self.metadata.rule_id,
                source,
                "NTP",
                "NTP peers or servers are configured without NTP authentication.",
                "H3C Comware supports NTP authentication for higher-security networks. "
                f"Peer/server lines: {count}.",
                "Configure supported authentication keys, trust them, and enable NTP "
                "authentication on all peers.",
                Confidence.DOCUMENTED,
            ),
        )
