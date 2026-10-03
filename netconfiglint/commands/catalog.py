"""Conservative command-family catalog.

A catalog hit identifies a documented CLI family, not valid arguments, support on
the detected model, effective configuration, or a completed semantic rule check.
Only commands left unparsed by a vendor normalizer reach this inventory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandFamily:
    name: str
    pattern: re.Pattern[str]
    source: str


_H3C_BASE = "https://www.h3c.com/en/Support/Resource_Center/EN/Home/Public/00-Public/Technical_Documents/Reference_Guides/Command_References/H3C_S6805_S9850_CRs_Release_6715-18388/00/"
_HUAWEI_BASE = "https://support.huawei.com/enterprise/en/doc/EDOC1100459368/8601ba7b/basic-configuration"


def _families(rows: tuple[tuple[str, str, str], ...]) -> tuple[CommandFamily, ...]:
    return tuple(
        CommandFamily(name, re.compile(r"^(?:undo\s+)?" + syntax + r"$", re.I), source)
        for name, syntax, source in rows
    )


H3C_FAMILIES = _families(
    (
        (
            "stp",
            r"stp\s+(?:mode\s+(?:mstp|rstp|stp|pvst)|(?:global\s+)?(?:enable|disable)|(?:global\s+)?(?:bpdu-protection|edged-port|root-protection|loop-protection|tc-protection|config-digest-snooping|mcheck|port-log)(?:\s+\S+)*|(?:region-configuration|instance\s+\d+|vlan\s+\d+)(?:\s+\S+)*)",
            "https://www.h3c.com/en/d_202511/2698540_294551_0.htm",
        ),
        (
            "stp_region",
            r"(?:region-name|revision-level|instance\s+\d+\s+vlan|active\s+region-configuration|check\s+region-configuration)(?:\s+\S+)*",
            "https://www.h3c.com/en/d_202511/2698540_294551_0.htm",
        ),
        (
            "info_center",
            r"info-center\s+(?:enable|loghost|source|logbuffer|logfile|timestamp|format|filter|synchronous|security-logfile|diagnostic-logfile|trace-logfile|syslog|logging)(?:\s+\S+)*",
            "https://www.h3c.com/en/d_201904/1174365_294551_0.htm",
        ),
        (
            "lldp",
            r"lldp\s+(?:global|enable|admin-status|notification|tlv-enable|timer|hold-multiplier|management-address|compliance|check-change-interval)(?:\s+\S+)*",
            _H3C_BASE,
        ),
        (
            "interface",
            r"(?:interface\s+\S+(?:\s+\S+)?|description\s+.+|shutdown|port\s+(?:link-type|access|trunk|hybrid|link-mode|link-aggregation|isolate|security|mirroring|speed|duplex|auto-power-down|bridge)(?:\s+\S+)*|mtu\s+\d+|jumboframe\s+enable(?:\s+\d+)?|speed\s+\S+|duplex\s+\S+|flow-control(?:\s+\S+)*)",
            _H3C_BASE,
        ),
        (
            "vlan",
            r"(?:vlan\s+\d+(?:\s+to\s+\d+)?|vlan\s+batch\s+.+|name\s+.+|description\s+.+|voice-vlan\s+\d+(?:\s+\S+)*|mac-vlan\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "irf",
            r"(?:irf\s+(?:member|domain|mac-address|auto-update|link-delay|priority)(?:\s+\S+)*|irf-port\s+\d+/[12]|irf-port-configuration\s+active|port\s+group\s+interface\s+\S+)",
            _H3C_BASE,
        ),
        (
            "ip",
            r"(?:ip\s+(?:address|route-static|forwarding|ttl|unreachables|redirects|verify|source|netstream|prefix-list|ip-prefix|vpn-instance|http|https|dns|host|domain|routing)(?:\s+\S+)*|ipv6\s+(?:address|route-static|enable|neighbor|prefix|nd|forwarding|source)(?:\s+\S+)*)",
            _H3C_BASE,
        ),
        (
            "routing",
            r"(?:ospf(?:v3)?(?:\s+\S+)*|isis(?:\s+\S+)*|bgp(?:\s+\S+)*|rip(?:ng)?(?:\s+\S+)*|route-policy\s+\S+.*|(?:ip|ipv6)\s+prefix-list\s+\S+.*|(?:import-route|filter-policy|network|peer|area|router-id|preference|maximum\s+load-balancing)(?:\s+\S+)*)",
            _H3C_BASE,
        ),
        (
            "acl",
            r"(?:acl(?:\s+\S+)*|rule\s+\d+\s+(?:permit|deny)(?:\s+\S+)*|packet-filter\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "qos",
            r"(?:qos\s+\S+.*|traffic\s+(?:classifier|behavior|policy|filter|remark|redirect|limit)(?:\s+\S+)*|if-match\s+\S+.*|car\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "services",
            r"(?:dhcp(?:v6)?\s+\S+.*|ntp-service\s+\S+.*|snmp-agent\s+\S+.*|ssh\s+\S+.*|sftp\s+\S+.*|telnet\s+\S+.*|ftp\s+\S+.*|radius\s+\S+.*|tacacs\s+\S+.*|local-user\s+\S+.*|domain\s+\S+.*|aaa\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "multicast",
            r"(?:igmp(?:-snooping)?\s+\S+.*|mld(?:-snooping)?\s+\S+.*|pim\s+\S+.*|multicast\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "vxlan_evpn",
            r"(?:vxlan\s+\S+.*|evpn\s+\S+.*|vsi\s+\S+.*|bridge-domain\s+\S+.*|l2vpn\s+\S+.*|tunnel\s+\S+.*|vtep\s+\S+.*)",
            _H3C_BASE,
        ),
        (
            "management",
            r"(?:line\s+\S+.*|user-interface\s+\S+.*|authentication-mode\s+\S+.*|protocol\s+inbound\s+\S+.*|user-role\s+\S+.*|password\s+\S+.*|service-type\s+\S+.*|authorization-attribute\s+\S+.*)",
            _H3C_BASE,
        ),
    )
)

HUAWEI_FAMILIES = _families(
    (
        (
            "stp",
            r"stp\s+(?:enable|disable|mode\s+(?:mstp|rstp|stp|vb-stp)|region-configuration|instance|bpdu-protection|edged-port|root-protection|loop-protection|tc-protection|priority|cost|port-priority|point-to-point|transmit-limit|timer|config-digest-snoop)(?:\s+\S+)*",
            "https://support.huawei.com/enterprise/en/doc/EDOC1100466171/c9a6630d/stp-rstp-mstp-configuration",
        ),
        (
            "info_center",
            r"info-center\s+(?:enable|loghost|source|logbuffer|logfile|timestamp|channel|console|monitor|trapbuffer|filter|synchronous|security-logfile)(?:\s+\S+)*",
            "https://info.support.huawei.com/enterprise/en/doc/EDOC1100439389/39d8e202/information-management-configuration-commands",
        ),
        (
            "lldp",
            r"lldp\s+(?:enable|admin-status|tlv-enable|management-address|notification|timer|hold-multiplier)(?:\s+\S+)*",
            _HUAWEI_BASE,
        ),
        (
            "interface",
            r"(?:interface\s+\S+(?:\s+\S+)?|description\s+.+|shutdown|port\s+(?:link-type|default|trunk|hybrid|link-aggregation|isolate|security|mirroring)(?:\s+\S+)*|eth-trunk\s+\d+|mtu\s+\d+|jumboframe\s+enable(?:\s+\d+)?|speed\s+\S+|duplex\s+\S+|flow-control(?:\s+\S+)*)",
            _HUAWEI_BASE,
        ),
        (
            "vlan",
            r"(?:vlan\s+\d+(?:\s+to\s+\d+)?|vlan\s+batch\s+.+|voice-vlan\s+\d+(?:\s+\S+)*)",
            _HUAWEI_BASE,
        ),
        (
            "ip",
            r"(?:ip\s+(?:address|route-static|forwarding|ttl|unreachables|redirects|netstream|ip-prefix|vpn-instance|http|https|dns|host|domain)(?:\s+\S+)*|ipv6\s+(?:address|route-static|enable|neighbor|prefix|nd|forwarding)(?:\s+\S+)*)",
            _HUAWEI_BASE,
        ),
        (
            "routing",
            r"(?:ospf(?:v3)?(?:\s+\S+)*|isis(?:\s+\S+)*|bgp(?:\s+\S+)*|rip(?:ng)?(?:\s+\S+)*|route-policy\s+\S+.*|(?:import-route|filter-policy|network|peer|area|router-id|preference)(?:\s+\S+)*)",
            _HUAWEI_BASE,
        ),
        (
            "acl",
            r"(?:acl(?:\s+\S+)*|rule\s+\d+\s+(?:permit|deny)(?:\s+\S+)*|traffic-filter\s+\S+.*)",
            _HUAWEI_BASE,
        ),
        (
            "qos",
            r"(?:qos\s+\S+.*|traffic\s+(?:classifier|behavior|policy|filter|remark|redirect|limit)(?:\s+\S+)*|if-match\s+\S+.*|car\s+\S+.*)",
            _HUAWEI_BASE,
        ),
        (
            "services",
            r"(?:dhcp(?:v6)?\s+\S+.*|ntp-service\s+\S+.*|snmp-agent\s+\S+.*|ssh\s+\S+.*|stelnet\s+\S+.*|sftp\s+\S+.*|telnet\s+\S+.*|ftp\s+\S+.*|radius\s+\S+.*|hwtacacs\s+\S+.*|local-user\s+\S+.*|aaa\s+\S+.*)",
            _HUAWEI_BASE,
        ),
        (
            "multicast",
            r"(?:igmp(?:-snooping)?\s+\S+.*|mld(?:-snooping)?\s+\S+.*|pim\s+\S+.*|multicast\s+\S+.*)",
            _HUAWEI_BASE,
        ),
        (
            "vxlan_evpn",
            r"(?:vxlan\s+\S+.*|evpn\s+\S+.*|vsi\s+\S+.*|bridge-domain\s+\S+.*|l2vpn\s+\S+.*|tunnel\s+\S+.*|vtep\s+\S+.*)",
            _HUAWEI_BASE,
        ),
        (
            "management",
            r"(?:user-interface\s+\S+.*|authentication-mode\s+\S+.*|protocol\s+inbound\s+\S+.*|user-role\s+\S+.*|password\s+\S+.*|service-type\s+\S+.*)",
            _HUAWEI_BASE,
        ),
    )
)


def catalogued_family(vendor: str, command: str) -> CommandFamily | None:
    families = (
        H3C_FAMILIES if vendor.lower() == "h3c" else HUAWEI_FAMILIES if vendor.lower() == "huawei" else ()
    )
    return next((entry for entry in families if entry.pattern.fullmatch(command.strip())), None)


def is_annotation(value: str) -> bool:
    """Identify prose-only lines; CLI arguments containing Chinese remain commands."""
    from netconfiglint.core.lexer import normalize_cli_line

    body = normalize_cli_line(value)[0].strip()
    return bool(
        body
        and (
            body.startswith(
                ("!", "//", ";", "\uff1b", "\u6ce8\uff1a", "\u5907\u6ce8\uff1a", "\u8bf4\u660e\uff1a")
            )
            or (body.startswith("#") and body != "#")
            or re.match(r"^[\u3400-\u9fff]", body)
        )
    )
