"""Vendor-neutral diagnostics shared by every frontend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


class Confidence(StrEnum):
    VERIFIED = "VERIFIED"
    DOCUMENTED = "DOCUMENTED"
    INFERRED = "INFERRED"
    GENERIC = "GENERIC"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class SourceRange:
    line: int
    end_line: int | None = None
    column: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        if self.line < 1:
            raise ValueError("Source line numbers are one-based")
        if self.end_line is not None and self.end_line < self.line:
            raise ValueError("end_line must not precede line")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    rule_id: str
    source: SourceRange
    object_name: str
    message: str
    explanation: str
    suggested_fix: str
    confidence: Confidence

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        data["confidence"] = self.confidence.value
        return data
