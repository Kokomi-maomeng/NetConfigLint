"""Source-mapped VRP views and bounded effective-command reduction.

This is not a command execution engine. Only the explicit keys below support
replacement/removal; unknown undo forms stay visible in coverage.
"""

from __future__ import annotations

import ipaddress
import re
from contextlib import suppress
from dataclasses import replace

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.lexer import SourceLine
from netconfiglint.core.model import ConfigBlock, ConfigCommand
from netconfiglint.vendors.huawei.parser.acl_identity import parse_acl_identity
from netconfiglint.vendors.huawei.parser.semantics import bgp_network, route_arguments


def interface_name(value: str) -> str:
    """Join a separated type/number without guessing abbreviations or hardware."""
    return re.sub(r"^([A-Za-z][A-Za-z0-9-]*)\s+(?=\d)", r"\1", value.strip())


def _block_key(header: str) -> str | None:
    if header.lower().startswith("interface "):
        return "interface " + interface_name(header[10:]).lower()
    if re.fullmatch(r"bgp \d+(?:\.\d+)?|(?:ospf|isis) \d+(?: .*)?", header, re.I):
        return " ".join(header.split()[:2]).lower()
    if re.fullmatch(r"ospf|isis|aaa", header, re.I):
        return header.lower() + (" 1" if header.lower() != "aaa" else "")
    if re.match(r"^(?:ip vpn-instance|traffic (?:classifier|behavior|policy)|user-interface) ", header, re.I):
        parts = header.split()
        return (
            " ".join([*(p.lower() for p in parts[:2]), *parts[2:3]])
            if parts[0].lower() != "user-interface"
            else header
        )
    if re.fullmatch(r"route-policy \S+ (?:permit|deny) node \d+", header, re.I):
        parts = header.split()
        return f"route-policy {parts[1]} node {parts[4]}"
    if re.fullmatch(r"(?:bridge-domain|vni) \d+", header, re.I):
        return header.lower()
    # ACL aliases are merged by the normalized ACL parser, not by textual guesses.
    if header.lower().startswith("acl "):
        identity = parse_acl_identity(tuple(header.split()[1:]))
        if identity is not None:
            return "acl " + identity.key
    return None


def _nested(header: str, text: str) -> bool:
    root, lower = header.lower(), text.lower()
    return (
        (root.startswith("bgp ") and lower.startswith(("ipv4-family ", "ipv6-family ", "l2vpn-family ")))
        or (root.startswith(("ospf ", "ospfv3 ")) and lower.startswith("area "))
        or (root.startswith("ip vpn-instance ") and lower in {"ipv4-family", "ipv6-family"})
    )


def index_blocks(lines: tuple[SourceLine, ...], initial_view: str | None = None) -> list[ConfigBlock]:
    active = ConfigBlock(initial_view, SourceRange(1)) if initial_view else None
    blocks = [active] if active else []
    views: list[tuple[int, str]] = []
    previous: tuple[int, str] | None = None
    for line in lines:
        checkpoint()
        text, lower = line.text, line.text.lower()
        indent = len(line.raw.expandtabs()) - len(line.raw.expandtabs().lstrip())
        if not text:
            continue
        if lower in {"return", "system-view"}:
            active, previous = None, None
            views.clear()
            continue
        if lower == "quit":
            if views:
                views.pop()
            else:
                active = None
            previous = None
            continue
        if text == "#":
            if indent == 0:
                active = None
            views = [(level, view) for level, view in views if level < indent]
            previous = None
            continue
        if indent == 0:
            active = ConfigBlock(text, SourceRange(line.number))
            blocks.append(active)
            views.clear()
            previous = None
            continue
        if active is None:
            active = ConfigBlock("Unknown context", SourceRange(line.number), context_known=False)
            blocks.append(active)
        while views and indent <= views[-1][0]:
            views.pop()
        if previous and indent > previous[0] and previous not in views:
            views.append(previous)
        active.commands.append(
            ConfigCommand(text, SourceRange(line.number), tuple(view for _, view in views))
        )
        previous = (indent, text)
        if _nested(active.header, text):
            views.append((indent, text))
    return blocks


def _key(header: str, text: str, views: tuple[str, ...]) -> tuple[str, ...] | None:
    """Keys identify only supported, replaceable clauses (never arbitrary prefixes)."""
    t = text.split()
    w = [s.lower() for s in t]
    root = header.lower()
    if not t:
        return None
    if root.startswith("interface ") and not views:
        if w[:2] == ["ip", "address"] and len(t) in {3, 4} and "sub" not in w:
            return ("ip", "address", "primary")
        for prefix in (
            "description",
            "port link-type",
            "eth-trunk",
            "ospf enable",
            "isis enable",
            "stp edged-port",
        ):
            if text.lower().startswith(prefix + " ") or text.lower() == prefix:
                return tuple(prefix.split())
        if w[:1] == ["shutdown"]:
            return ("shutdown",)
        if w[:1] == ["traffic-policy"] and len(t) >= 3:
            return ("traffic-policy", w[2])
        if w[:1] == ["traffic-filter"] and "acl" in w:
            return ("traffic-filter", "ipv6" if "ipv6" in w[: w.index("acl")] else "ipv4", w[1])
    if root.startswith("bgp "):
        if w[:1] == ["network"]:
            try:
                address, mask, _ = bgp_network(
                    tuple(t[1:]), 6 if views and views[-1].lower().startswith("ipv6") else 4
                )
                return ("network", address, mask)
            except ValueError:
                return None
        if w[:1] == ["group"] and len(t) >= 2:
            return ("group", t[1])
        if w[:1] == ["router-id"]:
            return ("router-id",)
        if w[:1] == ["peer"] and len(t) >= 3:
            if w[2] in {"as-number", "group", "enable", "description"}:
                return ("peer", t[1], w[2])
            if w[2] == "route-policy" and len(t) >= 5 and w[4] in {"import", "export"}:
                return ("peer", t[1], "route-policy", w[4])
    if root.startswith(("route-policy ", "traffic classifier ")) and w[:1] == ["if-match"]:
        if root.startswith("traffic classifier ") and (w[1:2] == ["acl"] or w[1:3] == ["ipv6", "acl"]):
            offset = 3 if w[1] == "ipv6" else 2
            identity = parse_acl_identity(tuple(t[offset:]), family="ipv6" if offset == 3 else "ipv4")
            return ("if-match", identity.key) if identity is not None else None
        if len(w) >= 2 and w[1] in {"ip-prefix", "acl"}:
            return ("if-match", w[1])
        if len(w) >= 3 and w[1:3] == ["ipv6", "acl"]:
            return ("if-match", "ipv6", "acl")
        if len(w) >= 3 and w[1] == "ipv6" and w[2] in {"address", "next-hop", "route-source"}:
            return ("if-match", "ipv6", w[2])
    if root.startswith("acl ") and w[:1] == ["rule"] and len(t) >= 2 and t[1].isdigit():
        # Repeating a rule ID can edit individual fields on VRP. Only exact duplicate
        # commands are redundant; differing edits are handled conservatively by the parser.
        return ("rule", *t[1:])
    if root.startswith("traffic policy ") and w[:1] == ["classifier"] and len(t) >= 2:
        return ("classifier", t[1])
    if root.startswith("bridge-domain ") and w[:2] == ["vxlan", "vni"]:
        return ("vxlan", "vni")
    if root.startswith("isis") and w[:1] == ["network-entity"]:
        return ("network-entity", *t[1:])
    if root == "aaa" and w[:1] == ["local-user"] and len(t) >= 3 and w[2] in {"password", "service-type"}:
        return ("local-user", t[1], w[2])
    if root.startswith("user-interface ") and w[0] in {"protocol", "authentication-mode"}:
        return tuple(w[:2]) if w[0] == "protocol" else (w[0],)
    return None


def _remove_match(header: str, command: ConfigCommand, undo: ConfigCommand) -> bool:
    if header.lower().startswith("bgp "):
        deletion = undo.text[5:].split()
        original = command.text.split()
        if (
            len(deletion) == 2
            and deletion[0].lower() == "peer"
            and original[:2] == deletion
            and (
                command.views == undo.views
                or (not undo.views and command.views and "vpn-instance" not in command.views[0])
            )
        ):
            return True
    if command.views != undo.views:
        # Removing an area/address-family removes only its own descendants.
        target = undo.text[5:]
        return command.views[: len(undo.views) + 1] == (*undo.views, target)
    text = undo.text[5:]
    a, b = command.text.split(), text.split()
    if b and b[0].lower() == "network" and header.lower().startswith("bgp "):
        key = _key(header, text, undo.views)
        return key is not None and _key(header, command.text, command.views) == key
    if b[:1] == ["traffic-policy"] and len(b) == 2 and b[1] in {"inbound", "outbound"}:
        return a[:1] == ["traffic-policy"] and len(a) >= 3 and a[2] == b[1]
    if a[:2] in (["ip", "address"], ["ipv6", "address"]) and b[:2] == a[:2] and len(b) >= 3:
        try:
            old = ipaddress.ip_interface(a[2] if "/" in a[2] else f"{a[2]}/{a[3]}")
            target_address = ipaddress.ip_interface(b[2] if "/" in b[2] else f"{b[2]}/{b[3]}")
            return old == target_address and a[4:] == b[4:]
        except (ValueError, IndexError):
            return a[: len(b)] == b
    return a[: len(b)] == b


def _undo_supported(header: str, text: str) -> bool:
    root = header.lower()
    if root.startswith("interface "):
        return bool(
            re.fullmatch(
                r"(?:ip address(?: \S+(?: \S+)?(?: sub)?)?|ipv6 address(?: .+)?|eth-trunk(?: \d+)?|"
                r"ospf enable(?: \d+)?(?: area \S+)?|isis enable(?: \d+)?|"
                r"traffic-policy(?: \S+)? (?:inbound|outbound)|"
                r"traffic-filter (?:inbound|outbound)(?: ipv6)? acl .+|description|"
                r"stp edged-port(?: enable|disable)?|vni \d+(?: .*)?)",
                text,
                re.I,
            )
        )
    if root.startswith("bgp "):
        return bool(
            re.fullmatch(
                r"(?:peer \S+(?: (?:as-number(?: \S+)?|group(?: \S+)?|description|"
                r"route-policy \S+ (?:import|export)))?|group \S+|router-id(?: \S+)?|"
                r"network .+|(?:ipv4|ipv6|l2vpn)-family .+)",
                text,
                re.I,
            )
        )
    if root.startswith(("ospf ", "ospfv3 ")):
        return text.lower().startswith(("area ", "network "))
    if root.startswith(("route-policy ", "traffic classifier ")):
        return bool(
            re.fullmatch(
                r"if-match (?:ip-prefix(?: \S+)?|acl(?: .+)?|ipv6 (?:acl(?: .+)?|"
                r"(?:address|next-hop|route-source)(?: (?:acl|prefix-list) .+)?))",
                text,
                re.I,
            )
        )
    if root.startswith("traffic policy "):
        return bool(re.fullmatch(r"classifier \S+(?: behavior \S+)?", text, re.I))
    if root.startswith("acl "):
        return bool(re.fullmatch(r"rule \d+", text, re.I))
    if root.startswith("isis"):
        return text.lower().startswith("network-entity")
    if root.startswith("bridge-domain "):
        return bool(re.fullmatch(r"vxlan vni(?: \d+)?", text, re.I))
    if root == "aaa":
        return bool(re.fullmatch(r"local-user \S+(?: (?:password|service-type)(?: .*)?)?", text, re.I))
    return False


def _route_selector(text: str) -> tuple[tuple[str, str | None, str], tuple[str, ...]] | None:
    tokens = text.split()
    if len(tokens) < 4 or tokens[0].lower() not in {"ip", "ipv6"} or tokens[1].lower() != "route-static":
        return None
    rest = tokens[2:]
    vpn = None
    if rest[0].lower() == "vpn-instance":
        if len(rest) < 4:
            return None
        vpn, rest = rest[1], rest[2:]
    try:
        size = 1 if "/" in rest[0] else 2
        network = ipaddress.ip_network(rest[0] if size == 1 else f"{rest[0]}/{rest[1]}", strict=True)
        if network.version != (4 if tokens[0].lower() == "ip" else 6):
            return None
    except (ValueError, IndexError):
        return None
    tail = rest[size:]
    if "description" in tail:
        tail = tail[: tail.index("description")]
    if len(tail) >= 2:
        joined = interface_name(" ".join(tail[:2]))
        if " " not in joined:
            tail = [joined, *tail[2:]]
    if tail:
        with suppress(ValueError):
            tail[0] = str(ipaddress.ip_address(tail[0]))
    return (tokens[0].lower(), vpn, str(network)), tuple(tail)


def effective_blocks(blocks: list[ConfigBlock]) -> tuple[list[ConfigBlock], list[SourceRange]]:
    """Merge re-entered views and remove known stale commands, preserving source IDs."""
    merged: list[ConfigBlock] = []
    by_key: dict[str, ConfigBlock] = {}
    ignored: list[SourceRange] = []
    global_singletons: dict[str, ConfigBlock] = {}
    acl_aliases: dict[str, str] = {}
    conflicts: set[str] = set()
    for block in blocks:
        checkpoint()
        tokens = block.header.split()
        words = [t.lower() for t in tokens]
        identity = parse_acl_identity(tuple(tokens[1:])) if words[:1] == ["acl"] else None
        if identity is not None and identity.kind == "name" and "number" in words:
            index = words.index("number")
            number = parse_acl_identity(tuple(tokens[index:]), family=identity.family)
            if number is not None:
                key, value = "acl " + identity.key, "acl " + number.key
                if key in acl_aliases and acl_aliases[key] != value:
                    conflicts.add(key)
                acl_aliases[key] = value
    for key in conflicts:
        acl_aliases.pop(key, None)
    reverse: dict[str, list[str]] = {}
    for key, value in acl_aliases.items():
        reverse.setdefault(value, []).append(key)
    for names in reverse.values():
        if len(names) > 1:
            for key in names:
                acl_aliases.pop(key, None)

    def block_key(header: str) -> str | None:
        key = _block_key(header)
        return acl_aliases.get(key, key) if key is not None else None

    for block in blocks:
        checkpoint()
        lower = block.header.lower()
        if lower.startswith("undo "):
            target = block.header[5:]
            selector = _route_selector(target)
            if selector is not None and (
                not selector[1]
                or not route_arguments(tuple(target.split()[2:]), 4 if selector[0][0] == "ip" else 6)[4]
            ):
                for old in merged[:]:
                    checkpoint()
                    prior = _route_selector(old.header)
                    if (
                        prior is not None
                        and prior[0] == selector[0]
                        and prior[1][: len(selector[1])] == selector[1]
                    ):
                        ignored.append(old.source)
                        merged.remove(old)
                ignored.append(block.source)
                continue
            delete_key = block_key(target)
            prefix = target + " "
            deletable = bool(
                re.fullmatch(
                    r"(?:interface .+|bgp \d+(?:\.\d+)?|ospf(?: \d+)?|isis(?: \d+)?|"
                    r"ip vpn-instance \S+|traffic (?:classifier|behavior|policy) \S+|"
                    r"route-policy \S+(?: (?:permit|deny) node \d+)?|bridge-domain \d+|vni \d+|"
                    r"acl .+|ip (?:ip-prefix|ipv6-prefix) \S+(?: index \d+)?)",
                    target,
                    re.I,
                )
            )
            if deletable:
                for old in merged[:]:
                    checkpoint()
                    prior_key = block_key(old.header)
                    if (
                        (delete_key is not None and prior_key == delete_key)
                        or old.header == target
                        or old.header.startswith(prefix)
                    ):
                        ignored.extend([old.source, *(c.source for c in old.commands)])
                        merged.remove(old)
                        if prior_key is not None:
                            by_key.pop(prior_key, None)
                ignored.append(block.source)
                continue
        # System-view flags and a small set of singleton management settings.
        base = lower.removeprefix("undo ")
        global_key = None
        if re.fullmatch(
            r"(?:telnet(?: (?:ipv4|ipv6))?|ftp|stelnet(?: (?:ipv4|ipv6))?|sftp|scp) "
            r"server (?:enable|disable)",
            base,
        ):
            global_key = " ".join(base.split()[:-1])
        elif base.startswith("ssh server-source"):
            global_key = "ssh server-source"
        elif base in {
            "stp bpdu-protection",
            "stp edged-port default",
            "ntp-service authentication enable",
            "ntp authentication enable",
        }:
            global_key = base
        if global_key is not None:
            if global_key in global_singletons:
                old = global_singletons[global_key]
                merged.remove(old)
                ignored.append(old.source)
            global_singletons[global_key] = block
        current_key = block_key(block.header)
        if current_key is not None and current_key in by_key:
            old = by_key[current_key]
            # Header options (e.g. OSPF VPN) belong to the last explicit entry.
            preserve_vpn = (
                old.header.lower().startswith(("ospf ", "isis "))
                and "vpn-instance" in old.header.lower().split()
                and len(block.header.split()) == 2
            )
            if not preserve_vpn and (
                not old.header.lower().startswith("acl ")
                or ("name" in block.header.lower().split() and "number" in block.header.lower().split())
            ):
                old.header = block.header
            old.commands.extend(block.commands)
            ignored.append(block.source)
        else:
            merged.append(block)
            if current_key is not None:
                by_key[current_key] = block
    for block in merged:
        checkpoint()
        active: list[ConfigCommand | None] = []
        positions: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
        for command in block.commands:
            checkpoint()
            lower = command.text.lower()
            if (
                lower.startswith("undo network")
                and block.header.lower().startswith("bgp ")
                and _key(block.header, command.text[5:], command.views) is None
            ):
                active.append(command)
                continue
            if lower.startswith("undo ") and _undo_supported(block.header, command.text[5:]):
                for index, old_command in enumerate(active):
                    checkpoint()
                    if old_command is not None and _remove_match(block.header, old_command, command):
                        ignored.append(old_command.source)
                        active[index] = None
                ignored.append(command.source)
                continue
            # Binding changes remove L3 addresses/protocols configured earlier in this view.
            if block.header.lower().startswith("interface ") and lower.startswith(
                ("ip binding vpn-instance ", "undo ip binding vpn-instance")
            ):
                for index, old_command in enumerate(active):
                    checkpoint()
                    if old_command is not None and old_command.text.lower().startswith(
                        (
                            "ip address ",
                            "ipv6 address ",
                            "ospf enable ",
                            "isis enable ",
                            "ip binding vpn-instance ",
                        )
                    ):
                        ignored.append(old_command.source)
                        active[index] = None
            command_key = _key(block.header, command.text, command.views)
            if command_key is not None:
                marker = (command.views, command_key)
                position = positions.get(marker)
                if position is not None and active[position] is not None:
                    old_command = active[position]
                    assert old_command is not None
                    ignored.append(old_command.source)
                    active[position] = None
                positions[marker] = len(active)
            active.append(command)
        block.commands = [replace(c) for c in active if c is not None]
    return merged, ignored
