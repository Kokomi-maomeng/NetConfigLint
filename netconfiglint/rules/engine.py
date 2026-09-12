from __future__ import annotations

from collections import Counter

from netconfiglint.core.analyzer.control import (
    ACTIVE_CONTROL,
    AnalysisLimitReached,
    checkpoint,
    record_diagnostic,
)
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules.protocols import Rule, RuleContext


class RuleEngine:
    def __init__(self, rules: tuple[Rule, ...]) -> None:
        ids = [rule.metadata.rule_id for rule in rules]
        duplicates = sorted(rule_id for rule_id, count in Counter(ids).items() if count > 1)
        if duplicates:
            raise ValueError(f"Duplicate rule IDs: {', '.join(duplicates)}")
        self._rules = rules

    @property
    def rules(self) -> tuple[Rule, ...]:
        return self._rules

    def run(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        control = ACTIVE_CONTROL.get()
        diagnostics = list(context.config.parse_issues)
        if control is not None:
            control.emitted = []
        try:
            for item in diagnostics:
                record_diagnostic(item)
            for rule in self._rules:
                checkpoint()
                diagnostics.extend(rule.evaluate(context))
        except AnalysisLimitReached as exc:
            diagnostics = list(control.emitted or ()) if control is not None else diagnostics
            context.config.incomplete_reasons.append(str(exc))
        finally:
            if control is not None:
                control.emitted = None
        if context.config.incomplete_reasons:
            diagnostics.append(limit_diagnostic(context.config.incomplete_reasons))
        diagnostics.sort(key=lambda item: (item.source.line, item.rule_id, item.object_name))
        return tuple(diagnostics)


def limit_diagnostic(reasons: list[str]) -> Diagnostic:
    return Diagnostic(
        Severity.UNKNOWN,
        "SYS-LIMIT-001",
        SourceRange(1),
        "Analysis",
        "Analysis is incomplete because a resource limit was reached.",
        "; ".join(reasons),
        "Split the input into smaller scopes and analyze again.",
        Confidence.LOW,
    )
