"""VRP operational interpretation owned by the Huawei plugin."""

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.rules import RuleContext, RuleMetadata


class HuaweiOperationalViewRule:
    metadata = RuleMetadata("HUA-VIEW-001", "Huawei operational view", Severity.INFO, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        snapshot = context.config.snapshot
        lldp_edges = snapshot.operational.get("lldp", {}).get("edges", [])
        if (
            snapshot.routes
            or snapshot.bgp_peers
            or snapshot.interfaces
            or lldp_edges
            or any(item.complete for item in snapshot.rib_captures)
        ):
            diagnostics.append(
                Diagnostic(
                    Severity.INFO,
                    "HUA-VIEW-001",
                    SourceRange(1),
                    "Operational view",
                    "Supported Huawei operational output was parsed.",
                    f"Observed {len(snapshot.routes)} routes, {len(snapshot.bgp_peers)} BGP peers "
                    f"and {len(snapshot.interfaces)} interfaces, plus {len(lldp_edges)} LLDP adjacency rows.",
                    "Use this as collection-time evidence; supply configuration for cause verification.",
                    Confidence.DOCUMENTED,
                )
            )
            for item in snapshot.interfaces.values():
                if item.physical_state.lower() == "down" or item.protocol_state.lower() == "down":
                    diagnostics.append(
                        Diagnostic(
                            Severity.WARNING,
                            "HUA-VIEW-002",
                            item.source,
                            item.name,
                            "An observed interface is down.",
                            "The snapshot cannot identify configuration, media or peer state as the cause.",
                            "Compare current interface detail, alarms, peer port and configuration.",
                            Confidence.INFERRED,
                        )
                    )
            for edge in lldp_edges:
                diagnostics.append(
                    Diagnostic(
                        Severity.INFO,
                        "HUA-VIEW-003",
                        SourceRange(edge["line"]),
                        edge["local"],
                        f"LLDP shows {edge['local']} connected to {edge['remote']} {edge['port']}.",
                        "This neighbor was observed at collection time; forwarding is not proven.",
                        "Compare peer-side LLDP and the intended cabling/topology plan.",
                        Confidence.DOCUMENTED,
                    )
                )
        else:
            diagnostics.append(
                Diagnostic(
                    Severity.UNKNOWN,
                    "HUA-VIEW-000",
                    SourceRange(1),
                    "Operational view",
                    "No supported operational table was recognized.",
                    "View parsing covers routing, BGP peer and interface tables in supported formats.",
                    "Supply complete command output with its display header and device model.",
                    Confidence.LOW,
                )
            )

        return tuple(diagnostics)


class HuaweiLldpEvidenceRule:
    metadata = RuleMetadata("HUA-VIEW-003", "Huawei LLDP evidence", Severity.INFO, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                Severity.INFO,
                self.metadata.rule_id,
                SourceRange(edge["line"]),
                edge["local"],
                f"LLDP shows {edge['local']} connected to {edge['remote']} {edge['port']}.",
                "Observed at collection time; forwarding is not proven.",
                "Compare peer-side LLDP and the intended topology.",
                Confidence.DOCUMENTED,
            )
            for edge in context.config.snapshot.operational.get("lldp", {}).get("edges", [])
        )
