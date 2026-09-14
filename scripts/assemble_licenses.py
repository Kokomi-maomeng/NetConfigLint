"""Offline distribution inventory and license gate, including the final ZIP bytes.

This does not certify upstream binary provenance or legal compliance. It matches
files against the qualified local toolchain and rejects unknown native components.
The release provenance audit is a separate gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "netconfiglint-distribution-sbom/1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and ":" not in name
    )


def native(path: Path) -> bool:
    return (
        path.suffix.lower() in {".dll", ".pyd", ".dylib", ".exe"}
        or ".so" in path.name
        or (path.name.startswith("Qt") and not path.suffix)
    )


def application_entry(relative: str) -> bool:
    return relative in {
        "NetConfigLint.exe",
        "NetConfigLint",
        "NetConfigLint.bin",
        "Contents/MacOS/NetConfigLint",
        "Contents/MacOS/deploy_main",
    }


def catalog() -> dict:
    return json.loads((ROOT / "licenses" / "components.json").read_text("utf-8"))


def qt_component(origin: str) -> str:
    lower = origin.lower()
    name = PurePosixPath(lower).name
    if name == "opengl32sw.dll":
        return "Mesa-llvmpipe"
    if name.startswith(("msvcp", "vcruntime")):
        return "Microsoft-VC-Runtime"
    if re.search(r"(?:qt6?|/qml/qt)(?:quick3d|web|pdf|multimedia|charts|graphs|3d|5compat)", lower):
        return "unreviewed-qt-module"
    if re.search(r"(?:^|/)(?:lib)?qt6?(?:qml|quick)", lower) or "/qml/qt" in lower:
        # Python bindings belong to PySide; their Qt libraries/plugins to declarative.
        return "pyside-setup" if name.endswith(".pyd") or ".abi3.so" in name else "qtdeclarative"
    if "svg" in name:
        return "pyside-setup" if name.endswith(".pyd") or ".abi3.so" in name else "qtsvg"
    if "shadertools" in name:
        return "qtshadertools"
    if "/qt/" in lower or name.startswith(("qt6", "libqt6")) or "/plugins/" in lower:
        return "qtbase"
    return "pyside-setup"


def origins() -> dict[str, list[tuple[Path, str, str]]]:
    result: dict[str, list[tuple[Path, str, str]]] = defaultdict(list)
    for package in ("PySide6_Essentials", "PySide6_Addons", "shiboken6"):
        distribution = importlib.metadata.distribution(package)
        if distribution.version != "6.11.2":
            raise ValueError("License assembly requires the pinned Qt 6.11.2 runtime")
        for item in distribution.files or ():
            relative = item.as_posix()
            result[item.name.lower()].append(
                (Path(distribution.locate_file(item)), qt_component(relative), relative)
            )
    base = Path(sys.base_prefix)
    for folder in (base, base / "DLLs", base / "lib", base / "lib" / "python3.13" / "lib-dynload"):
        if folder.is_dir():
            for item in folder.iterdir():
                if item.is_file() and native(item):
                    component = "Python"
                    if item.name.lower().startswith(("libcrypto", "libssl")):
                        component = "OpenSSL"
                    elif item.name.lower().startswith(("vcruntime", "msvcp")):
                        component = "Microsoft-VC-Runtime"
                    elif item.name.lower().startswith("libffi"):
                        component = "libffi"
                    result[item.name.lower()].append((item, component, item.name))
    return result


def windows_runtime_candidates(name: str) -> list[Path]:
    folders = [Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32"]
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if base := os.environ.get(variable):
            folders.extend(
                (Path(base) / "Microsoft Visual Studio").glob("*/*/VC/Redist/MSVC/*/x64/Microsoft.VC*.CRT")
            )
    return [folder / name for folder in folders if (folder / name).is_file()]


def is_microsoft_signed(path: Path) -> bool:
    # Pass filenames as stdin data, never interpolate them into PowerShell code.
    command = (
        "$ErrorActionPreference = 'Stop'; $p = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
        "$s = Get-AuthenticodeSignature -LiteralPath $p; "
        "@{valid=($s.Status -eq 'Valid'); subject=$s.SignerCertificate.Subject} "
        "| ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            input=json.dumps(str(path)),
            text=True,
            capture_output=True,
            # A caller running pwsh can export Core-only module paths to Windows PowerShell.
            env={key: value for key, value in os.environ.items() if key.upper() != "PSMODULEPATH"},
            timeout=30,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        signature = json.loads(result.stdout)
        return signature.get("valid") is True and bool(
            re.search(r"(?:^|,\s*)O=Microsoft Corporation(?:,|$)", signature.get("subject") or "")
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def windows_runtime_origin(path: Path, digest: str) -> tuple[str, str] | None:
    if sys.platform != "win32" or not re.fullmatch(
        r"(?:msvcp140(?:_\d+|_atomic_wait|_codecvt_ids)?|vcruntime140(?:_\d+)?|concrt140)\.dll",
        path.name,
        re.IGNORECASE,
    ):
        return None
    for candidate in windows_runtime_candidates(path.name):
        if sha(candidate.read_bytes()) == digest and is_microsoft_signed(candidate):
            # Do not disclose the build host's installation/user paths in the SBOM.
            return "Microsoft-VC-Runtime", f"Microsoft-signed VC runtime/{path.name}"
    return None


def assemble(distribution: Path) -> dict:
    if not distribution.is_dir() or distribution.is_symlink():
        raise ValueError("Expected a real standalone directory")
    components = catalog()
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "netconfiglint/__init__.py").read_text("utf-8"))
    if version is None:
        raise ValueError("Project version missing")
    components["NetConfigLint"]["version"] = version[1]
    source_records = json.loads((ROOT / "licenses" / "sources.json").read_text("utf-8"))
    for record in source_records:
        for item in record["files"]:
            if sha((ROOT / "licenses" / item["file"]).read_bytes()) != item["sha256"]:
                raise ValueError("Pinned upstream license material changed")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, distribution / name)
    shutil.copytree(ROOT / "licenses", distribution / "licenses", dirs_exist_ok=True)
    # Preserve the actual interpreter's full license, also on Unix builds.
    runtime_license = next(
        (
            p
            for p in (
                Path(sys.base_prefix) / "LICENSE.txt",
                Path(sys.base_prefix) / "lib" / "python3.13" / "LICENSE.txt",
            )
            if p.exists()
        ),
        None,
    )
    if runtime_license:
        shutil.copy2(runtime_license, distribution / "licenses" / "Python-runtime.txt")
        components["Python"]["licenses"].append("licenses/Python-runtime.txt")
    components["Python"]["version"] = ".".join(map(str, sys.version_info[:3]))
    indexed = origins()
    files = []
    used = {"NetConfigLint", "Nuitka-runtime"}
    for path in sorted(distribution.rglob("*")):
        if path.is_symlink() and not path.resolve().is_relative_to(distribution.resolve()):
            raise ValueError("Distribution symlink escapes its directory")
        if not path.is_file() or path.name == "SBOM.json":
            continue
        relative = path.relative_to(distribution).as_posix()
        data = path.read_bytes()
        digest = sha(data)
        component = "NetConfigLint"
        origin = "project source"
        if relative.startswith("licenses/") or relative in {"LICENSE", "THIRD_PARTY_NOTICES.md"}:
            component = "license-material"
        elif path.suffix.lower() in {".ttf", ".otf"}:
            component = "Noto-Sans-SC" if "noto" in path.name.lower() else "Roboto"
            candidates = list((ROOT / "netconfiglint/resources/fonts").rglob(path.name))
            if not any(sha(p.read_bytes()) == digest for p in candidates):
                raise ValueError(f"Unregistered font: {relative}")
        elif application_entry(relative):
            origin = "compiled project with Nuitka runtime exception"
        else:
            match = next(
                (
                    (category, upstream)
                    for p, category, upstream in indexed.get(path.name.lower(), [])
                    if p.is_file() and sha(p.read_bytes()) == digest
                ),
                None,
            )
            if match is None:
                match = windows_runtime_origin(path, digest)
            if match:
                component, origin = match
            elif native(path):
                raise ValueError(
                    f"Unregistered native file (add exact provenance/license mapping): {relative}"
                )
            elif relative.startswith(("PySide6/", "shiboken6/")):
                raise ValueError(f"Unregistered Qt data: {relative}")
        if component != "license-material":
            if component not in components:
                raise ValueError(f"Unreviewed component in distribution: {relative}")
            used.add(component)
        files.append(
            {"path": relative, "sha256": digest, "bytes": len(data), "component": component, "origin": origin}
        )
    if not any(application_entry(item["path"]) for item in files):
        raise ValueError("Compiled application entry point missing")
    # LGPL libraries must remain external and replaceable; no onefile payload accepted.
    if not any("qt6core" in item["path"].lower() or "/QtCore.framework/" in item["path"] for item in files):
        raise ValueError("External Qt Core library missing; onefile/static builds are not qualified")
    selected = {name: components[name] for name in sorted(used)}
    for component in selected.values():
        for license_path in component["licenses"]:
            if not (distribution / license_path).is_file():
                raise ValueError(f"Required license missing: {license_path}")
    result = {
        "schema": SCHEMA,
        "components": selected,
        "files": files,
        "qt_source_catalog": "licenses/sources.json",
        "scope": "Actual distributed files; Qt source attributions are a conservative module superset. "
        "Unknown native files fail assembly. Not an assertion that every source dependency is linked.",
    }
    (distribution / "SBOM.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return result


def verify_entries(entries: dict[str, bytes]) -> dict:
    if any(not safe_name(name) for name in entries):
        raise ValueError("Unsafe distribution path")
    manifest = json.loads(entries["SBOM.json"])
    if manifest["schema"] != SCHEMA:
        raise ValueError("Unknown distribution manifest schema")
    listed = {item["path"]: item for item in manifest["files"]}
    if len(listed) != len(manifest["files"]) or set(entries) != {*listed, "SBOM.json"}:
        raise ValueError("Distribution inventory differs from manifest")
    for name, item in listed.items():
        if sha(entries[name]) != item["sha256"] or len(entries[name]) != item["bytes"]:
            raise ValueError(f"Distributed file changed: {name}")
        if item["component"] != "license-material" and item["component"] not in manifest["components"]:
            raise ValueError("Missing component mapping")
    required = catalog()
    for name, component in manifest["components"].items():
        if name not in required or not set(required[name]["licenses"]) <= set(component["licenses"]):
            raise ValueError("Incomplete component license list")
        for license_path in component["licenses"]:
            if license_path not in entries or not entries[license_path].strip():
                raise ValueError("Missing or empty license text")
    # Compare reviewed legal material too: regenerating a manifest cannot bless deleted clauses.
    for path in (ROOT / "licenses").rglob("*"):
        if path.is_file():
            relative = "licenses/" + path.relative_to(ROOT / "licenses").as_posix()
            if entries.get(relative) != path.read_bytes():
                raise ValueError(f"Reviewed license material differs: {relative}")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if entries.get(name) != (ROOT / name).read_bytes():
            raise ValueError(f"Reviewed notice differs: {name}")
    return {"passed": True, "files": len(listed), "components": len(manifest["components"])}


def verify(path: Path) -> dict:
    if path.is_dir():
        return verify_entries(
            {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        )
    with ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(names) != len(set(names)) or any(not safe_name(name) for name in names):
            raise ValueError("Unsafe or duplicate archive entries")
        prefixes = {name.split("/", 1)[0] for name in names}
        if len(prefixes) != 1 or any("/" not in name for name in names):
            raise ValueError("Expected one portable ZIP root")
        return verify_entries({name.split("/", 1)[1]: archive.read(name) for name in names})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("distribution", type=Path)
    parser.add_argument("--verify", "--verify-archive", action="store_true")
    args = parser.parse_args()
    if not args.verify:
        assemble(args.distribution)
    print(json.dumps(verify(args.distribution), indent=2))


if __name__ == "__main__":
    main()
