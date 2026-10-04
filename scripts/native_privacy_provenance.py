"""Reproduce reviewed runtime relocation from exact official archive bytes.

The result authorizes only a matching complete file hash, never a native file
type, section-only comparison, prefix, or caller-provided expected hash.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

if __package__:
    from .audit_release import REVIEWED_UPSTREAM_WHEELS, scan_bytes
else:
    from audit_release import REVIEWED_UPSTREAM_WHEELS, scan_bytes

PYTHON_RELEASE = "3.13.15-31064747964"
REVIEWED_PYTHON_ARCHIVES = {
    "python-3.13.15-linux-24.04-x64.tar.gz": (
        "4e544242f8a4ef647a6f511b67f9b00eefc9ef366644e3c40a27a6eff709ae2b"
    ),
    "python-3.13.15-darwin-arm64.tar.gz": (
        "219bafef64b35db55107253aba27f42298ffc4dd76853167af8d565b1bc0a992"
    ),
}
PATCHER_WHEEL = "patchelf-0.19.1.0-py3-none-manylinux1_x86_64.manylinux_2_5_x86_64.musllinux_1_1_x86_64.whl"
PATCHER_SHA256 = "a8f6331ccf40c345507279f755f4a38c2cb00b9efda746fd43c17713cce0aba4"
PATCHER_URL = (
    "https://files.pythonhosted.org/packages/e7/03/"
    "afd9bdd2ba5f96997196109f25dadbe5141bc6e70dffd85f3f84cc85d69c/" + PATCHER_WHEEL
)
QT_RELOCATED_MODULES = {
    "linux": {"libQt6Network.so.6", "libQt6Quick.so.6", "libQt6Widgets.so.6"},
    "macos": {"QtCore.so", "QtNetwork", "QtQuick", "QtWidgets"},
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reviewed(path: Path, expected: dict[str, str]) -> bytes:
    data = path.read_bytes()
    if path.is_symlink() or expected.get(path.name) != _digest(data):
        raise ValueError("Runtime input is not the exact reviewed official distribution")
    return data


def _reviewed_download_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname
        not in {
            "github.com",
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
            "files.pythonhosted.org",
        }
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Reviewed runtime download requires an approved public HTTPS origin")


class _ReviewedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        _reviewed_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_inputs(platform: str, directory: Path) -> tuple[Path, Path | None]:
    """Fetch fixed public inputs; verify their pinned whole-archive digest."""
    name = {
        "linux": "python-3.13.15-linux-24.04-x64.tar.gz",
        "macos": "python-3.13.15-darwin-arm64.tar.gz",
    }[platform]
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / name
    inputs = [
        (
            archive,
            f"https://github.com/actions/python-versions/releases/download/{PYTHON_RELEASE}/{name}",
            REVIEWED_PYTHON_ARCHIVES,
        )
    ]
    patcher = directory / PATCHER_WHEEL if platform == "linux" else None
    if patcher:
        inputs.append((patcher, PATCHER_URL, {PATCHER_WHEEL: PATCHER_SHA256}))
    for path, url, reviewed in inputs:
        if path.exists():
            _reviewed(path, reviewed)
            continue
        _reviewed_download_url(url)
        opener = urllib.request.build_opener(_ReviewedRedirect())
        try:
            with opener.open(url, timeout=60) as response, path.open("wb") as output:
                _reviewed_download_url(response.url)
                shutil.copyfileobj(response, output)
        except (OSError, ValueError):
            raise ValueError("Reviewed runtime input download failed") from None
        _reviewed(path, reviewed)
    return archive, patcher


def _binding_name(name: str) -> str:
    return re.sub(r"\.(?:abi3|cpython-313-(?:x86_64-linux-gnu|darwin))\.so$", ".so", name)


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


class IndependentRuntimeProvenance:
    """Keep immutable official sources and independently derived hashes in memory."""

    def __init__(self, platform: str, archive: Path, wheels: list[Path], patcher: Path | None):
        if platform not in {"linux", "macos"}:
            raise ValueError("Reviewed runtime replay supports Linux and macOS only")
        expected_archive = {
            "linux": "python-3.13.15-linux-24.04-x64.tar.gz",
            "macos": "python-3.13.15-darwin-arm64.tar.gz",
        }[platform]
        if archive.name != expected_archive:
            raise ValueError("Reviewed Python input differs from the native package platform")
        _reviewed(archive, REVIEWED_PYTHON_ARCHIVES)
        self.platform = platform
        self.archive_name = archive.name
        self.archive_sha256 = REVIEWED_PYTHON_ARCHIVES[archive.name]
        self.sources: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self.ambiguous: set[str] = set()
        self.cache: dict[tuple[str, str], dict[str, Any] | None] = {}
        self.replay_failures: dict[tuple[str, str], dict[str, str]] = {}
        self.patcher_bytes = None
        if platform == "linux":
            if patcher is None:
                raise ValueError("Exact reviewed patcher wheel is required")
            _reviewed(patcher, {PATCHER_WHEEL: PATCHER_SHA256})
            with zipfile.ZipFile(patcher) as package:
                self.patcher_bytes = package.read("patchelf-0.19.1.0.data/scripts/patchelf")
        self._python_sources(archive)
        for wheel in wheels:
            _reviewed(wheel, REVIEWED_UPSTREAM_WHEELS)
            with zipfile.ZipFile(wheel) as package:
                for member in package.infolist():
                    name = _binding_name(PurePosixPath(member.filename).name)
                    if (
                        member.filename.startswith("PySide6/")
                        and not member.is_dir()
                        and name in QT_RELOCATED_MODULES[platform]
                    ):
                        self._add_source(name, package.read(member), wheel.name, member.filename)

    def _add_source(self, name: str, data: bytes, archive: str, member: str) -> None:
        categories = scan_bytes(data)
        if not categories:
            return
        record = {
            "upstream_archive": archive,
            "upstream_archive_sha256": (
                REVIEWED_PYTHON_ARCHIVES.get(archive) or REVIEWED_UPSTREAM_WHEELS.get(archive)
            ),
            "upstream_member": member,
            "upstream_sha256": _digest(data),
            "upstream_categories": categories,
        }
        if name in self.sources and self.sources[name][0] != data:
            self.ambiguous.add(name)
        else:
            self.sources[name] = (data, record)

    def _python_sources(self, archive: Path) -> None:
        with tarfile.open(archive) as package:
            if self.platform == "linux":
                for member in package.getmembers():
                    if not member.isfile():
                        continue
                    normalized = member.name.removeprefix("./")
                    if normalized != "lib/libpython3.13.so.1.0" and not (
                        str(PurePosixPath(normalized).parent) == "lib/python3.13/lib-dynload"
                        and re.fullmatch(
                            r"[A-Za-z_][A-Za-z0-9_]*\.cpython-313-x86_64-linux-gnu\.so",
                            PurePosixPath(normalized).name,
                        )
                    ):
                        continue
                    stream = package.extractfile(member)
                    assert stream is not None
                    self._add_source(
                        _binding_name(PurePosixPath(normalized).name),
                        stream.read(),
                        archive.name,
                        normalized,
                    )
                return
            if sys.platform != "darwin":
                raise ValueError("macOS official package replay requires its native tools")
            members = [
                member for member in package.getmembers() if member.isfile() and member.name.endswith(".pkg")
            ]
            if len(members) != 1 or PurePosixPath(members[0].name).name != "python-3.13.15-macos11.pkg":
                raise ValueError("Expected one reviewed Python framework installation package")
            stream = package.extractfile(members[0])
            assert stream is not None
            with tempfile.TemporaryDirectory(prefix="netconfiglint-python-provenance-") as directory:
                root = Path(directory)
                installer = root / "python.pkg"
                installer.write_bytes(stream.read())
                expanded = root / "expanded"
                _run("/usr/sbin/pkgutil", "--expand-full", str(installer), str(expanded))
                for path in expanded.rglob("*"):
                    name = path.name
                    if path.is_symlink() or not path.is_file():
                        continue
                    relative = path.relative_to(expanded).as_posix()
                    if name == "Python" and "/Python.framework/Versions/3.13/" in relative:
                        self._add_source(name, path.read_bytes(), archive.name, relative)
                    elif "/lib/python3.13/lib-dynload/" in relative and re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]*\.cpython-313-darwin\.so", name
                    ):
                        self._add_source(_binding_name(name), path.read_bytes(), archive.name, relative)

    def _canonical_target(self, name: str) -> str | None:
        parts = PurePosixPath(name).parts
        if self.platform == "linux":
            if len(parts) != 3 or parts[:2] != ("opt", "netconfiglint"):
                return None
            return parts[2]
        prefix = ("Applications", "NetConfigLint.app", "Contents")
        if parts[:3] != prefix:
            return None
        rest = parts[3:]
        if len(rest) == 2 and rest[0] == "MacOS":
            return rest[1]
        if len(rest) == 3 and rest[:2] == ("MacOS", "PySide6") and rest[2] == "QtCore.so":
            return rest[2]
        # Framework code path has five segments below Contents.
        if len(rest) == 5 and rest[0] == "Frameworks" and rest[2] == "Versions" and rest[3] in {"A", "3.13"}:
            return rest[-1]
        return None

    def match(self, name: str, deployed: bytes, payload: Path) -> dict[str, Any] | None:
        canonical = self._canonical_target(name)
        if canonical not in self.sources or canonical in self.ambiguous:
            return None
        original, record = self.sources[canonical]
        categories = scan_bytes(deployed)
        if not categories or not set(categories) <= set(record["upstream_categories"]):
            return None
        key = name, _digest(deployed)
        if key in self.cache:
            return self.cache[key]
        result = None
        with tempfile.TemporaryDirectory(prefix="netconfiglint-native-replay-") as directory:
            temporary = Path(directory)
            target = temporary / canonical
            target.write_bytes(original)
            try:
                if self.platform == "linux":
                    if sys.platform != "linux":
                        return None
                    tool = temporary / "patchelf"
                    assert self.patcher_bytes is not None
                    tool.write_bytes(self.patcher_bytes)
                    tool.chmod(0o700)
                    _run(str(tool), "--force-rpath", "--set-rpath", "$ORIGIN", str(target))
                    steps = ["reviewed-patchelf-0.19.1.0 --force-rpath --set-rpath $ORIGIN"]
                else:
                    target, steps = self._macos_replay(target, original, payload, name, temporary)
                derived = _digest(target.read_bytes())
                if derived == key[1]:
                    result = {
                        **record,
                        "derived_sha256": derived,
                        "steps": steps,
                        "reason": "exact-independently-replayed-official-runtime-binary",
                    }
                else:
                    self.replay_failures[key] = {
                        "outcome": "whole-file-hash-mismatch",
                        "derived_sha256": derived,
                    }
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                # A source/member mismatch or tool failure cannot grant an exception.
                self.replay_failures[key] = {
                    "outcome": "native-replay-failed",
                    "error_type": type(error).__name__,
                }
                result = None
        self.cache[key] = result
        return result

    @staticmethod
    def _personal_paths(data: bytes) -> list[bytes]:
        paths = []
        for match in re.finditer(rb"/(?:Users|home)/[A-Za-z0-9_.-]+/", data):
            tail = data[match.start() : match.start() + 4096]
            paths.append(re.split(rb"[\x00\r\n\"'\s]", tail, maxsplit=1)[0])
        return paths

    def path_classifications(self, data: bytes) -> dict[str, int]:
        """Identify exact official strings or this job's workspace, without printing them.

        This is diagnostic evidence only and never authorizes an application binary.
        """
        official = {value for source, _ in self.sources.values() for value in self._personal_paths(source)}
        workspace = os.environ.get("GITHUB_WORKSPACE", "").encode()
        result = {"exact-official-input-string": 0, "current-job-workspace": 0, "unclassified": 0}
        for value in self._personal_paths(data):
            key = (
                "exact-official-input-string"
                if value in official
                else "current-job-workspace"
                if workspace and value.startswith(workspace + b"/")
                else "unclassified"
            )
            result[key] += 1
        return result

    def _macos_replay(
        self, target: Path, original: bytes, payload: Path, name: str, temporary: Path
    ) -> tuple[Path, list[str]]:
        if sys.platform != "darwin":
            raise ValueError("macOS byte replay requires native Apple tools")
        steps = []
        architectures = _run("/usr/bin/lipo", "-archs", str(target)).strip().split()
        if "arm64" not in architectures:
            raise ValueError("Reviewed macOS replay requires an official arm64 slice")
        if len(architectures) != 1:
            thin = temporary / "thin"
            _run("/usr/bin/lipo", "-thin", "arm64", str(target), "-output", str(thin))
            thin.replace(target)
            steps.append("lipo -thin arm64")
        app = payload / "Applications/NetConfigLint.app"
        candidates: dict[str, set[str]] = {}
        for path in app.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(app / "Contents").as_posix()
            if relative.startswith("MacOS/"):
                destination = relative.removeprefix("MacOS/")
            elif relative.startswith("Frameworks/"):
                destination = relative.removeprefix("Frameworks/")
            else:
                continue
            if (
                not re.fullmatch(r"[A-Za-z0-9_./+-]+", destination)
                or ".." in PurePosixPath(destination).parts
            ):
                continue
            candidates.setdefault(path.name, set()).add(destination)
        libraries = _run("/usr/bin/otool", "-L", str(target)).splitlines()[1:]
        identity = _run("/usr/bin/otool", "-D", str(target)).splitlines()[1:]
        command = ["/usr/bin/install_name_tool"]
        for line in libraries:
            old = line.strip().split(" (", 1)[0]
            if old in identity or old.startswith(("/System/Library/", "/usr/lib/")):
                continue
            basename = PurePosixPath(old).name
            choices = candidates.get(basename, set())
            if len(choices) != 1:
                raise ValueError("Official dependency does not have one qualified application destination")
            replacement = "@executable_path/" + next(iter(choices))
            command.extend(("-change", old, replacement))
        if identity:
            command.extend(("-id", target.name))
        if len(command) > 1:
            _run(*command, str(target))
            steps.append("install_name_tool: canonical application-local dependencies and basename identity")
        deployed = payload / name
        framework = next((path for path in deployed.parents if path.suffix == ".framework"), None)
        signing_target = target
        if framework:
            # Signing covers public framework metadata too; every such payload file
            # is independently scanned by the installer gate, never exempted here.
            copied = temporary / "framework" / framework.name
            shutil.copytree(framework, copied, symlinks=True)
            new_target = copied / deployed.relative_to(framework)
            shutil.copy2(target, new_target)
            target = new_target
            signing_target = copied
        _run(
            "/usr/bin/codesign",
            "--sign",
            "-",
            "--force",
            "--deep",
            "--preserve-metadata=entitlements",
            str(signing_target),
        )
        steps.append("codesign: ad-hoc, force, deep, preserve official entitlements")
        return target, steps


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", choices=("linux", "macos"), required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    download_inputs(args.download, args.directory)
    print("Exact reviewed runtime inputs downloaded and verified")
