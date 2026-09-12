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

    @property
    def coverage(self) -> dict[str, Any]:
        config = self.config
        ignored = {item.line for item in config.ignored_lines}
        ignored.update(
            number
            for number, line in enumerate(config.source_lines, 1)
            if not line.strip() or line.strip().lower() in {"#", "return"}
        )
        unsupported = {item.line for item in config.unsupported_lines}
        unparsed = {item.line for item in config.unparsed_lines} - unsupported - ignored
        total = len(config.source_lines)
        return {
            "recognized": max(0, total - len(ignored | unsupported | unparsed)),
            "unparsed": len(unparsed),
            "unsupported": len(unsupported),
            "ignored": len(ignored),
            "unparsed_lines": sorted(unparsed),
            "unsupported_lines": sorted(unsupported),
            "context_unknown_lines": sorted({item.line for item in config.context_unknown_lines}),
            "complete": not config.incomplete_reasons,
            "incomplete_reasons": list(config.incomplete_reasons),
            "scope": (
                "Recognized commands are not a guarantee of complete device syntax or runtime validation."
            ),
        }

    def to_dict(self, *, include_config: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mode": self.mode.value,
            "detection": self.detection.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "elapsed_ms": round(self.elapsed_ms, 3),
            "source_line_count": self.source_line_count,
            "coverage": self.coverage,
        }
        if include_config:
            data["config"] = self.config.to_dict()
        return data
