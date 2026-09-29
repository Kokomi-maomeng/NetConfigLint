"""Release provenance rejects mismatched commits, missing runtime DLLs and changed code."""

from __future__ import annotations

import json
import plistlib
import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import resolve_windows_dlls, verify_release_identity
from scripts.macho_provenance import deployment_match
from scripts.prepare_macos_runtime import prune as prune_macos


def test_portable_identity_is_bound_to_tag_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Resolved:
        stdout = "a" * 40

    monkeypatch.setattr(verify_release_identity.subprocess, "run", lambda *args, **kwargs: Resolved())
    archive = tmp_path / "NetConfigLint-2.5.0-windows-x64-portable.zip"

    def write(version: str, commit: str) -> None:
        with ZipFile(archive, "w") as bundle:
            bundle.writestr(
                "NetConfigLint/SBOM.json",
                json.dumps(
                    {
                        "application_version": version,
                        "source_commit": commit,
                    }
                ),
            )

    write("2.5.0", "a" * 40)
    assert verify_release_identity.verify(archive, "v2.5.0")["source_commit"] == "a" * 40
    for version, commit in (("2.4.0", "a" * 40), ("2.5.0", "b" * 40)):
        write(version, commit)
        with pytest.raises(ValueError, match="differs"):
            verify_release_identity.verify(archive, "v2.5.0")


def test_resolver_bundles_interpreter_dlls_and_vc_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "dist" / "synthetic.dist"
    (target / "PySide6").mkdir(parents=True)
    (target / "NetConfigLint.exe").write_bytes(b"SYNTHETIC")
    base = tmp_path / "python"
    (base / "DLLs").mkdir(parents=True)
    for name in ("libssl-3.dll", "libcrypto-3.dll", "libffi-8.dll", "vcruntime140.dll"):
        (base / "DLLs" / name).write_bytes(b"SYNTHETIC-QUALIFIED-INTERPRETER")
    system = tmp_path / "system"
    (system / "System32").mkdir(parents=True)
    (system / "System32/vcruntime140.dll").write_bytes(b"SYNTHETIC-HOST-RUNTIME")
    monkeypatch.setenv("SYSTEMROOT", str(system))
    monkeypatch.setattr(resolve_windows_dlls.sys, "base_prefix", str(base))
    dependencies = {"libssl-3.dll", "libcrypto-3.dll", "libffi-8.dll", "vcruntime140.dll"}
    monkeypatch.setattr(
        resolve_windows_dlls, "imports_for", lambda path: dependencies if path.suffix == ".exe" else set()
    )
    result = resolve_windows_dlls.resolve(target, tmp_path / "site-packages")
    assert not result["unresolved_non_system"]
    for name in dependencies:
        assert (target / name).read_bytes() == b"SYNTHETIC-QUALIFIED-INTERPRETER"


def _macho(loader: str, content: bytes, *, signed: bool = False, library_id: bool = False) -> bytes:
    encoded = loader.encode() + b"\0"
    size = (24 + len(encoded) + 7) // 8 * 8
    dylib = struct.pack("<IIIIII", 0xD if library_id else 0xC, size, 24, 0, 1, 1) + encoded
    dylib = dylib.ljust(size, b"\0")
    section = struct.pack(
        "<16s16sQQIIIIIIII", b"__text", b"__TEXT", 0x1000, len(content), 512, 0, 0, 0, 0, 0, 0, 0
    )
    segment = struct.pack("<II16sQQQQiiII", 0x19, 152, b"__TEXT", 0x1000, 4096, 0, 1024, 7, 5, 1, 0) + section
    commands = segment + dylib
    if signed:
        commands += struct.pack("<IIII", 0x1D, 16, 768, 8)
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x1000007, 3, 6, 3 if signed else 2, len(commands), 0, 0)
    data = (header + commands).ljust(512, b"\0") + content
    return data.ljust(768, b"\0") + (b"SYNTHSIG" if signed else b"")


def test_macho_relocation_and_signing_preserve_executable_sections(tmp_path: Path) -> None:
    source, deployed = tmp_path / "source", tmp_path / "deployed"
    source.write_bytes(_macho("@rpath/QtCore", b"SYNTHETIC-CODE"))
    deployed.write_bytes(_macho("@loader_path/../Frameworks/QtCore", b"SYNTHETIC-CODE", signed=True))
    assert deployment_match(source, deployed)
    deployed.write_bytes(_macho("@loader_path/QtCore", b"MODIFIED-CODE", signed=True))
    assert not deployment_match(source, deployed)
    deployed.write_bytes(_macho("@loader_path/ForeignCore", b"SYNTHETIC-CODE", signed=True))
    assert not deployment_match(source, deployed)


def test_macho_python_module_identity_allows_only_abi_suffix_removal(tmp_path: Path) -> None:
    source, deployed = tmp_path / "source", tmp_path / "deployed"
    source.write_bytes(_macho("@rpath/QtCore.abi3.so", b"SYNTHETIC-CODE", library_id=True))
    deployed.write_bytes(_macho("QtCore.so", b"SYNTHETIC-CODE", signed=True, library_id=True))
    assert deployment_match(source, deployed)
    deployed.write_bytes(_macho("ForeignCore.so", b"SYNTHETIC-CODE", signed=True, library_id=True))
    assert not deployment_match(source, deployed)
    deployed.write_bytes(_macho("QtCore.so", b"SYNTHETIC-CODE", signed=True))
    assert not deployment_match(source, deployed)


def test_universal_macho_thinning_preserves_the_selected_architecture(tmp_path: Path) -> None:
    x64 = _macho("@rpath/QtCore", b"SYNTHETIC-CODE")
    arm = bytearray(x64)
    struct.pack_into("<ii", arm, 4, 0x100000C, 0)
    fat = struct.pack(">II", 0xCAFEBABE, 2)
    fat += struct.pack(">iiIII", 0x1000007, 3, 4096, len(x64), 12)
    fat += struct.pack(">iiIII", 0x100000C, 0, 8192, len(arm), 12)
    source, deployed = tmp_path / "source", tmp_path / "deployed"
    source.write_bytes(fat.ljust(4096, b"\0") + x64 + b"\0" * (4096 - len(x64)) + arm)
    deployed.write_bytes(arm)
    assert deployment_match(source, deployed)
    arm[512] ^= 1
    deployed.write_bytes(arm)
    assert not deployment_match(source, deployed)
    struct.pack_into("<ii", arm, 4, 0x100000C, 1)
    deployed.write_bytes(arm)
    assert not deployment_match(source, deployed)


def test_macos_pruning_removes_unused_qml_but_preserves_native_dependencies(tmp_path: Path) -> None:
    bundle = tmp_path / "dist/NetConfigLint.app"
    pyside = bundle / "Contents/MacOS/PySide6"
    for name in ("QtQuick/Controls/Material", "Qt3D/Animation", "QtQuick3D"):
        (pyside / "qml" / name).mkdir(parents=True)
        (pyside / "qml" / name / "qmldir").write_text("SYNTHETIC-MODULE")
    executable = bundle / "Contents/MacOS/NetConfigLintApp"
    executable.parent.mkdir(parents=True, exist_ok=True)
    (bundle / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleExecutable": "NetConfigLintApp"})
    )
    executable.write_bytes(_macho("@rpath/QtCore.framework/Versions/A/QtCore", b"APPLICATION"))
    core = bundle / "Contents/Frameworks/QtCore.framework/Versions/A/QtCore"
    core.parent.mkdir(parents=True)
    core.write_bytes(_macho("@rpath/QtSvg", b"CORE"))
    svg = bundle / "Contents/MacOS/QtSvg"
    svg.write_bytes(_macho("/usr/lib/libSystem.B.dylib", b"SVG"))
    unused = bundle / "Contents/Frameworks/Qt3DCore.framework/Versions/A/Qt3DCore"
    unused.parent.mkdir(parents=True)
    unused.write_bytes(_macho("@rpath/QtCore", b"UNUSED-3D"))
    result = prune_macos(bundle)
    assert result["removed_count"]
    assert executable.is_file() and core.is_file() and svg.is_file()
    assert (pyside / "qml/QtQuick/Controls/Material/qmldir").is_file()
    assert not (pyside / "qml/Qt3D").exists() and not (pyside / "qml/QtQuick3D").exists()
    assert not (bundle / "Contents/Frameworks/Qt3DCore.framework").exists()


def test_macos_bundle_uses_current_version_and_supported_os(tmp_path: Path, monkeypatch: object) -> None:
    import plistlib
    import runpy
    import tomllib

    root = Path(__file__).parents[2]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    namespace = runpy.run_path(str(root / "scripts/build_desktop.py"))
    expected = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    assert namespace["APP_VERSION"] == expected
    qualify = namespace["_qualify_macos_bundle"]
    qualify.__globals__["__file__"] = str(tmp_path / "scripts/build_desktop.py")
    (tmp_path / "build").mkdir()
    (tmp_path / "build/NetConfigLint.icns").write_bytes(b"SYNTHETIC-ICON")
    bundle = tmp_path / "dist/deploy.app"
    (bundle / "Contents/MacOS").mkdir(parents=True)
    (bundle / "Contents/Resources").mkdir()
    (bundle / "Contents/MacOS/deploy_main").write_bytes(b"SYNTHETIC-ENTRY")
    (bundle / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "deploy_main"}))
    target = qualify(bundle)
    info = plistlib.loads((target / "Contents/Info.plist").read_bytes())
    assert info["CFBundleVersion"] == info["CFBundleShortVersionString"] == expected
    assert info["LSMinimumSystemVersion"] == "13.0"
    assert (target / "Contents/MacOS/NetConfigLintApp").is_file()
