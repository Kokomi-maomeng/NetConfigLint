from __future__ import annotations

import ipaddress
from contextlib import suppress

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata


def _ospf_network(address: str, wildcard: str) -> ipaddress.IPv4Network | None:
    try:
        wildcard_int = int(ipaddress.IPv4Address(wildcard))
        mask = ipaddress.IPv4Address((2**32 - 1) ^ wildcard_int)
        return ipaddress.IPv4Network(f"{address}/{mask}", strict=False)
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return None


class OspfAreaAssociationRule:
    metadata = RuleMetadata("HUA-OSPF-001", "Invalid OSPF area network", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        result = []
        for process in context.config.ospf_processes.values():
            for network in process.networks:
                if network.area != "Unknown" and _ospf_network(network.address, network.wildcard):
                    continue
                severity = Severity.UNKNOWN if network.area == "Unknown" else Severity.ERROR
                result.append(
                    Diagnostic(
                        severity,
                        self.metadata.rule_id,
                        network.source,
                        f"OSPF {process.process_id}",
                        "The OSPF network cannot be associated with a valid area/network pair.",
                        "The area context is missing or the address/wildcard cannot be normalized.",
                        "Place the network under an OSPF area and verify its IPv4 wildcard mask.",
                        Confidence.VERIFIED if severity == Severity.ERROR else Confidence.GENERIC,
                    )
                )
        return tuple(result)


class OspfNoParticipatingInterfaceRule:
    metadata = RuleMetadata("HUA-OSPF-002", "No apparent OSPF interface", Severity.WARNING, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        interface_ips = []
        for interface in context.config.interfaces.values():
            for address, _, _ in interface.ip_addresses:
                with suppress(ValueError):
                    interface_ips.append(ipaddress.IPv4Address(address.split("/")[0]))
        result = []
        for process in context.config.ospf_processes.values():
            networks = [
                candidate
                for item in process.networks
                if (candidate := _ospf_network(item.address, item.wildcard)) is not None
            ]
            if any(ip in network for ip in interface_ips for network in networks):
                continue
            result.append(
                Diagnostic(
                    Severity.WARNING if networks else Severity.INFO,
                    self.metadata.rule_id,
                    process.source,
                    f"OSPF {process.process_id}",
                    "No interface can be shown to participate in this OSPF process.",
                    "Static configuration evidence contains no interface address matching an OSPF "
                    "network statement. Other activation mechanisms may exist.",
                    "Review OSPF activation and interface addresses; validate runtime state separately.",
                    Confidence.INFERRED,
                )
            )
        return tuple(result)
