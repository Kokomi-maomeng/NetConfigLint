"""Conservative, effective source-text object identities for CLI completion.

This index is independent of semantic analysis. A candidate means a complete
declaration remains in the document, never that a device has accepted it.
Names stay case sensitive and unrelated protocol/security namespaces stay apart.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_TYPE_DATA = json.loads((Path(__file__).with_name("data") / "interface_types.json").read_text("utf-8"))
INTERFACE_TYPES = {
    vendor: tuple(row["canonical"] for row in _TYPE_DATA["types"] if row["vendor"] == vendor)
    for vendor in ("h3c", "huawei")
}


def interface_parts(value: str, vendor: str) -> tuple[str, str] | None:
    """Combine documented type/number spellings; reject headings/unknown qualifiers."""
    for kind in sorted(INTERFACE_TYPES[vendor], key=len, reverse=True):
        match = re.fullmatch(re.escape(kind) + r"\s*(\d+(?:/\d+)*(?::\d+)?(?:\.\d+)?)", value, re.I)
        if match:
            return kind, match[1]
    return None


def cli_body(raw: str) -> str:
    # The lexer owns the shared prompt contract. Lazy import avoids a module cycle.
    from netconfiglint.core.lexer import normalize_cli_line

    return normalize_cli_line(raw)[0].strip()


@lru_cache(maxsize=16)
def declared(source: str, vendor: str) -> dict[str, tuple[str, ...]]:
    buckets: dict[str, set[str]] = {}
    bgp_scope = ""
    in_bgp = False
    route_nodes: dict[str, set[str]] = {}

    def update(key: str, name: str, removed: bool) -> None:
        values = buckets.setdefault(key, set())
        if removed:
            values.discard(name)
        else:
            values.add(name)

    for raw in source.splitlines():
        body = cli_body(raw)
        if not body or body.startswith(("#", "!", "//", ";")) or '"' in body or "'" in body:
            if body == "#":
                in_bgp = False
            continue
        words = body.split()
        lower = [value.lower() for value in words]
        removed = lower[0] == "undo"
        if removed:
            words, lower = words[1:], lower[1:]
        if not words:
            continue
        if lower[0] == "bgp" and len(words) > 1:
            bgp_scope = " ".join(words[1:])
            in_bgp = not removed
            continue
        if lower[0] in {"return", "quit", "exit", "system-view"}:
            in_bgp = False
            continue
        if lower[0] in {"interface", "acl", "vlan", "traffic", "qos", "ssl", "ip", "dhcp"}:
            in_bgp = False
        key = ""
        name = ""
        if lower[:2] == ["ip", "vpn-instance"] and len(words) == 3:
            key, name = "vpn", words[2]
        elif lower[0] == "route-policy" and len(words) >= 2:
            # A policy's permit/deny and node number are required for a declaration.
            if removed and len(words) == 2:
                route_nodes.pop(words[1], None)
                key, name = "route-policy", words[1]
            elif (
                len(words) == 5
                and lower[2] in {"permit", "deny"}
                and lower[3] == "node"
                and words[4].isdigit()
            ):
                nodes = route_nodes.setdefault(words[1], set())
                if removed:
                    nodes.discard(words[4])
                else:
                    nodes.add(words[4])
                update("route-policy", words[1], not nodes)
        elif lower[:2] in (
            ["traffic", "classifier"],
            ["traffic", "behavior"],
            ["traffic", "policy"],
            ["qos", "policy"],
        ):
            if len(words) >= 3 and (
                len(words) == 3
                or (
                    lower[1] == "classifier"
                    and len(words) == 5
                    and lower[3] == "operator"
                    and lower[4] in {"and", "or"}
                )
            ):
                key = {"classifier": "classifier", "behavior": "behavior", "policy": "policy"}[lower[1]]
                name = words[2]
        elif lower[0] == "interface" and len(words) in {2, 3}:
            parts = interface_parts(" ".join(words[1:]), vendor)
            if parts:
                key, name = "interface", "".join(parts)
        elif lower[0] == "acl" and len(words) >= 2:
            offset = 1
            if lower[1] in {"ipv6", "ipv4"}:
                offset += 1
            rest, tail = words[offset:], lower[offset:]
            if tail and tail[0] in {"basic", "advanced", "mac", "number"}:
                rest, tail = rest[1:], tail[1:]
            if tail and tail[0] == "name" and len(rest) >= 2:
                key, name = "acl-name", rest[1]
            elif rest and rest[0].isdigit():
                key, name = "acl-number", rest[0]
            if key:
                family = "ipv6" if lower[1] == "ipv6" else "mac" if "mac" in lower[:3] else "ipv4"
                update("acl-" + family + "-" + key.removeprefix("acl-"), name, removed)
                if key == "acl-number":
                    number = int(name)
                    category = (
                        "basic"
                        if 2000 <= number <= 2999
                        else "advanced"
                        if 3000 <= number <= 3999
                        else "mac"
                        if 4000 <= number <= 4999
                        else "other"
                    )
                    update("acl-" + category + "-number", name, removed)
        elif lower[0] == "vlan" and len(words) in {2, 4} and words[1].isdigit():
            start = int(words[1])
            stop = int(words[3]) if len(words) == 4 and lower[2] == "to" and words[3].isdigit() else start
            if 1 <= start <= stop <= 4094:
                for number in range(start, stop + 1):
                    update("vlan", str(number), removed)
        elif lower[:2] in (
            ["ip", "ip-prefix"],
            ["ip", "prefix-list"],
            ["ipv6", "prefix-list"],
            ["ipv6", "ip-prefix"],
        ):
            if len(words) >= 3 and (removed or any(value in {"permit", "deny"} for value in lower[3:])):
                key, name = "prefix6" if lower[0] == "ipv6" else "prefix4", words[2]
        elif lower[0] == "group" and in_bgp and len(words) >= 2:
            if removed or (len(words) == 3 and lower[2] in {"internal", "external"}):
                key, name = "bgp-group:" + bgp_scope, words[1]
                update("bgp-group", name, removed)
        elif lower[0] == "time-range" and len(words) >= 2 and (removed or len(words) >= 4):
            key, name = "time-range", words[1]
        elif lower[:3] == ["dhcp", "server", "ip-pool"] and len(words) == 4:
            key, name = "dhcp-pool", words[3]
        elif lower[:2] == ["ip", "pool"] and len(words) == 3:
            key, name = "dhcp-pool", words[2]
        elif (
            lower[:2] in (["ssl", "policy"], ["ssl", "client-policy"], ["ssl", "server-policy"])
            and len(words) == 3
        ):
            key, name = "ssl:" + lower[1], words[2]
        if key and name and not name.startswith(("<", "[", "{")):
            update(key, name, removed)
    return {key: tuple(sorted(values)) for key, values in buckets.items()}


# Explicit, reviewed aliases: never assume arbitrary "name"/"policy"/"group" denotes an object.
ALIASES = {
    "vpn": {
        "vpn-instance",
        "vpn-instance-name",
        "s-vpn-instance-name",
        "d-vpn-instance-name",
        "source-vpn-instance-name",
        "receive-vpn-instance-name",
        "vpn-ins-name",
        "vpn-source-name",
        "vpn-destination-name",
        "ipv4-vpn-name",
        "ipv6-vpn-name",
        "ipv6-vpn-instance-name",
        "vpn6-instance-name",
        "vpnv4-vpn-instance-name",
        "srcvpn6-instance-name",
        "dstvpn6-instance-name",
        "vpninstancename",
        "vpninstance",
        "vpn-instacne-name",
        "vpn_name",
        "vpn-name",
        "vpn-name-bak",
    },
    "route-policy": {
        "route-policy",
        "route-policy-name",
        "route-policy-name1",
        "route-policy-name2",
        "route-policy-name3",
        "attribute-policy-name",
        "advertise-policy-name",
        "exist-policy-name",
        "non-exist-policy-name",
    },
    "classifier": {"classifier-name", "traffic-classifier-name", "before-classifier-name"},
    "behavior": {"behavior-name", "traffic-behavior-name"},
    "policy": {"qos-policy-name", "traffic-policy-name"},
    "interface": {
        "interface-name",
        "ifname",
        "if-name",
        "interfacename",
        "interface-name1",
        "interface-name2",
        "ifname1",
        "ifname2",
        "interface-name-start",
        "interface-name-end",
        "in-if-name",
        "out-if-name",
        "in-interface-name",
        "out-interface-name",
        "src-interface-name",
        "member-if-name",
        "admin-if-name",
        "incoming-interfacename",
        "outgoing-interfacename",
        "protocol-interface-name",
        "arp-interface-name",
        "nd-interface-name",
        "sifname",
        "cifname",
        "endifname",
        "startifname",
        "nve-interface-name",
    },
    "interface-type": {
        "interface-type",
        "if-type",
        "iftype",
        "interfacetype",
        "interface_type",
        "interface-type1",
        "interface-type2",
        "interface-type-start",
        "interface-type-end",
        "in-interface-type",
        "out-interface-type",
        "member-interface-type",
        "member-if-type",
        "admin-interface-type",
        "admin-if-type",
        "protocol-interface-type",
        "incoming-interfacetype",
        "outgoing-interfacetype",
        "arp-interface-type",
        "arp-iftype",
        "nd-iftype",
        "siftype",
        "ciftype",
        "beginiftype",
        "endiftype",
        "localiftype",
        "unnumif-type",
    },
    "interface-number": {
        "interface-number",
        "interface-num",
        "interfacenum",
        "interfacenumber",
        "interface_num",
        "interface-number1",
        "interface-number2",
        "interface-number-start",
        "interface-number-end",
        "interface-number-begin",
        "start-interface-number",
        "end-interface-number",
        "interface-numbe",
        "interface-nmuber",
        "in-interface-number",
        "out-interface-number",
        "admin-interface-number",
        "member-interface-number",
        "protocol-interface-number",
        "arp-interface-number",
        "incoming-interfacenum",
        "outgoing-interfacenum",
        "interface-number.subnumber",
        "interface-number.subinterface-number",
        "interface-number.subnum",
        "interface-num.subnum",
    },
    "acl-name": {
        "acl-name",
        "ipv4-acl-name",
        "ipv6-acl-name",
        "basic-acl-name",
        "advance-acl-name",
        "mac-acl-name",
        "link-acl-name",
        "acl-name-l2",
        "acl-name-string",
        "acl-name-val",
        "acl-name-value",
        "source-acl-name",
        "dest-acl-name",
    },
    "acl-number": {
        "acl-number",
        "basic-acl-number",
        "advanced-acl-number",
        "advance-acl-number",
        "ipv4-acl-number",
        "ipv6-acl-number",
        "acl-number-ipv6",
        "mac-acl-number",
        "link-acl-number",
        "acl-number-l2",
        "acl-number1",
        "acl-number2",
        "acl-number3",
        "source-acl-number",
        "dest-acl-number",
    },
    "prefix4": {"prefix-list-name", "ipv4-prefix-list-name", "ip-prefix-name"},
    "prefix6": {"ipv6-prefix-list-name"},
    "time-range": {"time-range-name", "time-range", "time-name"},
    "vlan": {"vlan-id", "vlan-id1", "vlan-id2"},
}


def parameter_kind(token: str, syntax: str) -> str:
    name = token.strip("<>").lower()
    if name in {"ipv6-acl-name", "ipv6-acl-number", "acl-number-ipv6"}:
        return "acl-ipv6-" + ("name" if "name" in name else "number")
    if name in {"ipv4-acl-name", "ipv4-acl-number"}:
        return "acl-ipv4-" + ("name" if "name" in name else "number")
    if name in {
        "mac-acl-name",
        "link-acl-name",
        "acl-name-l2",
        "mac-acl-number",
        "link-acl-number",
        "acl-number-l2",
    }:
        return "acl-mac-" + ("name" if "name" in name else "number")
    if name in {"basic-acl-number", "advanced-acl-number", "advance-acl-number"}:
        return "acl-" + ("basic" if name.startswith("basic") else "advanced") + "-number"
    for key, aliases in ALIASES.items():
        if name in aliases:
            return key
    body = re.sub(r"^(?:undo|display)\s+", "", syntax.lower())
    if name == "policy-name" and re.match(r"(?:qos\b|traffic policy\b|traffic-policy\b)", body):
        return "policy"
    if name in {"group-name", "peer-group-name", "name"} and body.startswith(("peer ", "group ")):
        return "bgp-group"
    if name in {"pool-name", "ip-pool-name"} and body.startswith(("dhcp ", "ip pool ")):
        return "dhcp-pool"
    if name in {"policy-name", "ssl-policy-name"} and body.startswith("ssl "):
        if body.startswith("ssl server-policy"):
            return "ssl:server-policy"
        if body.startswith("ssl client-policy"):
            return "ssl:client-policy"
        return "ssl:policy"
    if name == "ssl-policy-name":
        if "server-policy" in body:
            return "ssl:server-policy"
        if "client-policy" in body:
            return "ssl:client-policy"
        return "ssl:policy"
    return ""


def parameter_status(token: str, syntax: str) -> str:
    kind = parameter_kind(token, syntax)
    if kind:
        return "interface-type" if kind == "interface-type" else "document-object"
    # Unknown object-looking aliases are explicit coverage gaps, not disguised
    # as parameters for which an object provider intentionally does not apply.
    if re.search(r"name|policy|group|prefix|vpn|interface|acl|pool", token, re.I):
        return "unconfirmed"
    return "manual-input"


def parameter_values(token: str, vendor: str, source: str, syntax: str, words: list[str]) -> tuple[str, ...]:
    kind = parameter_kind(token, syntax)
    if kind == "interface-type":
        return INTERFACE_TYPES[vendor]
    objects = declared(source, vendor)
    if kind == "interface-number":
        # Only numbers belonging to the preceding interface type, never arbitrary IDs.
        previous = words[-1].lower() if words else ""
        kinds = [name for name in INTERFACE_TYPES[vendor] if name.lower() == previous]
        return tuple(
            sorted(
                {
                    parts[1]
                    for name in objects.get("interface", ())
                    if (parts := interface_parts(name, vendor)) and parts[0] in kinds
                }
            )
        )
    if kind == "bgp-group":
        # A source document can contain multiple BGP instances. Scope an explicit current instance.
        scope = ""
        for raw in source.splitlines():
            match = re.fullmatch(r"bgp\s+(.+)", cli_body(raw), re.I)
            if match:
                scope = match[1]
        return objects.get("bgp-group:" + scope, ()) if scope else ()
    return objects.get(kind, ())
