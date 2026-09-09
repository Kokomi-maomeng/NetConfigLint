"""Read-only release audit. Reports locations/categories, never secret values.

This bounded pattern scan complements manual review and dedicated secret scanners. It is
not a proof that arbitrary private data cannot exist. Historical identity findings are
reported separately from newly introduced metadata; no history is rewritten by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

PATTERNS = {
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})",
    "openai-key": rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}",
    "google-api-key": rb"AIza[0-9A-Za-z_-]{30,}",
    "private-key-block": rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----[\s\S]{40,}?"
    rb"-----END (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "windows-personal-path": rb"(?i)[a-z]:[\\/]+Users[\\/]+(?!Public\b|Default\b)[\w.-]+[\\/]",
    "unix-personal-path": rb"/(?:Users|home)/[A-Za-z0-9_.-]+/",
}
FORBIDDEN = {".env", "history.json", "id_rsa", "id_ed25519", "credentials.json", "auth.json"}
# Published by the Qt project on PyPI. Exact upstream bytes can contain build-worker
# paths, locale strings resembling tokens, and PEM parser markers. They are reported
# separately; application code and changed binaries never inherit this exception.
# https://pypi.org/pypi/PySide6_Essentials/6.11.2/json
REVIEWED_UPSTREAM_WHEELS = {
    "pyside6_essentials-6.11.2-cp310-abi3-win_amd64.whl": (
        "c8a29def77032773a30879f7f24415b5395ad08592d147c170824ef4c735dfc1"
    ),
}


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def scan_bytes(data: bytes) -> list[str]:
    # Check ASCII-compatible data plus both UTF-16 alignments found in PE resources.
    representations = [data]
    if b"\x00" in data:
        representations.extend(
            data[offset:].decode("utf-16-le", errors="ignore").encode("utf-8") for offset in (0, 1)
        )
    return [
        name
        for name, pattern in PATTERNS.items()
        if any(re.search(pattern, candidate) for candidate in representations)
    ]


def forbidden_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return (
        path.name.lower() in FORBIDDEN
        or path.name.upper().startswith("PRIVATE_")
        or any(part.lower() in {".git", ".venv", "__pycache__"} for part in path.parts)
        or "docs/audits/" in str(path)
    )


def audit_repository(root: Path, baseline: str) -> dict[str, Any]:
    files = git(root, "ls-files", "-z").decode("utf-8").split("\0")
    findings: list[dict[str, str]] = []
    current_count = 0
    for name in filter(None, files):
        path = root / name
        if not path.is_file():
            continue
        current_count += 1
        categories = scan_bytes(path.read_bytes())
        if forbidden_path(name):
            categories.append("private-artifact-path")
        findings.extend({"scope": "current", "path": name, "category": category} for category in categories)

    # Read every reachable blob from the intended release ancestry, not unrelated worktrees.
    objects = git(root, "rev-list", "--objects", "HEAD").decode("utf-8").splitlines()
    blob_count = 0
    process = subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        for entry in objects:
            oid, _, name = entry.partition(" ")
            process.stdin.write((oid + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").split()
            if len(header) != 3:
                raise RuntimeError("Unexpected Git object response")
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] != "blob":
                continue
            blob_count += 1
            categories = scan_bytes(data)
            if name and forbidden_path(name):
                categories.append("private-artifact-path")
            findings.extend(
                {"scope": "history", "object": oid, "path": name, "category": category}
                for category in categories
            )
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=15)

    prior = set(git(root, "rev-list", baseline).decode("ascii").splitlines())
    metadata = []
    records = git(root, "log", "--format=%H%x00%ae%x00%ce", "HEAD").decode("utf-8").splitlines()
    for record in records:
        oid, author, committer = record.split("\0")
        for role, email in (("author", author), ("committer", committer)):
            if not (email.endswith("@users.noreply.github.com") or email == "noreply@github.com"):
                metadata.append(
                    {
                        "commit": oid,
                        "role": role,
                        "predates_release": oid in prior,
                        "category": "non-noreply-identity",
                    }
                )
    return {
        "current_files": current_count,
        "history_blobs": blob_count,
        "findings": findings,
        "metadata_findings": metadata,
        "passed": not findings and all(item["predates_release"] for item in metadata),
    }


def upstream_binary_hashes(wheels: list[Path]) -> dict[str, str]:
    result = {}
    for wheel in wheels:
        expected = REVIEWED_UPSTREAM_WHEELS.get(wheel.name)
        if expected is None or hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
            raise ValueError("Upstream wheel is not an exact reviewed official distribution")
        with zipfile.ZipFile(wheel) as package:
            for entry in package.infolist():
                if entry.filename.startswith("PySide6/") and entry.filename.endswith(".dll"):
                    digest = hashlib.sha256(package.read(entry)).hexdigest()
                    result[entry.filename] = digest
                    if entry.filename.startswith("PySide6/plugins/"):
                        result[entry.filename.replace("PySide6/plugins/", "PySide6/qt-plugins/", 1)] = digest
    return result


def audit_archive(root: Path, archive: Path, *, upstream: dict[str, str] | None = None) -> dict[str, Any]:
    findings = []
    reviewed_upstream = []
    resource_mismatches = []
    expected = {
        path.relative_to(root).as_posix(): path
        for parent in (
            root / "netconfiglint/gui/qml",
            root / "netconfiglint/gui/i18n",
            root / "netconfiglint/resources",
            root / "netconfiglint/vendors/huawei/profiles",
        )
        for path in parent.rglob("*")
        if path.is_file() and path.suffix in {".qml", ".json", ".svg", ".ttf"}
    }
    seen = set()
    with zipfile.ZipFile(archive) as package:
        entries = [entry for entry in package.infolist() if not entry.is_dir()]
        for entry in entries:
            name = entry.filename
            data = package.read(entry)
            categories = scan_bytes(data)
            relative_binary = name[name.index("PySide6/") :] if "PySide6/" in name else ""
            if categories and upstream and upstream.get(relative_binary) == hashlib.sha256(data).hexdigest():
                reviewed_upstream.append(
                    {"path": name, "categories": categories, "reason": "exact-reviewed-official-wheel-binary"}
                )
                categories = []
            if forbidden_path(name):
                categories.append("private-artifact-path")
            findings.extend({"path": name, "category": category} for category in categories)
            relative = name[name.index("netconfiglint/") :] if "netconfiglint/" in name else ""
            if relative in expected:
                seen.add(relative)
                if data != expected[relative].read_bytes():
                    resource_mismatches.append(relative)
            elif (
                relative
                and any(
                    relative.startswith(prefix)
                    for prefix in (
                        "netconfiglint/gui/qml/",
                        "netconfiglint/gui/i18n/",
                        "netconfiglint/resources/",
                        "netconfiglint/vendors/huawei/profiles/",
                    )
                )
                and PurePosixPath(relative).suffix in {".qml", ".json", ".svg", ".ttf"}
            ):
                resource_mismatches.append(relative)
    missing = sorted(expected.keys() - seen)
    return {
        "files": len(entries),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "findings": findings,
        "reviewed_upstream_matches": reviewed_upstream,
        "resource_mismatches": sorted(resource_mismatches),
        "missing_resources": missing,
        "passed": not findings and not resource_mismatches and not missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", default="v1.4.0")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--upstream-wheel", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"repository": audit_repository(args.root, args.baseline)}
    if args.archive:
        report["archive"] = audit_archive(
            args.root, args.archive, upstream=upstream_binary_hashes(args.upstream_wheel)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: {"passed": value["passed"], "findings": len(value["findings"])}
                for key, value in report.items()
            }
        )
    )
    return 0 if all(value["passed"] for value in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
