from __future__ import annotations

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


class SensitiveConfigurationRule:
    metadata = RuleMetadata("HUA-SEC-001", "Sensitive configuration detected", Severity.INFO, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.sensitive_lines:
            return ()
        first = context.config.sensitive_lines[0]
        return (
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                first,
                "Configuration",
                "Sensitive configuration data detected. NetConfigLint processes configuration locally.",
                f"Potentially sensitive keywords occur on {len(context.config.sensitive_lines)} line(s). "
                "Their values are not included in this diagnostic or default logs.",
                "Protect exported reports and configuration files according to your security policy.",
                Confidence.GENERIC,
            ),
        )
