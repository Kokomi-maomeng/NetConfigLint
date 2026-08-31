from __future__ import annotations

import ipaddress

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


class IPv6StaticRouteFormatRule:
    metadata = RuleMetadata("HUA-IPV6-001", "Invalid IPv6 static route", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for route in context.config.ipv6_static_routes:
            valid = route.parse_valid
            try:
                suffix = route.prefix_length or (
                    route.destination.split("/", 1)[1] if "/" in route.destination else "128"
                )
                address = route.destination.split("/", 1)[0]
                network = ipaddress.IPv6Network(f"{address}/{suffix}", strict=False)
            except (ValueError, IndexError):
                valid = False
                network = None
            if valid:
                continue
            result.append(
                Diagnostic(
                    Severity.ERROR,
                    self.metadata.rule_id,
                    route.source,
                    str(network) if network else route.destination or "IPv6 static route",
                    "The IPv6 static route destination/prefix cannot be normalized.",
                    route.parse_issue or "The destination is not a valid IPv6 prefix.",
                    "Correct the IPv6 destination and prefix length using the documented profile syntax.",
                    Confidence.VERIFIED,
                )
            )
        return tuple(result)


class IPv6InterfaceAddressRule:
    metadata = RuleMetadata("HUA-IPV6-002", "Invalid interface IPv6 address", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for interface in context.config.interfaces.values():
            for address, prefix, source in interface.ipv6_addresses:
                try:
                    suffix = prefix or (address.split("/", 1)[1] if "/" in address else "128")
                    ipaddress.IPv6Interface(f"{address.split('/', 1)[0]}/{suffix}")
                except (ValueError, IndexError):
                    result.append(
                        Diagnostic(
                            Severity.ERROR,
                            self.metadata.rule_id,
                            source,
                            interface.name,
                            "The interface IPv6 address or prefix length is invalid.",
                            "The normalized value is not a valid IPv6 interface address.",
                            "Correct the ipv6 address command and prefix length.",
                            Confidence.VERIFIED,
                        )
                    )
        return tuple(result)
