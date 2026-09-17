"""User-requested exports. Source text is included only in explicit source/full exports."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from typing import Any

from netconfiglint.core.diagnostics import Diagnostic


def render_report(
    source: str,
    diagnostics: tuple[Diagnostic, ...],
    *,
    scope: str,
    format: str,
    diagnostics_first: bool,
    mode: str,
    vendor: str,
    text: Callable[[str], str],
    translate: Callable[[str], str] = lambda value: value,
    coverage: dict[str, Any] | None = None,
    input_metadata: dict[str, Any] | None = None,
) -> str:
    if scope not in {"full", "configuration", "diagnostics"} or format not in {"json", "md", "txt"}:
        raise ValueError("Invalid export options")
    records = []
    for item in diagnostics:
        record = item.to_dict()
        for key in ("message", "explanation", "suggested_fix"):
            record[key] = translate(record[key])
        records.append(record)
    lines = source.splitlines()
    if source.endswith(("\n", "\r")):
        lines.append("")
    annotations: list[dict[str, Any]] = []
    if scope == "full" and diagnostics_first:
        by_line: dict[int, list[Diagnostic]] = {}
        for diagnostic in diagnostics:
            for number in range(
                diagnostic.source.line,
                min(len(lines), diagnostic.source.end_line or diagnostic.source.line) + 1,
            ):
                by_line.setdefault(number, []).append(diagnostic)
        for number, line in enumerate(lines, 1):
            relevant = by_line.get(number, [])
            annotations.append(
                {
                    "line": number,
                    "text": line,
                    "counts": dict(Counter(d.severity.value for d in relevant)),
                    "rule_ids": [d.rule_id for d in relevant],
                }
            )
    if format == "json":
        payload: dict[str, Any] = {"schema_version": "2.0", "scope": scope, "mode": mode, "vendor": vendor}
        if input_metadata:
            payload["input"] = input_metadata
        if coverage is not None and scope != "configuration":
            payload["coverage"] = coverage
        if scope == "diagnostics" or (scope == "full" and diagnostics_first):
            payload["diagnostics"] = records
        if scope != "diagnostics":
            payload["configuration"] = source
        if scope == "full":
            if diagnostics_first:
                payload["annotated_lines"] = annotations
            else:
                payload["diagnostics"] = records
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    markdown = format == "md"

    def heading(value: str) -> str:
        return ("## " if markdown else "") + value + "\n\n"

    def fenced(value: str) -> str:
        # Choose a delimiter longer than any run in untrusted configuration/diagnostic text.
        import re

        longest = max((len(m.group()) for m in re.finditer(r"`+", value)), default=0)
        fence = "`" * max(3, longest + 1)
        return f"{fence}text\n{value}\n{fence}\n" if markdown else value + "\n"

    def diagnostic_section() -> str:
        result = heading(text("analysis.diagnostics"))
        if input_metadata:
            result += fenced("Input: " + json.dumps(input_metadata, ensure_ascii=False)) + "\n"
        if coverage is not None:
            human_coverage = dict(coverage)
            for key in ("unparsed_lines", "unsupported_lines", "context_unknown_lines"):
                values = human_coverage.get(key)
                if isinstance(values, list) and len(values) > 80:
                    human_coverage[key] = [*values[:80], f"... {len(values) - 80} more"]
            result += (
                fenced(text("analysis.coverage") + ": " + json.dumps(human_coverage, ensure_ascii=False))
                + "\n"
            )
        if not diagnostics:
            return result + text("analysis.no_issues") + "\n"
        for item, record in zip(diagnostics, records, strict=True):
            result += (
                fenced(
                    f"[{text('analysis.' + item.severity.value.lower())}] {item.rule_id} · "
                    f"{text('issue.line')} {item.source.line}"
                    + (f"-{item.source.end_line}" if item.source.end_line else "")
                    + f"\n{text('issue.object')}: {item.object_name}"
                    + f"\n{text('issue.confidence')}: {item.confidence.value}"
                    + f"\n{text('issue.source_range')}: {json.dumps(record['source'], sort_keys=True)}"
                    + f"\n{record['message']}\n{text('issue.explanation')}: {record['explanation']}"
                    + f"\n{text('issue.fix')}: {record['suggested_fix']}"
                )
                + "\n"
            )
        return result

    def config_section(annotate: bool) -> str:
        if not annotate:
            return heading(text("editor.configuration")) + fenced(source)
        width = len(str(len(lines)))
        rows = []
        for row in annotations:
            counts = " · ".join(f"{key} {count}" for key, count in row["counts"].items())
            suffix = f"  [{counts}]" if counts else ""
            rows.append(f"{row['line']:>{width}} | {row['text']}{suffix}")
        return heading(text("editor.configuration")) + fenced("\n".join(rows))

    if scope == "configuration":
        return fenced(source) if markdown else source
    if scope == "diagnostics":
        return diagnostic_section()
    if diagnostics_first:
        return diagnostic_section() + "\n" + config_section(True)
    return config_section(False) + "\n" + diagnostic_section()
