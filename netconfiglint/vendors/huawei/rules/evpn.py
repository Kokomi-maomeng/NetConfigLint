from __future__ import annotations

import re
from collections import defaultdict

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata

_VNI_HEADER = re.compile(r"^vni\s+(\d+)(?:\s|$)", re.IGNORECASE)
_VXLAN_VNI = re.compile(r"^vxlan\s+vni\s+(\d+)(?:\s|$)", re.IGNORECASE)
_INTERFACE_VNI = re.compile(r"^vni\s+(\d+)(?:\s|$)", re.IGNORECASE)


def _vni_definitions(context: RuleContext) -> set[int]:
    result = set()
    for block in context.config.blocks:
        checkpoint()
        match = _VNI_HEADER.match(block.header)
        if match is not None:
            result.add(int(match.group(1)))
    return result


def _bridge_bindings(context: RuleContext) -> list[tuple[str, int, SourceRange]]:
    result = []
    for block in context.config.blocks:
        checkpoint()
        if not block.header.lower().startswith("bridge-domain "):
            continue
        bridge_domain = block.header.split(maxsplit=1)[1]
        for command in block.commands:
            checkpoint()
            if command.views:
                continue
            match = _VXLAN_VNI.match(command.text)
            if match is not None:
                result.append((bridge_domain, int(match.group(1)), command.source))
    return result


class InvalidVniRule:
    metadata = RuleMetadata("HUA-EVPN-001", "Invalid VXLAN VNI", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        candidates: list[tuple[int, SourceRange, str]] = []
        for block in context.config.blocks:
            checkpoint()
            header_match = _VNI_HEADER.match(block.header)
            if header_match is not None:
                candidates.append((int(header_match.group(1)), block.source, block.header))
            for command in block.commands:
                checkpoint()
                if command.views:
                    continue
                match = (
                    _VXLAN_VNI.match(command.text)
                    if block.header.lower().startswith("bridge-domain ")
                    else None
                )
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
    metadata = RuleMetadata("HUA-EVPN-002", "Unverified EVPN VNI relationship", Severity.UNKNOWN, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        definitions = _vni_definitions(context)
        # A bridge-domain VXLAN binding can be complete under BGP EVPN without a legacy
        # top-level `vni` block. Only enforce this relationship when that block family is present.
        if not definitions:
            return ()
        return tuple(
            Diagnostic(
                Severity.UNKNOWN,
                self.metadata.rule_id,
                source,
                f"Bridge-domain {bridge_domain}",
                f"Cannot verify whether VNI {vni} requires a separate EVPN VNI block.",
                "A bridge-domain VXLAN binding can itself create a VNI. Other top-level VNI blocks "
                "do not prove a universal requirement for this model, version, or service.",
                "Check the intended VXLAN/EVPN configuration against the exact device command reference.",
                Confidence.GENERIC,
            )
            for bridge_domain, vni, source in _bridge_bindings(context)
            if vni not in definitions
        )


class DuplicateBridgeDomainVniRule:
    metadata = RuleMetadata("HUA-EVPN-003", "VNI bound to multiple bridge-domains", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        by_vni: defaultdict[int, list[tuple[str, SourceRange]]] = defaultdict(list)
        for bridge_domain, vni, source in _bridge_bindings(context):
            checkpoint()
            by_vni[vni].append((bridge_domain, source))
        result = []
        for vni, bindings in sorted(by_vni.items()):
            checkpoint()
            if len({item[0] for item in bindings}) < 2:
                continue
            for _bridge_domain, source in bindings[1:]:
                checkpoint()
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
