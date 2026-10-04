"""Fail a release build on unqualified dependency drift; never upgrades an environment."""

import importlib.metadata
import json
import sys
import tomllib
from pathlib import Path


def check_application_version(root: Path) -> str:
    expected = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    actual = importlib.metadata.version("netconfiglint")
    if not isinstance(expected, str) or actual != expected:
        raise ValueError(
            f"Application metadata mismatch: {actual}, expected {expected}; reinstall editable metadata"
        )
    return actual


def check() -> dict[str, str]:
    versions = {"Python": ".".join(map(str, sys.version_info[:3]))}
    if versions["Python"] not in {"3.13.15"}:
        raise ValueError("Release Python must match the qualified 3.13.15 toolchain")
    root = Path(__file__).resolve().parents[1]
    versions["NetConfigLint"] = check_application_version(root)
    path = root / "constraints" / "release.txt"
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
