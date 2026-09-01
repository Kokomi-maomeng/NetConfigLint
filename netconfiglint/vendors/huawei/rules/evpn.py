from __future__ import annotations

import re
from collections import defaultdict

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic

_VNI_HEADER = re.compile(r"^vni\s+(\d+)(?:\s|$)", re.IGNORECASE)
_VXLAN_VNI = re.compile(r"^vxlan\s+vni\s+(\d+)(?:\s|$)", re.IGNORECASE)
_INTERFACE_VNI = re.compile(r"^vni\s+(\d+)(?:\s|$)", re.IGNORECASE)


def _vni_definitions(context: RuleContext) -> set[int]:
    result = set()
    for block in context.config.blocks:
        match = _VNI_HEADER.match(block.header)
        if match is not None:
            result.add(int(match.group(1)))
    return result


def _bridge_bindings(context: RuleContext) -> list[tuple[str, int, SourceRange]]:
    result = []
    for block in context.config.blocks:
        if not block.header.lower().startswith("bridge-domain "):
            continue
        bridge_domain = block.header.split(maxsplit=1)[1]
        for command in block.commands:
            match = _VXLAN_VNI.match(command.text)
            if match is not None:
                result.append((bridge_domain, int(match.group(1)), command.source))
    return result


class InvalidVniRule:
    metadata = RuleMetadata("HUA-EVPN-001", "Invalid VXLAN VNI", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        candidates: list[tuple[int, SourceRange, str]] = []
        for block in context.config.blocks:
            header_match = _VNI_HEADER.match(block.header)
            if header_match is not None:
                candidates.append((int(header_match.group(1)), block.source, block.header))
            for command in block.commands:
                match = _VXLAN_VNI.match(command.text)
                if match is None and block.header.lower().startswith("interface nve"):
                    match = _INTERFACE_VNI.match(command.text)
                if match is not None:
                    candidates.append((int(match.group(1)), command.source, block.header))
        return tuple(
            Diagnostic(
                Severity.ERROR,
                self.metadata.rule_id,
                source,
                object_name,
                f"VNI {vni} is outside the valid 1-16777215 range.",
                "VXLAN uses a 24-bit VNI; zero and values above 16777215 are invalid.",
                "Assign a VNI in the range 1 through 16777215 and update every reference.",
                Confidence.DOCUMENTED,
            )
            for vni, source, object_name in candidates
            if not 1 <= vni <= 16_777_215
        )


class MissingEvpnVniDefinitionRule:
    metadata = RuleMetadata("HUA-EVPN-002", "Undefined EVPN VNI", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        definitions = _vni_definitions(context)
        # A bridge-domain VXLAN binding can be complete under BGP EVPN without a legacy
        # top-level `vni` block. Only enforce this relationship when that block family is present.
        if not definitions:
            return ()
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=source,
                object_name=f"Bridge-domain {bridge_domain}",
                full_message=f"Bridge-domain {bridge_domain} references undefined EVPN VNI {vni}.",
                snippet_message=f"EVPN VNI {vni} was not found in the snippet.",
                explanation="The bridge-domain VXLAN binding has no matching VNI definition.",
                suggested_fix=f"Define VNI {vni} with the intended EVPN attributes or correct the binding.",
            )
            for bridge_domain, vni, source in _bridge_bindings(context)
            if vni not in definitions
        )


class DuplicateBridgeDomainVniRule:
    metadata = RuleMetadata("HUA-EVPN-003", "VNI bound to multiple bridge-domains", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        by_vni: defaultdict[int, list[tuple[str, SourceRange]]] = defaultdict(list)
        for bridge_domain, vni, source in _bridge_bindings(context):
            by_vni[vni].append((bridge_domain, source))
        result = []
        for vni, bindings in sorted(by_vni.items()):
            if len({item[0] for item in bindings}) < 2:
                continue
            for _bridge_domain, source in bindings[1:]:
                result.append(
                    Diagnostic(
                        Severity.ERROR,
                        self.metadata.rule_id,
                        source,
                        f"VNI {vni}",
                        f"VNI {vni} is bound to multiple bridge-domains.",
                        "A Layer 2 VNI must identify one bridge-domain within a device configuration.",
                        "Assign distinct VNIs or consolidate the duplicate bridge-domain binding.",
                        Confidence.VERIFIED,
                    )
                )
        return tuple(result)
