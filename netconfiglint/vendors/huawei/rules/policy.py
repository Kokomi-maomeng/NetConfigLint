from __future__ import annotations

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


class MissingBgpRoutePolicyRule:
    metadata = RuleMetadata("HUA-BGP-001", "Undefined BGP route-policy", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        if context.config.bgp is None:
            return ()
        for peer in context.config.bgp.peers.values():
            for name, source in (*peer.import_policies, *peer.export_policies):
                if name in context.config.route_policies:
                    continue
                result.append(
                    missing_reference_diagnostic(
                        context,
                        rule_id=self.metadata.rule_id,
                        source=source,
                        object_name=peer.address,
                        full_message=f"BGP peer references undefined route-policy {name}.",
                        snippet_message=f"Route-policy {name} was not found in the snippet.",
                        explanation="The peer policy reference has no matching route-policy definition "
                        "in the supplied full configuration.",
                        suggested_fix=f"Define route-policy {name} or remove/correct the peer reference.",
                    )
                )
        return tuple(result)


class MissingPrefixListRule:
    metadata = RuleMetadata("HUA-RPOL-001", "Undefined ip-prefix", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for policy in context.config.route_policies.values():
            for name, source in policy.prefix_references:
                if name in context.config.prefix_lists:
                    continue
                result.append(
                    missing_reference_diagnostic(
                        context,
                        rule_id=self.metadata.rule_id,
                        source=source,
                        object_name=policy.name,
                        full_message=f"Route-policy references undefined ip-prefix {name}.",
                        snippet_message=f"ip-prefix {name} was not found in the snippet.",
                        explanation="The if-match clause has no matching ip-prefix definition in the "
                        "supplied full configuration.",
                        suggested_fix=f"Define ip ip-prefix {name} or correct the if-match clause.",
                    )
                )
        return tuple(result)


class MissingAclRule:
    metadata = RuleMetadata("HUA-ACL-001", "Undefined ACL", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        references = list(context.config.acl_references)
        for policy in context.config.route_policies.values():
            references.extend((name, policy.name, source) for name, source in policy.acl_references)
        return tuple(
            missing_reference_diagnostic(
                context,
                rule_id=self.metadata.rule_id,
                source=source,
                object_name=object_name,
                full_message=f"ACL {name} is referenced but not defined.",
                snippet_message=f"ACL {name} was not found in the snippet.",
                explanation="No matching ACL definition exists in the supplied full configuration.",
                suggested_fix=f"Define ACL {name} or correct/remove the reference.",
            )
            for name, object_name, source in references
            if name not in context.config.acls
        )


class UnusedRoutePolicyRule:
    metadata = RuleMetadata("HUA-RPOL-002", "Unused route-policy", Severity.INFO, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        used: set[str] = set()
        if context.config.bgp is not None:
            for peer in context.config.bgp.peers.values():
                used.update(name for name, _ in (*peer.import_policies, *peer.export_policies))
        return tuple(
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                policy.source,
                policy.name,
                f"Route-policy {policy.name} has no supported reference.",
                "No BGP peer reference was found. Unsupported redistribution or other references "
                "may still exist in commands outside the beta parser coverage.",
                "Confirm all uses before removing the route-policy.",
                Confidence.GENERIC,
            )
            for policy in context.config.route_policies.values()
            if policy.name not in used
        )
