"""Synthetic gate checks; actual Windows distribution validation is a separate run."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import assemble_licenses as licensing


@pytest.fixture
def payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "synthetic.dist"
    directory.mkdir()
    (directory / "NetConfigLint.exe").write_bytes(b"synthetic entry, not a compiled app")
    library = tmp_path / "Qt6Core.dll"
    library.write_bytes(b"synthetic library, not an upstream binary")
    (directory / library.name).write_bytes(library.read_bytes())
    monkeypatch.setattr(
        licensing, "origins", lambda: {library.name.lower(): [(library, "qtbase", "PySide6/Qt6Core.dll")]}
    )
    licensing.assemble(directory)
    return directory


def test_f24_final_zip_inventory_and_licenses(payload: Path, tmp_path: Path) -> None:
    archive = tmp_path / "portable.zip"
    with ZipFile(archive, "w") as output:
        for path in payload.rglob("*"):
            if path.is_file():
                output.write(path, "portable/" + path.relative_to(payload).as_posix())
    assert licensing.verify(archive)["passed"]


@pytest.mark.parametrize("change", ["delete", "alter", "alter-and-rehash", "add-native"])
def test_f24_final_payload_changes_are_rejected(payload: Path, change: str) -> None:
    if change == "delete":
        (payload / "LICENSE").unlink()
    elif change == "add-native":
        (payload / "unknown.dll").write_bytes(b"unknown")
        with pytest.raises(ValueError, match="Unregistered native"):
            licensing.assemble(payload)
    else:
        (payload / "LICENSE").write_bytes(b"truncated terms")
        if change == "alter-and-rehash":
            path = payload / "SBOM.json"
            data = json.loads(path.read_text("utf-8"))
            record = next(item for item in data["files"] if item["path"] == "LICENSE")
            record.update(sha256=licensing.sha(b"truncated terms"), bytes=len(b"truncated terms"))
            path.write_text(json.dumps(data), "utf-8")
    with pytest.raises(ValueError):
        licensing.verify(payload)


def test_f24_external_qt_library_is_required(payload: Path) -> None:
    (payload / "Qt6Core.dll").unlink()
    with pytest.raises(ValueError, match="External Qt Core"):
        licensing.assemble(payload)


def test_windows_flattened_lowercase_library_keeps_exact_provenance(payload: Path) -> None:
    original = payload / "Qt6Core.dll"
    renamed = payload / "qt6core.dll"
    original.rename(renamed)
    licensing.assemble(payload)
    renamed.write_bytes(b"changed library")
    with pytest.raises(ValueError, match="Unregistered native"):
        licensing.assemble(payload)


def test_f24_zip_duplicate_or_traversal_names_fail(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as output:
        output.writestr("portable/../escape", b"data")
    with pytest.raises(ValueError, match="Unsafe"):
        licensing.verify(path)
