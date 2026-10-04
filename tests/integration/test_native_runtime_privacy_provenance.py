"""Only independently reproduced whole bytes can inherit official runtime findings."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import marshal
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


def test_official_stdlib_diagnostics_distinguish_metadata_docstrings_and_bytecode(
    reviewed_inputs: tuple[Path, Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, source = reviewed_inputs
    path = "/" + "home/" + "official-build-worker/" + "metadata"
    doc_path = "/" + "home/" + "public-example/" + "example.txt"
    filename = "/" + "home/" + "official-build-worker/" + "code.py"
    metadata = f"build_time_vars = {{'abs_srcdir': {path!r}, 'SOABI': 'stable'}}".encode()
    docstring = repr(doc_path).encode()
    code = compile("example = " + repr(path), filename, "exec")
    bytecode = importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(code)
    members = {
        "lib/python3.13/lib-dynload/array.cpython-313-x86_64-linux-gnu.so": source,
        "lib/python3.13/_sysconfigdata__linux_x86_64-linux-gnu.py": metadata,
        "lib/python3.13/__pycache__/_sysconfigdata__linux_x86_64-linux-gnu.cpython-313.pyc": bytecode,
        "lib/python3.13/public_example.py": docstring,
        "lib/python3.13/test/private_example.py": repr("/" + "home/" + "excluded/" + "test").encode(),
    }
    with tarfile.open(archive, "w:gz") as package:
        for name, data in members.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            package.addfile(member, io.BytesIO(data))
    monkeypatch.setitem(
        provenance.REVIEWED_PYTHON_ARCHIVES, archive.name, hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    compiled = b"\0".join(value.encode() for value in (path, doc_path, filename)) + b"\0"
    details = verifier.path_details(compiled)
    rows = details["stdlib_matches"]
    assert any(row["kind"] == "source-sysconfig-build-var" and row["key"] == "abs_srcdir" for row in rows)
    assert any(row["kind"] == "source-docstring" and row["module"] == "public_example.py" for row in rows)
    assert any(row["kind"] == "bytecode-code-filename" for row in rows)
    assert any(row["kind"] == "bytecode-string-constant" for row in rows)
    assert verifier.diagnostic_index["members"] == 3
    assert verifier.path_classifications(compiled)["exact-official-input-string"] == 3
    assert verifier.match("opt/netconfiglint/NetConfigLint", compiled, tmp_path) is None
    assert path not in str(details) and doc_path not in str(details) and filename not in str(details)


def test_stdlib_diagnostic_input_budget_is_enforced(
    reviewed_inputs: tuple[Path, Path, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, _ = reviewed_inputs
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    monkeypatch.setattr(provenance, "DIAGNOSTIC_MEMBER_BYTES", 8)
    verifier._index_stdlib("lib/python3.13/public.py", b"#" * 9)
    assert verifier.diagnostic_index["members"] == 0
    assert verifier.diagnostic_index["skipped"] == 1
    assert verifier.path_index == {}


def test_outer_installer_exact_proven_string_is_diagnostic_only_and_unknown_stays_rejected(
    reviewed_inputs: tuple[Path, Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, patcher, source = reviewed_inputs
    monkeypatch.setattr(provenance, "_run", lambda *args: "")
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    prepared = tmp_path / "payload"
    library = prepared / "opt/netconfiglint/array.so"
    library.parent.mkdir(parents=True)
    library.write_bytes(source)
    installer = tmp_path / "NetConfigLint.deb"
    unknown = b"/" + b"home/" + b"unknown-person/" + b"private.c\0"
    installer.write_bytes(b"container\0" + source + unknown)
    monkeypatch.setattr(payload_auditor, "unpack_installer", lambda *args: prepared)
    report = payload_auditor.audit_installer(installer, prepared, "linux", [], tmp_path, verifier)
    assert not report["passed"]
    assert report["payload"]["passed"]
    assert not report["payload_mismatches"]
    details = report["findings"][0]["path_details"]
    assert details["exact-proved-payload-string"] == 1
    assert details["not-proved-payload-string"] == 1
    assert details["proven_payload_matches"] == [{"module": "array.so", "count": 1}]
    assert unknown.decode().rstrip("\0") not in str(details)
    installer.write_bytes(b"container\0" + source)
    report = payload_auditor.audit_installer(installer, prepared, "linux", [], tmp_path, verifier)
    assert not report["passed"]
    assert report["findings"][0]["path_details"]["not-proved-payload-string"] == 0


def test_macos_official_main_python_member_excludes_the_application_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "python-3.13.15-darwin-arm64.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        member = tarfile.TarInfo("python-3.13.15-macos11.pkg")
        member.size = 1
        package.addfile(member, io.BytesIO(b"x"))
    monkeypatch.setitem(
        provenance.REVIEWED_PYTHON_ARCHIVES, archive.name, hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    original = b"official framework /" + b"Users/" + b"official-builder/source.c\0"

    def expand(*args: str) -> str:
        root = Path(args[-1]) / "Python_Framework.pkg/Payload/Versions/3.13"
        root.mkdir(parents=True)
        (root / "Python").write_bytes(original)
        stub = root / "Resources/Python.app/Contents/MacOS/Python"
        stub.parent.mkdir(parents=True)
        stub.write_bytes(original + b"different application launcher")
        return ""

    monkeypatch.setattr(provenance, "sys", types.SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(provenance, "_run", expand)
    verifier = provenance.IndependentRuntimeProvenance("macos", archive, [], None)
    assert verifier.sources["Python"][0] == original
    assert not verifier.ambiguous
    prefix = "Applications/NetConfigLint.app/Contents/Frameworks/"
    assert verifier._canonical_target(prefix + "Python.framework/Versions/3.13/Python") == "Python"
    assert verifier._canonical_target(prefix + "Wrong.framework/Versions/3.13/Python") is None
    assert verifier._canonical_target(prefix + "Python.framework/Versions/A/Python") is None


def test_macos_tool_diagnostics_never_expose_arguments_or_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def failure(*args: str) -> str:
        raise subprocess.CalledProcessError(1, args, stderr=b"private tool stderr")

    monkeypatch.setattr(provenance, "_run", failure)
    with pytest.raises(provenance.NativeReplayError) as raised:
        provenance._replay_tool("official-dependency-inspection", "/usr/bin/otool", "private input argument")
    assert raised.value.details == {
        "reason": "native-tool-failed",
        "stage": "official-dependency-inspection",
        "tool_error_type": "CalledProcessError",
    }
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("duplicate", [False, True])
def test_macos_dependency_mapping_ignores_bundle_root_documents_and_reports_ambiguity_safely(
    reviewed_inputs: tuple[Path, Path, bytes],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    duplicate: bool,
) -> None:
    archive, patcher, source = reviewed_inputs
    verifier = provenance.IndependentRuntimeProvenance("linux", archive, [], patcher)
    verifier.platform = "macos"
    monkeypatch.setattr(provenance, "sys", types.SimpleNamespace(platform="darwin"))
    payload = tmp_path / "payload"
    app = payload / "Applications/NetConfigLint.app"
    (app / "Contents/MacOS").mkdir(parents=True)
    (app / "LICENSE").write_text("public license", encoding="utf-8")
    (app / "Contents/MacOS/Python").write_bytes(source)
    if duplicate:
        framework = app / "Contents/Frameworks/Python.framework/Versions/3.13/Python"
        framework.parent.mkdir(parents=True)
        framework.write_bytes(source)
    target = tmp_path / "array.so"
    target.write_bytes(source)
    commands = []

    def run(*args: str) -> str:
        commands.append(args)
        if args[0].endswith("lipo"):
            return "arm64"
        if args[1] == "-L":
            return "header\n\t@rpath/Python (compatibility version 3.13.0, current version 3.13.0)\n"
        if args[1] == "-D":
            return "header\n"
        return ""

    monkeypatch.setattr(provenance, "_run", run)
    if duplicate:
        with pytest.raises(provenance.NativeReplayError) as raised:
            verifier._macos_replay(target, source, payload, "unused", tmp_path)
        assert raised.value.details == {
            "reason": "application-dependency-destination-not-unique",
            "official_dependency_basename": "Python",
            "candidate_count": 2,
        }
        assert str(payload) not in str(raised.value.details)
    else:
        derived, _ = verifier._macos_replay(target, source, payload, "unused", tmp_path)
        assert derived.read_bytes() == source
        assert any("@executable_path/Python" in command for command in commands)
