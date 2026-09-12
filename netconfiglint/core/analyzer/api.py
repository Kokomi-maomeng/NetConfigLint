"""Single analysis entry point shared by CLI and GUI."""

from __future__ import annotations

from time import perf_counter

from netconfiglint.core.analyzer.control import (
    ACTIVE_CONTROL,
    AnalysisControl,
    AnalysisLimitReached,
    AnalysisLimits,
    CancellationToken,
    checkpoint,
)
from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult, VendorDetection
from netconfiglint.core.model import DeviceConfig
from netconfiglint.vendors.registry import detect_vendor_plugin, get_vendor_plugin


def analyze(
    source: str,
    mode: AnalysisMode | str = AnalysisMode.SNIPPET,
    vendor: str = "auto",
    *,
    limits: AnalysisLimits | None = None,
    cancellation: CancellationToken | None = None,
    initial_view: str | None = None,
) -> AnalysisResult:
    started = perf_counter()
    analysis_mode = mode if isinstance(mode, AnalysisMode) else AnalysisMode(mode.lower())
    control = AnalysisControl(limits or AnalysisLimits(), cancellation or CancellationToken())
    token = ACTIVE_CONTROL.set(control)
    try:
        checkpoint()
        if len(source) > control.limits.max_characters:
            raise AnalysisLimitReached("Input character budget exceeded")
        # Bounded before tokenization and before constructing normalized objects.
        for number, line in enumerate(source.splitlines(), 1):
            checkpoint()
            if number > control.limits.max_lines or len(line) > control.limits.max_line_length:
                raise AnalysisLimitReached("Input line budget exceeded")
        control.emitted = []  # The diagnostic budget also bounds parser diagnostics.
        return _analyze(source, analysis_mode, vendor, started, initial_view)
    except AnalysisLimitReached as exc:
        from netconfiglint.rules.engine import limit_diagnostic

        control.emitted = None  # The incomplete marker must survive the exhausted budget.
        config = DeviceConfig(vendor="Unknown", source_lines=(), incomplete_reasons=[str(exc)])
        detection = VendorDetection("Unknown", "Unknown", "Unknown", "Unknown", 0.0)
        return AnalysisResult(
            analysis_mode,
            detection,
            config,
            (limit_diagnostic([str(exc)]),),
            (perf_counter() - started) * 1000,
            0,
        )
    finally:
        ACTIVE_CONTROL.reset(token)


def _analyze(
    source: str, analysis_mode: AnalysisMode, vendor: str, started: float, initial_view: str | None
) -> AnalysisResult:
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

    config = (
        plugin.parser.parse(source, analysis_mode, detection)
        if initial_view is None
        else plugin.parser.parse(source, analysis_mode, detection, initial_view=initial_view)
    )
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
