from __future__ import annotations

import re

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.parser.acl_identity import acl_label, parse_acl_identity
from netconfiglint.vendors.huawei.rules.facts import all_commands
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic

_ROUTE_POLICY = re.compile(r"\broute-policy\s+(\S+)", re.IGNORECASE)


class MissingRedistributionPolicyRule:
    metadata = RuleMetadata("HUA-RPOL-003", "Undefined redistribution route-policy", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for text, source, block in all_commands(context.config):
            if not text.lower().startswith(("import-route ", "export-route ")):
                continue
            match = _ROUTE_POLICY.search(text)
            if match is None or match.group(1) in context.config.route_policies:
                continue
            name = match.group(1)
            result.append(
                missing_reference_diagnostic(
                    context,
                    rule_id=self.metadata.rule_id,
                    source=source,
                    object_name=block.header,
                    full_message=f"Route redistribution references undefined route-policy {name}.",
                    snippet_message=f"Route-policy {name} was not found in the snippet.",
                    explanation="The import/export command has no matching route-policy definition.",
                    suggested_fix=f"Define route-policy {name} or correct/remove the redistribution filter.",
                )
            )
        return tuple(result)


class BroadPermitAclRule:
    metadata = RuleMetadata("HUA-ACL-002", "Broad ACL permit rule", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for block in context.config.blocks:
            if not block.header.lower().startswith("acl "):
                continue
            for command in block.commands:
                lower = command.text.lower()
                if not lower.startswith("rule ") or " permit " not in f" {lower} ":
                    continue
                if "source any" not in lower or "destination any" not in lower:
                    continue
                result.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.metadata.rule_id,
                        command.source,
                        block.header,
                        "ACL rule permits traffic from any source to any destination.",
                        "The rule is intentionally reported as broad; its impact depends on every consumer.",
                        "Confirm the policy intent and narrow protocol, source, destination, "
                        "or service fields.",
                        Confidence.VERIFIED,
                    )
                )
        return tuple(result)


class EmptyReferencedAclRule:
    metadata = RuleMetadata("HUA-ACL-003", "Referenced ACL has no rules", Severity.WARNING, "Huawei")

    @staticmethod
    def _acl_name(header: str) -> str | None:
        tokens = header.split()
        if not tokens or tokens[0].lower() != "acl":
            return None
        identity = parse_acl_identity(tuple(tokens[1:]))
        return identity.key if identity is not None else None

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        acl_has_rule = {
            name: any(command.text.lower().startswith("rule ") for command in block.commands)
            for block in context.config.blocks
            if (name := self._acl_name(block.header)) is not None
        }
        references = list(context.config.acl_references)
        for policy in context.config.route_policies.values():
            references.extend((name, policy.name, source) for name, source in policy.acl_references)
        for classifier in context.config.traffic_classifiers.values():
            references.extend((name, classifier.name, source) for name, source in classifier.acl_references)
        seen = set()
        result = []
        for name, object_name, source in references:
            if name in seen or acl_has_rule.get(name, True):
                continue
            seen.add(name)
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    self.metadata.rule_id,
                    source,
                    object_name,
                    f"Referenced ACL {acl_label(name)} contains no rules.",
                    "An empty ACL can deny expected traffic or leave a policy ineffective "
                    "depending on context.",
                    "Add the intended ACL rules or remove the stale reference after impact review.",
                    Confidence.VERIFIED,
                )
            )
        return tuple(result)
