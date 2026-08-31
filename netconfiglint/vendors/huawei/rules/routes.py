from __future__ import annotations

import ipaddress

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


def _route_network(destination: str, mask: str | None) -> ipaddress.IPv4Network | None:
    try:
        if "/" in destination:
            return ipaddress.IPv4Network(destination, strict=False)
        if mask is None:
            return None
        return ipaddress.IPv4Network(f"{destination}/{mask}", strict=False)
    except ValueError:
        return None


class StaticRouteFormatRule:
    metadata = RuleMetadata("HUA-ROUTE-001", "Invalid static route format", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for route in context.config.static_routes:
            valid = route.parse_valid and _route_network(route.destination, route.mask) is not None
            if valid:
                continue
            result.append(
                Diagnostic(
                    Severity.ERROR,
                    self.metadata.rule_id,
                    route.source,
                    route.destination or "ip route-static",
                    "The static route could not be normalized safely.",
                    route.parse_issue or "The destination or mask is not a valid IPv4 network form.",
                    "Correct the destination, mask/prefix length, and next-hop arguments.",
                    Confidence.VERIFIED,
                )
            )
        return tuple(result)


class AbnormalNextHopRule:
    metadata = RuleMetadata("HUA-ROUTE-002", "Abnormal static route next hop", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for route in context.config.static_routes:
            try:
                address = ipaddress.ip_address(route.next_hop)
            except ValueError:
                continue  # Interface names and supported keywords require platform knowledge.
            if not (address.is_unspecified or address.is_multicast or address.is_loopback):
                continue
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    self.metadata.rule_id,
                    route.source,
                    route.destination,
                    f"The next hop {address} is unusual for a static route.",
                    "The address is unspecified, multicast, or loopback. Some special designs may "
                    "still be intentional, so this is not asserted as an error.",
                    "Verify the next-hop intent and platform behavior using vendor-supported procedures.",
                    Confidence.GENERIC,
                )
            )
        return tuple(result)
