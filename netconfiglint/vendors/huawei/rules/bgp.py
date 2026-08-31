from __future__ import annotations

import ipaddress

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


def _network(address: str, mask: str | None) -> ipaddress.IPv4Network | None:
    try:
        if "/" in address:
            return ipaddress.IPv4Network(address, strict=False)
        if mask is None:
            return ipaddress.IPv4Network(f"{address}/32", strict=False)
        return ipaddress.IPv4Network(f"{address}/{mask}", strict=False)
    except ValueError:
        return None


class BgpNetworkCandidateRule:
    metadata = RuleMetadata("HUA-BGP-002", "Unproven BGP network", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        candidates: set[ipaddress.IPv4Network] = set()
        for route in context.config.static_routes:
            network = _network(route.destination, route.mask)
            if network is not None:
                candidates.add(network)
        for interface in context.config.interfaces.values():
            for address, mask, _ in interface.ip_addresses:
                network = _network(address, mask)
                if network is not None:
                    candidates.add(network)

        result = []
        for family in context.config.bgp.address_families:
            for address, mask, source in family.networks:
                network = _network(address, mask)
                if network is None or network in candidates:
                    continue
                severity = Severity.UNKNOWN if context.mode == AnalysisMode.SNAPSHOT else Severity.WARNING
                result.append(
                    Diagnostic(
                        severity,
                        self.metadata.rule_id,
                        source,
                        str(network),
                        "The configured BGP network cannot be proven to exist in the local RIB "
                        "using configuration data alone.",
                        "No matching normalized static or connected candidate route was found. "
                        "Runtime routing-table evidence is required for a definitive result.",
                        "Verify the route in the local RIB or add the intended contributing route.",
                        Confidence.INFERRED,
                    )
                )
        return tuple(result)
