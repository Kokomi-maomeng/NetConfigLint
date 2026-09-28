from __future__ import annotations

from netconfiglint.core.diagnostics import Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.h3c.rules.helpers import missing_reference_diagnostic


class MissingInterfaceVpnRule:
    metadata = RuleMetadata("H3C-VPN-001", "Undefined interface VPN instance", Severity.ERROR, "H3C Comware")

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
    metadata = RuleMetadata("H3C-VPN-002", "Undefined BGP VPN instance", Severity.ERROR, "H3C Comware")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=scope.source,
                object_name=f"BGP VPN {name}",
                full_message=f"BGP address-family references undefined VPN instance {name}.",
                snippet_message=f"VPN instance {name} was not found in the snippet.",
                explanation="The BGP VPN address-family has no matching VPN instance definition.",
                suggested_fix=f"Define VPN instance {name} or correct the address-family.",
            )
            for name, scope in context.config.bgp.vpn_scopes.items()
            if name not in context.config.vpn_instances
        )
