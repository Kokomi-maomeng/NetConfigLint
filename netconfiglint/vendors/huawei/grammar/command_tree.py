"""Experimental command-tree API; not used to validate product configuration input."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Resolution(StrEnum):
    MATCH = "match"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class CommandNode:
    word: str
    children: dict[str, CommandNode] = field(default_factory=dict)
    terminal: bool = False


class CommandTree:
    def __init__(self, commands: set[tuple[str, ...]]) -> None:
        self.root = CommandNode("")
        for command in commands:
            node = self.root
            for word in command:
                node = node.children.setdefault(word.lower(), CommandNode(word.lower()))
            node.terminal = True

    def resolve(self, tokens: tuple[str, ...]) -> Resolution:
        nodes = [self.root]
        for token in tokens:
            candidates = {
                id(child): child
                for node in nodes
                for word, child in node.children.items()
                if word.startswith(token.lower())
            }
            nodes = list(candidates.values())
            if not nodes:
                return Resolution.UNKNOWN
            if len(nodes) > 1:
                return Resolution.AMBIGUOUS
        return Resolution.MATCH if any(node.terminal for node in nodes) else Resolution.UNKNOWN
