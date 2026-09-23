"""Small, explicit VRP syntax branches. Unknown extensions never become valid facts."""

from __future__ import annotations

import ipaddress
import re

from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.model.config import ACLRule


def vlan_list(tokens: tuple[str, ...] | list[str], *, allow_all: bool = False) -> tuple[set[int], bool]:
    words = [token.lower() for token in tokens]
    if words == ["all"] and allow_all:
        return set(), True
    if not words:
        raise ValueError("Missing VLAN ID or range")
    result: set[int] = set()
    index = 0
    while index < len(words):
        if not words[index].isdigit():
            raise ValueError("Expected a VLAN ID")
        start = int(words[index])
        end = start
        index += 1
        if index < len(words) and words[index] == "to":
            if index + 1 >= len(words) or not words[index + 1].isdigit():
                raise ValueError("Missing VLAN range endpoint")
            end = int(words[index + 1])
            index += 2
        if not 1 <= start <= end <= 4094:
            raise ValueError("VLAN IDs must be within 1..4094 and ranges must be ascending")
        result.update(range(start, end + 1))
    return result, False


def bgp_network(tokens: tuple[str, ...], family: int) -> tuple[str, str, str | None]:
    """Normalize network using its own documented classful IPv4 default."""
    if not tokens:
        raise ValueError("Missing BGP network address")
    address = ipaddress.ip_address(tokens[0])
    if address.version != family:
        raise ValueError("BGP network address does not match the address family")
    rest = list(tokens[1:])
    if rest and rest[0].lower() != "route-policy":
        mask = rest.pop(0)
    elif family == 4:
        first = int(str(address).split(".")[0])
        if not 1 <= first <= 223 or first == 127:
            raise ValueError("No supported classful default for this address; specify a mask")
        mask = str(8 if first < 128 else 16 if first < 192 else 24)
    else:
        raise ValueError("IPv6 BGP network requires a prefix length")
    network = ipaddress.ip_network(f"{address}/{mask}", strict=True)
    policy = None
    if rest:
        if len(rest) != 2 or rest[0].lower() != "route-policy":
            raise ValueError("Unexpected BGP network arguments")
        policy = rest[1]
    return str(network.network_address), str(network.prefixlen), policy


_INTERFACE = re.compile(
    r"(?:NULL\s*0|(?:GigabitEthernet|XGigabitEthernet|GE|XGE|Ethernet|Eth-Trunk|"
    r"10GE|25GE|40GE|100GE|400GE|Vlanif|LoopBack|Tunnel|Serial|Dialer)\s*\d[\d/.:-]*)$",
    re.I,
)


def route_arguments(
    tokens: tuple[str, ...], family: int
) -> tuple[str, str | None, str, str | None, str, bool]:
    """Return destination, mask, next hop, VPN, issue, known syntax.

    The bounded branches are IP next-hop, NULL0, and known outgoing-interface forms,
    with an optional IP next-hop and common documented route attributes.
    """
    rest = list(tokens)
    vpn = None
    if rest and rest[0].lower() == "vpn-instance":
        if len(rest) < 2:
            return "", None, "", None, "Missing VPN instance name", True
        vpn = rest[1]
        rest = rest[2:]
    destination = rest.pop(0) if rest else ""
    mask = None if "/" in destination else (rest.pop(0) if rest else None)
    try:
        if mask is None and "/" not in destination:
            raise ValueError
        network = ipaddress.ip_network(destination if mask is None else f"{destination}/{mask}", strict=True)
        if network.version != family:
            raise ValueError
    except ValueError:
        return destination, mask, "", vpn, "Invalid destination or required mask/prefix length", True
    if not rest:
        return destination, mask, "", vpn, "Missing next hop or outgoing interface", True
    next_hop = rest.pop(0)
    # Cross-table lookup changes the next-hop scope, never the destination route's VPN.
    if next_hop.lower() == "vpn-instance":
        if not rest:
            return destination, mask, "", vpn, "Missing next-hop VPN instance name", True
        rest.pop(0)
        if rest:
            try:
                ipaddress.ip_address(rest[0])
                next_hop = rest.pop(0)
            except ValueError:
                return destination, mask, "", vpn, "Cannot verify next-table route syntax", False
        else:
            return destination, mask, "", vpn, "Cannot verify next-table route installation", False
    if rest and _INTERFACE.fullmatch(next_hop + rest[0]):
        next_hop += rest.pop(0)
    try:
        address = ipaddress.ip_address(next_hop)
        if address.version != family:
            return destination, mask, next_hop, vpn, "Next-hop address family mismatch", True
    except ValueError:
        if re.fullmatch(r"[\d.]+", next_hop) or ":" in next_hop:
            return destination, mask, next_hop, vpn, "Invalid next-hop address", True
        if not _INTERFACE.fullmatch(next_hop):
            return destination, mask, next_hop, vpn, "Cannot verify this outgoing-interface syntax", False
        if rest:
            try:
                address = ipaddress.ip_address(rest[0])
                if address.version != family:
                    return destination, mask, next_hop, vpn, "Next-hop address family mismatch", True
                rest.pop(0)
            except ValueError:
                if re.fullmatch(r"[\d.]+", rest[0]) or ":" in rest[0]:
                    return destination, mask, next_hop, vpn, "Invalid next-hop address", True
    seen: set[str] = set()
    while rest:
        key = rest.pop(0).lower()
        if key in seen:
            return destination, mask, next_hop, vpn, "Duplicate route attribute", True
        seen.add(key)
        if key in {"preference", "tag"}:
            maximum = 255 if key == "preference" else 4294967295
            if (
                not rest
                or not rest[0].isascii()
                or not rest[0].isdigit()
                or len(rest[0]) > 10
                or not 1 <= int(rest.pop(0)) <= maximum
            ):
                return destination, mask, next_hop, vpn, "Invalid route attribute value", True
        elif key == "description":
            if not rest:
                return destination, mask, next_hop, vpn, "Missing route description", True
            rest.clear()
        elif key == "public" and family == 4 and vpn is not None:
            continue
        else:
            return destination, mask, next_hop, vpn, "Cannot verify this route extension", False
    return destination, mask, next_hop, vpn, "", True


def acl_rule(tokens: tuple[str, ...], source: SourceRange, acl_type: str, family: str) -> ACLRule | None:
    words = [token.lower() for token in tokens]
    if len(words) < 3 or words[0] != "rule" or not words[1].isdigit() or words[2] not in {"permit", "deny"}:
        return None
    action = words[2]
    rest = words[3:]
    protocol = (rest.pop(0) if rest else "unknown") if acl_type == "advanced" else family.replace("4", "")
    matches: dict[str, tuple[str, ...]] = {"source": ("any",), "destination": ("any",)}
    ports: dict[str, tuple[str, ...]] = {"source-port": (), "destination-port": ()}
    extra: list[str] = []
    known = acl_type in {"basic", "advanced"}
    seen: set[str] = set()
    while rest:
        key = rest.pop(0)
        if key in seen:
            known = False
        seen.add(key)
        if key in matches:
            if not rest:
                known = False
                break
            value = rest.pop(0)
            if value == "any":
                matches[key] = ("any",)
            elif family == "ipv4" and rest:
                wildcard = rest.pop(0)
                if wildcard == "0":
                    # This is ACL wildcard syntax, not a socket bind address.
                    wildcard = "0.0.0.0"  # nosec B104
                try:
                    ipaddress.IPv4Address(value)
                    ipaddress.IPv4Address(wildcard)
                    # ACL wildcard semantics; this is not a socket bind address.
                    matches[key] = ("any",) if wildcard == "255.255.255.255" else (value, wildcard)
                except ValueError:
                    known = False
            elif family == "ipv6":
                try:
                    prefix = value if "/" in value else f"{value}/{rest.pop(0)}"
                    network = ipaddress.IPv6Network(prefix, strict=False)
                    matches[key] = (str(network),)
                    if network.prefixlen == 0:
                        known = False
                except (ValueError, IndexError):
                    known = False
            else:
                matches[key] = (value,)
                known = False
        elif key in ports:
            if len(rest) < 2:
                known = False
                break
            op = rest.pop(0)
            count = 2 if op == "range" else 1
            ports[key] = (op, *rest[:count])
            if op not in {"eq", "gt", "lt", "neq", "range"} or len(rest) < count:
                known = False
            del rest[:count]
        else:
            extra.extend((key, *rest))
            rest.clear()
            known = False
    return ACLRule(
        words[1],
        source,
        action,
        protocol,
        matches["source"],
        matches["destination"],
        ports["source-port"],
        ports["destination-port"],
        tuple(extra),
        known,
    )
