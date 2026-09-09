from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from netconfiglint import __version__, analyze
from netconfiglint.core.diagnostics import Diagnostic, Severity

_COLORS = {
    Severity.ERROR: "\033[31m",
    Severity.WARNING: "\033[33m",
    Severity.INFO: "\033[36m",
    Severity.UNKNOWN: "\033[35m",
}
_RESET = "\033[0m"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netconfiglint", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="analyze a local configuration file")
    check.add_argument("path", type=Path)
    check.add_argument(
        "--mode", choices=("snippet", "full", "snapshot"), default="snippet", help="default: snippet"
    )
    check.add_argument("--vendor", choices=("auto", "huawei"), default="auto")
    check.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    check.add_argument("--no-color", action="store_true")
    return parser


def _format_diagnostic(item: Diagnostic, *, color: bool) -> str:
    prefix = f"{item.severity.value:<7} {item.rule_id} Line {item.source.line}"
    if color:
        prefix = f"{_COLORS[item.severity]}{prefix}{_RESET}"
    return (
        f"{prefix}  {item.object_name}\n"
        f"  {item.message}\n"
        f"  Why: {item.explanation}\n"
        f"  Fix: {item.suggested_fix}\n"
        f"  Confidence: {item.confidence.value}"
    )


def _write_text(result: object, stream: TextIO, *, color: bool) -> None:
    from netconfiglint.core.analyzer import AnalysisResult

    if not isinstance(result, AnalysisResult):
        raise TypeError("Expected AnalysisResult")
    detection = result.detection
    stream.write(
        f"NetConfigLint {__version__}\n"
        f"Vendor: {detection.vendor}  "
        f"Platform: {detection.platform_family}  Model: {detection.model}\n"
        f"Version: {detection.version}  Detection confidence: {detection.confidence:.2f}\n"
        f"Profile: {detection.profile_id}  Profile confidence: {detection.profile_confidence}\n"
        f"Mode: {result.mode.value}  Lines: {result.source_line_count}  "
        f"Diagnostics: {len(result.diagnostics)}\n\n"
    )
    if not result.diagnostics:
        stream.write("No diagnostics produced.\n")
        return
    stream.write("\n\n".join(_format_diagnostic(item, color=color) for item in result.diagnostics))
    stream.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = args.path.read_text(encoding="utf-8-sig")
        result = analyze(source, args.mode, args.vendor)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"netconfiglint: {exc}", file=sys.stderr)
        return 2

    if args.output_format == "json":
        json.dump(result.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _write_text(result, sys.stdout, color=sys.stdout.isatty() and not args.no_color)
    return 1 if any(item.severity == Severity.ERROR for item in result.diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
