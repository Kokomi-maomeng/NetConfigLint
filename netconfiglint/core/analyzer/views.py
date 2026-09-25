"""Operational-only view analysis without assuming access to a full configuration."""

from __future__ import annotations

from time import perf_counter

from netconfiglint.core.analyzer.models import AnalysisMode, AnalysisResult, VendorDetection
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.core.model import DeviceConfig
from netconfiglint.rules import RuleContext
from netconfiglint.vendors.h3c.parser.snapshot_parser import H3CSnapshotParser
from netconfiglint.vendors.h3c.rules.operational import H3COperationalEvidenceRule
from netconfiglint.vendors.huawei.parser.snapshot_parser import HuaweiSnapshotParser
from netconfiglint.vendors.registry import VendorPlugin


def analyze_view(
    source: str, plugin: VendorPlugin, detection: VendorDetection, started: float
) -> AnalysisResult:
    config = DeviceConfig(vendor=detection.vendor, source_lines=tuple(source.splitlines()))
    config.ignored_lines = [SourceRange(i) for i in range(1, len(config.source_lines) + 1)]
    config.snapshot = (
        H3CSnapshotParser().parse(source) if plugin.key == "h3c" else HuaweiSnapshotParser().parse(source)
    )
    diagnostics: list[Diagnostic] = []
    if plugin.key == "h3c":
        diagnostics.extend(
            H3COperationalEvidenceRule().evaluate(RuleContext(config, AnalysisMode.VIEW, detection))
        )
    else:
        snapshot = config.snapshot
        lldp_edges = snapshot.operational.get("lldp", {}).get("edges", [])
        observed = sum(
            (
                snapshot.ipv4_rib_present,
                snapshot.ipv6_rib_present,
                snapshot.bgp_peer_table_present,
                snapshot.interface_table_present,
            )
        )
        if observed or lldp_edges:
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
    return AnalysisResult(
        AnalysisMode.VIEW,
        detection,
        config,
        tuple(diagnostics),
        (perf_counter() - started) * 1000,
        len(config.source_lines),
    )
