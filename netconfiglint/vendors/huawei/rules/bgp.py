from __future__ import annotations

import ipaddress

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _network(address: str, mask: str | None) -> Network | None:
    try:
        if "/" in address:
            return ipaddress.ip_network(address, strict=False)
        if mask is None:
            suffix = 128 if ipaddress.ip_address(address).version == 6 else 32
            return ipaddress.ip_network(f"{address}/{suffix}", strict=False)
        return ipaddress.ip_network(f"{address}/{mask}", strict=False)
    except ValueError:
        return None


class BgpNetworkCandidateRule:
    metadata = RuleMetadata("HUA-BGP-002", "Unproven BGP network", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        candidates: set[Network] = set()
        for route in context.config.static_routes:
            network = _network(route.destination, route.mask)
            if network is not None:
                candidates.add(network)
        for interface in context.config.interfaces.values():
            for address, mask, _ in interface.ip_addresses:
                network = _network(address, mask)
                if network is not None:
                    candidates.add(network)
            for address, mask, _ in interface.ipv6_addresses:
                network = _network(address, mask)
                if network is not None:
                    candidates.add(network)
        for ipv6_route in context.config.ipv6_static_routes:
            network = _network(ipv6_route.destination, ipv6_route.prefix_length)
            if network is not None:
                candidates.add(network)

        snapshot_routes = {
            parsed
            for route in context.config.snapshot.routes
            if (parsed := _network(route.prefix, None)) is not None
        }

        result = []
        for family in context.config.bgp.address_families:
            for address, mask, source in family.networks:
                network = _network(address, mask)
                if network is None:
                    continue
                rib_present = (
                    context.config.snapshot.ipv4_rib_present
                    if network.version == 4
                    else context.config.snapshot.ipv6_rib_present
                )
                if context.mode == AnalysisMode.SNAPSHOT and rib_present:
                    if network in snapshot_routes:
                        continue
                    severity = Severity.ERROR
                    message = f"BGP network {network} is absent from the supplied local RIB snapshot."
                    explanation = (
                        "A matching routing-table section was supplied and contains no exact route prefix."
                    )
                    confidence = Confidence.VERIFIED
                elif network in candidates:
                    continue
                else:
                    severity = Severity.UNKNOWN if context.mode == AnalysisMode.SNAPSHOT else Severity.WARNING
                    message = (
                        "The configured BGP network cannot be proven to exist in the local RIB "
                        "using configuration data alone."
                    )
                    explanation = (
                        "No matching normalized static or connected candidate route was found. "
                        "Runtime routing-table evidence is required for a definitive result."
                    )
                    confidence = Confidence.INFERRED
                result.append(
                    Diagnostic(
                        severity,
                        self.metadata.rule_id,
                        source,
                        str(network),
                        message,
                        explanation,
                        "Verify the route in the local RIB or add the intended contributing route.",
                        confidence,
                    )
                )
        return tuple(result)


class BgpPeerOperationalStateRule:
    metadata = RuleMetadata("HUA-BGP-003", "BGP peer not established", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode != AnalysisMode.SNAPSHOT or context.config.bgp is None:
            return ()
        return tuple(
            Diagnostic(
                Severity.ERROR,
                self.metadata.rule_id,
                status.source,
                address,
                f"BGP peer {address} is in {status.state} state, not Established.",
                "The supplied display bgp peer output explicitly reports a non-established state.",
                "Troubleshoot reachability, AS numbers, authentication, policy, and "
                "address-family activation.",
                Confidence.VERIFIED,
            )
            for address, peer in context.config.bgp.peers.items()
            if (status := context.config.snapshot.bgp_peers.get(address)) is not None
            and status.state.lower() != "established"
        )


class MissingBgpPeerGroupRule:
    metadata = RuleMetadata("HUA-BGP-004", "Undefined BGP peer group", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=peer.source,
                object_name=peer.address,
                full_message=f"BGP peer references undefined group {peer.group}.",
                snippet_message=f"BGP group {peer.group} was not found in the snippet.",
                explanation="The peer group reference has no matching group definition.",
                suggested_fix=f"Define group {peer.group} or correct the peer group reference.",
            )
            for peer in context.config.bgp.peers.values()
            if peer.group is not None and peer.group not in context.config.bgp.groups
        )
