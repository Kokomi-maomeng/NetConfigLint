from __future__ import annotations

from netconfiglint.core.diagnostics import Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class MissingInterfaceVpnRule:
    metadata = RuleMetadata("HUA-VPN-001", "Undefined interface VPN instance", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=interface.command_sources.get("vpn_instance", interface.source),
                object_name=interface.name,
                full_message=f"VPN instance {interface.vpn_instance} is not defined.",
                snippet_message=f"VPN instance {interface.vpn_instance} was not found in the snippet.",
                explanation="The interface binding has no matching VPN instance definition.",
                suggested_fix=f"Define VPN instance {interface.vpn_instance} or correct the binding.",
            )
            for interface in context.config.interfaces.values()
            if interface.vpn_instance is not None
            and interface.vpn_instance not in context.config.vpn_instances
        )


class MissingBgpVpnRule:
    metadata = RuleMetadata("HUA-VPN-002", "Undefined BGP VPN instance", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=family.source,
                object_name=family.name,
                full_message=f"BGP address-family references undefined VPN instance {family.vpn_instance}.",
                snippet_message=f"VPN instance {family.vpn_instance} was not found in the snippet.",
                explanation="The BGP VPN address-family has no matching VPN instance definition.",
                suggested_fix=f"Define VPN instance {family.vpn_instance} or correct the address-family.",
            )
            for family in context.config.bgp.address_families
            if family.vpn_instance is not None and family.vpn_instance not in context.config.vpn_instances
        )
