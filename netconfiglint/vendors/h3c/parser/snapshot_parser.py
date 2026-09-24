"""Conservative extraction of operational facts from H3C diagnostic sections."""

from __future__ import annotations

import re
from typing import Any

from netconfiglint.core.model import SnapshotEvidence

_HEADER = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$")
_BOUNDARY = re.compile(r"^\s*=+\s*$")
_PROMPT = re.compile(r"^\s*(?:<[^>]+>|\[[^]]+\])\s*(display\s+.+?)\s*$", re.I)


def _sections(source: str) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    lines = source.splitlines()
    result: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    for index, line in enumerate(lines):
        match = _HEADER.fullmatch(line)
        if not match or not match.group(1).strip():
            continue
        name = match.group(1).strip().lower()
        end = next(
            (value for value in range(index + 1, len(lines)) if _BOUNDARY.fullmatch(lines[value])),
            len(lines),
        )
        result.setdefault(name, (index + 1, [(i + 1, lines[i]) for i in range(index + 1, end)]))
    for index, line in enumerate(lines):
        match = _PROMPT.fullmatch(line)
        if match is None:
            continue
        name = match.group(1).strip().lower()
        end = next(
            (
                i
                for i in range(index + 1, len(lines))
                if _PROMPT.fullmatch(lines[i]) or _HEADER.fullmatch(lines[i])
            ),
            len(lines),
        )
        result.setdefault(name, (index + 1, [(i + 1, lines[i]) for i in range(index + 1, end)]))
    return result


class H3CSnapshotParser:
    def parse(self, source: str) -> SnapshotEvidence:
        evidence = SnapshotEvidence()
        sections = _sections(source)
        facts: dict[str, Any] = {}
        facts["observed_sections"] = len(sections)

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
                    temperature, warning = int(tokens[3]), int(tokens[5])
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
                        "selected": int(match.group(2)),
                        "unselected": int(match.group(3)),
                        "individual": int(match.group(4)),
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
                mlag.update(health=int(match.group(1)), health_line=number)
        for number, line in section("display m-lag drcp statistics"):
            match = re.search(r"(\d+)/(\d+)/(\d+)\s*$", line)
            if match:
                mlag.update(
                    received_normal=int(match.group(1)),
                    received_error=int(match.group(2)),
                    received_unknown=int(match.group(3)),
                    drcp_line=number,
                )
        facts["m_lag"] = mlag

        ospf_count = 0
        ospf_not_full: list[int] = []
        for number, line in section("display ospf peer"):
            match = re.match(r"^\s*\d+(?:\.\d+){3}\s+\d+(?:\.\d+){3}\s+\d+\s+\d+\s+(\S+)", line)
            if match:
                ospf_count += 1
                if not match.group(1).lower().startswith("full/"):
                    ospf_not_full.append(number)
        facts["ospf"] = {"neighbors": ospf_count, "not_full_lines": ospf_not_full}

        routes: dict[str, Any] = {}
        for number, line in section("display ip routing-table all-routes"):
            if match := re.search(r"Destinations\s*:\s*(\d+)\s+Routes\s*:\s*(\d+)", line, re.I):
                routes = {
                    "destinations": int(match.group(1)),
                    "routes": int(match.group(2)),
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
        for index, (number, line) in enumerate(alarm_section):
            if "current alarm information:" not in line.lower():
                continue
            following = next((text.strip() for _, text in alarm_section[index + 1 :] if text.strip()), "")
            if following and following.lower() not in {"none", "the transceiver is absent."}:
                active_alarms.append(number)
        facts["transceivers"] = {"active_alarm_lines": active_alarms}

        log_facts: dict[str, Any] = {}
        for number, line in section("display logbuffer size 512"):
            if match := re.search(r"Overwritten messages\s*:\s*(\d+)", line, re.I):
                log_facts = {"overwritten": int(match.group(1)), "line": number}
                break
        facts["log_buffer"] = log_facts
        evidence.operational = facts
        return evidence
