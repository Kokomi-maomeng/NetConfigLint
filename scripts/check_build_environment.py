"""Fail a release build on unqualified dependency drift; never upgrades an environment."""

import importlib.metadata
import json
import sys
from pathlib import Path


def check() -> dict[str, str]:
    versions = {"Python": ".".join(map(str, sys.version_info[:3]))}
    if versions["Python"] not in {"3.13.2"}:
        raise ValueError("Release Python must match the qualified 3.13.2 toolchain")
    path = Path(__file__).resolve().parents[1] / "constraints" / "release.txt"
    for line in path.read_text("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, required = line.split("==")
        actual = importlib.metadata.version(name)
        if actual != required:
            raise ValueError(f"Release dependency mismatch: {name} {actual}, expected {required}")
        versions[name] = actual
    return versions


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
