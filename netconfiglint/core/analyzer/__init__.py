from netconfiglint.core.analyzer.control import AnalysisLimits, CancellationToken
from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult, VendorDetection


def analyze(
    source: str,
    mode: AnalysisMode | str = AnalysisMode.SNIPPET,
    vendor: str = "auto",
    *,
    limits: AnalysisLimits | None = None,
    cancellation: CancellationToken | None = None,
    initial_view: str | None = None,
) -> AnalysisResult:
    """Lazy public wrapper that keeps model imports free of vendor-registry cycles."""
    from netconfiglint.core.analyzer.api import analyze as run_analysis

    return run_analysis(
        source, mode, vendor, limits=limits, cancellation=cancellation, initial_view=initial_view
    )


__all__ = [
    "AnalysisLimits",
    "AnalysisMode",
    "AnalysisResult",
    "CancellationToken",
    "VendorDetection",
    "analyze",
]
