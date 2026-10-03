"""Validate imported CLI notation and apply explicit source-linked manual errata."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


def normalize_notation(syntax: str) -> str:
    # Some manuals put notation operators in the same italic spans as parameters.
    while True:
        syntax = re.sub(r"<\s*<([^<>]+)>\s*>", r"<\1>", syntax)
        normalized = re.sub(r"<\s*([\[\]{}|*])\s*>", r"\1", syntax)
        if normalized == syntax:
            break
        syntax = normalized
    syntax = re.sub(r"<([^<>]+)\|>", r"<\1> |", syntax)
    syntax = syntax.replace("community - list", "community-list")
    return " ".join(syntax.split())


def validate_notation(syntax: str) -> None:
    stack: list[str] = []
    for token in re.findall(r"<[^>]+>|[\[\]{}]|[^\s\[\]{}]+", syntax):
        if token.startswith("<") and any(char in token for char in "[]{}|*"):
            raise ValueError(f"CLI operator inside argument notation: {syntax}")
        if token in ("[", "{"):
            stack.append(token)
        elif token in ("]", "}") and (not stack or (stack.pop(), token) not in (("[", "]"), ("{", "}"))):
            raise ValueError(f"Unbalanced CLI notation: {syntax}")
    if stack:
        raise ValueError(f"Unbalanced CLI notation: {syntax}")


@lru_cache(maxsize=1)
def errata() -> dict[tuple[str, str], str]:
    rows = json.loads(Path(__file__).with_name("completion_errata.json").read_text(encoding="utf-8"))
    result = {}
    for row in rows:
        original = normalize_notation(row["original"])
        corrected = normalize_notation(row["corrected"])
        validate_notation(corrected)
        key = (row["vendor"], original)
        if key in result:
            raise ValueError("Duplicate CLI erratum")
        result[key] = corrected
    return result


def normalize_syntax(vendor: str, syntax: str) -> str:
    normalized = normalize_notation(syntax)
    normalized = errata().get((vendor, normalized), normalized)
    validate_notation(normalized)
    return normalized
