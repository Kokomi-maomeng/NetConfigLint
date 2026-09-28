from __future__ import annotations

import ipaddress

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.core.model import Interface
from netconfiglint.rules import RuleContext, RuleMetadata


def _has_business(interface: Interface) -> bool:
    return bool(
        interface.allowed_vlans
        or interface.hybrid_tagged_vlans
        or interface.hybrid_untagged_vlans
        or interface.vlan_all
        or interface.access_vlan is not None
        or interface.pvid_vlan is not None
        or interface.ip_addresses
        or interface.ipv6_addresses
        or interface.vpn_instance
        or interface.traffic_policies
        or interface.eth_trunk
    )


class ShutdownWithBusinessConfigRule:
    metadata = RuleMetadata(
        "H3C-IF-001", "Shutdown interface with business configuration", Severity.WARNING, "H3C Comware"
    )

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            business = _has_business(interface)
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
    metadata = RuleMetadata("H3C-IF-002", "Interface link-type mismatch", Severity.ERROR, "H3C Comware")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            trunk = bool(interface.allowed_vlans or "allowed_vlans" in interface.vlan_all)
            hybrid = bool(
                interface.hybrid_tagged_vlans
                or interface.hybrid_untagged_vlans
                or {"hybrid_tagged_vlans", "hybrid_untagged_vlans"} & interface.vlan_all
            )
            mismatch = bool(trunk and interface.link_type not in {None, "trunk"})
            mismatch = mismatch or bool(hybrid and interface.link_type not in {None, "hybrid"})
            mismatch = mismatch or bool(
                interface.access_vlan is not None and interface.link_type not in {None, "access"}
            )
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


class InvalidInterfaceAddressRule:
    metadata = RuleMetadata("H3C-IF-005", "Invalid interface IPv4 address", Severity.ERROR, "H3C Comware")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            for address, mask, source in interface.ip_addresses:
                checkpoint()
                try:
                    if mask is None and "/" not in address:
                        raise ValueError
                    ipaddress.IPv4Interface(address if "/" in address else f"{address}/{mask}")
                except ValueError:
                    result.append(
                        Diagnostic(
                            Severity.ERROR,
                            self.metadata.rule_id,
                            source,
                            interface.name,
                            "The interface IPv4 address or mask is invalid.",
                            "The address and mask cannot be normalized as an IPv4 interface.",
                            "Correct the IPv4 address and dotted-decimal mask or prefix length.",
                            Confidence.VERIFIED,
                        )
                    )
        return tuple(result)
