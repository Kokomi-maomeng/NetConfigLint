"""Resource bounds for vendor-owned numeric conversions."""

from netconfiglint.core.analyzer.control import AnalysisLimitReached


def bounded_integer(value: str) -> int:
    if len(value.lstrip("+-")) > 128:
        raise AnalysisLimitReached("Numeric parameter exceeds the 128-digit budget")
    return int(value)
