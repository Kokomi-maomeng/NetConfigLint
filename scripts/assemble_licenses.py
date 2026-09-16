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
import struct
import subprocess
import sys
from collections import Counter, defaultdict
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
        "Contents/MacOS/NetConfigLintApp",
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
                    names = {item.name.lower()}
                    # Nuitka drops CPython's ABI/platform suffix when copying
                    # standard-library extension modules into standalone builds.
                    names.add(re.sub(r"\.cpython-\d+[^.]*\.so$", ".so", item.name.lower()))
                    for name in names:
                        result[name].append((item, component, item.name))
    return result


def origin_names(name: str) -> tuple[str, ...]:
    """Return exact and compiler-normalized names that may share the same bytes.

    Nuitka removes the CPython ``.abi3`` tag when it copies PySide extension
    modules into a Linux standalone directory.  The byte-for-byte digest check
    below remains authoritative; this alias only lets us locate the matching
    file from the pinned upstream wheel.
    """
    lower = name.lower()
    if lower.endswith(".so") and not lower.endswith(".abi3.so"):
        return lower, lower[:-3] + ".abi3.so"
    return (lower,)


def elf_snapshot(path: Path) -> tuple[int, dict[str, bytes], list[str]] | None:
    """Read named sections from a little-endian ELF64 file without extra dependencies."""
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        return None
    header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    machine, section_offset = header[1], header[5]
    section_size, section_count, names_index = header[10], header[11], header[12]
    if section_size < 64 or section_count == 0 or names_index >= section_count:
        return None
    table_end = section_offset + section_size * section_count
    if table_end > len(data):
        return None
    records = [
        struct.unpack_from("<IIQQQQIIQQ", data, section_offset + index * section_size)
        for index in range(section_count)
    ]
    names_record = records[names_index]
    names = data[names_record[4] : names_record[4] + names_record[5]]
    section_names: list[str] = []
    for record in records:
        name_offset = record[0]
        if name_offset >= len(names):
            return None
        end = names.find(b"\0", name_offset)
        if end < 0:
            return None
        name = names[name_offset:end].decode("ascii", errors="strict")
        section_names.append(name)
    sections: dict[str, bytes] = {}
    for name, record in zip(section_names, records, strict=True):
        _, section_type, _, _, offset, size, *_ = record
        if not name:
            continue
        # SHT_NOBITS occupies memory but has no bytes in the file.
        content = b"" if section_type == 8 else data[offset : offset + size]
        if section_type != 8 and len(content) != size:
            return None
        if name in sections:
            return None
        sections[name] = content
    return machine, sections, section_names


def _elf_strings(data: bytes) -> Counter[bytes]:
    return Counter(item for item in data.split(b"\0") if item)


def _cstring(data: bytes, offset: int) -> bytes | None:
    if offset < 0 or offset >= len(data):
        return None
    end = data.find(b"\0", offset)
    return None if end < 0 else data[offset:end]


def _dynamic_entries(data: bytes) -> list[tuple[int, int]] | None:
    if len(data) % 16:
        return None
    return [struct.unpack_from("<QQ", data, offset) for offset in range(0, len(data), 16)]


def _dynamic_symbols(
    data: bytes, strings: bytes, section_names: list[str]
) -> list[tuple[bytes, int, int, str, int, int]] | None:
    if len(data) % 24:
        return None
    result = []
    for offset in range(0, len(data), 24):
        name_offset, info, other, section_index, value, size = struct.unpack_from("<IBBHQQ", data, offset)
        name = _cstring(strings, name_offset)
        if name is None:
            return None
        if section_index == 0:
            section = ""
        elif section_index >= 0xFF00:
            section = f"#{section_index}"
        elif section_index < len(section_names):
            section = section_names[section_index]
        else:
            return None
        result.append((name, info, other, section, value, size))
    return result


def _expected_deployment_rpath(source: bytes, deployed: bytes) -> bool:
    source_parts = [item for item in source.decode("ascii", errors="strict").split(":") if item]
    deployed_parts = [item for item in deployed.decode("ascii", errors="strict").split(":") if item]
    extras = set(deployed_parts) - set(source_parts)
    return set(source_parts) <= set(deployed_parts) and all(
        re.fullmatch(r"\$ORIGIN(?:/\.\.)*", item) for item in extras
    )


def _normalized_dynamic(
    entries: list[tuple[int, int]], strings: bytes
) -> tuple[list[tuple[int, int | bytes | None]], list[bytes]] | None:
    result: list[tuple[int, int | bytes | None]] = []
    rpaths: list[bytes] = []
    for tag, value in entries:
        if tag == 0:  # Ignore spare DT_NULL slots consumed when patchelf adds RPATH.
            continue
        if tag in {1, 14}:  # DT_NEEDED, DT_SONAME
            text = _cstring(strings, value)
            if text is None:
                return None
            result.append((tag, text))
        elif tag in {15, 29}:  # DT_RPATH, DT_RUNPATH
            text = _cstring(strings, value)
            if text is None:
                return None
            rpaths.append(text)
        elif tag in {5, 6, 10, 0x6FFFFEF5}:  # relocated string/symbol/hash tables
            result.append((tag, None))
        else:
            result.append((tag, value))
    return result, rpaths


def elf_deployment_match(source: Path, deployed: Path) -> bool:
    """Verify a Nuitka/patchelf copy while allowing only its RPATH relocation.

    Patchelf moves ``.gnu.hash`` and ``.dynstr`` and updates three dynamic
    pointers when it adds ``$ORIGIN`` lookup locations.  Every other named ELF
    section must remain byte-identical, all dependency strings must remain
    identical, and the only added dynamic string may be the constrained RPATH.
    """
    source_snapshot = elf_snapshot(source)
    deployed_snapshot = elf_snapshot(deployed)
    if source_snapshot is None or deployed_snapshot is None:
        return False
    source_machine, source_sections, source_section_names = source_snapshot
    deployed_machine, deployed_sections, deployed_section_names = deployed_snapshot
    if source_machine != deployed_machine or source_sections.keys() != deployed_sections.keys():
        return False
    allowed_sections = {".dynstr", ".dynsym", ".dynamic"}
    if any(
        source_sections[name] != deployed_sections[name] for name in source_sections.keys() - allowed_sections
    ):
        return False
    try:
        source_dynstr = source_sections[".dynstr"]
        deployed_dynstr = deployed_sections[".dynstr"]
        source_dynamic = _dynamic_entries(source_sections[".dynamic"])
        deployed_dynamic = _dynamic_entries(deployed_sections[".dynamic"])
    except KeyError:
        return False
    if source_dynamic is None or deployed_dynamic is None:
        return False
    if ".dynsym" in source_sections and _dynamic_symbols(
        source_sections[".dynsym"], source_dynstr, source_section_names
    ) != _dynamic_symbols(deployed_sections[".dynsym"], deployed_dynstr, deployed_section_names):
        return False
    source_normalized = _normalized_dynamic(source_dynamic, source_dynstr)
    deployed_normalized = _normalized_dynamic(deployed_dynamic, deployed_dynstr)
    if source_normalized is None or deployed_normalized is None:
        return False
    source_entries, source_rpaths = source_normalized
    deployed_entries, deployed_rpaths = deployed_normalized
    if source_entries != deployed_entries or len(deployed_rpaths) != 1 or len(source_rpaths) > 1:
        return False
    source_rpath = source_rpaths[0] if source_rpaths else b""
    try:
        if not _expected_deployment_rpath(source_rpath, deployed_rpaths[0]):
            return False
    except UnicodeDecodeError:
        return False
    source_strings = _elf_strings(source_dynstr)
    deployed_strings = _elf_strings(deployed_dynstr)
    for value in source_rpaths:
        source_strings[value] -= 1
    for value in deployed_rpaths:
        deployed_strings[value] -= 1
    # Patchelf overwrites the old in-place RPATH with same-length filler before
    # appending the enlarged value to the relocated string table.
    for value in source_rpaths:
        deployed_strings[b"X" * len(value)] -= 1
    return +source_strings == +deployed_strings


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
                    for name in origin_names(path.name)
                    for p, category, upstream in indexed.get(name, [])
                    if p.is_file() and sha(p.read_bytes()) == digest
                ),
                None,
            )
            if match is None:
                match = windows_runtime_origin(path, digest)
            if match is None:
                match = next(
                    (
                        (category, upstream + " (verified Nuitka RPATH relocation)")
                        for name in origin_names(path.name)
                        for p, category, upstream in indexed.get(name, [])
                        if p.is_file() and elf_deployment_match(p, path)
                    ),
                    None,
                )
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
