from __future__ import annotations

import re

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.facts import all_commands


class SensitiveConfigurationRule:
    metadata = RuleMetadata("HUA-SEC-001", "Sensitive configuration detected", Severity.INFO, "Huawei")

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


def _first_match(context: RuleContext, pattern: re.Pattern[str]) -> tuple[SourceRange, int] | None:
    matches = [source for text, source, _block in all_commands(context.config) if pattern.search(text)]
    return (matches[0], len(matches)) if matches else None


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
    match = _first_match(context, pattern)
    if match is None:
        return ()
    source, count = match
    return (
        Diagnostic(
            severity,
            rule_id,
            source,
            "Management plane",
            message,
            f"{explanation} Matching configuration lines: {count}.",
            suggested_fix,
            Confidence.DOCUMENTED,
        ),
    )


class TelnetServerRule:
    metadata = RuleMetadata("HUA-SEC-002", "Telnet server enabled", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^telnet(?:\s+(?:ipv4|ipv6))?\s+server\s+enable$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="The Telnet server is enabled.",
            explanation="Telnet does not protect management credentials or session contents in transit.",
            suggested_fix="Use STelnet/SSH and disable Telnet after confirming the management path.",
        )


class FtpServerRule:
    metadata = RuleMetadata("HUA-SEC-003", "FTP server enabled", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^ftp\s+server\s+enable$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="The FTP server is enabled.",
            explanation="Huawei documents FTP as a protocol with security risks.",
            suggested_fix="Use SFTP/SCP and disable FTP when it is not explicitly required.",
        )


class PlaintextPasswordRule:
    metadata = RuleMetadata("HUA-SEC-004", "Plaintext password command", Severity.ERROR, "Huawei")
    _PATTERN = re.compile(r"\b(?:password|authentication password)\s+simple\b", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.ERROR,
            message="A plaintext password command is present.",
            explanation="The credential is exposed directly in configuration text and backups.",
            suggested_fix=(
                "Replace it using a supported irreversible password method and rotate the credential."
            ),
        )


class SnmpCommunityRule:
    metadata = RuleMetadata("HUA-SEC-005", "SNMP community configured", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^snmp-agent\s+community\b", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="An SNMP community is configured.",
            explanation="Community-based SNMPv1/v2c lacks SNMPv3 USM authentication and encryption.",
            suggested_fix="Migrate the NMS and device to SNMPv3 USM/VACM, then remove legacy communities.",
        )


class UnauthenticatedNtpRule:
    metadata = RuleMetadata("HUA-SEC-006", "NTP without authentication", Severity.WARNING, "Huawei")
    _SERVER = re.compile(r"^(?:ntp|ntp-service)\s+(?:server|unicast-server|unicast-peer)\b", re.IGNORECASE)
    _AUTH = re.compile(r"^(?:ntp|ntp-service)\s+authentication\s+enable$", re.IGNORECASE)

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
                "Huawei supports NTP authentication for higher-security networks. "
                f"Peer/server lines: {count}.",
                "Configure supported authentication keys, trust them, and enable NTP "
                "authentication on all peers.",
                Confidence.DOCUMENTED,
            ),
        )


class SshAllInterfacesRule:
    metadata = RuleMetadata("HUA-SEC-007", "SSH listens on all interfaces", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^ssh\s+server-source\s+all-interface$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="The SSH server source is set to all interfaces.",
            explanation="This broadens the management-plane exposure beyond a dedicated management path.",
            suggested_fix=(
                "Bind SSH to the intended management interface after verifying reachability and rollback."
            ),
        )


class LocalUserTelnetRule:
    metadata = RuleMetadata("HUA-SEC-008", "Local user permits Telnet", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^local-user\s+\S+\s+service-type\s+.*\btelnet\b", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="One or more local users permit Telnet access.",
            explanation="The account service scope retains an insecure remote-management protocol.",
            suggested_fix="Remove Telnet from user service types after confirming SSH access and rollback.",
        )


class VtyInboundProtocolRule:
    metadata = RuleMetadata("HUA-SEC-009", "VTY permits non-SSH access", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^protocol\s+inbound\b.*\b(?:all|telnet)\b", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="A VTY line permits Telnet or all inbound protocols.",
            explanation="Huawei recommends SSH-only VTY access for protected remote management.",
            suggested_fix="Set protocol inbound ssh after validating SSH authentication and access control.",
        )


class VtyPasswordAuthenticationRule:
    metadata = RuleMetadata("HUA-SEC-010", "VTY uses password authentication", Severity.WARNING, "Huawei")
    _PATTERN = re.compile(r"^authentication-mode\s+password$", re.IGNORECASE)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _diagnostic(
            context,
            rule_id=self.metadata.rule_id,
            pattern=self._PATTERN,
            severity=Severity.WARNING,
            message="A VTY line uses password authentication instead of AAA.",
            explanation="Huawei warns that password authentication mode is not secure.",
            suggested_fix="Use AAA authentication with least-privilege users and SSH-only VTY access.",
        )
