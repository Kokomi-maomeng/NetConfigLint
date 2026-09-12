from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from netconfiglint import __version__, analyze
from netconfiglint.core.analyzer.control import AnalysisLimits
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
    check.add_argument(
        "--initial-view", help="starting view for a snippet, e.g. 'aaa' or 'interface Vlanif10'"
    )
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
        f"Coverage: {json.dumps(result.coverage, ensure_ascii=True)}\n\n"
    )
    if not result.diagnostics:
        stream.write("No diagnostics within the supported checks.\n")
        return
    stream.write("\n\n".join(_format_diagnostic(item, color=color) for item in result.diagnostics))
    stream.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with args.path.open("r", encoding="utf-8-sig") as stream:
            source = stream.read(AnalysisLimits().max_characters + 1)
        result = analyze(source, args.mode, args.vendor, initial_view=args.initial_view)
    except (OSError, UnicodeError, ValueError) as exc:
        _error(f"Cannot read or analyze {args.path.name!r} ({type(exc).__name__}).")
        return 2
    try:
        if args.output_format == "json":
            # ASCII is also valid UTF-8 and survives legacy Windows output encodings.
            payload = json.dumps(result.to_dict(), ensure_ascii=True, indent=2) + "\n"
        else:
            buffer = io.StringIO()
            _write_text(result, buffer, color=sys.stdout.isatty() and not args.no_color)
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            payload = buffer.getvalue().encode(encoding, errors="backslashreplace").decode(encoding)
        sys.stdout.write(payload)
        sys.stdout.flush()
    except (OSError, UnicodeError, ValueError):
        _error("Output could not be written completely.")
        # Prevent a second broken-pipe error during interpreter shutdown.
        sys.stdout = io.StringIO()
        return 2
    return 1 if any(item.severity == Severity.ERROR for item in result.diagnostics) else 0


def _error(message: str) -> None:
    try:
        sys.stderr.write(f"netconfiglint: {message}\n".encode("ascii", "backslashreplace").decode("ascii"))
        sys.stderr.flush()
    except (OSError, UnicodeError):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
