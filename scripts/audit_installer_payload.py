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
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

if __package__:
    from .audit_release import (
        PATTERNS,
        expected_resources,
        forbidden_path,
        git,
        release_asset_names,
        resource_bytes_equal,
        resource_path,
        scan_bytes,
        upstream_binary_hashes,
    )
    from .native_privacy_provenance import IndependentRuntimeProvenance
else:
    from audit_release import (
        PATTERNS,
        expected_resources,
        forbidden_path,
        git,
        release_asset_names,
        resource_bytes_equal,
        resource_path,
        scan_bytes,
        upstream_binary_hashes,
    )
    from native_privacy_provenance import IndependentRuntimeProvenance


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


def audit(
    payload: Path,
    wheels: list[Path],
    root: Path | None = None,
    provenance: IndependentRuntimeProvenance | None = None,
) -> dict[str, Any]:
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
        if categories and provenance and (proof := provenance.match(name, data, payload)):
            reviewed.append({"path": name, "categories": categories, **proof})
            categories = []
        if forbidden_path(name):
            categories.append("private-artifact-path")
        for category in categories:
            finding: dict[str, Any] = {"path": name, "category": category}
            if provenance:
                if category == "unix-personal-path":
                    finding["path_sources"] = provenance.path_classifications(data)
                if replay := provenance.replay_failures.get((name, digest)):
                    finding["replay"] = replay
            findings.append(finding)
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
    installer: Path,
    prepared: Path,
    platform: str,
    wheels: list[Path],
    root: Path,
    provenance: IndependentRuntimeProvenance | None = None,
) -> dict[str, Any]:
    expected = inventory(prepared)
    outer_findings = [
        {"path": installer.name, "category": name} for name in scan_bytes(installer.read_bytes())
    ]
    if provenance:
        for finding in outer_findings:
            if finding["category"] == "unix-personal-path":
                finding["path_sources"] = provenance.path_classifications(installer.read_bytes())
    with tempfile.TemporaryDirectory(prefix="netconfiglint-payload-audit-") as directory:
        extracted = unpack_installer(installer.resolve(), Path(directory), platform)
        actual = inventory(extracted)
        changed = sorted(
            name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name)
        )
        payload = audit(extracted, wheels, root, provenance)
    return {
        "name": installer.name,
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "prepared_files": len(expected),
        "extracted_files": len(actual),
        "payload_mismatches": changed,
        "payload_mismatch_details": [
            {
                "path": name,
                "prepared_sha256": expected.get(name, {}).get("sha256"),
                "extracted_sha256": actual.get(name, {}).get("sha256"),
                "prepared_mode": expected.get(name, {}).get("mode"),
                "extracted_mode": actual.get(name, {}).get("mode"),
            }
            for name in changed
        ],
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
    python_archive: Path | None = None,
    patcher_wheel: Path | None = None,
) -> dict[str, Any]:
    provenance = (
        IndependentRuntimeProvenance(platform, python_archive, wheels, patcher_wheel)
        if python_archive
        else None
    )
    result = audit(payload, wheels, root, provenance)
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
            "installer": audit_installer(installer, payload, platform, wheels, root, provenance),
        }
    )
    result["passed"] = result["passed"] and result["installer"]["passed"]
    return result


def failure_diagnostics(
    result: dict[str, Any], prepared: Path, root: Path, wheels: list[Path]
) -> list[dict[str, Any]]:
    """Log known public modules and digests, hiding arbitrary payload filenames."""
    upstream = upstream_binary_hashes(wheels) if wheels else {}
    native_names = {key.removeprefix("basename:").lower() for key in upstream if key.startswith("basename:")}
    public_resources = expected_resources(root)
    fixed_names = {
        "netconfiglint",
        "netconfiglint.exe",
        "netconfiglintapp",
        "sbom.json",
        "netconfiglint-sbom.json",
        "license",
        "third_party_notices.md",
    }

    def module(name: str) -> str:
        relative = resource_path(name)
        if relative in public_resources:
            return relative
        basename = PurePosixPath(name).name
        if basename.lower() in native_names and not scan_bytes(basename.encode()):
            return "PySide6/" + basename
        if basename.lower() in fixed_names:
            return basename
        if basename in {"Python", "libpython3.13.so.1.0"} or (
            basename.endswith(".so") and basename.removesuffix(".so") in sys.stdlib_module_names
        ):
            return "CPython/" + basename
        if name == "DEBIAN/control":
            return name
        return "unclassified-payload-file"

    diagnostics = []

    def add(name: str, category: str, **details: Any) -> None:
        path = prepared / name
        digest = None
        if path.resolve().is_relative_to(prepared.resolve()) and path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        diagnostics.append({"module": module(name), "category": category, "sha256": digest, **details})

    installer = result.get("installer", {})
    extracted = installer.get("payload", {})
    for payload in (result, extracted):
        for finding in payload.get("findings", []):
            category = finding["category"]
            if category not in PATTERNS and category != "private-artifact-path":
                category = "unclassified-privacy-finding"
            add(
                finding["path"],
                category,
                **{key: finding[key] for key in ("path_sources", "replay") if key in finding},
            )
        for name in payload.get("resource_mismatches", []):
            add(name, "resource-content-mismatch")
        for name in payload.get("missing_resources", []):
            add(name, "missing-resource")
    for mismatch in installer.get("payload_mismatch_details", []):
        add(
            mismatch["path"],
            "native-payload-mismatch",
            **{
                key: mismatch[key]
                for key in ("prepared_sha256", "extracted_sha256", "prepared_mode", "extracted_mode")
            },
        )
    for finding in installer.get("findings", []):
        diagnostics.append(
            {
                "module": "native-installer",
                "category": finding["category"],
                "sha256": installer.get("sha256"),
                **{key: finding[key] for key in ("path_sources",) if key in finding},
            }
        )
    # A byte scan can occur on both prepared and extracted copies. Log one row.
    return list({json.dumps(row, sort_keys=True): row for row in diagnostics}.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--platform", choices=("windows", "linux", "macos"), required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--release-directory", type=Path, default=Path("release"))
    parser.add_argument("--source-run-id", type=int, default=int(os.environ.get("GITHUB_RUN_ID", "0")))
    parser.add_argument("--upstream-wheel", type=Path, action="append", default=[])
    parser.add_argument("--upstream-python-archive", type=Path)
    parser.add_argument("--reviewed-patcher-wheel", type=Path)
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
        args.upstream_python_archive,
        args.reviewed_patcher_wheel,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    summary = {"passed": result["passed"], "findings": len(result["findings"])}
    if not result["passed"]:
        summary["diagnostics"] = failure_diagnostics(result, args.payload, args.root, args.upstream_wheel)
    print(json.dumps(summary))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
