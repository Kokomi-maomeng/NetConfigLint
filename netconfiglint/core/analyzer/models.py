from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from netconfiglint.core.lexer import is_comment_line

if TYPE_CHECKING:
    from netconfiglint.core.diagnostics import Diagnostic
    from netconfiglint.core.model import DeviceConfig


class AnalysisMode(StrEnum):
    SNIPPET = "snippet"
    MESSAGE = "message"
    VIEW = "view"
    FULL = "full"
    # Accepted by the CLI for older reports; the GUI offers the four modes above.
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
        scope = (
            config.analysis_lines
            if config.metadata.get("analysis_scope_explicit") == "true"
            else config.analysis_lines or set(range(1, len(config.source_lines) + 1))
        )
        ignored = {item.line for item in config.ignored_lines if item.line in scope}
        ignored.update(
            number
            for number, line in enumerate(config.source_lines, 1)
            if number in scope
            and (not line.strip() or is_comment_line(line) or line.strip().lower() == "return")
        )
        unsupported = {item.line for item in config.unsupported_lines if item.line in scope}
        catalogued = {item.line for item in config.catalogued_lines if item.line in scope} - ignored
        unparsed = (
            {item.line for item in config.unparsed_lines if item.line in scope}
            - unsupported
            - ignored
            - catalogued
        )
        total = len(scope)
        context_unknown = {item.line for item in config.context_unknown_lines if item.line in scope} - ignored
        pending = (unsupported | unparsed | catalogued | context_unknown) - ignored
        return {
            "recognized": max(0, total - len(ignored | unsupported | unparsed | catalogued)),
            "catalogued": len(catalogued),
            "unparsed": len(unparsed),
            "unsupported": len(unsupported),
            "ignored": len(ignored),
            "source_total_lines": len(config.source_lines),
            "analysis_scope_lines": total,
            "excluded_operational_lines": len(config.source_lines) - total,
            "unparsed_lines": sorted(unparsed),
            "unsupported_lines": sorted(unsupported),
            "catalogued_lines": sorted(catalogued),
            "catalogued_families": [
                {"family": family, "count": value["count"]}
                for family, value in sorted(config.command_catalog.items())
                if isinstance(value, dict) and isinstance(value.get("count"), int)
            ],
            "context_unknown_lines": sorted(context_unknown),
            "pending": len(pending),
            "pending_lines": sorted(pending),
            "pending_line_details": [
                {
                    "line": number,
                    "status": (
                        "context_required"
                        if number in context_unknown
                        else "unsupported"
                        if number in unsupported
                        else "catalogued_only"
                        if number in catalogued
                        else "unparsed"
                    ),
                }
                for number in sorted(pending)
            ],
            "complete": not config.incomplete_reasons,
            "semantic_complete": not (
                pending or config.incomplete_reasons or config.metadata.get("operational_only") == "true"
            ),
            "incomplete_reasons": list(config.incomplete_reasons),
            "scope": (
                "Catalogued lines identify a documented command family only; recognized lines are not a "
                "guarantee of device syntax or runtime validation."
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
