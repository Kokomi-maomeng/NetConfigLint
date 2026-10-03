from __future__ import annotations

import re
from dataclasses import dataclass

# A terminal prompt is recognized only at the beginning of a line. Brackets in
# command arguments and quoted descriptions never reach this expression.
_PROMPT = re.compile(r"^\s*(?P<prompt><[A-Za-z][\w.:-]*>|\[[~*]?[A-Za-z][\w./: -]*\])\s*")


def normalize_cli_line(raw: str) -> tuple[str, int]:
    """Return a command and its source offset, retaining every argument verbatim."""
    match = _PROMPT.match(raw)
    if match is not None:
        tail = raw[match.end() :]
        if not tail or re.match(r"[A-Za-z#]", tail):
            return tail, match.end()
    offset = len(raw) - len(raw.lstrip())
    return raw[offset:], offset


def is_comment_line(raw: str) -> bool:
    """A leading # starts a pure comment; # inside an argument is ordinary text."""
    return normalize_cli_line(raw)[0].startswith("#")


@dataclass(frozen=True, slots=True)
class SourceLine:
    number: int
    raw: str
    text: str
    tokens: tuple[str, ...]
    prompt: str = ""
    command_offset: int = 0


def lex_lines(source: str) -> tuple[SourceLine, ...]:
    """Normalize newlines while preserving one-based source positions."""
    lines = []
    for number, raw in enumerate(source.splitlines(), start=1):
        body, offset = normalize_cli_line(raw)
        text = body.strip()
        match = _PROMPT.match(raw)
        prompt = match.group("prompt") if match is not None and offset == match.end() else ""
        lines.append(SourceLine(number, raw, text, tuple(text.split()), prompt, offset))
    return tuple(lines)
