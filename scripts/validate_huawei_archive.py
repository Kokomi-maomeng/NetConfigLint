"""Aggregate, privacy-safe validation of Huawei configs stored in a ZIP archive.

The script never writes extracted configurations and never emits archive entry names,
configuration lines, object names, addresses, or diagnostic prose.
"""

from __future__ import annotations

import argparse
import json
import statistics
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from netconfiglint import analyze


def validate_archive(path: Path, *, minimum_size: int = 1000) -> dict[str, Any]:
    rule_hits: Counter[str] = Counter()
    severity_hits: Counter[str] = Counter()
    diagnostic_counts: list[int] = []
    unparsed_ratios: list[float] = []
    failure_types: Counter[str] = Counter()
    candidates = 0

    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            normalized = entry.filename.replace("\\", "/")
            if "/Huawei_华为/" not in normalized or not normalized.lower().endswith(".cfg"):
                continue
            if entry.file_size < minimum_size:
                continue
            candidates += 1
            try:
                source = archive.read(entry).decode("utf-8-sig")
                result = analyze(source, "full", "huawei")
            except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
                failure_types[type(exc).__name__] += 1
                continue
            diagnostic_counts.append(len(result.diagnostics))
            rule_hits.update(item.rule_id for item in result.diagnostics)
            severity_hits.update(item.severity.value for item in result.diagnostics)
            denominator = max(1, sum(bool(line.strip()) for line in result.config.source_lines))
            unparsed_ratios.append(len(result.config.unparsed_lines) / denominator)

    analyzed = len(diagnostic_counts)
    return {
        "schema": 1,
        "candidate_configs": candidates,
        "analyzed_configs": analyzed,
        "failed_configs": sum(failure_types.values()),
        "failure_types": dict(sorted(failure_types.items())),
        "configs_with_multiple_diagnostics": sum(count > 1 for count in diagnostic_counts),
        "diagnostics_per_config": {
            "minimum": min(diagnostic_counts, default=0),
            "median": statistics.median(diagnostic_counts) if diagnostic_counts else 0,
            "maximum": max(diagnostic_counts, default=0),
        },
        "severity_hits": dict(sorted(severity_hits.items())),
        "rule_hits": dict(sorted(rule_hits.items())),
        "mean_unparsed_ratio": round(statistics.fmean(unparsed_ratios), 4) if unparsed_ratios else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--minimum-size", type=int, default=1000)
    arguments = parser.parse_args()
    if not arguments.archive.is_file():
        parser.error("archive does not exist or is not a file")
    print(
        json.dumps(
            validate_archive(arguments.archive, minimum_size=arguments.minimum_size),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
