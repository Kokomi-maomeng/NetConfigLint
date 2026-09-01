from __future__ import annotations

import ipaddress

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.facts import all_commands
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


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


class MissingStaticRouteVpnRule:
    metadata = RuleMetadata("HUA-ROUTE-003", "Undefined static-route VPN", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        seen: set[tuple[int, str]] = set()
        for text, source, block in all_commands(context.config):
            tokens = text.split()
            lowered = [token.lower() for token in tokens]
            if lowered[:2] not in (["ip", "route-static"], ["ipv6", "route-static"]):
                continue
            for index, token in enumerate(lowered[:-1]):
                if token != "vpn-instance":
                    continue
                vpn_instance = tokens[index + 1]
                marker = (source.line, vpn_instance)
                if marker in seen or vpn_instance in context.config.vpn_instances:
                    continue
                seen.add(marker)
                result.append(
                    missing_reference_diagnostic(
                        context,
                        rule_id=self.metadata.rule_id,
                        source=source,
                        object_name=block.header,
                        full_message=f"Static route references undefined VPN instance {vpn_instance}.",
                        snippet_message=f"VPN instance {vpn_instance} was not found in the snippet.",
                        explanation=(
                            "The route source or next-table scope names a VPN instance absent "
                            "from the supplied configuration."
                        ),
                        suggested_fix=f"Define VPN instance {vpn_instance} or correct the route scope.",
                    )
                )
        return tuple(result)
