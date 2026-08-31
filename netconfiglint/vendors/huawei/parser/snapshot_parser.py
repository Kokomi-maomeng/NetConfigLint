"""Bounded parsers for Huawei operational snapshot sections."""

from __future__ import annotations

import ipaddress
import re
from typing import cast

from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.lexer import lex_lines
from netconfiglint.core.model import (
    SnapshotBgpPeer,
    SnapshotEvidence,
    SnapshotInterface,
    SnapshotRoute,
)

_BGP_STATES = {"idle", "connect", "active", "opensent", "openconfirm", "established", "no", "noneg"}


class HuaweiSnapshotParser:
    def parse(self, source: str) -> SnapshotEvidence:
        evidence = SnapshotEvidence()
        section: str | None = None
        pending_ipv6: dict[str, object] | None = None
        for line in lex_lines(source):
            lower = line.text.lower()
            if "display ipv6 routing-table" in lower:
                section = "rib6"
                evidence.ipv6_rib_present = True
                continue
            if "display ip routing-table" in lower:
                section = "rib4"
                evidence.ipv4_rib_present = True
                continue
            if "display bgp peer" in lower:
                section = "bgp"
                evidence.bgp_peer_table_present = True
                continue
            if "display ip interface brief" in lower or "display interface brief" in lower:
                section = "interface"
                evidence.interface_table_present = True
                continue
            if "destination/mask" in lower and "nexthop" in lower:
                section = "rib4"
                evidence.ipv4_rib_present = True
                continue
            if lower.startswith("peer ") and "state" in lower and "as" in lower:
                section = "bgp"
                evidence.bgp_peer_table_present = True
                continue
            if lower.startswith("interface ") and "physical" in lower and "protocol" in lower:
                section = "interface"
                evidence.interface_table_present = True
                continue

            if section in {"rib4", "rib6"}:
                if section == "rib6":
                    pending_ipv6, parsed = self._ipv6_route_line(line.text, line.number, pending_ipv6)
                    if parsed is not None:
                        evidence.routes.append(parsed)
                    if pending_ipv6 is not None or parsed is not None:
                        continue
                route = self._route(line.text, line.number, 4 if section == "rib4" else 6)
                if route is not None:
                    evidence.routes.append(route)
            elif section == "bgp":
                peer = self._peer(line.text, line.number)
                if peer is not None:
                    evidence.bgp_peers[peer.address] = peer
            elif section == "interface":
                interface = self._interface(line.text, line.number)
                if interface is not None:
                    evidence.interfaces[interface.name.lower()] = interface
        if pending_ipv6 is not None:
            evidence.routes.append(self._finish_ipv6_route(pending_ipv6))
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
