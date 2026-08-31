from __future__ import annotations

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class MissingTrunkVlanRule:
    metadata = RuleMetadata("HUA-VLAN-001", "Undefined trunk VLAN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result: list[Diagnostic] = []
        for interface in context.config.interfaces.values():
            source = interface.command_sources.get("allowed_vlans", interface.source)
            for vlan_id in sorted(interface.allowed_vlans - context.config.vlans.keys()):
                result.append(
                    missing_reference_diagnostic(
                        context,
                        rule_id=self.metadata.rule_id,
                        source=source,
                        object_name=interface.name,
                        full_message=f"VLAN {vlan_id} is referenced but not defined.",
                        snippet_message=f"VLAN {vlan_id} was not found in the supplied snippet.",
                        explanation=f"The interface allows VLAN {vlan_id}, but that VLAN does not "
                        "exist in the supplied full configuration.",
                        suggested_fix=f"Create VLAN {vlan_id} or remove it from the allowed VLAN list.",
                    )
                )
        return tuple(result)


class MissingAccessVlanRule:
    metadata = RuleMetadata("HUA-VLAN-002", "Undefined access VLAN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result: list[Diagnostic] = []
        for interface in context.config.interfaces.values():
            vlan_id = interface.access_vlan
            if vlan_id is None or vlan_id in context.config.vlans:
                continue
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=interface.command_sources.get("access_vlan", interface.source),
                    object_name=interface.name,
                    full_message=f"Access VLAN {vlan_id} is not defined.",
                    snippet_message=f"Access VLAN {vlan_id} was not found in the supplied snippet.",
                    explanation=f"The interface uses VLAN {vlan_id} as its default VLAN, but the "
                    "VLAN is absent from the supplied full configuration.",
                    suggested_fix=f"Create VLAN {vlan_id} or select an existing access VLAN.",
                )
            )
        return tuple(result)


class UnusedVlanRule:
    metadata = RuleMetadata("HUA-VLAN-003", "Unused VLAN", Severity.INFO, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        used = {
            vlan_id for interface in context.config.interfaces.values() for vlan_id in interface.allowed_vlans
        }
        used.update(
            interface.access_vlan
            for interface in context.config.interfaces.values()
            if interface.access_vlan is not None
        )
        return tuple(
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                vlan.source,
                f"VLAN {vlan.vlan_id}",
                f"VLAN {vlan.vlan_id} is defined but no supported reference was found.",
                "No interface access/trunk reference to this VLAN was found in the normalized "
                "configuration. Other unsupported service references may still exist.",
                "Confirm that the VLAN is required before removing it.",
                Confidence.GENERIC,
            )
            for vlan in context.config.vlans.values()
            if vlan.vlan_id not in used
        )
