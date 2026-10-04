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
import shutil
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
    "pyside6_essentials-6.11.2-cp310-abi3-manylinux_2_34_x86_64.whl": (
        "aaf9f25f0f324874085fa5b26a610318db8a8e243cf85bb3e5400595191c7778"
    ),
    "pyside6_essentials-6.11.2-cp310-abi3-macosx_13_0_universal2.whl": (
        "77795c145202e65a78d88f7cd409d186e3ba23d159bdb3ba2dcd159ae5e5f0d9"
    ),
}

RESOURCE_PREFIXES = (
    "netconfiglint/commands/data/",
    "netconfiglint/gui/qml/",
    "netconfiglint/gui/i18n/",
    "netconfiglint/resources/",
    "netconfiglint/vendors/huawei/profiles/",
)
RESOURCE_SUFFIXES = {".qml", ".json", ".svg", ".ttf", ".png", ".ico"}
SUPPORT_RESOURCE = "netconfiglint/vendors/support_matrix.json"
DESKTOP_ARTIFACTS = {
    "windows": "compiled-desktop-windows-latest",
    "linux": "compiled-desktop-ubuntu-latest",
    "macos": "compiled-desktop-macos-latest",
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


def is_public_github_merge(oid: str, parents: str, committer: str, subject: str, release_head: str) -> bool:
    return (
        oid == release_head
        and len(parents.split()) == 2
        and committer == "noreply@github.com"
        and re.fullmatch(r"Merge pull request #\d+ from .+", subject) is not None
    )


def unsafe_package_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", str(path)) is not None


def expected_resources(root: Path) -> dict[str, bytes]:
    expected = {}
    for prefix in RESOURCE_PREFIXES:
        for path in (root / prefix).rglob("*"):
            if path.is_file() and path.suffix in RESOURCE_SUFFIXES:
                expected[path.relative_to(root).as_posix()] = path.read_bytes()
    if (root / SUPPORT_RESOURCE).is_file():
        expected[SUPPORT_RESOURCE] = (root / SUPPORT_RESOURCE).read_bytes()
    return expected


def resource_path(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    # The Debian deployment directory is itself /opt/netconfiglint. Select the
    # package resource anchor, rather than treating that outer directory as it.
    for anchor in re.finditer(r"(?:^|(?<=/))netconfiglint/", normalized):
        relative = "netconfiglint/" + normalized[anchor.end() :]
        if relative == SUPPORT_RESOURCE or (
            relative.startswith(RESOURCE_PREFIXES) and PurePosixPath(relative).suffix in RESOURCE_SUFFIXES
        ):
            return relative
    return None


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
    records = git(root, "log", "--format=%H%x00%P%x00%ae%x00%ce%x00%s", "HEAD").decode("utf-8").splitlines()
    release_head = git(root, "rev-parse", "HEAD").decode("ascii").strip()
    for record in records:
        oid, parents, author, committer, subject = record.split("\0")
        # GitHub's merge button may retain the account's public author email even
        # though GitHub itself commits the merge. This is already public Git
        # metadata, not an application/package secret. Only the release HEAD's
        # identifiable two-parent GitHub merge receives this narrow exception.
        public_github_merge = is_public_github_merge(oid, parents, committer, subject, release_head)
        for role, email in (("author", author), ("committer", committer)):
            if not (email.endswith("@users.noreply.github.com") or email == "noreply@github.com"):
                metadata.append(
                    {
                        "commit": oid,
                        "role": role,
                        "predates_release": oid in prior,
                        "public_github_merge_attribution": public_github_merge and role == "author",
                        "category": "non-noreply-identity",
                    }
                )
    return {
        "source_commit": release_head,
        "current_files": current_count,
        "history_blobs": blob_count,
        "findings": findings,
        "metadata_findings": metadata,
        "passed": not findings
        and all(item["predates_release"] or item["public_github_merge_attribution"] for item in metadata),
    }


def upstream_binary_hashes(wheels: list[Path]) -> dict[str, str]:
    result = {}
    basename_hashes: dict[str, set[str]] = {}
    for wheel in wheels:
        expected = REVIEWED_UPSTREAM_WHEELS.get(wheel.name)
        if expected is None or hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
            raise ValueError("Upstream wheel is not an exact reviewed official distribution")
        with zipfile.ZipFile(wheel) as package:
            for entry in package.infolist():
                if not entry.filename.startswith("PySide6/") or entry.is_dir():
                    continue
                data = package.read(entry)
                name = PurePosixPath(entry.filename).name
                # Modified or CPU-thinned native binaries never inherit this exception.
                framework_binary = (
                    ".framework/Versions/" in entry.filename
                    and re.fullmatch(r"Qt[A-Z]\w+", name) is not None
                    and data[:4] in {b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}
                )
                if re.search(r"\.(?:dll|pyd|dylib|so)(?:\.\d+)*$", name) or framework_binary:
                    digest = hashlib.sha256(data).hexdigest()
                    result[entry.filename] = digest
                    basename = name.lower()
                    basename_hashes.setdefault(basename, set()).add(digest)
                    if entry.filename.startswith("PySide6/plugins/"):
                        result[entry.filename.replace("PySide6/plugins/", "PySide6/qt-plugins/", 1)] = digest
                    binding = re.sub(r"\.(?:abi3|cpython-\d+[^.]*)\.so$", ".so", basename)
                    basename_hashes.setdefault(binding, set()).add(digest)
    # Nuitka relocates Qt runtime DLLs from PySide6/ to the application root and
    # normalizes their names to lowercase. Accept that layout only when a basename
    # maps to exactly one byte-identical reviewed upstream binary.
    for basename, digests in basename_hashes.items():
        if len(digests) == 1:
            result[f"basename:{basename}"] = next(iter(digests))
    return result


def resource_bytes_equal(path: str, packaged: bytes, source: bytes) -> bool:
    if PurePosixPath(path).suffix.lower() in {".json", ".qml", ".svg"}:
        return packaged.replace(b"\r\n", b"\n") == source.replace(b"\r\n", b"\n")
    return packaged == source


def audit_archive(root: Path, archive: Path, *, upstream: dict[str, str] | None = None) -> dict[str, Any]:
    findings = []
    reviewed_upstream = []
    resource_mismatches = []
    expected = expected_resources(root)
    seen = set()
    archive_names = set()
    duplicates = []
    with zipfile.ZipFile(archive) as package:
        entries = [entry for entry in package.infolist() if not entry.is_dir()]
        for entry in entries:
            name = entry.filename
            data = package.read(entry)
            categories = scan_bytes(data)
            relative_binary = name[name.index("PySide6/") :] if "PySide6/" in name else ""
            digest = hashlib.sha256(data).hexdigest()
            upstream_digest = None
            if upstream:
                upstream_digest = upstream.get(relative_binary)
                if upstream_digest is None:
                    upstream_digest = upstream.get(f"basename:{PurePosixPath(name).name.lower()}")
            if categories and upstream_digest == digest:
                reviewed_upstream.append(
                    {"path": name, "categories": categories, "reason": "exact-reviewed-official-wheel-binary"}
                )
                categories = []
            if forbidden_path(name):
                categories.append("private-artifact-path")
            if unsafe_package_path(name):
                categories.append("unsafe-package-path")
            if name in archive_names:
                duplicates.append(name)
            archive_names.add(name)
            findings.extend({"path": name, "category": category} for category in categories)
            relative = resource_path(name)
            if relative in expected:
                if relative in seen:
                    duplicates.append(relative)
                seen.add(relative)
                if not resource_bytes_equal(relative, data, expected[relative]):
                    resource_mismatches.append(relative)
            elif relative:
                resource_mismatches.append(relative)
    missing = sorted(expected.keys() - seen)
    return {
        "files": len(entries),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "findings": findings,
        "reviewed_upstream_matches": reviewed_upstream,
        "resource_mismatches": sorted(resource_mismatches),
        "missing_resources": missing,
        "duplicate_members": sorted(set(duplicates)),
        "passed": bool(entries)
        and not findings
        and not resource_mismatches
        and not missing
        and not duplicates,
    }


def _api_items(pages: Any, key: str) -> list[dict[str, Any]]:
    """Accept a single REST response or gh --paginate --slurp response pages."""
    values = pages if isinstance(pages, list) else [pages]
    return [item for page in values for item in page[key]]


def verify_ci_run(
    run: dict[str, Any],
    jobs: Any,
    artifacts: Any,
    *,
    workflow_id: int,
    repository: str,
    source_commit: str,
    run_id: int,
) -> dict[str, Any]:
    """A scoped retry or successful desktop job cannot qualify a release."""
    if (
        run.get("id") != run_id
        or run.get("workflow_id") != workflow_id
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") != source_commit
        or run.get("head_repository", {}).get("full_name") != repository
        or run.get("event") not in {"push", "workflow_dispatch"}
    ):
        raise ValueError("Source run must be a successful complete CI run at the release tag commit")
    expected_jobs = {
        f"{system} / Python {python} / Qt {qt}"
        for system in ("windows-latest", "ubuntu-latest", "macos-latest")
        for python in ("3.12.10", "3.13.15")
        for qt in ("6.9.0", "6.11.2")
    }
    expected_jobs.update(f"ubuntu-latest / Python 3.12.14 / Qt {qt}" for qt in ("6.9.0", "6.11.2"))
    expected_jobs.update(
        f"Actual build and desktop smoke / {system}"
        for system in ("windows-latest", "ubuntu-latest", "macos-latest")
    )
    expected_jobs.add("Static and dependency security gates")
    actual_jobs = _api_items(jobs, "jobs")
    if (
        len(actual_jobs) != len(expected_jobs)
        or {job.get("name") for job in actual_jobs} != expected_jobs
        or any(job.get("status") != "completed" or job.get("conclusion") != "success" for job in actual_jobs)
    ):
        raise ValueError("All 14 quality, three desktop and security CI jobs must pass")
    actual_artifacts = _api_items(artifacts, "artifacts")
    for name in DESKTOP_ARTIFACTS.values():
        matching = [item for item in actual_artifacts if item.get("name") == name]
        if len(matching) != 1 or matching[0].get("expired") or matching[0].get("size_in_bytes", 0) <= 0:
            raise ValueError("All three unexpired desktop artifacts must exist exactly once")
    return {
        "passed": True,
        "source_run_id": run_id,
        "source_commit": source_commit,
        "jobs": len(actual_jobs),
        "artifacts": sorted(DESKTOP_ARTIFACTS.values()),
    }


def release_asset_names(version: str, platform: str, names: list[str]) -> bool:
    patterns = {
        "windows": (
            rf"NetConfigLint-{re.escape(version)}-windows-x64(?:-unsigned)?\.msi",
            rf"NetConfigLint-{re.escape(version)}-windows-x64-portable\.zip",
        ),
        "linux": (rf"NetConfigLint-{re.escape(version)}-linux-amd64\.deb",),
        "macos": (rf"NetConfigLint-{re.escape(version)}-macos-(?:arm64|x64|universal)(?:-unsigned)?\.pkg",),
    }
    expected = patterns.get(platform, ())
    return len(names) == len(expected) and all(
        sum(re.fullmatch(pattern, name) is not None for name in names) == 1 for pattern in expected
    )


def verify_reused_artifacts(
    root: Path, artifact_root: Path, tag: str, staging: Path, run_id: int
) -> dict[str, Any]:
    if re.fullmatch(r"v\d+\.\d+\.\d+", tag) is None:
        raise ValueError("Release tag must be a semantic version beginning with v")
    source_commit = git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}").decode().strip()
    version = tag.removeprefix("v")
    verified = []
    for platform, artifact_name in DESKTOP_ARTIFACTS.items():
        folder = artifact_root / artifact_name
        source = json.loads((folder / "build/source-privacy.json").read_text(encoding="utf-8"))
        payload = json.loads((folder / "build/installer-payload-privacy.json").read_text(encoding="utf-8"))
        repository_audit = source["repository"]
        if (
            repository_audit.get("passed") is not True
            or repository_audit.get("source_commit") != source_commit
        ):
            raise ValueError("Source privacy report does not qualify the release tag commit")
        if (
            payload.get("passed") is not True
            or payload.get("source_commit") != source_commit
            or payload.get("application_version") != version
            or payload.get("platform") != platform
            or payload.get("source_run_id") != run_id
            or payload.get("installer", {}).get("passed") is not True
        ):
            raise ValueError("Native installer payload report does not qualify this CI run and release tag")
        declared = payload.get("release_files", [])
        names = [item["name"] for item in declared]
        actual = sorted(path.name for path in (folder / "release").iterdir() if path.is_file())
        if sorted(names) != actual or not release_asset_names(version, platform, names):
            raise ValueError("Release assets differ from the required audited native and portable packages")
        for item in declared:
            path = folder / "release" / item["name"]
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Downloaded release asset differs from its audited SHA-256")
            verified.append((path, item["sha256"]))
        installer = payload["installer"]
        if not any(
            item["name"] == installer.get("name") and item["sha256"] == installer.get("sha256")
            for item in declared
        ):
            raise ValueError("Native installer audit is not bound to a release asset")
        if platform == "windows":
            portable = json.loads((folder / "build/portable-privacy.json").read_text(encoding="utf-8"))
            if (
                portable["repository"].get("passed") is not True
                or portable["repository"].get("source_commit") != source_commit
                or portable["archive"].get("passed") is not True
                or not any(
                    item["name"].endswith(".zip") and item["sha256"] == portable["archive"].get("sha256")
                    for item in declared
                )
            ):
                raise ValueError("Portable ZIP does not have a matching successful privacy audit")
    staging.mkdir(parents=True, exist_ok=True)
    if any(staging.iterdir()):
        raise ValueError("Release staging directory must be empty")
    for path, _ in verified:
        shutil.copy2(path, staging / path.name)
    checksums = "".join(
        f"{digest}  {path.name}\n" for path, digest in sorted(verified, key=lambda item: item[0].name)
    )
    (staging / "SHA256SUMS.txt").write_text(checksums, encoding="ascii", newline="\n")
    return {
        "passed": True,
        "source_run_id": run_id,
        "source_commit": source_commit,
        "application_version": version,
        "release_files": [{"name": path.name, "sha256": digest} for path, digest in verified],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", default="v1.4.0")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--upstream-wheel", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-ci-run", type=Path)
    parser.add_argument("--ci-jobs", type=Path)
    parser.add_argument("--ci-artifacts", type=Path)
    parser.add_argument("--expected-workflow-id", type=int)
    parser.add_argument("--repository")
    parser.add_argument("--source-run-id", type=int)
    parser.add_argument("--release-tag")
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--staging-directory", type=Path)
    args = parser.parse_args()
    if args.verify_ci_run:
        expected = git(args.root, "rev-parse", "--verify", f"refs/tags/{args.release_tag}^{{commit}}")
        report = verify_ci_run(
            json.loads(args.verify_ci_run.read_text()),
            json.loads(args.ci_jobs.read_text()),
            json.loads(args.ci_artifacts.read_text()),
            workflow_id=args.expected_workflow_id,
            repository=args.repository,
            source_commit=expected.decode().strip(),
            run_id=args.source_run_id,
        )
    elif args.artifact_root:
        report = verify_reused_artifacts(
            args.root, args.artifact_root, args.release_tag, args.staging_directory, args.source_run_id
        )
    else:
        report = {"repository": audit_repository(args.root, args.baseline)}
        if args.archive:
            report["archive"] = audit_archive(
                args.root, args.archive, upstream=upstream_binary_hashes(args.upstream_wheel)
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    passed = (
        report.get("passed") is True
        if "passed" in report
        else all(value["passed"] for value in report.values())
    )
    print(json.dumps({"passed": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
