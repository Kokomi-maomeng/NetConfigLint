"""NetConfigLint public API."""

from netconfiglint.core.analyzer.api import analyze
from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult

__all__ = ["AnalysisMode", "AnalysisResult", "analyze"]
__version__ = "1.1.0b1"
