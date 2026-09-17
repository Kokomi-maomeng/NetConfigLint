"""Per-call resource accounting and cooperative cancellation, safe across threads."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Event
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netconfiglint.core.diagnostics import Diagnostic


class AnalysisCancelled(Exception):
    pass


class AnalysisLimitReached(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AnalysisLimits:
    # Diagnostic bundles can be much larger than their embedded configuration.
    max_input_bytes: int = 64_000_000
    max_characters: int = 16_000_000
    max_lines: int = 300_000
    max_line_length: int = 32_768
    max_diagnostics: int = 2_000
    max_work: int = 20_000_000
    max_vlan_memberships: int = 250_000
    max_seconds: float = 60.0

    def __post_init__(self) -> None:
        if (
            min(
                self.max_characters,
                self.max_input_bytes,
                self.max_lines,
                self.max_line_length,
                self.max_diagnostics,
                self.max_work,
                self.max_vlan_memberships,
                self.max_seconds,
            )
            <= 0
        ):
            raise ValueError("Analysis limits must be positive")


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(slots=True)
class AnalysisControl:
    limits: AnalysisLimits
    cancellation: CancellationToken
    started: float = field(default_factory=monotonic)
    work: int = 0
    vlan_memberships: int = 0
    emitted: list[Diagnostic] | None = None

    def checkpoint(self, work: int = 1) -> None:
        if self.cancellation.cancelled:
            raise AnalysisCancelled("Analysis cancelled")
        self.work += work
        if self.work > self.limits.max_work:
            raise AnalysisLimitReached("Work budget exceeded")
        if monotonic() - self.started > self.limits.max_seconds:
            raise AnalysisLimitReached("Time budget exceeded")


ACTIVE_CONTROL: ContextVar[AnalysisControl | None] = ContextVar("analysis_control", default=None)


def checkpoint(work: int = 1) -> None:
    if (control := ACTIVE_CONTROL.get()) is not None:
        control.checkpoint(work)


def charge_vlan_memberships(count: int) -> None:
    if (control := ACTIVE_CONTROL.get()) is not None:
        control.checkpoint()
        control.vlan_memberships += count
        if control.vlan_memberships > control.limits.max_vlan_memberships:
            raise AnalysisLimitReached("VLAN membership budget exceeded")


def record_diagnostic(item: Diagnostic) -> None:
    control = ACTIVE_CONTROL.get()
    if control is None or control.emitted is None:
        return
    control.checkpoint()
    if len(control.emitted) >= control.limits.max_diagnostics:
        raise AnalysisLimitReached("Diagnostic budget exceeded")
    control.emitted.append(item)
