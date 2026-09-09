"""Release gates must reject secrets and obsolete packaged resources."""

import importlib.util
import zipfile
from pathlib import Path


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
