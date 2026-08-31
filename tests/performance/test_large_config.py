from time import perf_counter

import pytest

from benchmarks.benchmark_large_config import synthetic_config
from netconfiglint import analyze


@pytest.mark.performance
def test_fifteen_thousand_line_config_completes_within_budget() -> None:
    source = synthetic_config(5_000)
    started = perf_counter()
    result = analyze(source, "full", "huawei")
    duration = perf_counter() - started

    assert result.source_line_count >= 15_000
    assert not result.diagnostics
    assert duration < 2.0
