"""Offline, parameter-aware CLI completion, independent of diagnostic vendor selection.

Templates contain literal keywords and <argument> slots. Arguments are never invented,
read from another device, or expanded into user configuration by this module.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

VENDORS = ("h3c", "huawei")
LABELS = {"h3c": "H3C", "huawei": "Huawei"}
_INTERFACE_TYPES = {
    "h3c": (
        "GigabitEthernet",
        "Ten-GigabitEthernet",
        "FortyGigE",
        "HundredGigE",
        "FourHundredGigE",
        "M-GigabitEthernet",
        "Bridge-Aggregation",
        "Route-Aggregation",
        "LoopBack",
        "Vlan-interface",
        "Tunnel",
        "NULL",
    ),
    "huawei": (
        "GigabitEthernet",
        "XGigabitEthernet",
        "GE",
        "10GE",
        "25GE",
        "40GE",
        "100GE",
        "400GE",
        "MEth",
        "Eth-Trunk",
        "Vlanif",
        "LoopBack",
        "Tunnel",
        "Nve",
        "Vbdif",
        "NULL",
    ),
}


@lru_cache(maxsize=8)
def _declared(source: str) -> dict[str, tuple[str, ...]]:
    """Reuse only named CLI objects, never passwords, users, addresses, or secrets."""
    declarations = {
        "vpn": r"^[ \t]*ip vpn-instance (\S+)",
        "route-policy": r"^[ \t]*route-policy (\S+)",
        "classifier": r"^[ \t]*traffic classifier (\S+)",
        "behavior": r"^[ \t]*traffic behavior (\S+)",
        "policy": r"^[ \t]*(?:traffic|qos) policy (\S+)",
        "interface": r"^[ \t]*interface (\S+)",
    }
    return {
        key: tuple(sorted(set(re.findall(pattern, source, re.I | re.M))))
        for key, pattern in declarations.items()
    }


def _parameter_values(token: str, vendor: str, source: str, syntax: str) -> tuple[str, ...]:
    name = token.strip("<>").lower()
    if name in {"interface-type", "if-type"}:
        return _INTERFACE_TYPES[vendor]
    object_parameters = {
        "vpn-instance": "vpn",
        "vpn-instance-name": "vpn",
        "route-policy-name": "route-policy",
        "classifier-name": "classifier",
        "traffic-classifier-name": "classifier",
        "behavior-name": "behavior",
        "traffic-behavior-name": "behavior",
        "qos-policy-name": "policy",
        "traffic-policy-name": "policy",
        "interface-name": "interface",
    }
    key = object_parameters.get(name)
    if key:
        return _declared(source)[key]
    if name == "policy-name" and re.match(
        r"^(?:undo |display )?(?:qos\b|traffic policy\b|traffic-policy\b)", syntax
    ):
        return _declared(source)["policy"]
    return ()


@dataclass(frozen=True, slots=True)
class Command:
    vendor: str
    syntax: str
    tokens: tuple[str, ...]
    source: str
    views: tuple[str, ...]


@lru_cache(maxsize=1)
def commands() -> tuple[Command, ...]:
    result = []
    for vendor in VENDORS:
        path = Path(__file__).with_name("data") / f"{vendor}.json"
        data = json.loads(path.read_text("utf-8"))
        if data["vendor"] != vendor or data["schema"] != 1:
            raise ValueError("Invalid completion catalog")
        for row in data["commands"]:
            syntax = row["syntax"]
            result.append(
                Command(
                    vendor,
                    syntax,
                    tuple(syntax.split()),
                    row["source"],
                    tuple(_view_label(value) for value in row["views"]),
                )
            )
    return tuple(result)


@lru_cache(maxsize=1)
def _index() -> dict[str, tuple[Command, ...]]:
    grouped: dict[str, list[Command]] = {}
    for entry in commands():
        grouped.setdefault(entry.tokens[0].lower(), []).append(entry)
    return {root: tuple(entries) for root, entries in grouped.items()}


@lru_cache(maxsize=256)
def _entries(prefix: str) -> tuple[Command, ...]:
    return tuple(entry for root, entries in _index().items() if root.startswith(prefix) for entry in entries)


def _view_label(value: str) -> str:
    value = value.lower()
    if "all view" in value or "any view" in value:
        return "any"
    if any(term in value for term in ("user interface", "vty", "console", "line view")):
        return "line"
    if "route-policy" in value or "route policy" in value:
        return "route-policy"
    for text, label in (
        ("interface", "interface"),
        ("bgp", "bgp"),
        ("ospf", "ospf"),
        ("is-is", "isis"),
        ("acl", "acl"),
        ("vlan", "vlan"),
        ("line", "line"),
        ("classifier", "classifier"),
        ("behavior", "behavior"),
        ("policy", "policy"),
        ("vpn", "vpn"),
        ("mst", "stp"),
        ("aaa", "aaa"),
        ("system", "system"),
        ("user view", "user"),
    ):
        if text in value:
            return label
    return value


@dataclass(slots=True)
class _Node:
    edges: list[tuple[str, int]]


@lru_cache(maxsize=32768)
def _grammar(syntax: str) -> tuple[_Node, ...]:
    """Compile bracket/choice/repetition notation into a bounded epsilon NFA."""
    tokens = re.findall(r"<[^>]+>|[\[\]{}|*]|[^\s\[\]{}|*]+", syntax)
    nodes = [_Node([])]
    index = 0

    def node() -> int:
        nodes.append(_Node([]))
        return len(nodes) - 1

    def expression(start: int, stop: str = "") -> int:
        nonlocal index
        end = node()
        current = start
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token == stop:
                break
            if token == "|":
                nodes[current].edges.append(("", end))
                current = start
            elif token in ("[", "{"):
                group_start = node()
                nodes[current].edges.append(("", group_start))
                group_end = expression(group_start, "]" if token == "[" else "}")
                next_node = node()
                nodes[group_end].edges.append(("", next_node))
                if token == "[":
                    nodes[current].edges.append(("", next_node))
                if index < len(tokens) and tokens[index] == "*":
                    nodes[group_end].edges.append(("", group_start))
                    index += 1
                current = next_node
            elif token not in ("]", "}", "*", "&"):
                next_node = node()
                nodes[current].edges.append((token, next_node))
                if index < len(tokens) and tokens[index] == "*":
                    nodes[next_node].edges.append((token, next_node))
                    index += 1
                current = next_node
        nodes[current].edges.append(("", end))
        return end

    expression(0)
    return tuple(nodes)


def _next_tokens(entry: Command, words: list[str]) -> set[str]:
    nodes = _grammar(entry.syntax)

    def closure(states: set[int]) -> set[int]:
        pending = list(states)
        while pending:
            for token, target in nodes[pending.pop()].edges:
                if not token and target not in states:
                    states.add(target)
                    pending.append(target)
        return states

    states = closure({0})
    for word in words:
        edges = [edge for state in states for edge in nodes[state].edges if edge[0]]
        # An exact keyword wins over wildcard parameters at the same grammar point.
        exact = [(token, target) for token, target in edges if token.lower() == word.lower()]
        matches = exact or [
            (token, target)
            for token, target in edges
            if token.startswith("<") or token.lower().startswith(word.lower())
        ]
        states = closure({target for _, target in matches})
        if not states:
            return set()
    return {token for state in states for token, _ in nodes[state].edges if token}


# Distinctive syntax, not generic 'system', 'vlan', 'sysname', or interface names.
# Repeated lines contribute once per feature, so a large shared stanza cannot dominate.
_FEATURES = {
    "h3c": (
        (r"^(?:H3C Comware|HP Comware|HPE Comware|Comware Software).*", 6),
        (r"^version\s+7\.1\.\d+", 4),
        (r"^irf(?:-port)?\s+", 4),
        (r"^interface\s+(?:Bridge-Aggregation|Route-Aggregation|Routed-Aggregation)\S*", 4),
        (r"^(?:undo\s+)?port\s+access\s+vlan\s+", 3),
        (r"^(?:undo\s+)?stp\s+global\s+enable\b", 3),
        (r"^(?:undo\s+)?lldp\s+global\s+enable\b", 3),
        (r"^line\s+(?:class\s+)?(?:vty|console|aux)\b", 3),
        (r"^(?:undo\s+)?(?:radius|hwtacacs)\s+scheme\s+", 2),
        (r"^local-user\s+\S+\s+class\s+(?:manage|network)\b", 3),
        (r"^(?:undo\s+)?qos\s+(?:policy|apply\s+policy)\s+", 2),
    ),
    "huawei": (
        (r"^(?:Huawei Versatile Routing Platform|VRP \(R\)|Huawei VRP).*", 6),
        (r"^!Software Version\s+V[268]\d{2}R\d+", 4),
        (r"^interface\s+(?:Eth-Trunk|Vbdif|Nve)\S*", 4),
        (r"^(?:undo\s+)?eth-trunk\s+\d+\b", 4),
        (r"^(?:undo\s+)?port\s+default\s+vlan\s+", 3),
        (r"^(?:undo\s+)?stelnet\s+server\s+enable\b", 3),
        (r"^(?:undo\s+)?stack\s+(?:member|slot|port)\b", 3),
        (r"^(?:undo\s+)?traffic-policy\s+\S+\s+(?:inbound|outbound)\b", 3),
        (r"^(?:undo\s+)?hwtacacs-server\s+template\b", 3),
        (r"^(?:undo\s+)?authentication-profile\s+name\s+", 3),
        (r"^(?:undo\s+)?commit\s*$", 2),
    ),
}
_PATTERNS = {
    vendor: tuple((re.compile(r"^[ \t]*" + p[1:], re.I | re.M), w) for p, w in rows)
    for vendor, rows in _FEATURES.items()
}


@lru_cache(maxsize=8)
def detect_vendors(source: str) -> tuple[str, ...]:
    """Select every supported vendor with distinctive evidence; fall back broadly."""
    found = []
    for vendor, patterns in _PATTERNS.items():
        weights = [weight for pattern, weight in patterns if pattern.search(source)]
        if sum(weights) >= 3:
            found.append(vendor)
    return tuple(found) or VENDORS


def _python_offset(text: str, utf16_offset: int) -> int:
    """QML cursor positions are UTF-16 code units, Python indexes Unicode scalars."""
    remaining = max(0, utf16_offset)
    for index, char in enumerate(text):
        remaining -= 2 if ord(char) > 0xFFFF else 1
        if remaining < 0:
            return index
        if remaining == 0:
            return index + 1
    return len(text)


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _view(source: str, line_start: int) -> str:
    lines = source[max(0, line_start - 20_000) : line_start].splitlines()
    for raw in reversed(lines):
        body = raw.strip().lower()
        if body in {"#", "return", "system-view"}:
            return "system"
        if body in {"quit", "exit"}:
            return "any"
        for prefix, view in (
            ("interface ", "interface"),
            ("bgp ", "bgp"),
            ("ospf ", "ospf"),
            ("ospfv3 ", "ospf"),
            ("isis ", "isis"),
            ("acl ", "acl"),
            ("vlan ", "vlan"),
            ("user-interface ", "line"),
            ("line ", "line"),
            ("traffic classifier ", "classifier"),
            ("traffic behavior ", "behavior"),
            ("traffic policy ", "policy"),
            ("qos policy ", "policy"),
            ("route-policy ", "route-policy"),
            ("ip vpn-instance ", "vpn"),
            ("stp region-configuration", "stp"),
            ("aaa", "aaa"),
        ):
            if body.startswith(prefix):
                return view
    return "system"


def complete(source: str, cursor: int, selected: tuple[str, ...] = ()) -> dict[str, object]:
    """Return replacements in QML coordinates, with common-prefix shell behavior."""
    position = _python_offset(source, cursor)
    line_start = source.rfind("\n", 0, position) + 1
    line_end = source.find("\n", position)
    line_end = len(source) if line_end < 0 else line_end
    before = source[line_start:position]
    empty = {"items": [], "arguments": [], "start": cursor, "end": cursor, "insert": "", "vendors": []}
    if before.lstrip().startswith(("#", "!", "//", ";")) or '"' in before or "'" in before:
        return empty
    words = before.split()
    prefix = "" if not before or before[-1].isspace() else words.pop()
    # Replace the whole current token even when completing from the middle of it.
    start = position - len(prefix)
    end = position
    while end < line_end and not source[end].isspace():
        end += 1
    vendors = tuple(v for v in selected if v in VENDORS)
    if not vendors:
        context = source[:line_start] + "\n" + source[line_end:]
        vendors = detect_vendors(context)
    view = _view(source, line_start)
    matches: dict[str, dict[str, object]] = {}
    arguments: set[str] = set()
    for entry in _entries((words[0] if words else prefix).lower()):
        if entry.vendor not in vendors:
            continue
        head = []
        for value in entry.tokens:
            if value.startswith(("<", "[", "{")) or value in {"|", "*"}:
                break
            head.append(value)
        if any(
            not expected.lower().startswith(actual.lower())
            for actual, expected in zip(words, head, strict=False)
        ):
            continue
        relevance = 0 if view in entry.views else 1 if "any" in entry.views or view == "any" else 2
        if entry.tokens[0] in {"system-view", "quit", "return", "undo", "display"}:
            relevance = min(relevance, 1)
        next_tokens = _next_tokens(entry, words) if words else {entry.tokens[0]}
        values: set[str] = set()
        for token in next_tokens:
            if token.startswith("<"):
                arguments.add(token)
                values.update(_parameter_values(token, entry.vendor, source, entry.syntax))
            else:
                values.add(token)
        for token in values:
            if not token.lower().startswith(prefix.lower()):
                continue
            item = matches.setdefault(
                token,
                {
                    "text": token,
                    "vendors": [],
                    "syntax": entry.syntax,
                    "source": entry.source,
                    "rank": relevance,
                },
            )
            item_vendors = item["vendors"]
            assert isinstance(item_vendors, list)
            if LABELS[entry.vendor] not in item_vendors:
                item_vendors.append(LABELS[entry.vendor])
            if relevance < int(str(item["rank"])):
                item.update(syntax=entry.syntax, source=entry.source, rank=relevance)
    items = sorted(matches.values(), key=lambda item: (int(str(item["rank"])), str(item["text"]).lower()))
    texts = [str(item["text"]) for item in items]
    shared = os.path.commonprefix(texts) if texts else ""
    insertion = (
        (texts[0] + ("" if end < len(source) and source[end].isspace() else " "))
        if len(texts) == 1 and (prefix or not arguments)
        else (shared if len(texts) > 1 and (prefix or not arguments) and len(shared) > len(prefix) else "")
    )
    return {
        "items": items,
        "arguments": sorted(arguments),
        "start": _utf16_length(source[:start]),
        "end": _utf16_length(source[:end]),
        "insert": insertion,
        "vendors": [LABELS[v] for v in vendors],
    }
