from __future__ import annotations

from collections.abc import Iterator

from netconfiglint.core.analyzer import AnalysisMode
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.model import BGPProcess
from netconfiglint.rules import RuleContext


def missing_reference_diagnostic(
    context: RuleContext,
    *,
    rule_id: str,
    source: SourceRange,
    object_name: str,
    full_message: str,
    snippet_message: str,
    explanation: str,
    suggested_fix: str,
) -> Diagnostic:
    if context.mode == AnalysisMode.SNIPPET:
        return Diagnostic(
            Severity.UNKNOWN,
            rule_id,
            source,
            object_name,
            snippet_message,
            "The referenced object was not found in the supplied snippet. A full configuration "
            "is required for definitive validation.",
            "Analyze the full running configuration before treating this as a configuration error.",
            Confidence.GENERIC,
        )
    return Diagnostic(
        Severity.ERROR,
        rule_id,
        source,
        object_name,
        full_message,
        explanation,
        suggested_fix,
        Confidence.VERIFIED,
    )


def bgp_processes(bgp: BGPProcess) -> Iterator[BGPProcess]:
    """Public and explicit Comware VPN transport scopes never share peer namespaces."""
    yield bgp
    yield from bgp.vpn_scopes.values()
