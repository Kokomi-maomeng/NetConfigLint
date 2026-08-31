from __future__ import annotations

from netconfiglint.core.diagnostics import Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class MissingTrafficPolicyComponentRule:
    metadata = RuleMetadata("HUA-POL-001", "Undefined traffic policy component", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for policy in context.config.traffic_policies.values():
            for classifier, behavior, source in policy.classifier_bindings:
                if classifier not in context.config.traffic_classifiers:
                    result.append(
                        missing_reference_diagnostic(
                            context,
                            rule_id=self.metadata.rule_id,
                            source=source,
                            object_name=policy.name,
                            full_message=f"Traffic policy references undefined classifier {classifier}.",
                            snippet_message=f"Traffic classifier {classifier} was not found in the snippet.",
                            explanation="The classifier binding has no matching traffic "
                            "classifier definition.",
                            suggested_fix=f"Define traffic classifier {classifier} or correct the binding.",
                        )
                    )
                if behavior not in context.config.traffic_behaviors:
                    result.append(
                        missing_reference_diagnostic(
                            context,
                            rule_id=self.metadata.rule_id,
                            source=source,
                            object_name=policy.name,
                            full_message=f"Traffic policy references undefined behavior {behavior}.",
                            snippet_message=f"Traffic behavior {behavior} was not found in the snippet.",
                            explanation="The behavior binding has no matching traffic behavior definition.",
                            suggested_fix=f"Define traffic behavior {behavior} or correct the binding.",
                        )
                    )
        return tuple(result)


class MissingAppliedTrafficPolicyRule:
    metadata = RuleMetadata("HUA-POL-002", "Undefined applied traffic policy", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=source,
                object_name=interface.name,
                full_message=f"Interface references undefined traffic policy {name}.",
                snippet_message=f"Traffic policy {name} was not found in the snippet.",
                explanation="The applied policy has no matching traffic policy definition.",
                suggested_fix=f"Define traffic policy {name} or correct/remove the interface reference.",
            )
            for interface in context.config.interfaces.values()
            for name, _direction, source in interface.traffic_policies
            if name not in context.config.traffic_policies
        )
