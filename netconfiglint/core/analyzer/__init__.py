from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult, VendorDetection


def analyze(
    source: str,
    mode: AnalysisMode | str = AnalysisMode.FULL,
    vendor: str = "auto",
) -> AnalysisResult:
    """Lazy public wrapper that keeps model imports free of vendor-registry cycles."""
    from netconfiglint.core.analyzer.api import analyze as run_analysis

    return run_analysis(source, mode, vendor)


__all__ = ["AnalysisMode", "AnalysisResult", "VendorDetection", "analyze"]
