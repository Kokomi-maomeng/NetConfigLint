"""Conservative extraction of operational facts from H3C diagnostic sections."""

from __future__ import annotations

import re
from typing import Any

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.model import SnapshotEvidence
from netconfiglint.core.parser.numbers import bounded_integer

_HEADER = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$")
_BOUNDARY = re.compile(r"^\s*=+\s*$")
_PROMPT = re.compile(r"^\s*(?:<[^>]+>|\[[^]]+\])\s*(display\s+.+?)\s*$", re.I)


def _sections(source: str) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    result: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    active: list[tuple[int, str]] | None = None
    for number, line in enumerate(source.splitlines(), 1):
        checkpoint()
        match = _HEADER.fullmatch(line) or _PROMPT.fullmatch(line)
        if match and match.group(1).strip():
            name = match.group(1).strip().lower()
            # Keep the first capture; never merge states from different collection times.
            if name not in result:
                active = []
                result[name] = (number, active)
            else:
                active = None
        elif _BOUNDARY.fullmatch(line) or re.fullmatch(r"\s*(?:<[^>]+>|\[[^]]+\])\s*", line):
            active = None
        elif active is not None:
            active.append((number, line))
    return result


class H3CSnapshotParser:
    def parse(self, source: str) -> SnapshotEvidence:
        evidence = SnapshotEvidence()
        sections = _sections(source)
        facts: dict[str, Any] = {}
        facts["observed_sections"] = 0
        supported = {
            "display device verbose",
            "display fan",
            "display power",
            "display environment",
            "display link-aggregation summary",
            "display m-lag summary",
            "display m-lag system",
            "display m-lag drcp statistics",
            "display ospf peer",
            "display ip routing-table all-routes",
            "display lldp neighbor-information list",
            "display transceiver alarm interface",
            "display logbuffer size 512",
        }
        rejected: list[int] = []
        for name, (number, rows) in list(sections.items()):
            checkpoint()
            failed = any(
                re.search(
                    r"(?i)(?:^\s*(?:%\s*)?(?:error|failed|permission|access denied|unrecognized|"
                    r"incomplete command)|--+\s*more|truncat)",
                    text,
                )
                for _, text in rows
            )
            if name not in supported or failed or not any(text.strip() for _, text in rows):
                rejected.append(number)
                del sections[name]
        facts["unverified_section_lines"] = rejected

        def section(name: str) -> list[tuple[int, str]]:
            return sections.get(name, (0, []))[1]

        abnormal_hardware: list[int] = []
        for number, line in section("display device verbose"):
            match = re.match(r"^\s*\d+\s+(\S+)\s+(\S+)\s+\d+\s+", line)
            if (
                match
                and match.group(1).upper() != "NONE"
                and match.group(2).lower()
                not in {
                    "master",
                    "standby",
                    "normal",
                }
            ):
                abnormal_hardware.append(number)
        facts["hardware"] = {"abnormal_lines": abnormal_hardware}

        fan_abnormal = [
            number
            for number, line in section("display fan")
            if (match := re.search(r"State\s*:\s*(\S+)", line, re.I)) and match.group(1).lower() != "normal"
        ]
        facts["fans"] = {"abnormal_lines": fan_abnormal}

        power_abnormal: list[int] = []
        for number, line in section("display power"):
            match = re.match(r"^\s*\d+\s+(\S+)\s+(?:AC|DC)\b", line, re.I)
            if match and match.group(1).lower() != "normal":
                power_abnormal.append(number)
        facts["power"] = {"abnormal_lines": power_abnormal}

        hot: list[int] = []
        max_temperature: int | None = None
        for number, line in section("display environment"):
            tokens = line.split()
            if len(tokens) >= 7 and tokens[0].isdigit() and tokens[2].isdigit():
                try:
                    temperature, warning = bounded_integer(tokens[3]), bounded_integer(tokens[5])
                except ValueError:
                    continue
                max_temperature = (
                    temperature if max_temperature is None else max(max_temperature, temperature)
                )
                if temperature >= warning:
                    hot.append(number)
        facts["temperature"] = {"abnormal_lines": hot, "maximum_c": max_temperature}

        lag_rows: list[dict[str, Any]] = []
        for number, line in section("display link-aggregation summary"):
            match = re.match(r"^\s*(\S*AGG\d+)\s+\S+\s+.*?\s+(\d+)\s+(\d+)\s+(\d+)\s+\S+\s*$", line)
            if match:
                lag_rows.append(
                    {
                        "name": match.group(1),
                        "selected": bounded_integer(match.group(2)),
                        "unselected": bounded_integer(match.group(3)),
                        "individual": bounded_integer(match.group(4)),
                        "line": number,
                    }
                )
        facts["link_aggregation"] = {"groups": lag_rows}

        mlag: dict[str, Any] = {}
        for number, line in section("display m-lag summary"):
            if match := re.search(r"Peer-link interface state.*:\s*(\S+)", line, re.I):
                mlag.update(peer_link=match.group(1), peer_line=number)
            if match := re.search(r"Keepalive link state.*:\s*(\S+)", line, re.I):
                mlag.update(keepalive=match.group(1), keepalive_line=number)
        for number, line in section("display m-lag system"):
            if match := re.search(r"Health level\s*:\s*(\d+)", line, re.I):
                mlag.update(health=bounded_integer(match.group(1)), health_line=number)
        for number, line in section("display m-lag drcp statistics"):
            match = re.search(r"(\d+)/(\d+)/(\d+)\s*$", line)
            if match:
                mlag.update(
                    received_normal=bounded_integer(match.group(1)),
                    received_error=bounded_integer(match.group(2)),
                    received_unknown=bounded_integer(match.group(3)),
                    drcp_line=number,
                )
        facts["m_lag"] = mlag

        ospf_count = 0
        ospf_not_full: list[int] = []
        ospf_two_way: list[int] = []
        for number, line in section("display ospf peer"):
            row = re.match(r"^\s*\d+(?:\.\d+){3}\s+\d+(?:\.\d+){3}\s+\d+\s+\d+\s+", line)
            match = re.search(r"(?i)\b(Full|2-Way|2Way|Init|Down|ExStart|Exchange|Loading|Attempt)\b", line)
            if row and match:
                ospf_count += 1
                if match.group(1).lower().startswith(("2-way", "2way")):
                    ospf_two_way.append(number)
                elif not match.group(1).lower().startswith("full"):
                    ospf_not_full.append(number)
        facts["ospf"] = {
            "neighbors": ospf_count,
            "not_full_lines": ospf_not_full,
            "two_way_lines": ospf_two_way,
        }

        routes: dict[str, Any] = {}
        for number, line in section("display ip routing-table all-routes"):
            if match := re.search(r"Destinations\s*:\s*(\d+)\s+Routes\s*:\s*(\d+)", line, re.I):
                routes = {
                    "destinations": bounded_integer(match.group(1)),
                    "routes": bounded_integer(match.group(2)),
                    "line": number,
                }
                break
        facts["ipv4_routing_table"] = routes

        lldp_edges: list[dict[str, Any]] = []
        lldp_section = section("display lldp neighbor-information list")
        reverse_columns = any(line.strip().lower().startswith("system name") for _, line in lldp_section)
        for number, line in lldp_section:
            columns = line.split()
            if len(columns) < 4:
                continue
            local, chassis, port, remote = (
                (columns[1], columns[2], columns[3], columns[0])
                if reverse_columns
                else (columns[0], columns[1], columns[2], columns[3])
            )
            if re.fullmatch(r"[0-9a-f]{4}(?:-[0-9a-f]{4}){2}", chassis, re.I):
                lldp_edges.append(
                    {"local": local, "chassis": chassis, "port": port, "remote": remote, "line": number}
                )
        facts["lldp"] = {"neighbors": len(lldp_edges), "edges": lldp_edges}

        active_alarms: list[int] = []
        alarm_section = section("display transceiver alarm interface")
        following_alarm: int | None = None
        for number, line in alarm_section:
            checkpoint()
            if following_alarm is not None and line.strip():
                if line.strip().lower() not in {"none", "the transceiver is absent."}:
                    active_alarms.append(following_alarm)
                following_alarm = None
            if "current alarm information:" not in line.lower():
                continue
            following_alarm = number
        facts["transceivers"] = {"active_alarm_lines": active_alarms}

        log_facts: dict[str, Any] = {}
        for number, line in section("display logbuffer size 512"):
            if match := re.search(r"Overwritten messages\s*:\s*(\d+)", line, re.I):
                log_facts = {"overwritten": bounded_integer(match.group(1)), "line": number}
                break
        facts["log_buffer"] = log_facts
        # A command header alone is not evidence of a successfully parsed output format.
        families = (
            "hardware",
            "fans",
            "power",
            "temperature",
            "link_aggregation",
            "m_lag",
            "ospf",
            "ipv4_routing_table",
            "lldp",
            "transceivers",
            "log_buffer",
        )
        parsed = sum(bool(any(value for value in facts[name].values())) for name in families)
        # Normal hardware and fan output also provides positive state evidence.
        normal_rows = any(
            re.search(r"(?i)\b(?:normal|master|standby)\b", text)
            for name in ("display device verbose", "display fan", "display power")
            for _, text in section(name)
        )
        facts["observed_sections"] = parsed + (1 if normal_rows else 0)
        evidence.operational = facts
        return evidence
