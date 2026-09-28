"""Vendor-neutral dispatch of operational-only analysis."""

from time import perf_counter

from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult, VendorDetection
from netconfiglint.core.diagnostics import Severity, SourceRange
from netconfiglint.core.model import DeviceConfig
from netconfiglint.rules import RuleContext, RuleEngine
from netconfiglint.vendors.registry import VendorPlugin


def analyze_view(
    source: str, plugin: VendorPlugin, detection: VendorDetection, started: float
) -> AnalysisResult:
    config = DeviceConfig(vendor=detection.vendor, source_lines=tuple(source.splitlines()))
    config.snapshot = plugin.snapshot_parser.parse(source)
    diagnostics = RuleEngine(plugin.view_rules).run(RuleContext(config, AnalysisMode.VIEW, detection))
    # Operational parsing is partial: configuration semantics were not checked.
    config.metadata["operational_only"] = "true"
    if not diagnostics or all(item.severity == Severity.UNKNOWN for item in diagnostics):
        config.unparsed_lines = [
            SourceRange(i) for i, text in enumerate(config.source_lines, 1) if text.strip()
        ]
    else:
        config.catalogued_lines = [
            SourceRange(i) for i, text in enumerate(config.source_lines, 1) if text.strip()
        ]
    return AnalysisResult(
        AnalysisMode.VIEW,
        detection,
        config,
        diagnostics,
        (perf_counter() - started) * 1000,
        len(config.source_lines),
    )
