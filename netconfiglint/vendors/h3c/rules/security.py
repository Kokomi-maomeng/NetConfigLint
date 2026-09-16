from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.facts import all_commands


def _matches(context: RuleContext, pattern: re.Pattern[str]) -> list[tuple[str, SourceRange, str]]:
    result: list[tuple[str, SourceRange, str]] = []
    for command, source, block in all_commands(context.config):
        checkpoint()
        if pattern.search(command):
            result.append((command, source, block.header))
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
