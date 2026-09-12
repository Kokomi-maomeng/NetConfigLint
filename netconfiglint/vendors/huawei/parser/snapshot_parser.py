"""Bounded parsers for Huawei operational snapshot sections."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import replace
from typing import cast

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.lexer import lex_lines
from netconfiglint.core.model import (
    SnapshotBgpPeer,
    SnapshotEvidence,
    SnapshotInterface,
    SnapshotRoute,
)
from netconfiglint.core.model.config import RibCapture

_BGP_STATES = {"idle", "connect", "active", "opensent", "openconfirm", "established", "no", "noneg"}


class HuaweiSnapshotParser:
    def parse(self, source: str) -> SnapshotEvidence:
        evidence = SnapshotEvidence()
        section: str | None = None
        capture: RibCapture | None = None
        pending_ipv6: dict[str, object] | None = None
        # Identity is used only within this parse; no device name is retained in metadata.
        devices = set(re.findall(r"(?im)^\s*sysname\s+(\S+)\s*$", source))
        peer_scope_known = True

        def append_route(route: SnapshotRoute) -> None:
            if capture is not None:
                capture.routes.append(
                    replace(route, vpn_instance=capture.vpn_instance, scope_known=capture.scope_known)
                )

        for line in lex_lines(source):
            checkpoint()
            text, lower = line.text, line.text.lower()
            prompt = re.match(r"^<([^>]+)>\s*(.*)$", text)
            command = prompt.group(2) if prompt else text
            if prompt:
                devices.add(prompt.group(1))
            if prompt or command.lower().startswith("display "):
                if capture is not None:
                    capture.terminated = prompt is not None
                    if pending_ipv6 is not None:
                        capture.truncated = True
                capture, pending_ipv6, section = None, None, None
                rib = re.fullmatch(r"display (ip|ipv6) routing-table(?:\s+(.*))?", command, re.I)
                if rib:
                    args = (rib.group(2) or "").split()
                    vpn = None
                    if len(args) >= 2 and args[0].lower() == "vpn-instance":
                        vpn, args = args[1], args[2:]
                    capture = RibCapture(
                        4 if rib.group(1).lower() == "ip" else 6,
                        SourceRange(line.number),
                        vpn,
                        unfiltered=not args,
                    )
                    evidence.rib_captures.append(capture)
                    section = "rib"
                    if capture.family == 4:
                        evidence.ipv4_rib_present = True
                    else:
                        evidence.ipv6_rib_present = True
                elif command.lower().startswith("display bgp peer"):
                    section = "bgp"
                    # Scoped/filtered peer output must not satisfy global peer references.
                    peer_scope_known = command.lower() == "display bgp peer"
                    evidence.bgp_peer_table_present = True
                elif command.lower() in {"display ip interface brief", "display interface brief"}:
                    section = "interface"
                    evidence.interface_table_present = True
                continue
            if section == "rib" and capture is not None:
                if re.search(r"permission|denied|error|failed|unrecognized|incomplete command", lower):
                    capture.failed = True
                if re.search(r"--+\s*more|truncat|press.*(?:space|continue)|^\^$", lower):
                    capture.truncated = True
                table = re.match(r"routing table\s*:\s*(\S+)", text, re.I)
                if table:
                    table_vpn = None if table.group(1).lower() in {"public", "_public_"} else table.group(1)
                    if table_vpn != capture.vpn_instance:
                        capture.scope_known = False
                count = re.search(r"destinations?\s*:\s*(\d+)", text, re.I)
                if count:
                    capture.expected_count = int(count.group(1))
                    if capture.expected_count == 0:
                        capture.header_seen = True
                if ("destination/mask" in lower and "nexthop" in lower) or (
                    "destination" in lower and "prefixlength" in lower
                ):
                    capture.header_seen = True
                if capture.family == 6:
                    pending_ipv6, route = self._ipv6_route_line(text, line.number, pending_ipv6)
                    if route is not None:
                        append_route(route)
                else:
                    route = self._route(text, line.number, 4)
                    if route is not None:
                        append_route(route)
                    elif re.match(r"^[0-9]+\.", text):
                        capture.truncated = True
            elif section == "bgp" and peer_scope_known:
                peer = self._peer(text, line.number)
                if peer is not None:
                    evidence.bgp_peers[peer.address] = peer
            elif section == "interface":
                interface = self._interface(text, line.number)
                if interface is not None:
                    evidence.interfaces[interface.name.lower()] = interface
        if pending_ipv6 is not None and capture is not None:
            capture.truncated = True
        conflicting_scopes: set[tuple[int, str | None]] = set()
        complete_prefixes: dict[tuple[int, str | None], set[str]] = {}
        for item in evidence.rib_captures:
            key = (item.family, item.vpn_instance)
            prefixes = {route.prefix for route in item.routes}
            if item.complete:
                previous = complete_prefixes.setdefault(key, prefixes)
                if previous != prefixes:
                    conflicting_scopes.add(key)
        for item in evidence.rib_captures:
            key = (item.family, item.vpn_instance)
            # A partial later/earlier positive record also contradicts a complete absence.
            if key in complete_prefixes and not {r.prefix for r in item.routes} <= complete_prefixes[key]:
                conflicting_scopes.add(key)
        for item in evidence.rib_captures:
            checkpoint()
            if len(devices) > 1 or (item.family, item.vpn_instance) in conflicting_scopes:
                item.scope_known = False
            if not item.failed and item.scope_known:
                evidence.routes.extend(item.routes)
        if len(devices) > 1:
            evidence.bgp_peers.clear()
            evidence.interfaces.clear()
        return evidence

    @staticmethod
    def _finish_ipv6_route(fields: dict[str, object]) -> SnapshotRoute:
        return SnapshotRoute(
            prefix=str(fields["prefix"]),
            protocol=str(fields.get("protocol", "Unknown")),
            next_hop=str(fields.get("next_hop", "Unknown")),
            interface=str(fields.get("interface", "Unknown")),
            source=SourceRange(cast(int, fields["line"])),
        )

    @classmethod
    def _ipv6_route_line(
        cls, text: str, line_number: int, pending: dict[str, object] | None
    ) -> tuple[dict[str, object] | None, SnapshotRoute | None]:
        destination = re.search(r"Destination\s*:\s*(\S+).*PrefixLength\s*:\s*(\d+)", text, re.IGNORECASE)
        if destination:
            try:
                network = ipaddress.ip_network(f"{destination.group(1)}/{destination.group(2)}", strict=False)
            except ValueError:
                return pending, None
            completed = cls._finish_ipv6_route(pending) if pending is not None else None
            return {"prefix": network, "line": line_number, "format": "detail"}, completed

        if pending is not None and pending.get("format") == "detail":
            next_hop = re.search(r"NextHop\s*:\s*(\S+)", text, re.IGNORECASE)
            protocol = re.search(r"Protocol\s*:\s*(\S+)", text, re.IGNORECASE)
            interface = re.search(r"Interface\s*:\s*(.*?)\s+Flags\s*:", text, re.IGNORECASE)
            if next_hop:
                pending["next_hop"] = next_hop.group(1)
            if protocol:
                pending["protocol"] = protocol.group(1)
            if interface:
                pending["interface"] = interface.group(1).strip()
                return None, cls._finish_ipv6_route(pending)
            return pending, None

        tokens = text.split()
        if pending is not None and pending.get("format") == "brief":
            if len(tokens) >= 2:
                try:
                    ipaddress.ip_address(tokens[0])
                except ValueError:
                    return pending, None
                pending["next_hop"] = tokens[0]
                pending["interface"] = " ".join(tokens[1:])
                return None, cls._finish_ipv6_route(pending)
            return pending, None
        if len(tokens) >= 2:
            try:
                network = ipaddress.ip_network(tokens[0], strict=False)
            except ValueError:
                return None, None
            if network.version == 6:
                return {
                    "prefix": network,
                    "protocol": tokens[1],
                    "line": line_number,
                    "format": "brief",
                }, None
        return None, None

    @staticmethod
    def _route(text: str, line_number: int, family: int) -> SnapshotRoute | None:
        tokens = text.split()
        if len(tokens) < 4:
            return None
        try:
            network = ipaddress.ip_network(tokens[0], strict=False)
        except ValueError:
            return None
        if network.version != family:
            return None
        return SnapshotRoute(
            prefix=str(network),
            protocol=tokens[1],
            next_hop=tokens[-2],
            interface=tokens[-1],
            source=SourceRange(line_number),
        )

    @staticmethod
    def _peer(text: str, line_number: int) -> SnapshotBgpPeer | None:
        tokens = text.split()
        if len(tokens) < 5:
            return None
        try:
            address = str(ipaddress.ip_address(tokens[0]))
        except ValueError:
            return None
        state_index = next(
            (index for index, token in enumerate(tokens) if token.lower().replace(" ", "") in _BGP_STATES),
            None,
        )
        if state_index is None:
            return None
        received = None
        if state_index + 1 < len(tokens) and tokens[state_index + 1].isdigit():
            received = int(tokens[state_index + 1])
        return SnapshotBgpPeer(
            address=address,
            remote_as=tokens[2] if len(tokens) > 2 else "Unknown",
            state=tokens[state_index],
            received_prefixes=received,
            source=SourceRange(line_number),
        )

    @staticmethod
    def _interface(text: str, line_number: int) -> SnapshotInterface | None:
        tokens = text.split()
        if len(tokens) < 4 or tokens[0].startswith("-"):
            return None
        physical = tokens[-2].lstrip("*").lower()
        protocol = tokens[-1].lstrip("*").lower()
        if physical not in {"up", "down", "administratively-down", "administratively"}:
            return None
        return SnapshotInterface(
            name=tokens[0],
            address=tokens[1],
            physical_state=physical,
            protocol_state=protocol,
            source=SourceRange(line_number),
        )
