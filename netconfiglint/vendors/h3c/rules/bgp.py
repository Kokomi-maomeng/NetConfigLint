from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from dataclasses import replace

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.core.model import BGPPeer, BGPProcess
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.h3c.rules.helpers import bgp_processes, missing_reference_diagnostic

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _peer_scopes(bgp: BGPProcess) -> Iterator[BGPProcess]:
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


def peer_scopes(bgp: BGPProcess) -> Iterator[BGPProcess]:
    for scope in bgp_processes(bgp):
        yield from _peer_scopes(scope)


class MissingBgpPeerGroupRule:
    metadata = RuleMetadata("H3C-BGP-004", "Undefined BGP peer group", Severity.ERROR, "H3C Comware")

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
    metadata = RuleMetadata("H3C-BGP-005", "BGP peer without remote AS", Severity.ERROR, "H3C Comware")

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
