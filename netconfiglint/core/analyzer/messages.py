"""Bounded interpretation of network device messages and command errors.

These are hypotheses for investigation, never a claim that a root cause is proven.
"""

from __future__ import annotations

import re

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange

EventDefinition = tuple[str, str, Severity, str, str, str]

_COMMON_EVENTS: tuple[EventDefinition, ...] = (
    (
        r"(?:BGP|BGP/).{0,80}(?:down|idle|active|notification|reset|cease)",
        "BGP-PEER",
        Severity.WARNING,
        "BGP peer state changed",
        "A BGP event is reported; reachability, AS, authentication, policy or peer reset may cause it.",
        "Check both peer states and last errors; compare source, remote AS and reachability.",
    ),
    (
        r"(?:OSPF|OSPF/).{0,80}(?:down|init|exstart|exchange|mismatch|error)",
        "OSPF-ADJ",
        Severity.WARNING,
        "OSPF adjacency event",
        "An OSPF neighbor event is reported; this alone does not identify the faulty side.",
        "Compare area, network type, timers, MTU, authentication and interface status on both peers.",
    ),
    (
        r"(?:LACP|aggregation).{0,70}(?:unselected|individual|mismatch|timeout|failed)",
        "LACP",
        Severity.WARNING,
        "Aggregation member event",
        "An aggregation member may not be forwarding as part of the selected group.",
        "Compare LACP mode, partner system, member settings and physical state.",
    ),
    (
        r"(?:STP|MSTP).{0,70}(?:topology|tc|loop|bpdu|blocked)",
        "STP",
        Severity.WARNING,
        "Spanning tree event",
        "A topology or protection event is reported; an isolated event does not prove a loop.",
        "Check topology-change rate, blocked ports, BPDU guard and recent link changes.",
    ),
    (
        r"(?:duplicate|conflict).{0,60}(?:IP|address|ARP)|(?:IP|ARP).{0,60}(?:duplicate|conflict)",
        "IP-CONFLICT",
        Severity.WARNING,
        "Address conflict",
        "An address conflict is indicated; the message alone does not identify the owner.",
        "Correlate ARP/MAC tables, DHCP leases and both endpoint addresses.",
    ),
    (
        r"(?:interface|port|link).{0,60}(?:flap|flapping)|(?:flap|flapping).{0,45}(?:port|link)",
        "LINK-FLAP",
        Severity.WARNING,
        "Repeated link change",
        "Repeated link changes can disrupt neighbors and forwarding.",
        "Compare event timestamps, interface counters, optics, cable and peer-side logs.",
    ),
    (
        r"(?:link|interface|port).{0,65}(?:down|lost)|(?:down|lost).{0,40}(?:link|interface)",
        "LINK-DOWN",
        Severity.WARNING,
        "Interface link down",
        "A link is down; media, peer state and administrative shutdown are possible causes.",
        "Check current interface state, optics/cable, peer port and adjacent alarms.",
    ),
    (
        r"(?:CPU|memory|utilization).{0,65}(?:high|threshold|critical|exceed|alarm)",
        "RESOURCE",
        Severity.WARNING,
        "Device resource alarm",
        "A resource threshold is reported; one event does not establish sustained overload.",
        "Collect timed CPU/memory samples and correlate processes, traffic and protocol events.",
    ),
    (
        r"(?:temperature|fan|power|voltage).{0,70}(?:alarm|abnormal|failed|critical|high)|"
        r"(?:alarm|abnormal).{0,55}(?:temperature|fan|power)",
        "HARDWARE",
        Severity.ERROR,
        "Hardware or environment alarm",
        "A hardware/environment alarm is present in the supplied message.",
        "Check live device/environment output and the matching hardware maintenance guide.",
    ),
    (
        r"(?:%\s*)?(?:unrecognized|unknown|invalid|incomplete|ambiguous)\s+"
        r"(?:command|input|parameter)|错误\s*[:\uff1a]?\s*(?:命令|参数)|命令不完整|无法识别.*命令",
        "CLI-ERROR",
        Severity.WARNING,
        "Command rejected by device",
        "The device rejected a command. View, platform, release, license, syntax and privilege may matter.",
        "Record the command, view and caret position; check the matching device release.",
    ),
    (
        r"(?:authentication|login|password).{0,60}(?:fail|denied|reject)|"
        r"(?:fail|denied|reject).{0,45}(?:authentication|login)",
        "AUTH-FAIL",
        Severity.WARNING,
        "Authentication failure",
        "Authentication was rejected. The message alone does not prove a password error or an attack.",
        "Correlate source, account, AAA server reachability, policy and event frequency.",
    ),
)


def interpret_messages(source: str, vendor: str, *, include_unmatched: bool = True) -> tuple[Diagnostic, ...]:
    from netconfiglint.vendors.registry import get_vendor_plugin

    try:
        specific = get_vendor_plugin(vendor).message_events
    except ValueError:
        specific = ()
    events = (*specific, *_COMMON_EVENTS)
    diagnostics: list[Diagnostic] = []
    for number, line in enumerate(source.splitlines(), 1):
        checkpoint()
        text = line.strip()
        if not text or text.startswith(("#", "!")) or re.fullmatch(r"\s*\^\s*", text):
            continue
        if not include_unmatched and text.lower().startswith(("description ", "remark ")):
            continue
        for pattern, code, severity, title, explanation, fix in events:
            if re.search(pattern, text, re.IGNORECASE):
                diagnostics.append(
                    Diagnostic(
                        severity,
                        f"MSG-{code}",
                        SourceRange(number),
                        title,
                        f"{vendor} message: {title}.",
                        explanation,
                        fix,
                        Confidence.INFERRED,
                    )
                )
                break
        else:
            if include_unmatched:
                diagnostics.append(
                    Diagnostic(
                        Severity.UNKNOWN,
                        "MSG-UNCLASSIFIED",
                        SourceRange(number),
                        "Unclassified message",
                        "No supported interpretation matched this line.",
                        "The text is preserved; no cause can be inferred safely from this line alone.",
                        "Provide surrounding lines, timestamp, device model and software release.",
                        Confidence.LOW,
                    )
                )
    return tuple(diagnostics)
