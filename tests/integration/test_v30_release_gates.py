"""Release qualification must bind a complete CI run to exact audited packages."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts import audit_installer_payload as payload_auditor
from scripts import audit_release as auditor


def qualified_run() -> tuple[dict, dict, dict]:
    run = {
        "id": 44,
        "workflow_id": 7,
        "status": "completed",
        "conclusion": "success",
        "head_sha": "a" * 40,
        "head_repository": {"full_name": "example/project"},
        "event": "workflow_dispatch",
        "head_branch": "codex/release-v30",
    }
    names = [
        f"{system} / Python {python} / Qt {qt}"
        for system in ("windows-latest", "ubuntu-latest", "macos-latest")
        for python in ("3.12.10", "3.13.15")
        for qt in ("6.9.0", "6.11.2")
    ]
    names += [f"ubuntu-latest / Python 3.12.14 / Qt {qt}" for qt in ("6.9.0", "6.11.2")]
    names += [
        f"Actual build and desktop smoke / {system}"
        for system in ("windows-latest", "ubuntu-latest", "macos-latest")
    ]
    names += ["Static and dependency security gates"]
    jobs = {"jobs": [{"name": name, "status": "completed", "conclusion": "success"} for name in names]}
    artifacts = {
        "artifacts": [
            {"name": name, "expired": False, "size_in_bytes": 12}
            for name in auditor.DESKTOP_ARTIFACTS.values()
        ]
    }
    return run, jobs, artifacts


def verify_run(run: dict, jobs: dict | list, artifacts: dict | list) -> dict:
    return auditor.verify_ci_run(
        run, jobs, artifacts, workflow_id=7, repository="example/project", source_commit="a" * 40, run_id=44
    )


def test_complete_ci_from_codex_branch_can_qualify_without_rebuilding() -> None:
    run, jobs, artifacts = qualified_run()
    result = verify_run(run, [jobs], [artifacts])
    assert result["passed"] and result["jobs"] == 18


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-sha",
        "wrong-workflow",
        "failed-run",
        "unfinished",
        "foreign-repo",
        "pull-request",
        "wrong-id",
        "scoped-retry",
        "failed-job",
        "skipped-job",
        "missing-artifact",
        "expired-artifact",
        "duplicate-artifact",
    ],
)
def test_ci_reuse_rejects_unqualified_run(mutation: str) -> None:
    run, jobs, artifacts = qualified_run()
    if mutation == "wrong-sha":
        run["head_sha"] = "b" * 40
    elif mutation == "wrong-workflow":
        run["workflow_id"] = 8
    elif mutation == "failed-run":
        run["conclusion"] = "failure"
    elif mutation == "unfinished":
        run["status"] = "in_progress"
    elif mutation == "foreign-repo":
        run["head_repository"]["full_name"] = "foreign/project"
    elif mutation == "pull-request":
        run["event"] = "pull_request"
    elif mutation == "wrong-id":
        run["id"] = 45
    elif mutation == "scoped-retry":
        jobs["jobs"] = jobs["jobs"][-3:]
    elif mutation in {"failed-job", "skipped-job"}:
        jobs["jobs"][0]["conclusion"] = "failure" if mutation == "failed-job" else "skipped"
    elif mutation == "missing-artifact":
        artifacts["artifacts"].pop()
    elif mutation == "expired-artifact":
        artifacts["artifacts"][0]["expired"] = True
    else:
        artifacts["artifacts"].append(artifacts["artifacts"][0].copy())
    with pytest.raises(ValueError):
        verify_run(run, jobs, artifacts)


@pytest.mark.parametrize(
    "member",
    [
        "PySide6/Qt/lib/libQt6Core.so.6",
        "PySide6/QtCore.abi3.so",
        "PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
    ],
)
def test_native_wheel_exceptions_require_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    wheel = tmp_path / "reviewed-test-only.whl"
    binary = (
        (b"\xcf\xfa\xed\xfe" if member.endswith("/QtCore") else b"\x7fELF") + b"/" + b"home/" + b"qt-build/"
    )
    with zipfile.ZipFile(wheel, "w") as package:
        package.writestr(member, binary)
        package.writestr("PySide6/private.txt", binary)
    monkeypatch.setitem(
        auditor.REVIEWED_UPSTREAM_WHEELS, wheel.name, hashlib.sha256(wheel.read_bytes()).hexdigest()
    )
    hashes = auditor.upstream_binary_hashes([wheel])
    assert "PySide6/private.txt" not in hashes
    original_name = Path(member).name
    normalized = "QtCore.so" if original_name == "QtCore.abi3.so" else original_name
    payload = tmp_path / "payload"
    payload.mkdir()
    target = payload / normalized
    target.write_bytes(binary)
    assert payload_auditor.audit(payload, [wheel])["passed"]
    target.write_bytes(binary + b"modified")
    result = payload_auditor.audit(payload, [wheel])
    assert not result["passed"]
    assert result["findings"][0]["category"] == "unix-personal-path"


def test_payload_gate_checks_support_inventory_and_forbidden_private_files(tmp_path: Path) -> None:
    root = tmp_path / "source"
    source = root / auditor.SUPPORT_RESOURCE
    source.parent.mkdir(parents=True)
    source.write_text('{"revision":3}', encoding="utf-8")
    payload = tmp_path / "payload"
    target = payload / "Contents/MacOS" / auditor.SUPPORT_RESOURCE
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    assert payload_auditor.audit(payload, [], root)["passed"]
    target.write_text('{"revision":2}', encoding="utf-8")
    (payload / "history.json").write_text("[]", encoding="utf-8")
    result = payload_auditor.audit(payload, [], root)
    assert not result["passed"] and result["resource_mismatches"] == [auditor.SUPPORT_RESOURCE]
    assert {item["category"] for item in result["findings"]} == {"private-artifact-path"}
    target.unlink()
    assert payload_auditor.audit(payload, [], root)["missing_resources"] == [auditor.SUPPORT_RESOURCE]


def test_debian_outer_application_directory_does_not_hide_packaged_resources(tmp_path: Path) -> None:
    resource = "netconfiglint/gui/qml/Main.qml"
    source = tmp_path / "source" / resource
    source.parent.mkdir(parents=True)
    source.write_text("Item {}", encoding="utf-8")
    payload = tmp_path / "payload"
    deployed = payload / "opt/netconfiglint" / resource
    deployed.parent.mkdir(parents=True)
    deployed.write_bytes(source.read_bytes())
    assert auditor.resource_path(deployed.relative_to(payload).as_posix()) == resource
    assert payload_auditor.audit(payload, [], tmp_path / "source")["passed"]
    deployed.write_text("Item { visible: false }", encoding="utf-8")
    result = payload_auditor.audit(payload, [], tmp_path / "source")
    assert not result["passed"] and result["resource_mismatches"] == [resource]
    assert not result["missing_resources"]


def test_failure_diagnostics_hide_private_values_and_arbitrary_filenames(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    private_filename = "ghp_" + "A" * 36 + ".txt"
    private_bytes = b"/" + b"home/" + b"private-person/" + b"source/"
    (payload / private_filename).write_bytes(private_bytes)
    result = payload_auditor.audit(payload, [])
    diagnostics = payload_auditor.failure_diagnostics(result, payload, tmp_path, [])
    serialized = json.dumps(diagnostics)
    assert private_filename not in serialized and private_bytes.decode() not in serialized
    assert diagnostics == [
        {
            "module": "unclassified-payload-file",
            "category": "unix-personal-path",
            "sha256": hashlib.sha256(private_bytes).hexdigest(),
        }
    ]


def test_failure_diagnostics_show_known_qt_module_without_granting_an_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = tmp_path / "reviewed-test-only.whl"
    original = b"/" + b"home/" + b"qt-build/"
    with zipfile.ZipFile(wheel, "w") as package:
        package.writestr("PySide6/Qt6Core.dll", original)
    monkeypatch.setitem(
        auditor.REVIEWED_UPSTREAM_WHEELS, wheel.name, hashlib.sha256(wheel.read_bytes()).hexdigest()
    )
    payload = tmp_path / "payload"
    payload.mkdir()
    modified = original + b"modified"
    (payload / "Qt6Core.dll").write_bytes(modified)
    result = payload_auditor.audit(payload, [wheel])
    assert not result["passed"]
    diagnostics = payload_auditor.failure_diagnostics(result, payload, tmp_path, [wheel])
    assert diagnostics == [
        {
            "module": "PySide6/Qt6Core.dll",
            "category": "unix-personal-path",
            "sha256": hashlib.sha256(modified).hexdigest(),
        }
    ]


def test_archive_rejects_unsafe_paths_duplicate_resources_and_empty_payload(tmp_path: Path) -> None:
    source = tmp_path / "netconfiglint/gui/qml/Main.qml"
    source.parent.mkdir(parents=True)
    source.write_text("Item {}", encoding="utf-8")
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../escape.txt", "unsafe")
        package.write(source, "first/netconfiglint/gui/qml/Main.qml")
        package.write(source, "second/netconfiglint/gui/qml/Main.qml")
    result = auditor.audit_archive(tmp_path, archive)
    assert not result["passed"]
    assert result["duplicate_members"] == ["netconfiglint/gui/qml/Main.qml"]
    assert result["findings"] == [{"path": "../escape.txt", "category": "unsafe-package-path"}]
    with zipfile.ZipFile(archive, "w"):
        pass
    assert not auditor.audit_archive(tmp_path, archive)["passed"]


@pytest.mark.parametrize("platform", ["windows", "linux", "macos"])
def test_native_installer_comparison_rejects_changed_extracted_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "binary").write_bytes(b"qualified")
    installer = tmp_path / "native-installer"
    installer.write_bytes(b"installer")
    extracted = tmp_path / "extracted"
    shutil.copytree(prepared, extracted)
    monkeypatch.setattr(payload_auditor, "unpack_installer", lambda *_: extracted)
    assert payload_auditor.audit_installer(installer, prepared, platform, [], tmp_path)["passed"]
    (extracted / "binary").write_bytes(b"tampered")
    result = payload_auditor.audit_installer(installer, prepared, platform, [], tmp_path)
    assert not result["passed"] and result["payload_mismatches"] == ["binary"]


def make_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(auditor, "git", lambda *_: ("a" * 40).encode())
    artifact_root = tmp_path / "artifacts"
    names = {
        "windows": [
            "NetConfigLint-3.0.0-windows-x64-portable.zip",
            "NetConfigLint-3.0.0-windows-x64-unsigned.msi",
        ],
        "linux": ["NetConfigLint-3.0.0-linux-amd64.deb"],
        "macos": ["NetConfigLint-3.0.0-macos-arm64-unsigned.pkg"],
    }
    for platform, folder_name in auditor.DESKTOP_ARTIFACTS.items():
        folder = artifact_root / folder_name
        (folder / "build").mkdir(parents=True)
        (folder / "release").mkdir()
        records = []
        for name in names[platform]:
            binary = name.encode()
            (folder / "release" / name).write_bytes(binary)
            records.append({"name": name, "sha256": hashlib.sha256(binary).hexdigest()})
        source = {"repository": {"passed": True, "source_commit": "a" * 40}}
        installer = next(item for item in records if not item["name"].endswith(".zip")) | {"passed": True}
        payload = {
            "passed": True,
            "source_commit": "a" * 40,
            "application_version": "3.0.0",
            "platform": platform,
            "source_run_id": 44,
            "installer": installer,
            "release_files": records,
        }
        (folder / "build/source-privacy.json").write_text(json.dumps(source), encoding="utf-8")
        (folder / "build/installer-payload-privacy.json").write_text(json.dumps(payload), encoding="utf-8")
        if platform == "windows":
            source["archive"] = {"passed": True, "sha256": records[0]["sha256"]}
            (folder / "build/portable-privacy.json").write_text(json.dumps(source), encoding="utf-8")
    return artifact_root


def test_reused_artifacts_stage_only_four_audited_assets_and_checksums(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = make_artifacts(tmp_path, monkeypatch)
    stage = tmp_path / "release"
    result = auditor.verify_reused_artifacts(tmp_path, artifacts, "v3.0.0", stage, 44)
    assert result["passed"] and len(result["release_files"]) == 4
    assert len(list(stage.iterdir())) == 5
    assert len((stage / "SHA256SUMS.txt").read_text().splitlines()) == 4


@pytest.mark.parametrize(
    "change",
    [
        "native-tamper",
        "wrong-commit",
        "wrong-run",
        "failed-payload",
        "failed-native-audit",
        "unexpected-asset",
        "missing-portable-proof",
        "wrong-installer-hash",
    ],
)
def test_reused_artifacts_reject_unqualified_or_substituted_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    artifacts = make_artifacts(tmp_path, monkeypatch)
    folder = artifacts / auditor.DESKTOP_ARTIFACTS["windows"]
    report = folder / "build/installer-payload-privacy.json"
    payload = json.loads(report.read_text())
    if change == "native-tamper":
        (folder / "release" / payload["installer"]["name"]).write_bytes(b"modified")
    elif change == "unexpected-asset":
        (folder / "release/unexpected.txt").write_text("unsafe")
    elif change == "missing-portable-proof":
        (folder / "build/portable-privacy.json").unlink()
    elif change == "wrong-commit":
        payload["source_commit"] = "b" * 40
    elif change == "wrong-run":
        payload["source_run_id"] = 45
    elif change == "failed-payload":
        payload["passed"] = False
    elif change == "failed-native-audit":
        payload["installer"]["passed"] = False
    else:
        payload["installer"]["sha256"] = "0" * 64
    report.write_text(json.dumps(payload), encoding="utf-8")
    stage = tmp_path / "release"
    with pytest.raises((ValueError, FileNotFoundError)):
        auditor.verify_reused_artifacts(tmp_path, artifacts, "v3.0.0", stage, 44)
    assert not stage.exists()


@pytest.mark.parametrize("compression", [[], ["-Zxz"]], ids=["default", "xz"])
def test_debian_native_extraction_matches_control_and_data(tmp_path: Path, compression: list[str]) -> None:
    if shutil.which("dpkg-deb") is None:
        pytest.skip("Native dpkg-deb extraction is exercised by Linux CI")
    prepared = tmp_path / "prepared"
    (prepared / "DEBIAN").mkdir(parents=True)
    (prepared / "DEBIAN/control").write_text(
        "Package: synthetic-audit-test\nVersion: 1.0\nArchitecture: all\n"
        "Maintainer: Contributors\nDescription: Synthetic payload test\n",
        encoding="utf-8",
    )
    (prepared / "DEBIAN/control").chmod(0o644)
    (prepared / "application.txt").write_text("synthetic", encoding="utf-8")
    installer = tmp_path / "application.deb"
    subprocess.run(
        ["dpkg-deb", *compression, "--build", str(prepared), str(installer)],
        check=True,
        capture_output=True,
    )
    assert payload_auditor.audit_installer(installer, prepared, "linux", [], tmp_path)["passed"]
    # Compression must never hide a private value from the extracted-payload gate.
    (prepared / "personal.txt").write_bytes(b"/home/" + b"SYNTHETIC-ACCOUNT/private-file")
    subprocess.run(
        ["dpkg-deb", *compression, "--build", str(prepared), str(installer)],
        check=True,
        capture_output=True,
    )
    report = payload_auditor.audit_installer(installer, prepared, "linux", [], tmp_path)
    assert not report["passed"]
    assert {"path": "personal.txt", "category": "unix-personal-path"} in report["payload"]["findings"]
