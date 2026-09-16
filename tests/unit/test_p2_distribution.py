"""Synthetic gate checks; actual Windows distribution validation is a separate run."""

import json
import struct
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


def test_linux_abi3_suffix_normalization_still_requires_exact_bytes(
    payload: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = payload / "Qt6Core.dll"
    upstream = payload.parent / "QtCore.abi3.so"
    upstream.write_bytes(b"pinned PySide extension")
    deployed = payload / "PySide6/QtCore.so"
    deployed.parent.mkdir()
    deployed.write_bytes(upstream.read_bytes())
    monkeypatch.setattr(
        licensing,
        "origins",
        lambda: {
            "qt6core.dll": [(original, "qtbase", "PySide6/Qt6Core.dll")],
            "qtcore.abi3.so": [(upstream, "pyside-setup", "PySide6/QtCore.abi3.so")],
        },
    )
    licensing.assemble(payload)
    deployed.write_bytes(b"changed extension")
    with pytest.raises(ValueError, match="Unregistered native"):
        licensing.assemble(payload)


def test_linux_cpython_suffix_normalization_still_requires_verified_bytes(
    payload: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = payload / "Qt6Core.dll"
    upstream = payload.parent / "_bz2.cpython-313-x86_64-linux-gnu.so"
    upstream.write_bytes(b"pinned Python extension")
    deployed = payload / "_bz2.so"
    deployed.write_bytes(upstream.read_bytes())
    monkeypatch.setattr(
        licensing,
        "origins",
        lambda: {
            "qt6core.dll": [(original, "qtbase", "PySide6/Qt6Core.dll")],
            "_bz2.so": [(upstream, "Python", upstream.name)],
        },
    )
    licensing.assemble(payload)
    deployed.write_bytes(b"changed extension")
    with pytest.raises(ValueError, match="Unregistered native"):
        licensing.assemble(payload)


def test_macos_entry_name_avoids_case_insensitive_package_collision() -> None:
    assert licensing.application_entry("Contents/MacOS/NetConfigLintApp")
    assert "netconfiglintapp" != "netconfiglint"


def test_linux_relocated_elf_allows_only_expected_rpath_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "QtCore.abi3.so"
    deployed = tmp_path / "QtCore.so"
    source.write_bytes(b"source")
    deployed.write_bytes(b"deployed")

    def snapshot(rpath: bytes | None, needed: bytes = b"libQt6Core.so.6", text: bytes = b"code"):
        dynstr = b"\0" + needed + b"\0" + ((rpath + b"\0") if rpath is not None else b"")
        needed_offset = 1
        rpath_offset = needed_offset + len(needed) + 1
        dynamic_items = [(1, needed_offset)]
        if rpath is not None:
            dynamic_items.append((15, rpath_offset))
        dynamic_items.extend(
            (
                (5, 0x1000),
                (10, len(dynstr)),
                (0x6FFFFEF5, 0x2000),
                (0, 0),
            )
        )
        dynamic = b"".join(struct.pack("<QQ", tag, value) for tag, value in dynamic_items)
        return (
            62,
            {".text": text, ".dynstr": dynstr, ".dynamic": dynamic},
            [
                "",
                ".text",
                ".dynstr",
                ".dynamic",
            ],
        )

    snapshots = {
        source: snapshot(b"$ORIGIN/:$ORIGIN/Qt/lib"),
        deployed: snapshot(b"$ORIGIN:$ORIGIN/..:$ORIGIN/:$ORIGIN/Qt/lib"),
    }
    monkeypatch.setattr(licensing, "elf_snapshot", snapshots.get)
    assert licensing.elf_deployment_match(source, deployed)

    snapshots[deployed] = snapshot(b"$ORIGIN:$ORIGIN/..:$ORIGIN/:$ORIGIN/Qt/lib", text=b"changed code")
    assert not licensing.elf_deployment_match(source, deployed)

    snapshots[deployed] = snapshot(b"$ORIGIN:$ORIGIN/..:$ORIGIN/:$ORIGIN/Qt/lib", needed=b"libInjected.so")
    assert not licensing.elf_deployment_match(source, deployed)

    snapshots[deployed] = snapshot(b"$ORIGIN:/tmp:$ORIGIN/:$ORIGIN/Qt/lib")
    assert not licensing.elf_deployment_match(source, deployed)

    snapshots[source] = snapshot(None)
    snapshots[deployed] = snapshot(b"$ORIGIN")
    assert licensing.elf_deployment_match(source, deployed)


def test_f24_zip_duplicate_or_traversal_names_fail(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as output:
        output.writestr("portable/../escape", b"data")
    with pytest.raises(ValueError, match="Unsafe"):
        licensing.verify(path)
