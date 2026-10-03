"""Audit resources, privacy and actual native installer contents before upload.

Only byte-identical binaries from exact reviewed Qt wheels inherit an exception.
Reports contain categories and relative paths, never matching secret values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

if __package__:
    from .audit_release import (
        expected_resources,
        forbidden_path,
        git,
        release_asset_names,
        resource_bytes_equal,
        resource_path,
        scan_bytes,
        upstream_binary_hashes,
    )
else:
    from audit_release import (
        expected_resources,
        forbidden_path,
        git,
        release_asset_names,
        resource_bytes_equal,
        resource_path,
        scan_bytes,
        upstream_binary_hashes,
    )


def inventory(payload: Path) -> dict[str, dict[str, str]]:
    """Preserve links as links, rejecting any target outside the payload."""
    if payload.is_symlink() or not payload.is_dir():
        raise ValueError("A real installer payload directory is required")
    resolved = payload.resolve()
    result = {}
    for path in sorted(payload.rglob("*")):
        name = path.relative_to(payload).as_posix()
        if path.is_symlink():
            if not path.exists() or not path.resolve().is_relative_to(resolved):
                raise ValueError("Installer payload contains a link outside its root")
            result[name] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            result[name] = {"kind": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            if os.name != "nt":
                result[name]["mode"] = f"{stat.S_IMODE(path.stat().st_mode):04o}"
    if not result:
        raise ValueError("Installer payload is empty")
    return result


def audit(payload: Path, wheels: list[Path], root: Path | None = None) -> dict[str, Any]:
    upstream = upstream_binary_hashes(wheels) if wheels else {}
    records = inventory(payload)
    expected = expected_resources(root) if root else {}
    findings = []
    reviewed = []
    mismatches = []
    seen = set()
    for name, record in records.items():
        path = payload / name
        if record["kind"] == "symlink" and not path.is_file():
            continue
        data = path.read_bytes()
        categories = scan_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        if categories and upstream.get(f"basename:{path.name.lower()}") == digest:
            reviewed.append(
                {"path": name, "categories": categories, "reason": "exact-reviewed-official-wheel-binary"}
            )
            categories = []
        if forbidden_path(name):
            categories.append("private-artifact-path")
        findings.extend({"path": name, "category": category} for category in categories)
        relative = resource_path(name) if root else None
        if relative:
            if relative in seen:
                mismatches.append(relative)
            seen.add(relative)
            if relative not in expected or not resource_bytes_equal(relative, data, expected[relative]):
                mismatches.append(relative)
    missing = sorted(expected.keys() - seen)
    return {
        "files": len(records),
        "findings": findings,
        "reviewed_upstream": reviewed,
        "resource_mismatches": sorted(set(mismatches)),
        "missing_resources": missing,
        "passed": not findings and not mismatches and not missing,
    }


def unpack_installer(installer: Path, temporary: Path, platform: str) -> Path:
    """Use each OS's native administrative/data extraction, never install the app."""
    if platform == "linux":
        extracted = temporary / "payload"
        subprocess.run(["dpkg-deb", "--extract", str(installer), str(extracted)], check=True)
        subprocess.run(["dpkg-deb", "--control", str(installer), str(extracted / "DEBIAN")], check=True)
        return extracted
    if platform == "macos":
        expanded = temporary / "expanded"
        subprocess.run(["pkgutil", "--expand-full", str(installer), str(expanded)], check=True)
        payloads = [path for path in expanded.rglob("Payload") if path.is_dir()]
        if len(payloads) != 1:
            raise ValueError("Expected one macOS component installer payload")
        return payloads[0]
    if platform == "windows":
        extracted = temporary / "administrative"
        extracted.mkdir()
        subprocess.run(
            ["msiexec.exe", "/a", str(installer), "/qn", "/norestart", f"TARGETDIR={extracted}"],
            check=True,
        )
        executables = list(extracted.rglob("NetConfigLint.exe"))
        if len(executables) != 1:
            raise ValueError("Expected one administrative MSI application payload")
        payload = executables[0].parent
        # An administrative image also includes its installation database.
        extras = [
            path
            for path in extracted.rglob("*")
            if path.is_file()
            and not path.is_relative_to(payload)
            and not (path.parent == extracted and path.name == installer.name)
        ]
        if extras:
            raise ValueError("Unexpected files outside the MSI application payload")
        return payload
    raise ValueError("Unsupported native installer platform")


def audit_installer(
    installer: Path, prepared: Path, platform: str, wheels: list[Path], root: Path
) -> dict[str, Any]:
    expected = inventory(prepared)
    outer_findings = [
        {"path": installer.name, "category": name} for name in scan_bytes(installer.read_bytes())
    ]
    with tempfile.TemporaryDirectory(prefix="netconfiglint-payload-audit-") as directory:
        extracted = unpack_installer(installer.resolve(), Path(directory), platform)
        actual = inventory(extracted)
        changed = sorted(
            name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name)
        )
        payload = audit(extracted, wheels, root)
    return {
        "name": installer.name,
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "prepared_files": len(expected),
        "extracted_files": len(actual),
        "payload_mismatches": changed,
        "findings": outer_findings,
        "payload": payload,
        "passed": not changed and not outer_findings and payload["passed"],
    }


def audit_release_payload(
    payload: Path,
    wheels: list[Path],
    root: Path,
    platform: str,
    release: Path,
    installer: Path,
    run_id: int,
) -> dict[str, Any]:
    result = audit(payload, wheels, root)
    source_commit = git(root, "rev-parse", "HEAD").decode().strip()
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    manifests = [
        path
        for path in payload.rglob("*")
        if path.name in {"SBOM.json", "NetConfigLint-SBOM.json"} and path.is_file()
    ]
    if len(manifests) != 1:
        raise ValueError("Expected one final application inventory in the installer payload")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest.get("source_commit") != source_commit or manifest.get("application_version") != version:
        raise ValueError("Installer inventory differs from the checked-out application commit/version")
    assets = sorted(path for path in release.iterdir() if path.suffix in {".zip", ".msi", ".deb", ".pkg"})
    if not release_asset_names(version, platform, [path.name for path in assets]):
        raise ValueError("Expected exactly the native installer and platform's required portable package")
    if installer.is_symlink() or installer.resolve() not in {path.resolve() for path in assets}:
        raise ValueError("Audited installer must be one of this build's release assets")
    result.update(
        {
            "source_commit": source_commit,
            "application_version": version,
            "platform": platform,
            "source_run_id": run_id,
            "release_files": [
                {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in assets
            ],
            "installer": audit_installer(installer, payload, platform, wheels, root),
        }
    )
    result["passed"] = result["passed"] and result["installer"]["passed"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--platform", choices=("windows", "linux", "macos"), required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--release-directory", type=Path, default=Path("release"))
    parser.add_argument("--source-run-id", type=int, default=int(os.environ.get("GITHUB_RUN_ID", "0")))
    parser.add_argument("--upstream-wheel", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_release_payload(
        args.payload,
        args.upstream_wheel,
        args.root,
        args.platform,
        args.release_directory,
        args.installer,
        args.source_run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "findings": len(result["findings"])}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
