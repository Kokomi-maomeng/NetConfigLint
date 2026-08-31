from __future__ import annotations

import pytest

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange


def test_diagnostic_serialization_uses_enum_values() -> None:
    diagnostic = Diagnostic(
        Severity.ERROR,
        "TEST-001",
        SourceRange(4, 5),
        "object",
        "message",
        "explanation",
        "fix",
        Confidence.VERIFIED,
    )

    assert diagnostic.to_dict()["severity"] == "ERROR"
    assert diagnostic.to_dict()["source"] == {
        "line": 4,
        "end_line": 5,
        "column": None,
        "end_column": None,
    }


def test_source_range_rejects_zero_line() -> None:
    with pytest.raises(ValueError):
        SourceRange(0)
