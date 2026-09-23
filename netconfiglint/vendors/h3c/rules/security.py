from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata


def _commands(context: RuleContext) -> list[tuple[str, SourceRange, str]]:
    result: list[tuple[str, SourceRange, str]] = []
    for block in context.config.blocks:
        result.append((block.header, block.source, block.header))
        result.extend((command.text, command.source, block.header) for command in block.commands)
    return result


def _matches(context: RuleContext, pattern: re.Pattern[str]) -> list[tuple[str, SourceRange, str]]:
    result: list[tuple[str, SourceRange, str]] = []
    for command, source, header in _commands(context):
        checkpoint()
        if pattern.search(command):
            result.append((command, source, header))
    return result


class PlaintextPasswordRule:
    metadata = RuleMetadata("H3C-SEC-004", "Plaintext password command", Severity.ERROR, "H3C")
    _PATTERN = re.compile(r"^(?:local-user\s+\S+\s+password|password)\s+simple\b", re.I)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                Severity.ERROR,
                self.metadata.rule_id,
                source,
                header,
                "A plaintext password command is present.",
                "The credential is exposed directly in configuration text and backups.",
                "Replace it with a supported irreversible hash and rotate the exposed credential.",
                Confidence.DOCUMENTED,
            )
            for _command, source, header in _matches(context, self._PATTERN)
        )


class LocalUserTelnetRule:
    metadata = RuleMetadata("H3C-SEC-008", "Local user permits Telnet", Severity.WARNING, "H3C")
    _PATTERN = re.compile(r"^(?:local-user\s+\S+\s+)?service-type\s+.*\btelnet\b", re.I)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                Severity.WARNING,
                self.metadata.rule_id,
                source,
                header,
                "A local user permits Telnet access.",
                "The account service scope retains a cleartext remote-management protocol.",
                "Remove Telnet from the service type after confirming SSH access and rollback.",
                Confidence.DOCUMENTED,
            )
            for _command, source, header in _matches(context, self._PATTERN)
        )


class H3CSnmpCommunityRule:
    metadata = RuleMetadata("H3C-SEC-005", "SNMP community configured", Severity.WARNING, "H3C")
    _PATTERN = re.compile(r"^snmp-agent\s+community\s+(read|write)\b", re.I)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for command, source, _header in _matches(context, self._PATTERN):
            access = self._PATTERN.search(command)
            writable = access is not None and access.group(1).lower() == "write"
            result.append(
                Diagnostic(
                    Severity.ERROR if writable else Severity.WARNING,
                    self.metadata.rule_id,
                    source,
                    "SNMP",
                    "A writable SNMPv1/v2c community is configured."
                    if writable
                    else "An SNMPv1/v2c community is configured.",
                    "Community-based SNMP lacks SNMPv3 authentication and privacy; write access "
                    "also permits configuration-changing operations.",
                    "Migrate to SNMPv3 USM/VACM with a management ACL, remove write communities, "
                    "then rotate the exposed community values.",
                    Confidence.DOCUMENTED,
                )
            )
        return tuple(result)


class LegacyTlsVersionRule:
    metadata = RuleMetadata("H3C-SEC-011", "Legacy TLS version enabled", Severity.WARNING, "H3C")
    _PATTERN = re.compile(r"^undo\s+ssl\s+version\s+(ssl3\.0|tls1\.[01])\s+disable$", re.I)

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                Severity.WARNING,
                self.metadata.rule_id,
                source,
                "SSL/TLS",
                f"Legacy {match.group(1).upper()} is explicitly enabled.",
                "This undo form reverses the protocol-version disable command; the old protocol "
                "therefore remains available.",
                "After checking client compatibility and rollback, disable SSL 3.0, TLS 1.0, and "
                "TLS 1.1 and retain a supported modern TLS version.",
                Confidence.DOCUMENTED,
            )
            for command, source, _header in _matches(context, self._PATTERN)
            if (match := self._PATTERN.search(command)) is not None
        )


class H3CVtyInboundProtocolRule:
    metadata = RuleMetadata("H3C-SEC-009", "VTY not restricted to SSH", Severity.WARNING, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        telnet_enabled = any(
            re.fullmatch(r"telnet\s+server\s+enable", command, re.I)
            for command, _source, _header in _commands(context)
        )
        result = []
        candidates = [
            block for block in context.config.blocks if re.match(r"line\s+vty\b", block.header, re.I)
        ]
        if not candidates:
            candidates = [
                block
                for block in context.config.blocks
                if re.match(r"line\s+class\s+vty\b", block.header, re.I)
            ]
        for block in candidates:
            protocols = [
                command.text.lower()
                for command in block.commands
                if command.text.lower().startswith("protocol inbound ")
            ]
            if protocols == ["protocol inbound ssh"]:
                continue
            result.append(
                Diagnostic(
                    Severity.WARNING if telnet_enabled or protocols else Severity.UNKNOWN,
                    self.metadata.rule_id,
                    block.source,
                    block.header,
                    "The VTY is not explicitly restricted to SSH.",
                    "Telnet is enabled globally or the effective inbound protocol cannot be proven "
                    "SSH-only from this configuration.",
                    "Verify console/SSH rollback access, then configure protocol inbound ssh and "
                    "disable the Telnet server.",
                    Confidence.DOCUMENTED if telnet_enabled else Confidence.LOW,
                )
            )
        return tuple(result)


class H3COspfExposureRule:
    metadata = RuleMetadata("H3C-OSPF-004", "Broad OSPF access network", Severity.WARNING, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        silent = any(
            re.match(r"(?:silent-interface|passive-interface)\b", command, re.I)
            for command, _source, _header in _commands(context)
        )
        if silent:
            return ()
        result = []
        for process in context.config.ospf_processes.values():
            for network in process.networks:
                try:
                    host_bits = sum(bin(int(part)).count("1") for part in network.wildcard.split("."))
                except ValueError:
                    continue
                if host_bits < 3:
                    continue
                result.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.metadata.rule_id,
                        network.source,
                        f"OSPF {process.process_id}",
                        "A multi-host subnet participates in OSPF without an observed "
                        "silent/passive interface policy.",
                        "Endpoint-facing VLANs can form unintended adjacencies when OSPF hellos are emitted.",
                        "Confirm the interface role; make endpoint VLANs silent/passive while "
                        "still advertising "
                        "their networks, and leave only intended routed adjacencies active.",
                        Confidence.GENERIC,
                    )
                )
        return tuple(result)


class H3COspfAuthenticationRule:
    metadata = RuleMetadata("H3C-OSPF-005", "OSPF authentication not observed", Severity.INFO, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet" or not context.config.ospf_processes:
            return ()
        authenticated = any(
            "authentication" in command.lower()
            for command, _source, header in _commands(context)
            if header.lower().startswith("ospf ")
        )
        if authenticated:
            return ()
        process = next(iter(context.config.ospf_processes.values()))
        return (
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                process.source,
                f"OSPF {process.process_id}",
                "No OSPF authentication command was observed.",
                "Authentication requirements are design-specific; absence cannot be declared a "
                "defect without "
                "the routing security standard.",
                "Confirm the design requirement and deploy matching authentication on both ends if required.",
                Confidence.LOW,
            ),
        )
