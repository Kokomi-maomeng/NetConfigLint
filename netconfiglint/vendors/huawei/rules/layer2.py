from __future__ import annotations

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.facts import all_commands


class MissingBpduProtectionRule:
    metadata = RuleMetadata("HUA-STP-001", "Edge port without BPDU protection", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        edge_sources = [
            source
            for text, source, _block in all_commands(context.config)
            if text.lower() in {"stp edged-port enable", "stp edged-port default"}
        ]
        protected = any(
            text.lower() == "stp bpdu-protection" for text, _source, _block in all_commands(context.config)
        )
        if not edge_sources or protected or context.mode.value == "snippet":
            return ()
        return (
            Diagnostic(
                Severity.WARNING,
                self.metadata.rule_id,
                edge_sources[0],
                "Spanning tree",
                "STP edge ports are configured without global BPDU protection.",
                "Forged or unexpected BPDUs can trigger topology recalculation on an edge port.",
                "Review edge-port scope, then enable stp bpdu-protection where supported and intended.",
                Confidence.DOCUMENTED,
            ),
        )
