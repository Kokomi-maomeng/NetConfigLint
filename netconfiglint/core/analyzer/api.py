"""Single analysis entry point shared by CLI and GUI."""

from __future__ import annotations

from time import perf_counter

from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult
from netconfiglint.vendors.registry import detect_vendor_plugin, get_vendor_plugin


def analyze(
    source: str,
    mode: AnalysisMode | str = AnalysisMode.SNIPPET,
    vendor: str = "auto",
) -> AnalysisResult:
    started = perf_counter()
    analysis_mode = mode if isinstance(mode, AnalysisMode) else AnalysisMode(mode.lower())
    requested_vendor = vendor.lower()
    if requested_vendor == "auto":
        detected = detect_vendor_plugin(source)
        if detected is None:
            raise ValueError("Could not identify a supported vendor; select a vendor to override")
        plugin, detection = detected
    else:
        plugin = get_vendor_plugin(requested_vendor)
        detection = plugin.detector.detect(source)
        if detection.vendor == "Unknown":
            detection = plugin.forced_detection()

    config = plugin.parser.parse(source, analysis_mode, detection)
    from netconfiglint.rules import RuleContext, RuleEngine

    diagnostics = RuleEngine(plugin.rules).run(RuleContext(config, analysis_mode, detection))
    return AnalysisResult(
        mode=analysis_mode,
        detection=detection,
        config=config,
        diagnostics=diagnostics,
        elapsed_ms=(perf_counter() - started) * 1000,
        source_line_count=len(config.source_lines),
    )
