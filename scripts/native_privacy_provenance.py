"""Reproduce reviewed runtime relocation from exact official archive bytes.

The result authorizes only a matching complete file hash, never a native file
type, section-only comparison, prefix, or caller-provided expected hash.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import marshal
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
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
DIAGNOSTIC_MEMBER_LIMIT = 4096
DIAGNOSTIC_MEMBER_BYTES = 2 * 1024 * 1024
DIAGNOSTIC_TOTAL_BYTES = 96 * 1024 * 1024
DIAGNOSTIC_PATH_LIMIT = 16384


class NativeReplayError(ValueError):
    """A fixed public failure reason, with no input path or tool output."""

    def __init__(self, reason: str, **details: str | int):
        super().__init__(reason)
        self.details = {"reason": reason, **details}


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


def _replay_tool(stage: str, *args: str) -> str:
    try:
        return _run(*args)
    except (OSError, subprocess.SubprocessError) as error:
        raise NativeReplayError(
            "native-tool-failed", stage=stage, tool_error_type=type(error).__name__
        ) from None


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
        self.replay_failures: dict[tuple[str, str], dict[str, Any]] = {}
        self.path_index: dict[bytes, set[tuple[str, str, str]]] = {}
        self.proven_paths: dict[bytes, set[str]] = {}
        self.diagnostic_index = {"members": 0, "bytes": 0, "skipped": 0, "decode_failures": 0}
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

    def _index_paths(self, data: bytes, module: str, kind: str, key: str = "") -> None:
        for value in self._personal_paths(data):
            if len(self.path_index) >= DIAGNOSTIC_PATH_LIMIT and value not in self.path_index:
                self.diagnostic_index["skipped"] += 1
                continue
            self.path_index.setdefault(value, set()).add((module, kind, key))

    @staticmethod
    def _stdlib_module(member: str) -> str | None:
        """Use only safe public names under the official production standard library."""
        parts = PurePosixPath(member).parts
        if "python3.13" not in parts:
            return None
        relative = parts[parts.index("python3.13") + 1 :]
        if not relative or any(
            part in {"test", "tests", "site-packages", "idle_test", "lib-dynload"} for part in relative
        ):
            return None
        if any(not re.fullmatch(r"[A-Za-z0-9_.+-]+", part) for part in relative):
            return None
        name = relative[-1]
        if not name.endswith((".py", ".pyc")):
            return None
        name = re.sub(r"\.cpython-313(?:\.opt-[12])?\.pyc$", ".py", name)
        relative = (*(part for part in relative[:-1] if part != "__pycache__"), name)
        return "/".join(relative)

    def _index_stdlib(self, member: str, data: bytes) -> None:
        """Read pinned source/bytecode as bounded diagnostic data, never execute it."""
        module = self._stdlib_module(member)
        if module is None:
            return
        stats = self.diagnostic_index
        if (
            len(data) > DIAGNOSTIC_MEMBER_BYTES
            or stats["members"] >= DIAGNOSTIC_MEMBER_LIMIT
            or stats["bytes"] + len(data) > DIAGNOSTIC_TOTAL_BYTES
        ):
            stats["skipped"] += 1
            return
        stats["members"] += 1
        stats["bytes"] += len(data)
        try:
            if member.endswith(".py"):
                tree = ast.parse(data)
                docstrings = set()
                for node in ast.walk(tree):
                    if (
                        isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and node.body
                        and isinstance(node.body[0], ast.Expr)
                    ):
                        docstrings.add(id(node.body[0].value))
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        kind = "source-docstring" if id(node) in docstrings else "source-string-constant"
                        self._index_paths(node.value.encode(), module, kind)
                if PurePosixPath(module).name.startswith("_sysconfigdata_"):
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                            continue
                        if not any(
                            isinstance(target, ast.Name) and target.id == "build_time_vars"
                            for target in node.targets
                        ):
                            continue
                        for key, value in zip(node.value.keys, node.value.values, strict=True):
                            if (
                                isinstance(key, ast.Constant)
                                and isinstance(key.value, str)
                                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", key.value)
                                and isinstance(value, ast.Constant)
                                and isinstance(value.value, str)
                            ):
                                self._index_paths(
                                    value.value.encode(), module, "source-sysconfig-build-var", key.value
                                )
            elif data[:4] == importlib.util.MAGIC_NUMBER and len(data) > 16:
                # Exact SHA-pinned official CPython archive; decode only, never execute.
                code = marshal.loads(data[16:])  # nosec B302
                pending = [code]
                visited = 0
                while pending and visited < 8192:
                    value = pending.pop()
                    visited += 1
                    if isinstance(value, types.CodeType):
                        self._index_paths(value.co_filename.encode(), module, "bytecode-code-filename")
                        pending.extend(value.co_consts)
                    elif isinstance(value, str):
                        self._index_paths(value.encode(), module, "bytecode-string-constant")
                    elif isinstance(value, (tuple, frozenset)):
                        pending.extend(value)
            else:
                stats["decode_failures"] += 1
        except (SyntaxError, UnicodeError, EOFError, ValueError, TypeError):
            stats["decode_failures"] += 1

    def _python_sources(self, archive: Path) -> None:
        with tarfile.open(archive) as package:
            if self.platform == "linux":
                for member in package.getmembers():
                    if not member.isfile():
                        continue
                    normalized = member.name.removeprefix("./")
                    if self._stdlib_module(normalized) is not None:
                        if member.size > DIAGNOSTIC_MEMBER_BYTES:
                            self.diagnostic_index["skipped"] += 1
                        else:
                            stream = package.extractfile(member)
                            assert stream is not None
                            self._index_stdlib(normalized, stream.read())
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
                _replay_tool(
                    "official-python-package-expansion",
                    "/usr/sbin/pkgutil",
                    "--expand-full",
                    str(installer),
                    str(expanded),
                )
                for path in expanded.rglob("*"):
                    name = path.name
                    if path.is_symlink() or not path.is_file():
                        continue
                    relative = path.relative_to(expanded).as_posix()
                    if self._stdlib_module(relative) is not None:
                        if path.stat().st_size > DIAGNOSTIC_MEMBER_BYTES:
                            self.diagnostic_index["skipped"] += 1
                        else:
                            self._index_stdlib(relative, path.read_bytes())
                    if PurePosixPath(relative).parts == (
                        "Python_Framework.pkg",
                        "Payload",
                        "Versions",
                        "3.13",
                        "Python",
                    ):
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
        if (
            len(rest) == 5
            and rest[0] == "Frameworks"
            and rest[1] == rest[-1] + ".framework"
            and rest[2] == "Versions"
            and rest[3] == ("3.13" if rest[-1] == "Python" else "A")
        ):
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
                    for value in self._personal_paths(target.read_bytes()):
                        self.proven_paths.setdefault(value, set()).add(canonical)
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
                    **(error.details if isinstance(error, NativeReplayError) else {}),
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
        official = set(self.path_index) | {
            value for source, _ in self.sources.values() for value in self._personal_paths(source)
        }
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

    def path_details(self, data: bytes) -> dict[str, Any]:
        """Publish only safe official module/key labels and counts; never matching bytes."""
        counts: dict[tuple[str, str, str], int] = {}
        proven_counts: dict[str, int] = {}
        proven_matches = 0
        values = self._personal_paths(data)
        for value in values:
            for label in self.path_index.get(value, ()):
                counts[label] = counts.get(label, 0) + 1
            if value in self.proven_paths:
                proven_matches += 1
            for module in self.proven_paths.get(value, ()):
                proven_counts[module] = proven_counts.get(module, 0) + 1
        return {
            "stdlib_matches": [
                {"module": module, "kind": kind, **({"key": key} if key else {}), "count": count}
                for (module, kind, key), count in sorted(counts.items())[:256]
            ],
            "index": self.diagnostic_index.copy(),
            "proven_payload_matches": [
                {"module": module, "count": count} for module, count in sorted(proven_counts.items())[:256]
            ],
            "exact-proved-payload-string": proven_matches,
            "not-proved-payload-string": len(values) - proven_matches,
            "truncated": len(counts) > 256,
        }

    def _macos_replay(
        self, target: Path, original: bytes, payload: Path, name: str, temporary: Path
    ) -> tuple[Path, list[str]]:
        if sys.platform != "darwin":
            raise NativeReplayError("native-apple-tools-required")
        steps = []
        architectures = (
            _replay_tool("official-architecture-inspection", "/usr/bin/lipo", "-archs", str(target))
            .strip()
            .split()
        )
        if "arm64" not in architectures:
            raise NativeReplayError("official-arm64-slice-missing")
        if len(architectures) != 1:
            thin = temporary / "thin"
            _replay_tool(
                "official-arm64-thinning",
                "/usr/bin/lipo",
                "-thin",
                "arm64",
                str(target),
                "-output",
                str(thin),
            )
            thin.replace(target)
            steps.append("lipo -thin arm64")
        app = payload / "Applications/NetConfigLint.app"
        candidates: dict[str, set[str]] = {}
        missing_framework_aliases = set()
        for path in app.rglob("*"):
            if path.is_symlink() or not path.is_file() or not path.is_relative_to(app / "Contents"):
                continue
            relative = path.relative_to(app / "Contents").as_posix()
            if relative.startswith("MacOS/"):
                destination = relative.removeprefix("MacOS/")
            elif relative.startswith("Frameworks/"):
                destination = relative.removeprefix("Frameworks/")
                # Nuitka first fixes loader names against MacOS-relative paths,
                # then relocates frameworks and keeps that original path as a
                # symlink. Derive only that actual qualified runtime alias.
                alias = app / "Contents/MacOS" / destination
                if not alias.is_file() or alias.resolve() != path.resolve():
                    missing_framework_aliases.add(path.name)
                    continue
            else:
                continue
            if (
                not re.fullmatch(r"[A-Za-z0-9_./+-]+", destination)
                or ".." in PurePosixPath(destination).parts
            ):
                continue
            candidates.setdefault(path.name, set()).add(destination)
        libraries = _replay_tool(
            "official-dependency-inspection", "/usr/bin/otool", "-L", str(target)
        ).splitlines()[1:]
        identity = _replay_tool(
            "official-identity-inspection", "/usr/bin/otool", "-D", str(target)
        ).splitlines()[1:]
        command = ["/usr/bin/install_name_tool"]
        for line in libraries:
            old = line.strip().split(" (", 1)[0]
            if old in identity or old.startswith(("/System/Library/", "/usr/lib/")):
                continue
            basename = PurePosixPath(old).name
            choices = candidates.get(basename, set())
            if len(choices) != 1:
                details: dict[str, str | int] = {"candidate_count": len(choices)}
                if re.fullmatch(r"[A-Za-z0-9_.+-]{1,128}", basename):
                    details["official_dependency_basename"] = basename
                reason = (
                    "framework-runtime-alias-missing"
                    if not choices and basename in missing_framework_aliases
                    else "application-dependency-destination-not-unique"
                )
                raise NativeReplayError(reason, **details)
            replacement = "@executable_path/" + next(iter(choices))
            command.extend(("-change", old, replacement))
        # Nuitka 4.2 resolves @-prefixed self references and marks had_self,
        # but skips an absolute/bare self ID by its source basename before
        # marking had_self. The reviewed official Python.framework uses that
        # absolute self ID, so Nuitka preserves it instead of setting -id.
        rewrite_identity = any(
            value.startswith(("@rpath/", "@loader_path/", "@executable_path/")) for value in identity
        )
        if rewrite_identity:
            command.extend(("-id", target.name))
        elif identity:
            steps.append("LC_ID_DYLIB: keep official absolute/bare self identity, matching Nuitka 4.2")
        if len(command) > 1:
            _replay_tool("canonical-loader-relocation", *command, str(target))
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
        _replay_tool(
            "independent-ad-hoc-signing",
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
