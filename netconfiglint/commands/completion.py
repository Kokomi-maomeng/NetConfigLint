"""Offline, parameter-aware CLI completion, independent of diagnostic vendor selection.

Templates contain literal keywords and <argument> slots. Arguments are never invented,
read from another device, or expanded into user configuration by this module.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from netconfiglint.commands.objects import (
    INTERFACE_TYPES,
    declared,
    parameter_kind,
    parameter_status,
    parameter_values,
)
from netconfiglint.core.lexer import normalize_cli_line

VENDORS = ("h3c", "huawei")
LABELS = {"h3c": "H3C", "huawei": "Huawei"}
_INTERFACE_TYPES = INTERFACE_TYPES


class CompletionCancelled(Exception):
    """A superseded interactive request stopped before producing any result."""


def _unique_extend(
    row: dict[str, object], field: str, values: Iterable[object], seen: dict[str, set[str]]
) -> None:
    """Keep source order without quadratic comparisons in large command groups."""
    target = row[field]
    assert isinstance(target, list)
    known = seen.setdefault(field, set())
    for value in values:
        identity = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
        if identity not in known:
            known.add(identity)
            target.append(value)


@lru_cache(maxsize=8)
def _declared(source: str) -> dict[str, tuple[str, ...]]:
    """Reuse only named CLI objects, never passwords, users, addresses, or secrets."""
    return declared(source, "h3c")


def _parameter_values(
    token: str, vendor: str, source: str, syntax: str, words: list[str] | None = None
) -> tuple[str, ...]:
    return parameter_values(token, vendor, source, syntax, words or [])


@dataclass(frozen=True, slots=True)
class Command:
    vendor: str
    syntax: str
    tokens: tuple[str, ...]
    source: str
    views: tuple[str, ...]
    sources: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    annotations: tuple[str, ...] = ()
    provenance: tuple[dict[str, object], ...] = ()
    legacy: bool = False


@lru_cache(maxsize=1)
def commands() -> tuple[Command, ...]:
    result = []
    for vendor in VENDORS:
        path = Path(__file__).with_name("data") / f"{vendor}.json"
        data = json.loads(path.read_text("utf-8"))
        if data["vendor"] != vendor or data["schema"] not in {1, 2}:
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
                    tuple(dict.fromkeys(p["url"] for p in row.get("sources", []))) or (row["source"],),
                    tuple(dict.fromkeys(p.get("manual", "") for p in row.get("sources", []))),
                    tuple(dict.fromkeys(a for p in row.get("sources", []) for a in p.get("annotations", []))),
                    tuple(row.get("sources", [])),
                    bool(row.get("legacy", False)),
                )
            )
    return tuple(result)


@lru_cache(maxsize=1)
def _index() -> dict[str, tuple[Command, ...]]:
    grouped: dict[str, list[Command]] = {}
    for entry in commands():
        for root in _initial_roots(entry.syntax):
            if not root.startswith("<"):
                grouped.setdefault(root.lower(), []).append(entry)
    return {root: tuple(entries) for root, entries in grouped.items()}


def _initial_roots(syntax: str) -> set[str]:
    """Catalog imports start with literals; only true top-level alternatives add roots."""
    roots: set[str] = set()
    depth = 0
    take = True
    for token in re.findall(r"<[^>]+>|[\[\]{}|*]|[^\s\[\]{}|*]+", syntax):
        if take and token not in {"[", "{"}:
            roots.add(token)
            take = False
        if token in {"[", "{"}:
            depth += 1
        elif token in {"]", "}"}:
            depth -= 1
        elif token == "|" and depth == 0:
            take = True
    return roots


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


@lru_cache(maxsize=65536)
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


def _match_tokens(entry: Command, words: list[str]) -> tuple[set[str], tuple[int, ...]]:
    nodes = _grammar(entry.syntax)

    def closure(states: dict[int, tuple[int, ...]]) -> dict[int, tuple[int, ...]]:
        pending = list(states)
        while pending:
            state = pending.pop()
            for token, target in nodes[state].edges:
                if not token and (target not in states or states[target] < states[state]):
                    states[target] = states[state]
                    pending.append(target)
        return states

    states = closure({0: ()})
    for word in words:
        matched: dict[int, tuple[int, ...]] = {}
        for state, previous in states.items():
            for token, target in nodes[state].edges:
                if not token:
                    continue
                argument = token.startswith("<")
                if argument:
                    kind = parameter_kind(token, entry.syntax)
                    if kind == "interface-type" and not any(
                        value.lower().startswith(word.lower()) for value in _INTERFACE_TYPES[entry.vendor]
                    ):
                        continue
                    # A documented numeric slot cannot swallow a keyword from another branch.
                    if re.search(
                        r"(?:number|(?:^|-)id|(?:^|-)value|length|count|interval)$", token[1:-1], re.I
                    ) and not re.fullmatch(r"\d+(?:[/.:,-]\d+)*", word):
                        continue
                    quality = 0
                elif token.lower() == word.lower():
                    quality = 2
                elif token.lower().startswith(word.lower()):
                    # An abbreviation and a valid argument remain ambiguous.
                    # Treating every prefix as stronger would misread ACL "ip"
                    # as an abbreviation of "ipv4" and swallow time-range.
                    quality = 0
                else:
                    continue
                score = (*previous, quality)
                if target not in matched or matched[target] < score:
                    matched[target] = score
        states = closure(matched)
        if not states:
            return set(), ()
    score = max(states.values())
    return {
        token for state, value in states.items() if value == score for token, _ in nodes[state].edges if token
    }, score


def _next_tokens(entry: Command, words: list[str]) -> set[str]:
    return _match_tokens(entry, words)[0]


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
        body = normalize_cli_line(raw)[0].strip().lower()
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


def _legacy_requested(entry: Command, words: list[str], prefix: str) -> bool:
    """A shared modern root alone does not opt into a historical feature chapter."""
    requested = [*words, *([prefix] if prefix else [])]
    generic = {"undo", "display", "reset", "interface", "ip", "ipv6"}
    for index, token in enumerate(entry.tokens):
        if token.startswith(("<", "[", "{")) or token in {"|", "*"}:
            break
        if index >= len(requested):
            break
        if token.lower() not in generic and len(requested[index]) >= min(3, len(token)):
            return token.lower().startswith(requested[index].lower())
    return False


def _syntax_details(entry: Command) -> list[dict[str, object]]:
    return [
        {
            "syntax": entry.syntax,
            "sources": [origin["url"]],
            "views": origin.get("views", []),
            "scopes": [origin.get("manual", "")],
            "annotations": origin.get("annotations", []),
        }
        for origin in entry.provenance
    ] or [
        {
            "syntax": entry.syntax,
            "sources": [entry.source],
            "views": list(entry.views),
            "scopes": list(entry.scopes),
            "annotations": list(entry.annotations),
        }
    ]


def interactive_requires_async(source: str, cursor: int) -> bool:
    """Keep catalog loading and broad/large-document work off the GUI thread."""
    if len(source) > 10_000 or not _index.cache_info().currsize:
        return True
    position = _python_offset(source, cursor)
    before, _ = normalize_cli_line(source[source.rfind("\n", 0, position) + 1 : position])
    words = before.split()
    return len(_entries(words[0].lower() if words else "")) > 256


def complete(
    source: str,
    cursor: int,
    selected: tuple[str, ...] = (),
    manuals: tuple[str, ...] = (),
    *,
    include_details: bool = True,
    detail_key: str = "",
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, object]:
    """Return replacements in QML coordinates, with common-prefix shell behavior.

    Interactive callers omit bulk provenance and load a selected ``detailKey``
    separately. The default retains the full metadata API for offline callers.
    """

    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise CompletionCancelled

    check_cancelled()
    position = _python_offset(source, cursor)
    line_start = source.rfind("\n", 0, position) + 1
    line_end = source.find("\n", position)
    line_end = len(source) if line_end < 0 else line_end
    before, _ = normalize_cli_line(source[line_start:position])
    empty = {
        "items": [],
        "arguments": [],
        "argumentDetails": [],
        "start": cursor,
        "end": cursor,
        "insert": "",
        "vendors": [],
        "scopeNote": "",
    }
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
    context = source[:line_start] + "\n" + source[line_end:]
    if not vendors:
        vendors = detect_vendors(context)
    view = _view(source, line_start)
    matches: dict[tuple[str, str], dict[str, object]] = {}
    item_seen: dict[tuple[str, str], dict[str, set[str]]] = {}
    arguments: set[str] = set()
    argument_details: dict[tuple[str, str], dict[str, object]] = {}
    argument_seen: dict[tuple[str, str], dict[str, set[str]]] = {}
    paths: list[tuple[Command, set[str], tuple[int, ...]]] = []
    for index, entry in enumerate(_entries((words[0] if words else prefix).lower())):
        if index % 128 == 0:
            check_cancelled()
        if entry.vendor not in vendors:
            continue
        if manuals and not any(scope in manuals for scope in entry.scopes):
            continue
        # Historical chapters require either a selected reference or an explicit
        # feature prefix. They do not inflate modern empty/undo/display menus.
        if entry.legacy and not manuals and not _legacy_requested(entry, words, prefix):
            continue
        next_tokens, score = _match_tokens(entry, words) if words else (_initial_roots(entry.syntax), ())
        if next_tokens:
            paths.append((entry, next_tokens, score))
    # Resolve consumed exact keywords across the complete catalog, not only
    # within a single syntax. Abbreviations retain equal-quality alternatives.
    best_scores = {
        vendor: max((score for entry, _, score in paths if entry.vendor == vendor), default=())
        for vendor in vendors
    }
    for index, (entry, next_tokens, score) in enumerate(paths):
        if index % 128 == 0:
            check_cancelled()
        if score != best_scores[entry.vendor]:
            continue
        relevance = 0 if view in entry.views else 1 if "any" in entry.views or view == "any" else 2
        if entry.tokens[0] in {"system-view", "quit", "return", "undo", "display"}:
            relevance = min(relevance, 1)
        values: set[tuple[str, str]] = set()
        for token in next_tokens:
            if token.startswith("<"):
                arguments.add(token)
                kind = parameter_kind(token, entry.syntax)
                status = parameter_status(token, entry.syntax)
                description = (
                    "Documented interface type; verify hardware support in the linked reference."
                    if kind == "interface-type"
                    else "Complete effective declarations in this document; device existence is unverified."
                    if kind
                    else "Object meaning is unmapped; enter manually and check the official namespace."
                    if status == "unconfirmed"
                    else "Enter manually; consult the official definition for format and range."
                )
                detail = argument_details.setdefault(
                    (kind or token, status),
                    {
                        "token": token,
                        "aliases": [],
                        "kind": kind or "free-parameter",
                        "status": status,
                        "description": description,
                        "sources": [],
                        "syntaxes": [],
                        "syntaxDetails": [],
                        "detailKey": "argument:" + (kind or token) + ":" + status,
                    },
                )
                for field, incoming in (
                    ("aliases", [token]),
                    ("sources", list(entry.sources or (entry.source,))),
                    ("syntaxes", [entry.syntax]),
                ):
                    if include_details or field == "aliases" or not detail[field]:
                        _unique_extend(
                            detail, field, incoming, argument_seen.setdefault((kind or token, status), {})
                        )
                if include_details:
                    _unique_extend(
                        detail,
                        "syntaxDetails",
                        _syntax_details(entry),
                        argument_seen.setdefault((kind or token, status), {}),
                    )
                values.update(
                    (value, "interface-type" if kind == "interface-type" else "object:" + kind)
                    for value in _parameter_values(token, entry.vendor, context, entry.syntax, words)
                )
            else:
                # Fixed interface keywords and the domain provider share identity.
                canonical = next(
                    (value for value in _INTERFACE_TYPES[entry.vendor] if value.lower() == token.lower()),
                    None,
                )
                values.add((canonical or token, "interface-type" if canonical else "keyword"))
        for token, kind in values:
            if not token.lower().startswith(prefix.lower()):
                continue
            identity = (kind, token) if kind.startswith("object:") else ("cli", token.casefold())
            key = identity[0] + ":" + identity[1]
            if detail_key and detail_key != key:
                continue
            item = matches.setdefault(
                identity,
                {
                    "text": token,
                    "kind": "object" if kind.startswith("object:") else kind,
                    "objectType": kind.removeprefix("object:") if kind.startswith("object:") else "",
                    "vendors": [],
                    "syntax": entry.syntax,
                    "source": entry.source,
                    "rank": relevance,
                    "views": [],
                    "sources": [],
                    "scopes": [],
                    "annotations": [],
                    "syntaxes": [],
                    "sourceDetails": [],
                    "syntaxDetails": [],
                    "detailKey": key,
                },
            )
            item_vendors = item["vendors"]
            assert isinstance(item_vendors, list)
            if LABELS[entry.vendor] not in item_vendors:
                item_vendors.append(LABELS[entry.vendor])
            for field, metadata_values in (
                ("views", list(entry.views)),
                ("sources", list(entry.sources or (entry.source,))),
                ("scopes", list(entry.scopes)),
                ("annotations", list(entry.annotations)),
                ("syntaxes", [entry.syntax]),
                ("sourceDetails", list(entry.provenance)),
            ):
                if include_details or (field == "views") or (field != "sourceDetails" and not item[field]):
                    _unique_extend(item, field, metadata_values, item_seen.setdefault(identity, {}))
            if include_details:
                _unique_extend(
                    item, "syntaxDetails", _syntax_details(entry), item_seen.setdefault(identity, {})
                )
            if relevance < int(str(item["rank"])):
                item.update(syntax=entry.syntax, source=entry.source, rank=relevance)
    items = sorted(matches.values(), key=lambda item: (int(str(item["rank"])), str(item["text"]).lower()))
    for detail in argument_details.values():
        aliases = detail["aliases"]
        assert isinstance(aliases, list)
        aliases.sort()
        detail["token"] = aliases[0]
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
        "argumentDetails": sorted(argument_details.values(), key=lambda row: str(row["token"])),
        "start": _utf16_length(source[:start]),
        "end": _utf16_length(source[:end]),
        "insert": insertion,
        "vendors": [LABELS[v] for v in vendors],
        "scopeNote": (
            "Completion covers the listed references. Recognition does not prove semantic checks "
            "or compatibility with every product/version. Historical forms retain their reference scope."
        ),
    }
