from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from netconfiglint.core.diagnostics import Diagnostic
    from netconfiglint.core.model import DeviceConfig


class AnalysisMode(StrEnum):
    SNIPPET = "snippet"
    FULL = "full"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True, slots=True)
class VendorDetection:
    vendor: str
    os: str
    platform_family: str
    model: str
    version: str
    confidence: float
    evidence: tuple[str, ...] = ()
    profile_id: str = "unresolved"
    profile_confidence: str = "GENERIC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    mode: AnalysisMode
    detection: VendorDetection
    config: DeviceConfig
    diagnostics: tuple[Diagnostic, ...]
    elapsed_ms: float
    source_line_count: int

    def to_dict(self, *, include_config: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mode": self.mode.value,
            "detection": self.detection.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "elapsed_ms": round(self.elapsed_ms, 3),
            "source_line_count": self.source_line_count,
        }
        if include_config:
            data["config"] = self.config.to_dict()
        return data
