from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.diagnostics import Diagnostic, Severity
from netconfiglint.core.model import DeviceConfig


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    rule_id: str
    title: str
    default_severity: Severity
    vendor: str


@dataclass(frozen=True, slots=True)
class RuleContext:
    config: DeviceConfig
    mode: AnalysisMode
    detection: VendorDetection


class Rule(Protocol):
    metadata: RuleMetadata

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]: ...
