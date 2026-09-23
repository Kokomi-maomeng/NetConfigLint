"""Locate source-mapped configuration sections in an H3C diagnostic bundle."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADER = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$")
_BOUNDARY = re.compile(r"^\s*=+\s*$")


@dataclass(frozen=True, slots=True)
class H3CDiagnosticBundle:
    masked_configuration: str
    analysis_lines: frozenset[int]
    section_count: int
    saved_present: bool
    saved_matches_current: bool | None


def _section(lines: list[str], header_index: int) -> tuple[int, int]:
    start = header_index + 1
    end = next(
        (index for index in range(start, len(lines)) if _BOUNDARY.fullmatch(lines[index])),
        len(lines),
    )
    return start, end


def extract_h3c_diagnostic_bundle(source: str) -> H3CDiagnosticBundle | None:
    lines = source.splitlines()
    named: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADER.fullmatch(line)
        if match and match.group(1).strip():
            named.append((index, match.group(1).strip().lower()))
    current_header = next((index for index, name in named if name == "display current-configuration"), None)
    if current_header is None:
        return None
    current_start, current_end = _section(lines, current_header)
    saved_header = next((index for index, name in named if name == "display saved-configuration"), None)
    saved_matches: bool | None = None
    if saved_header is not None:
        saved_start, saved_end = _section(lines, saved_header)
        saved_matches = lines[current_start:current_end] == lines[saved_start:saved_end]

    masked = [""] * len(lines)
    masked[current_start:current_end] = lines[current_start:current_end]
    return H3CDiagnosticBundle(
        masked_configuration="\n".join(masked) + ("\n" if source.endswith("\n") else ""),
        analysis_lines=frozenset(range(current_start + 1, current_end + 1)),
        section_count=len(named),
        saved_present=saved_header is not None,
        saved_matches_current=saved_matches,
    )
