"""Only independently reproduced whole bytes can inherit official runtime findings."""

from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
import types
import zipfile
from pathlib import Path

import pytest

from scripts import audit_installer_payload as payload_auditor
from scripts import native_privacy_provenance as provenance


@pytest.fixture
def reviewed_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, bytes]:
    archive = tmp_path / "python-3.13.15-linux-24.04-x64.tar.gz"
    source = b"\x7fELF" + b"/" + b"home/" + b"official-build-worker/" + b"source.c\0"
    with tarfile.open(archive, "w:gz") as package:
        entry = tarfile.TarInfo("./lib/python3.13/lib-dynload/array.cpython-313-x86_64-linux-gnu.so")
        entry.size = len(source)
        package.addfile(entry, io.BytesIO(source))
    monkeypatch.setitem(
        provenance.REVIEWED_PYTHON_ARCHIVES,
        archive.name,
        hashlib.sha256(archive.read_bytes()).hexdigest(),
    )
    patcher = tmp_path / provenance.PATCHER_WHEEL
    with zipfile.ZipFile(patcher, "w") as package:
        package.writestr("patchelf-0.19.1.0.data/scripts/patchelf", b"synthetic-tool")
    monkeypatch.setattr(provenance, "PATCHER_SHA256", hashlib.sha256(patcher.read_bytes()).hexdigest())
    monkeypatch.setattr(provenance, "sys", types.SimpleNamespace(platform="linux"))
    return archive, patcher, source


def test_complete_derived_bytes_are_required_and_application_entry_is_never_exempted(
    reviewed_inputs: tuple[Path, Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, source = reviewed_inputs
    calls = []

    def replay(*args: str) -> str:
        calls.append(args)
        assert args[1:4] == ("--force-rpath", "--set-rpath", "$ORIGIN")
        target = Path(args[-1])
        assert target.read_bytes() == source
        target.write_bytes(source + b"qualified-relocation")
        return ""

    monkeypatch.setattr(provenance, "_run", replay)
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    payload = tmp_path / "payload"
    target = payload / "opt/netconfiglint/array.so"
    target.parent.mkdir(parents=True)
    qualified = source + b"qualified-relocation"
    target.write_bytes(qualified)
    report = payload_auditor.audit(payload, [], provenance=verifier)
    assert report["passed"]
    proof = report["reviewed_upstream"][0]
    assert proof["derived_sha256"] == hashlib.sha256(qualified).hexdigest()
    assert proof["upstream_sha256"] == hashlib.sha256(source).hexdigest()
    assert len(calls) == 1
    # Repeated extraction proof may reuse the same hash; changed bytes never do.
    assert verifier.match("opt/netconfiglint/array.so", qualified, payload)
    assert len(calls) == 1
    target.write_bytes(qualified + b"injected-code")
    report = payload_auditor.audit(payload, [], provenance=verifier)
    assert not report["passed"]
    assert report["findings"][0]["replay"]["outcome"] == "whole-file-hash-mismatch"
    assert verifier.match("opt/netconfiglint/NetConfigLint", qualified, payload) is None
    assert verifier.match("unqualified/array.so", qualified, payload) is None
    assert verifier.match("opt/netconfiglint/array.so", qualified + b"sk-" + b"A" * 40, payload) is None


@pytest.mark.parametrize("input_name", ["archive", "patcher"])
def test_changed_official_input_cannot_establish_provenance(
    reviewed_inputs: tuple[Path, Path, bytes], input_name: str
) -> None:
    archive, patcher, _ = reviewed_inputs
    target = archive if input_name == "archive" else patcher
    target.write_bytes(target.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="exact reviewed"):
        provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)


def test_failed_native_tool_stays_rejected_without_logging_its_private_stderr(
    reviewed_inputs: tuple[Path, Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, source = reviewed_inputs

    def failed(*args: str) -> str:
        raise subprocess.CalledProcessError(1, args, stderr=b"sensitive tool error")

    monkeypatch.setattr(provenance, "_run", failed)
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    assert verifier.match("opt/netconfiglint/array.so", source, tmp_path) is None
    assert verifier.replay_failures[("opt/netconfiglint/array.so", hashlib.sha256(source).hexdigest())] == {
        "outcome": "native-replay-failed",
        "error_type": "CalledProcessError",
    }


def test_safe_path_classification_never_authorizes_compiled_application(
    reviewed_inputs: tuple[Path, Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, source = reviewed_inputs
    workspace = "/" + "home/" + "public-job/" + "work/project"
    monkeypatch.setenv("GITHUB_WORKSPACE", workspace)
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    private = b"/" + b"home/" + b"private-person/file.txt\0"
    data = source + workspace.encode() + b"/generated.c\0" + private
    assert verifier.path_classifications(data) == {
        "exact-official-input-string": 1,
        "current-job-workspace": 1,
        "unclassified": 1,
    }
    assert verifier.match("opt/netconfiglint/NetConfigLint", data, tmp_path) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/actions/python-versions",
        "https://untrusted.example/archive",
        "https://github.com.untrusted.example/archive",
        "https://example-user@github.com/archive",
        "file:///public/archive",
        "https://github.com:444/archive",
    ],
)
def test_download_rejects_insecure_and_unreviewed_redirect_origins(url: str) -> None:
    with pytest.raises(ValueError):
        provenance._reviewed_download_url(url)


def test_download_allows_only_reviewed_public_https_origins() -> None:
    provenance._reviewed_download_url("https://github.com/actions/python-versions/releases/download/public")
    provenance._reviewed_download_url("https://release-assets.githubusercontent.com/public")
    provenance._reviewed_download_url("https://files.pythonhosted.org/packages/public.whl")
