from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic

_VLAN_REFERENCE = re.compile(r"\b(?:vlan|vid)\s+((?:\d+(?:\s+to\s+\d+)?\s*)+)", re.IGNORECASE)


def _defined_vlans(context: RuleContext) -> set[int]:
    # VLAN 1 exists by default on Huawei switches even when omitted from display output.
    return {*context.config.vlans, 1}


def _expand_reference(value: str) -> set[int]:
    tokens = value.lower().split()
    result: set[int] = set()
    index = 0
    while index < len(tokens):
        checkpoint()
        if not tokens[index].isdigit():
            index += 1
            continue
        start = int(tokens[index])
        if index + 2 < len(tokens) and tokens[index + 1] == "to" and tokens[index + 2].isdigit():
            end = int(tokens[index + 2])
            if 1 <= start <= end <= 4094:
                result.update(range(start, end + 1))
            index += 3
            continue
        if 1 <= start <= 4094:
            result.add(start)
        index += 1
    return result


def _service_vlan_references(context: RuleContext) -> set[int]:
    references: set[int] = set()
    for block in context.config.blocks:
        checkpoint()
        for command in block.commands:
            checkpoint()
            lower = command.text.lower()
            if not lower.startswith(
                (
                    "encapsulation ",
                    "if-match vlan ",
                    "l2 binding vlan ",
                    "qinq ",
                    "vlan mapping ",
                )
            ):
                continue
            references.update(
                vlan_id
                for match in _VLAN_REFERENCE.finditer(command.text)
                for vlan_id in _expand_reference(match.group(1))
            )
    return references


def _missing_ranges(context: RuleContext, key: str, rule_id: str) -> tuple[Diagnostic, ...]:
    result = []
    defined = _defined_vlans(context)
    for interface in context.config.interfaces.values():
        # 'all' admits existing VLANs; it is not a request to create every possible VLAN.
        checkpoint()
        if key in interface.vlan_all:
            continue
        sources = interface.vlan_sources.get(key, {})
        by_source: dict[SourceRange, list[int]] = {}
        for value in sorted(getattr(interface, key) - defined):
            checkpoint()
            by_source.setdefault(sources.get(value, interface.source), []).append(value)
        for source, values in by_source.items():
            checkpoint()
            ranges: list[str] = []
            start = end = values[0]
            for value in values[1:]:
                checkpoint()
                if value == end + 1:
                    end = value
                else:
                    ranges.append(str(start) if start == end else f"{start}-{end}")
                    start = end = value
            ranges.append(str(start) if start == end else f"{start}-{end}")
            label = ", ".join(ranges)
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=rule_id,
                    source=source,
                    object_name=interface.name,
                    full_message=f"VLAN {label} is referenced but not defined.",
                    snippet_message=f"VLAN {label} was not found in the supplied snippet.",
                    explanation=(
                        f"This command references {len(values)} VLAN(s) "
                        "absent from the supplied configuration."
                    ),
                    suggested_fix=f"Create VLAN {label} or correct this VLAN list.",
                )
            )
    return tuple(result)


class MissingTrunkVlanRule:
    metadata = RuleMetadata("HUA-VLAN-001", "Undefined trunk VLAN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return _missing_ranges(context, "allowed_vlans", self.metadata.rule_id)


class MissingAccessVlanRule:
    metadata = RuleMetadata("HUA-VLAN-002", "Undefined access VLAN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result: list[Diagnostic] = []
        for interface in context.config.interfaces.values():
            checkpoint()
            vlan_id = interface.access_vlan
            if vlan_id is None or vlan_id in _defined_vlans(context):
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
        used.update(
            vlan_id
            for interface in context.config.interfaces.values()
            for vlan_id in (
                interface.hybrid_tagged_vlans
                | interface.hybrid_untagged_vlans
                | ({interface.pvid_vlan} if interface.pvid_vlan is not None else set())
            )
        )
        used.update(_service_vlan_references(context))
        for interface in context.config.interfaces.values():
            checkpoint()
            for key in interface.vlan_all:
                checkpoint()
                used.update(set(context.config.vlans) - interface.vlan_exclusions.get(key, set()))
            match = re.fullmatch(r"vlanif\s*(\d+)", interface.name, re.IGNORECASE)
            if match is not None:
                used.add(int(match.group(1)))
        unused = sorted(
            (vlan for vlan in context.config.vlans.values() if vlan.vlan_id not in used),
            key=lambda vlan: vlan.vlan_id,
        )
        if not unused:
            return ()
        preview = ", ".join(str(vlan.vlan_id) for vlan in unused[:20])
        if len(unused) > 20:
            preview += f", and {len(unused) - 20} more"
        return (
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                unused[0].source,
                "VLAN inventory",
                f"{len(unused)} defined VLAN(s) have no recognized consumer.",
                f"Unreferenced VLAN IDs: {preview}. Consumers outside the supported model may still exist.",
                "Confirm each VLAN is unused across the intended scope before removing it.",
                Confidence.GENERIC,
            ),
        )


class MissingHybridVlanRule:
    metadata = RuleMetadata("HUA-VLAN-004", "Undefined hybrid VLAN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return (
            *_missing_ranges(context, "hybrid_tagged_vlans", self.metadata.rule_id),
            *_missing_ranges(context, "hybrid_untagged_vlans", self.metadata.rule_id),
        )


class MissingPvidVlanRule:
    metadata = RuleMetadata("HUA-VLAN-005", "Undefined interface PVID", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            if interface.pvid_vlan is None or interface.pvid_vlan in _defined_vlans(context):
                continue
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=interface.command_sources.get("pvid_vlan", interface.source),
                    object_name=interface.name,
                    full_message=f"PVID VLAN {interface.pvid_vlan} is not defined.",
                    snippet_message=f"PVID VLAN {interface.pvid_vlan} was not found in the snippet.",
                    explanation="The trunk or hybrid PVID has no matching global VLAN definition.",
                    suggested_fix=f"Create VLAN {interface.pvid_vlan} or correct the interface PVID.",
                )
            )
        return tuple(result)
