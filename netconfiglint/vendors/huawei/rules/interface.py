from __future__ import annotations

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class ShutdownWithBusinessConfigRule:
    metadata = RuleMetadata(
        "HUA-IF-001", "Shutdown interface with business configuration", Severity.WARNING, "Huawei"
    )

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            business = bool(
                interface.allowed_vlans
                or interface.access_vlan is not None
                or interface.ip_addresses
                or interface.vpn_instance
            )
            if interface.shutdown and business:
                result.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.metadata.rule_id,
                        interface.command_sources.get("shutdown", interface.source),
                        interface.name,
                        "The interface is shut down while business configuration is present.",
                        "Administrative shutdown may intentionally stage configuration, so this is "
                        "reported as a warning rather than an error.",
                        "Verify intent; use undo shutdown only when the interface should be active.",
                        Confidence.VERIFIED,
                    )
                )
        return tuple(result)


class LinkTypeMismatchRule:
    metadata = RuleMetadata("HUA-IF-002", "Interface link-type mismatch", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            mismatch = bool(interface.allowed_vlans and interface.link_type not in {None, "trunk", "hybrid"})
            mismatch = mismatch or bool(interface.access_vlan is not None and interface.link_type == "trunk")
            if mismatch:
                result.append(
                    Diagnostic(
                        Severity.ERROR,
                        self.metadata.rule_id,
                        interface.command_sources.get("link_type", interface.source),
                        interface.name,
                        "The VLAN command conflicts with the configured interface link type.",
                        "The normalized access/trunk VLAN intent is inconsistent with link-type.",
                        "Align port link-type with the intended access, trunk, or hybrid behavior.",
                        Confidence.VERIFIED,
                    )
                )
        return tuple(result)


class MissingEthTrunkRule:
    metadata = RuleMetadata("HUA-IF-003", "Undefined Eth-Trunk", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        names = {name.lower() for name in context.config.interfaces}
        result = []
        for interface in context.config.interfaces.values():
            if interface.eth_trunk is None:
                continue
            expected = f"eth-trunk{interface.eth_trunk}".lower()
            if expected in names:
                continue
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=interface.command_sources.get("eth_trunk", interface.source),
                    object_name=interface.name,
                    full_message=f"Eth-Trunk {interface.eth_trunk} is referenced but not defined.",
                    snippet_message=f"Eth-Trunk {interface.eth_trunk} was not found in the snippet.",
                    explanation="The member interface references an Eth-Trunk interface that is "
                    "absent from the supplied full configuration.",
                    suggested_fix=f"Create Eth-Trunk{interface.eth_trunk} or correct the member reference.",
                )
            )
        return tuple(result)


class OperationalInterfaceDownRule:
    metadata = RuleMetadata("HUA-IF-004", "Business interface operationally down", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode != AnalysisMode.SNAPSHOT:
            return ()
        result = []
        for interface in context.config.interfaces.values():
            status = context.config.snapshot.interfaces.get(interface.name.lower())
            business = bool(
                interface.allowed_vlans
                or interface.access_vlan is not None
                or interface.ip_addresses
                or interface.ipv6_addresses
                or interface.vpn_instance
            )
            if status is None or not business or interface.shutdown:
                continue
            if status.physical_state == "up" and status.protocol_state == "up":
                continue
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    self.metadata.rule_id,
                    status.source,
                    interface.name,
                    "The configured business interface is not operationally up.",
                    f"Snapshot state is physical={status.physical_state}, protocol={status.protocol_state}.",
                    "Check link, optics/cabling, peer state, VLAN/L3 configuration, and device logs.",
                    Confidence.VERIFIED,
                )
            )
        return tuple(result)
