"""Adapters for rules whose normalized semantics are shared by VRP and Comware."""

from __future__ import annotations

from dataclasses import replace

from netconfiglint.core.diagnostics import Diagnostic
from netconfiglint.rules import Rule, RuleContext, RuleMetadata


class H3CAdaptedRule:
    def __init__(self, delegate: Rule) -> None:
        self._delegate = delegate
        original = delegate.metadata
        self.metadata = RuleMetadata(
            original.rule_id.replace("HUA-", "H3C-"),
            original.title,
            original.default_severity,
            "H3C",
        )

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            replace(
                item,
                rule_id=self.metadata.rule_id,
                explanation=item.explanation.replace("Huawei", "H3C Comware"),
                suggested_fix=item.suggested_fix.replace("STelnet/SSH", "SSH"),
            )
            for item in self._delegate.evaluate(context)
        )
