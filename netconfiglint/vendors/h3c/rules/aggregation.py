"""Local Comware aggregation facts do not establish peer negotiation."""

from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


class AggregationModeEvidenceRule:
    metadata = RuleMetadata("H3C-IF-007", "LACP peer evidence required", Severity.UNKNOWN, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            match = re.fullmatch(r"(?:bridge|route)-aggregation(\d+)", interface.name, re.I)
            if match is None or interface.aggregation_mode != "dynamic":
                continue
            members = sum(member.eth_trunk == match.group(1) for member in context.config.interfaces.values())
            result.append(
                Diagnostic(
                    Severity.UNKNOWN,
                    self.metadata.rule_id,
                    interface.command_sources.get("aggregation_mode", interface.source),
                    interface.name,
                    "Local dynamic aggregation is configured; peer LACP negotiation is not verified.",
                    f"The normalized local configuration has {members} member reference(s). "
                    "Member references and local mode do not establish peer mode, "
                    "cabling, or selected state.",
                    "Compare both ends and collect display link-aggregation verbose with current LACP state.",
                    Confidence.LOW,
                )
            )
        return tuple(result)
