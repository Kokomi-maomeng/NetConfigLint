from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceLine:
    number: int
    raw: str
    text: str
    tokens: tuple[str, ...]


def lex_lines(source: str) -> tuple[SourceLine, ...]:
    """Normalize newlines while preserving one-based source positions."""
    return tuple(
        SourceLine(number, raw, raw.strip(), tuple(raw.strip().split()))
        for number, raw in enumerate(source.splitlines(), start=1)
    )
