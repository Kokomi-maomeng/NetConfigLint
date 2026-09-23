from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class MissingVlanInterfaceVlanRule:
    metadata = RuleMetadata("H3C-IF-006", "VLAN interface without VLAN", Severity.ERROR, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            match = re.fullmatch(r"vlan-interface\s*(\d+)", interface.name, re.IGNORECASE)
            if match is None or int(match.group(1)) in {*context.config.vlans, 1}:
                continue
            vlan_id = int(match.group(1))
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=interface.source,
                    object_name=interface.name,
                    full_message=f"VLAN interface {vlan_id} exists but VLAN {vlan_id} is not defined.",
                    snippet_message=f"VLAN {vlan_id} was not found in the supplied snippet.",
                    explanation="The Layer 3 VLAN interface references a VLAN absent from the configuration.",
                    suggested_fix=f"Create VLAN {vlan_id} or remove/correct the VLAN interface.",
                )
            )
        return tuple(result)


class MissingBridgeAggregationRule:
    metadata = RuleMetadata("H3C-IF-003", "Undefined bridge aggregation group", Severity.ERROR, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        groups = {
            match.group(1)
            for name in context.config.interfaces
            if (match := re.fullmatch(r"bridge-aggregation\s*(\d+)", name, re.IGNORECASE))
        }
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            if interface.eth_trunk is None or interface.eth_trunk in groups:
                continue
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=interface.command_sources.get("eth_trunk", interface.source),
                    object_name=interface.name,
                    full_message=(f"Interface references undefined Bridge-Aggregation{interface.eth_trunk}."),
                    snippet_message=(
                        f"Bridge-Aggregation{interface.eth_trunk} was not found in the snippet."
                    ),
                    explanation="The member port has no matching aggregate interface definition.",
                    suggested_fix=(
                        f"Define Bridge-Aggregation{interface.eth_trunk} or correct the group number."
                    ),
                )
            )
        return tuple(result)


class UnsupportedCommandSummaryRule:
    metadata = RuleMetadata("H3C-CMD-002", "Unsupported H3C command summary", Severity.UNKNOWN, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        lines = sorted({item.line for item in context.config.unsupported_lines})
        if not lines:
            return ()
        preview = ", ".join(str(value) for value in lines[:12])
        if len(lines) > 12:
            preview += f", and {len(lines) - 12} more"
        return (
            Diagnostic(
                Severity.UNKNOWN,
                self.metadata.rule_id,
                context.config.unsupported_lines[0],
                "H3C command coverage",
                f"{len(lines)} command line(s) are preserved but not semantically verified.",
                f"Unsupported line numbers: {preview}.",
                "Review H3C-CMD-001 and H3C-PLATFORM-001 items against the exact device model and "
                "Comware release.",
                Confidence.LOW,
            ),
        )
