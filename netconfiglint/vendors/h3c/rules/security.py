from __future__ import annotations

import ipaddress
import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.model import ConfigBlock
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


def _vty_settings(context: RuleContext, prefix: str) -> list[tuple[str, SourceRange, str, bool]]:
    """Reduce class inheritance and each explicit line range without assuming line capacity."""
    classes = [b for b in context.config.blocks if b.header.lower() == "line class vty"]
    ranges = [b for b in context.config.blocks if re.fullmatch(r"line vty \d+(?: \d+)?", b.header, re.I)]
    inherited = [
        (c.text.lower(), c.source) for b in classes for c in b.commands if c.text.lower().startswith(prefix)
    ]
    result = []
    for block in ranges:
        explicit = [(c.text.lower(), c.source) for c in block.commands if c.text.lower().startswith(prefix)]
        values = explicit or inherited
        value, source = values[-1] if values else ("", block.source)
        result.append((value, source, block.header, False))
    if classes:
        value, source = inherited[-1] if inherited else ("", classes[-1].source)
        # Explicit ranges cannot prove that the platform has no additional VTY lines.
        result.append((value, source, "line class vty (remaining capacity unknown)", bool(ranges)))
    return result


class H3CVtyInboundProtocolRule:
    metadata = RuleMetadata("H3C-SEC-009", "VTY not restricted to SSH", Severity.WARNING, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for value, source, header, uncertain in _vty_settings(context, "protocol inbound "):
            if value == "protocol inbound ssh":
                continue
            documented = value in {"protocol inbound telnet", "protocol inbound all"} and not uncertain
            result.append(
                Diagnostic(
                    Severity.WARNING if documented else Severity.UNKNOWN,
                    self.metadata.rule_id,
                    source,
                    header,
                    "The effective VTY protocol is not SSH-only."
                    if documented
                    else "SSH-only access cannot be proven for this VTY scope.",
                    "Line settings override class settings. Additional line capac"
                    "ity and release defaults cannot be assumed.",
                    "Check all available VTY ranges and effective inheritance, th"
                    "en restrict intended remote access to SSH.",
                    Confidence.DOCUMENTED if documented else Confidence.LOW,
                )
            )
        return tuple(result)


class H3CVtyAuthenticationRule:
    metadata = RuleMetadata("H3C-SEC-010", "VTY authentication policy", Severity.WARNING, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for value, source, header, uncertain in _vty_settings(context, "authentication-mode "):
            if value == "authentication-mode scheme":
                continue
            severity = Severity.ERROR if value == "authentication-mode none" else Severity.WARNING
            if not value or uncertain:
                severity = Severity.UNKNOWN
            result.append(
                Diagnostic(
                    severity,
                    self.metadata.rule_id,
                    source,
                    header,
                    "VTY authentication is disabled."
                    if value.endswith(" none") and not uncertain
                    else "VTY authentication requires verification.",
                    "Authentication inherits from the line class unless overridde"
                    "n for this range; capacity and omitted defaults are unknown.",
                    "Confirm working console/SSH rollback access and apply the ap"
                    "proved scheme to every intended VTY range.",
                    Confidence.LOW if severity == Severity.UNKNOWN else Confidence.DOCUMENTED,
                )
            )
        return tuple(result)


def _ospf_block(context: RuleContext, process_id: str) -> ConfigBlock | None:
    return next(
        (
            b
            for b in context.config.blocks
            if (process_id == "1" and b.header.lower() == "ospf")
            or re.match(rf"^ospf\s+{re.escape(process_id)}(?:\s|$)", b.header, re.I)
        ),
        None,
    )


class H3COspfExposureRule:
    metadata = RuleMetadata("H3C-OSPF-004", "Broad OSPF access network", Severity.WARNING, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:

        result = []
        for process in context.config.ospf_processes.values():
            block = _ospf_block(context, process.process_id)
            silent = (
                {
                    c.text.split()[1].lower()
                    for c in block.commands
                    if not c.views and re.fullmatch(r"silent-interface \S+", c.text, re.I)
                }
                if block
                else set()
            )
            if "all" in silent:
                continue
            for network in process.networks:
                checkpoint()
                try:
                    scope = ipaddress.IPv4Network(
                        (
                            network.address,
                            str(
                                ipaddress.IPv4Address(
                                    int(ipaddress.IPv4Address(network.wildcard)) ^ 0xFFFFFFFF
                                )
                            ),
                        ),
                        strict=False,
                    )
                except ValueError:
                    continue
                if scope.num_addresses < 8:
                    continue
                participants = [
                    interface
                    for interface in context.config.interfaces.values()
                    if any(
                        _address_in_scope(address, scope)
                        for address, _mask, _source in interface.ip_addresses
                    )
                ]
                if participants and all(interface.name.lower() in silent for interface in participants):
                    continue
                result.append(
                    Diagnostic(
                        Severity.WARNING if not silent else Severity.UNKNOWN,
                        self.metadata.rule_id,
                        network.source,
                        f"OSPF {process.process_id} area {network.area}",
                        "A multi-host OSPF network has no proven complete silent-interface policy.",
                        "A silent interface in another process or on another subnet d"
                        "oes not protect this network.",
                        "Check the participating interfaces and endpoint roles; confi"
                        "gure silence only on intended access interfaces.",
                        Confidence.GENERIC if not silent else Confidence.LOW,
                    )
                )
        return tuple(result)


def _address_in_scope(address: str, scope: ipaddress.IPv4Network) -> bool:

    try:
        return ipaddress.IPv4Address(address.split("/")[0]) in scope
    except ValueError:
        return False


class H3COspfAuthenticationRule:
    metadata = RuleMetadata("H3C-OSPF-005", "OSPF authentication not observed", Severity.INFO, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        result = []
        for process in context.config.ospf_processes.values():
            block = _ospf_block(context, process.process_id)
            for area in sorted(process.areas or {"Unknown"}):
                commands = [c for c in block.commands if c.views == (f"area {area}",)] if block else []
                authenticated = any(
                    re.fullmatch(
                        r"authentication-mode (?:simple|md5|hmac-md5|hmac-sha-256)(?: .+)?", c.text, re.I
                    )
                    for c in commands
                )
                if authenticated:
                    continue
                result.append(
                    Diagnostic(
                        Severity.INFO,
                        self.metadata.rule_id,
                        process.source,
                        f"OSPF {process.process_id} area {area}",
                        "Area authentication was not observed in this scope.",
                        "Authentication on another process/area does not prove protec"
                        "tion here; interface overrides and design requirements still"
                        " require verification.",
                        "Check every intended adjacency and matching peer authenticat"
                        "ion against the routing security standard.",
                        Confidence.LOW,
                    )
                )
        return tuple(result)
