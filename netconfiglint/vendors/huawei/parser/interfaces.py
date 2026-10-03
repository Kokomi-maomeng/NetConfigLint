"""Scoped Huawei interface identities shared by config and operational parsers."""

from __future__ import annotations

import re


def interface_name(value: str) -> str:
    """Join a separated type/number without guessing abbreviations or hardware."""
    # These numeric types have separate source witnesses in the three scoped
    # switch references. The list does not assert availability on every model.
    match = re.fullmatch(r"(10GE|25GE|40GE|100GE)\s*(\d+(?:[/.:]\d+)*)", value.strip(), re.I)
    if match:
        return match.group(1).upper() + match.group(2)
    types = (
        "Ethernet",
        "GigabitEthernet",
        "XGigabitEthernet",
        "GE",
        "MultiGE",
        "MEth",
        "Eth-Trunk",
        "LoopBack",
        "NULL",
        "Tunnel",
        "Vlanif",
        "Vbdif",
        "Nve",
        "fabric-port",
        "fc",
        "fcoe-port",
        "mtunnel",
        "Stack-Port",
        "virtual-ethernet",
        "Virtual-Template",
        "Serial",
    )
    pattern = "|".join(re.escape(item) for item in types)
    return re.sub(rf"^({pattern})\s+(?=\d+(?:[/.:]\d+)*$)", r"\1", value.strip(), flags=re.I)
