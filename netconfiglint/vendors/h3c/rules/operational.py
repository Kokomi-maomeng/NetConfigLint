from __future__ import annotations

from typing import Any

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata


def _line(value: Any, fallback: int = 1) -> SourceRange:
    return SourceRange(int(value) if isinstance(value, int) and value > 0 else fallback)


class H3COperationalEvidenceRule:
    metadata = RuleMetadata("H3C-OPS-000", "H3C operational evidence", Severity.INFO, "H3C")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        facts = context.config.snapshot.operational
        if not facts:
            if context.mode.value != "snapshot":
                return ()
            return (
                Diagnostic(
                    Severity.UNKNOWN,
                    "H3C-OPS-011",
                    SourceRange(1),
                    "Operational state",
                    "No supported H3C operational command output was found.",
                    "Configuration syntax alone cannot prove live interface, neighbor, hardware, "
                    "or alarm state.",
                    "Collect a diagnostic bundle with device, environment, aggregation, M-LAG, OSPF, route, "
                    "LLDP, and transceiver outputs, then run snapshot mode again.",
                    Confidence.LOW,
                ),
            )
        ospf = facts.get("ospf", {})
        routes = facts.get("ipv4_routing_table", {})
        lldp = facts.get("lldp", {})
        groups = facts.get("link_aggregation", {}).get("groups", [])
        summary_source = _line(routes.get("line"))
        result = [
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                summary_source,
                "Operational snapshot",
                "H3C operational evidence was parsed from the diagnostic bundle.",
                f"Observed {ospf.get('neighbors', 0)} OSPF neighbor(s), "
                f"{routes.get('destinations', 0)} IPv4 destination(s), "
                f"{routes.get('routes', 0)} route(s), {lldp.get('neighbors', 0)} LLDP neighbor(s), "
                f"and {len(groups)} aggregation group(s).",
                "Treat this as the state at collection time; compare later captures to confirm trends.",
                Confidence.DOCUMENTED,
            )
        ]

        for key, label, rule_id in (
            ("hardware", "installed card", "H3C-OPS-001"),
            ("fans", "fan", "H3C-OPS-002"),
            ("power", "power module", "H3C-OPS-003"),
            ("temperature", "temperature sensor", "H3C-OPS-004"),
        ):
            for number in facts.get(key, {}).get("abnormal_lines", []):
                result.append(
                    Diagnostic(
                        Severity.ERROR,
                        rule_id,
                        _line(number),
                        label,
                        f"An abnormal {label} state is present in the collected output.",
                        "The value differs from the normal/healthy state or reaches the warning threshold.",
                        "Validate the component in the live device, inspect adjacent alarms, and follow the "
                        "hardware maintenance procedure.",
                        Confidence.DOCUMENTED,
                    )
                )
        for group in groups:
            if group.get("unselected", 0) or group.get("individual", 0):
                result.append(
                    Diagnostic(
                        Severity.WARNING,
                        "H3C-OPS-005",
                        _line(group.get("line")),
                        str(group.get("name", "Aggregation")),
                        "An aggregation has unselected or individual member ports.",
                        f"Selected={group.get('selected', 0)}, unselected={group.get('unselected', 0)}, "
                        f"individual={group.get('individual', 0)}.",
                        "Check member configuration, physical state, and LACP/static aggregation "
                        "consistency.",
                        Confidence.DOCUMENTED,
                    )
                )
        mlag = facts.get("m_lag", {})
        if (
            str(mlag.get("peer_link", "up")).lower() != "up"
            or str(mlag.get("keepalive", "up")).lower() != "up"
            or mlag.get("health", 0) != 0
        ):
            result.append(
                Diagnostic(
                    Severity.ERROR,
                    "H3C-OPS-006",
                    _line(mlag.get("health_line") or mlag.get("peer_line")),
                    "M-LAG",
                    "M-LAG peer-link, keepalive, or health state is abnormal.",
                    f"Peer-link={mlag.get('peer_link', 'unknown')}, "
                    f"keepalive={mlag.get('keepalive', 'unknown')}, "
                    f"health={mlag.get('health', 'unknown')}.",
                    "Inspect peer-link/keepalive reachability and the M-LAG "
                    "consistency/troubleshooting outputs.",
                    Confidence.DOCUMENTED,
                )
            )
        if mlag.get("received_error", 0):
            result.append(
                Diagnostic(
                    Severity.UNKNOWN,
                    "H3C-OPS-007",
                    _line(mlag.get("drcp_line")),
                    "M-LAG DRCP counters",
                    f"The cumulative DRCP receive-error counter is {mlag['received_error']}.",
                    "A cumulative counter does not prove a current fault without a second time-based sample.",
                    "Capture the counter again after a defined interval and investigate only if "
                    "it continues rising.",
                    Confidence.LOW,
                )
            )
        for number in facts.get("ospf", {}).get("not_full_lines", []):
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    "H3C-OPS-008",
                    _line(number),
                    "OSPF neighbor",
                    "An observed OSPF neighbor is not Full.",
                    "The collected neighbor table contains a non-Full adjacency.",
                    "Check interface state, timers, MTU, authentication, area, and network type "
                    "on both ends.",
                    Confidence.DOCUMENTED,
                )
            )
        for number in facts.get("transceivers", {}).get("active_alarm_lines", []):
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    "H3C-OPS-009",
                    _line(number),
                    "Transceiver",
                    "An active transceiver alarm is reported.",
                    "The alarm section contains a value other than None.",
                    "Check optical power, module compatibility, fiber path, and peer-side telemetry.",
                    Confidence.DOCUMENTED,
                )
            )
        log_buffer = facts.get("log_buffer", {})
        if log_buffer.get("overwritten", 0):
            result.append(
                Diagnostic(
                    Severity.INFO,
                    "H3C-OPS-010",
                    _line(log_buffer.get("line")),
                    "Log buffer",
                    f"The log buffer reports {log_buffer['overwritten']} overwritten message(s).",
                    "Older in-memory events are no longer present, so this bundle cannot prove "
                    "their content.",
                    "Use the external log host and compare collection intervals; increase buffer "
                    "size only after "
                    "assessing memory and logging policy.",
                    Confidence.DOCUMENTED,
                )
            )
        if context.config.metadata.get("saved_configuration_matches") == "false":
            result.append(
                Diagnostic(
                    Severity.WARNING,
                    "H3C-OPS-012",
                    SourceRange(1),
                    "Saved configuration",
                    "The current and saved configurations differ.",
                    "A reboot could restore a different configuration from the one currently running.",
                    "Review the exact diff and save only after change-control approval.",
                    Confidence.DOCUMENTED,
                )
            )
        return tuple(result)
