from __future__ import annotations

from collections import Counter

from netconfiglint.core.diagnostics import Diagnostic
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
        diagnostics = [item for rule in self._rules for item in rule.evaluate(context)]
        diagnostics.sort(key=lambda item: (item.source.line, item.rule_id, item.object_name))
        return tuple(diagnostics)
