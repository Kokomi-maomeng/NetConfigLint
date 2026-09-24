"""Separate pasted display output from configuration while retaining line numbers."""

from __future__ import annotations

import re

_DISPLAY = re.compile(r"^\s*(?:(?:<[^>]+>|\[[^]]+\])\s*)?(display\s+\S+.*)$", re.I)


def mask_operational_output(source: str) -> tuple[str, set[int]]:
    lines = source.splitlines()
    kept: list[str] = []
    scope: set[int] = set()
    operational = False
    for number, line in enumerate(lines, 1):
        match = _DISPLAY.fullmatch(line)
        if match:
            operational = not match.group(1).lower().startswith("display current-configuration")
            kept.append("")
            continue
        if operational:
            kept.append("")
        else:
            kept.append(line)
            scope.add(number)
    return "\n".join(kept) + ("\n" if source.endswith(("\n", "\r")) else ""), scope
