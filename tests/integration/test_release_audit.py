"""Release gates must reject secrets and obsolete packaged resources."""

import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest


def load_auditor():
    spec = importlib.util.spec_from_file_location(
        "release_auditor", Path(__file__).parents[2] / "scripts/audit_release.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secret_gate_checks_binary_utf16_and_does_not_echo_values() -> None:
    auditor = load_auditor()
    synthetic_token = "ghp_" + "A" * 36
    assert auditor.scan_bytes(synthetic_token.encode()) == ["github-token"]
    assert auditor.scan_bytes(synthetic_token.encode("utf-16-le")) == ["github-token"]
    assert auditor.scan_bytes(b"\xff" + synthetic_token.encode("utf-16-le")) == ["github-token"]
    assert auditor.scan_bytes(b"password cipher SYNTHETIC-ONLY-NOT-A-SECRET") == []


def test_public_github_merge_exception_is_limited_to_release_head() -> None:
    auditor = load_auditor()
    arguments = ("merge", "parent1 parent2", "noreply@github.com", "Merge pull request #4 from owner/branch")
    assert auditor.is_public_github_merge(*arguments, "merge")
    assert not auditor.is_public_github_merge(*arguments, "later-release")
    assert not auditor.is_public_github_merge("merge", "parent1", *arguments[2:], "merge")
    assert not auditor.is_public_github_merge(
        "merge", arguments[1], "person@example.com", arguments[3], "merge"
    )
    assert not auditor.is_public_github_merge("merge", arguments[1], arguments[2], "Manual merge", "merge")


def test_archive_gate_rejects_old_qml_missing_resources_and_private_files(tmp_path: Path) -> None:
    auditor = load_auditor()
    qml = tmp_path / "netconfiglint/gui/qml/Main.qml"
    qml.parent.mkdir(parents=True)
    qml.write_text("import QtQuick\nItem {}\n", encoding="utf-8")
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/netconfiglint/gui/qml/Old.qml", "import QtQuick\nItem {}\n")
        package.writestr("portable/history/history.json", "[]")
    result = auditor.audit_archive(tmp_path, archive)
    assert not result["passed"]
    assert result["resource_mismatches"] == ["netconfiglint/gui/qml/Old.qml"]
    assert result["missing_resources"] == ["netconfiglint/gui/qml/Main.qml"]
    assert result["findings"] == [
        {"path": "portable/history/history.json", "category": "private-artifact-path"}
    ]


def test_archive_gate_accepts_exact_resources(tmp_path: Path) -> None:
    auditor = load_auditor()
    qml = tmp_path / "netconfiglint/gui/qml/Main.qml"
    qml.parent.mkdir(parents=True)
    qml.write_text("import QtQuick\nItem {}\n", encoding="utf-8")
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.write(qml, "portable/netconfiglint/gui/qml/Main.qml")
    assert auditor.audit_archive(tmp_path, archive)["passed"]


def test_archive_gate_accepts_only_line_ending_changes_for_text_resources(tmp_path: Path) -> None:
    auditor = load_auditor()
    qml = tmp_path / "netconfiglint/gui/qml/Main.qml"
    qml.parent.mkdir(parents=True)
    qml.write_bytes(b"import QtQuick\r\nItem {}\r\n")
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/netconfiglint/gui/qml/Main.qml", b"import QtQuick\nItem {}\n")
    assert auditor.audit_archive(tmp_path, archive)["passed"]

    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/netconfiglint/gui/qml/Main.qml", b"import QtQuick\nItem {x: 1}\n")
    assert not auditor.audit_archive(tmp_path, archive)["passed"]


def test_reviewed_upstream_needs_exact_wheel_and_binary_bytes(tmp_path: Path) -> None:
    auditor = load_auditor()
    wheel = tmp_path / "synthetic-review-only.whl"
    binary = b"C:" + b"/Users/" + b"qt/build/"
    with zipfile.ZipFile(wheel, "w") as package:
        package.writestr("PySide6/Qt6Core.dll", binary)
    with pytest.raises(ValueError, match="official distribution"):
        auditor.upstream_binary_hashes([wheel])
    auditor.REVIEWED_UPSTREAM_WHEELS[wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    hashes = auditor.upstream_binary_hashes([wheel])
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/PySide6/Qt6Core.dll", binary)
    report = auditor.audit_archive(tmp_path, archive, upstream=hashes)
    assert report["passed"]
    assert len(report["reviewed_upstream_matches"]) == 1
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/qt6core.dll", binary)
    relocated = auditor.audit_archive(tmp_path, archive, upstream=hashes)
    assert relocated["passed"]
    assert len(relocated["reviewed_upstream_matches"]) == 1
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("portable/PySide6/Qt6Core.dll", binary + b"modified")
    assert not auditor.audit_archive(tmp_path, archive, upstream=hashes)["passed"]
    wheel.write_bytes(wheel.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="official distribution"):
        auditor.upstream_binary_hashes([wheel])
