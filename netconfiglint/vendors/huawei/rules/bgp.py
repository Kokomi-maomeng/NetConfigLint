from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from dataclasses import replace

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.core.model import BGPPeer, BGPProcess
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def peer_scopes(bgp: BGPProcess) -> Iterator[BGPProcess]:
    """Public AF peers inherit transport settings; VPN AF peers have their own namespace."""
    yield bgp
    for family in bgp.address_families:
        checkpoint()
        groups = dict(bgp.groups) if family.vpn_instance is None else {}
        for name, group in family.groups.items():
            parent = groups.get(name)
            groups[name] = replace(
                group,
                declared=group.declared or bool(parent and parent.declared),
                remote_as=group.remote_as or (parent.remote_as if parent else None),
                group_type=group.group_type or (parent.group_type if parent else None),
                semantics_known=group.semantics_known and (parent.semantics_known if parent else True),
            )
        peers = {}
        for address, peer in family.peers.items():
            parent_peer = bgp.peers.get(address) if family.vpn_instance is None else None
            peers[address] = replace(
                peer,
                remote_as=peer.remote_as or (parent_peer.remote_as if parent_peer else None),
                group=peer.group or (parent_peer.group if parent_peer else None),
            )
        yield BGPProcess(bgp.local_as, family.source, peers=peers, groups=groups)


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
        candidates: set[tuple[str | None, Network]] = set()
        for route in context.config.static_routes:
            checkpoint()
            network = _network(route.destination, route.mask)
            if route.parse_valid and network is not None:
                candidates.add((route.vpn_instance, network))
        for interface in context.config.interfaces.values():
            checkpoint()
            for address, mask, _ in interface.ip_addresses:
                checkpoint()
                network = _network(address, mask)
                if network is not None:
                    candidates.add((interface.vpn_instance, network))
            for address, mask, _ in interface.ipv6_addresses:
                checkpoint()
                network = _network(address, mask)
                if network is not None:
                    candidates.add((interface.vpn_instance, network))
        for ipv6_route in context.config.ipv6_static_routes:
            checkpoint()
            network = _network(ipv6_route.destination, ipv6_route.prefix_length)
            if ipv6_route.parse_valid and network is not None:
                candidates.add((ipv6_route.vpn_instance, network))

        snapshot_routes = {
            (route.vpn_instance, parsed)
            for route in context.config.snapshot.routes
            if route.scope_known
            if (parsed := _network(route.prefix, None)) is not None
        }

        result = []
        for family in context.config.bgp.address_families:
            checkpoint()
            for address, mask, source in family.networks:
                checkpoint()
                network = _network(address, mask)
                if network is None:
                    continue
                key = (family.vpn_instance, network)
                complete_rib = any(
                    capture.complete
                    and capture.family == network.version
                    and capture.vpn_instance == family.vpn_instance
                    for capture in context.config.snapshot.rib_captures
                )
                if context.mode == AnalysisMode.SNAPSHOT and key in snapshot_routes:
                    continue
                if context.mode == AnalysisMode.SNAPSHOT and complete_rib:
                    severity = Severity.ERROR
                    message = f"BGP network {network} is absent from the supplied local RIB snapshot."
                    explanation = (
                        "A complete, successful, unfiltered routing table in the same "
                        "VPN/address family contains no exact prefix."
                    )
                    confidence = Confidence.VERIFIED
                elif key in candidates:
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
                source=peer.group_source or peer.source,
                object_name=peer.address,
                full_message=f"BGP peer references undefined group {peer.group}.",
                snippet_message=f"BGP group {peer.group} was not found in the snippet.",
                explanation="The peer group reference has no matching group definition.",
                suggested_fix=f"Define group {peer.group} or correct the peer group reference.",
            )
            for scope in peer_scopes(context.config.bgp)
            for peer in scope.peers.values()
            if peer.group is not None
            and (peer.group not in scope.groups or not scope.groups[peer.group].declared)
        )


class MissingBgpPeerRemoteAsRule:
    metadata = RuleMetadata("HUA-BGP-005", "BGP peer without remote AS", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.bgp is None:
            return ()
        return tuple(
            Diagnostic(
                Severity.UNKNOWN
                if context.mode == AnalysisMode.SNIPPET
                or (peer.group in scope.groups and not scope.groups[peer.group].semantics_known)
                else Severity.ERROR,
                self.metadata.rule_id,
                peer.source,
                peer.address,
                "BGP peer has no effective remote AS in the supplied configuration.",
                "The supplied full configuration does not establish how the peer inherits its remote AS.",
                "Configure the peer AS number or bind the peer to a defined group with a remote AS.",
                Confidence.LOW
                if context.mode == AnalysisMode.SNIPPET
                or (peer.group in scope.groups and not scope.groups[peer.group].semantics_known)
                else Confidence.DOCUMENTED,
            )
            for scope in peer_scopes(context.config.bgp)
            for peer in scope.peers.values()
            if effective_remote_as(scope, peer) is None
        )


def _valid_as(value: str | None) -> bool:
    if value is None:
        return False
    parts = value.split(".")
    if len(parts) == 1:
        return (
            parts[0].isascii()
            and parts[0].isdigit()
            and len(parts[0]) <= 10
            and 1 <= int(parts[0]) <= 4294967295
        )
    return (
        len(parts) == 2
        and all(
            part.isascii() and part.isdigit() and len(part) <= 5 and 0 <= int(part) <= 65535 for part in parts
        )
        and any(int(part) for part in parts)
    )


def effective_remote_as(bgp: BGPProcess, peer: BGPPeer) -> str | None:
    if peer.remote_as is not None:
        return peer.remote_as if _valid_as(peer.remote_as) else None
    group = bgp.groups.get(peer.group or "")
    if group is None or not group.declared:
        return None
    value = bgp.local_as if group.group_type == "internal" else group.remote_as
    return value if _valid_as(value) else None
