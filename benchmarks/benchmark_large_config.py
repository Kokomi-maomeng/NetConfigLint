"""Repeatable, dependency-free large configuration benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
from time import perf_counter

from netconfiglint import analyze


def synthetic_config(interface_count: int) -> str:
    interfaces = "".join(
        f"interface GigabitEthernet1/{index // 48}/{index % 48}\n"
        " port link-type access\n"
        " port default vlan 10\n"
        for index in range(interface_count)
    )
    return f"sysname PERFORMANCE-SYNTHETIC\nvlan 10\n{interfaces}"


def run(interface_count: int, repeats: int) -> dict[str, float | int]:
    source = synthetic_config(interface_count)
    durations = []
    for _ in range(repeats):
        started = perf_counter()
        result = analyze(source, "full", "huawei")
        durations.append((perf_counter() - started) * 1000)
        if result.diagnostics:
            raise RuntimeError("Benchmark fixture unexpectedly produced diagnostics")
    return {
        "interfaces": interface_count,
        "lines": len(source.splitlines()),
        "bytes": len(source.encode("utf-8")),
        "repeats": repeats,
        "median_ms": round(statistics.median(durations), 3),
        "min_ms": round(min(durations), 3),
        "max_ms": round(max(durations), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interfaces", type=int, default=10_000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run(args.interfaces, args.repeats), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
