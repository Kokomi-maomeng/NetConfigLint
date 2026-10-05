"""Inspect local storage and find/restore indexed historical evidence.

Uses only the standard library. No command deletes files. Historical downloads
are opt-in, anonymous, and checked against the recorded SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
STORE = "archive/evidence-store/2026-10-06"
REPO = "Kokomi-maomeng/NetConfigLint"
_ASSET_CACHE: dict[str, tuple[Path, int, int]] = {}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root: Path, relative: str) -> Path:
    """Reject absolute/traversal paths and every reparse-point ancestor."""
    name = PurePosixPath(relative.replace("\\", "/"))
    if name.is_absolute() or ".." in name.parts or not name.parts or ":" in relative:
        raise ValueError(f"Unsafe relative path: {relative}")
    base = root.resolve(strict=True)
    target = base.joinpath(*name.parts)
    target.relative_to(base)
    current = base
    for part in name.parts:
        current /= part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Reparse point is not followed: {current}")
    return target


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    root = ROOT if root is None else root
    with gzip.open(inside(root, f"{STORE}/paths.json.gz"), "rt", encoding="utf-8") as stream:
        return cast(dict[str, Any], json.load(stream))


def old_paths(root: Path, query: str) -> list[str]:
    queries = [query.replace("\\", "/").strip("/")]
    mapping = root / "archive/build-path-map-2026-09-24.csv"
    if mapping.is_file():
        with mapping.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                original = row["Original"].replace("\\", "/")
                if queries[0] == original or queries[0].startswith(original + "/"):
                    queries.append(row["Archived"].replace("\\", "/") + queries[0][len(original) :])
    return queries


def matching(manifest: dict[str, Any], queries: list[str], *, exact: bool) -> list[dict[str, Any]]:
    if exact:
        for query in queries:
            found = [item for item in manifest["files"] if item["path"] == query]
            if found:
                return found
        return []
    return [
        item
        for item in manifest["files"]
        if any(item["path"] == q or (not exact and q.casefold() in item["path"].casefold()) for q in queries)
    ]


def asset_key(name: str) -> tuple[str, str, str] | None:
    match = re.search(r"-(windows|linux|macos)-(x64|amd64|arm64|aarch64)(.*)$", name)
    if not match:
        return None
    platform, arch, suffix = match.groups()
    arch = {"amd64": "x64", "aarch64": "arm64"}.get(arch, arch)
    if suffix.endswith(".zip"):
        kind = "portable.zip"
    elif suffix.endswith(".msi"):
        kind = "installer.msi"
    elif suffix.endswith(".deb"):
        kind = "installer.deb"
    elif suffix.endswith(".pkg"):
        kind = "installer.pkg"
    elif suffix.endswith(".exe"):
        kind = "installer.exe"
    else:
        return None
    return platform, arch, kind


def latest_assets(releases: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}

    def version(release: dict[str, Any]) -> tuple[int, int, int, str]:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", release["tag_name"])
        if not match:
            return -1, -1, -1, release["published_at"] or ""
        return int(match[1]), int(match[2]), int(match[3]), release["published_at"] or ""

    ordered = sorted(releases, key=version, reverse=True)
    for release in ordered:
        if release["draft"] or release["prerelease"]:
            continue
        for item in release["assets"]:
            key = asset_key(item["name"])
            if key is not None and key not in result:
                result[key] = {**item, "tag": release["tag_name"]}
    return result


def download_verified(asset: dict[str, Any], target: Path) -> None:
    """Never replace an existing file; partial downloads are removed on failure."""
    url = asset.get("url") or asset.get("browser_download_url")
    allowed_sources = (
        f"https://github.com/{REPO}/releases/download/",
        "https://files.pythonhosted.org/packages/",
        "https://github.com/actions/python-versions/releases/download/",
    )
    if not url or not url.startswith(allowed_sources):
        raise ValueError("Only recorded public Release/PyPI/Python toolchain assets can be downloaded")
    digest = asset.get("sha256") or str(asset.get("digest", "")).removeprefix("sha256:")
    size = asset.get("bytes", asset.get("size"))
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(size, int):
        raise ValueError("Download requires an exact size and SHA-256")
    if target.exists():
        if target.stat().st_size != size or sha256(target) != digest:
            raise ValueError(f"Existing file does not match the asset: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".download-", dir=target.parent)
    temporary = Path(name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "NetConfigLint-local-storage"})
        with os.fdopen(descriptor, "wb") as output, urllib.request.urlopen(request, timeout=60) as response:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if temporary.stat().st_size != size or sha256(temporary) != digest:
            raise ValueError("Downloaded asset failed size/SHA-256 verification")
        # link provides atomic create-without-overwrite on the same volume.
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_asset(root: Path, destination: str, asset: dict[str, Any], *, allow_download: bool) -> Path:
    cache_key = f"{root.resolve()}/{destination}/{asset['sha256']}"
    cached_result = _ASSET_CACHE.get(cache_key)
    if cached_result:
        path, size, modified = cached_result
        inside(root, path.relative_to(root).as_posix())
        if path.is_file() and (path.stat().st_size, path.stat().st_mtime_ns) == (size, modified):
            return path
    canonical = inside(root, f"release/{asset['name']}")
    if (
        canonical.is_file()
        and canonical.stat().st_size == asset["bytes"]
        and sha256(canonical) == asset["sha256"]
    ):
        info = canonical.stat()
        _ASSET_CACHE[cache_key] = canonical, info.st_size, info.st_mtime_ns
        return canonical
    cached = inside(root, f"{destination}/.downloads/{asset['name']}")
    if not cached.exists() and not allow_download:
        raise ValueError("Public download needed; rerun with --download")
    download_verified(asset, cached)
    info = cached.stat()
    _ASSET_CACHE[cache_key] = cached, info.st_size, info.st_mtime_ns
    return cached


def restore_item(root: Path, item: dict[str, Any], destination: str, *, allow_download: bool = False) -> Path:
    destination_parts = PurePosixPath(destination.replace("\\", "/")).parts
    if not destination_parts or destination_parts[0] not in {"build", "archive"}:
        raise ValueError("Restore destination must be in build/ or archive/")
    if destination_parts[:2] in {("archive", "evidence-store"), ("archive", "source-history")}:
        raise ValueError("Cannot restore into an archive store or source backup")
    target = inside(root, f"{destination}/{item['path']}")
    if target.exists():
        raise ValueError(f"Refusing to overwrite: {target}")
    mode = item["storage"]
    if mode == "historical-reference":
        raise ValueError(
            "Original evidence was absent before cleanup; "
            f"see {item['document']}:{item['line']} and Codex chat {item.get('task_id', 'unrecorded')}"
        )
    if mode in {"regenerate", "link-record"}:
        raise ValueError(f"This is {mode}; see its recorded reason/target")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            if mode == "blob":
                with (
                    zipfile.ZipFile(inside(root, f"{STORE}/content.zip")) as archive,
                    archive.open(item["member"]) as source,
                ):
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            elif mode == "local":
                with inside(root, item["local"]).open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            elif mode in {"release", "release-member", "upstream"}:
                asset = item["asset"]
                package = resolve_asset(root, destination, asset, allow_download=allow_download)
                if mode in {"release", "upstream"}:
                    with package.open("rb") as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                else:
                    with zipfile.ZipFile(package) as archive, archive.open(item["member"]) as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
            elif mode == "archive-member":
                package_info = item["package"]
                if package_info["storage"] == "indexed-package":
                    found = matching(load_manifest(root), [package_info["path"]], exact=True)
                    if len(found) != 1 or found[0]["sha256"] != package_info["sha256"]:
                        raise ValueError("Historical package reference differs from the manifest")
                    package_info = found[0]
                package = inside(root, f"{destination}/.downloads/{package_info['sha256']}.zip")
                if not package.exists():
                    restore_item(
                        root,
                        {**package_info, "path": f".downloads/{package_info['sha256']}.zip"},
                        destination,
                        allow_download=allow_download,
                    )
                if sha256(package) != package_info["sha256"]:
                    raise ValueError("Retained historical package failed verification")
                with zipfile.ZipFile(package) as archive, archive.open(item["member"]) as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            elif mode == "package-delta":
                checked_packages: dict[str, Path] = {}
                with zipfile.ZipFile(inside(root, f"{STORE}/content.zip")) as archive:
                    for segment in item["segments"]:
                        if segment["storage"] == "blob":
                            data = archive.read(segment["member"])
                        else:
                            asset = segment["asset"]
                            if asset["name"] not in checked_packages:
                                checked_packages[asset["name"]] = resolve_asset(
                                    root, destination, asset, allow_download=allow_download
                                )
                            package = checked_packages[asset["name"]]
                            with package.open("rb") as source:
                                source.seek(segment["offset"])
                                data = source.read(segment["bytes"])
                        if (
                            len(data) != segment["bytes"]
                            or hashlib.sha256(data).hexdigest() != segment["sha256"]
                        ):
                            raise ValueError("Historical ZIP segment failed verification")
                        output.write(data)
            else:
                raise ValueError(f"Unknown storage mode: {mode}")
        if temporary.stat().st_size != item["bytes"] or sha256(temporary) != item["sha256"]:
            raise ValueError("Restored file failed SHA-256/size verification")
        os.link(temporary, target)
        if item.get("mtime_ns"):
            os.utime(target, ns=(item["mtime_ns"], item["mtime_ns"]))
        return target
    finally:
        temporary.unlink(missing_ok=True)


def verify_store(root: Path, manifest: dict[str, Any]) -> dict[str, int]:
    blobs = {item["member"]: item for item in manifest["files"] if item["storage"] == "blob"}
    for item in manifest["files"]:
        if item["storage"] == "package-delta":
            for segment in item["segments"]:
                if segment["storage"] == "blob":
                    blobs[segment["member"]] = segment
    local = {item["local"]: item for item in manifest["files"] if item["storage"] == "local"}
    with zipfile.ZipFile(inside(root, f"{STORE}/content.zip")) as archive:
        names = set(archive.namelist())
        if set(blobs) != names:
            raise ValueError("Archive membership differs from the manifest")
        for number, (member, item) in enumerate(blobs.items(), 1):
            with archive.open(member) as source:
                hasher = hashlib.sha256()
                while block := source.read(1024 * 1024):
                    hasher.update(block)
                digest = hasher.hexdigest()
            if archive.getinfo(member).file_size != item["bytes"] or digest != item["sha256"]:
                raise ValueError(f"Archive verification failed: {member}")
            if number % 1000 == 0:
                print(f"verified {number}/{len(blobs)} archive members", flush=True)
    for relative, item in local.items():
        path = inside(root, relative)
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"Local recovery file differs: {relative}")
    releases = {
        item["asset"]["name"]
        for item in manifest["files"]
        if item["storage"] in {"release", "release-member"}
    }
    for item in manifest["files"]:
        if item["storage"] == "package-delta":
            releases.update(
                segment["asset"]["name"]
                for segment in item["segments"]
                if segment["storage"] == "release-range"
            )
    upstream = {item["asset"]["name"] for item in manifest["files"] if item["storage"] == "upstream"}
    return {
        "archive_members": len(blobs),
        "local_recovery_files": len(local),
        "release_assets": len(releases),
        "upstream_assets": len(upstream),
    }


def scan(root: Path) -> dict[str, Any]:
    totals: dict[str, list[int]] = {}
    links, errors = [], []

    def walk_error(error: OSError) -> None:
        errors.append({"path": str(error.filename), "error": str(error)})

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in list(dirs):
            path = Path(directory) / name
            if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                dirs.remove(name)
                links.append(path.relative_to(root).as_posix())
        for name in names:
            path = Path(directory) / name
            try:
                info = path.lstat()
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                    links.append(path.relative_to(root).as_posix())
                    continue
                category = path.relative_to(root).parts[0]
                count = totals.setdefault(category, [0, 0])
                count[0] += info.st_size
                count[1] += 1
            except OSError as error:
                errors.append({"path": str(path), "error": str(error)})
    return {
        "bytes": sum(value[0] for value in totals.values()),
        "files": sum(value[1] for value in totals.values()),
        "directories": dict(sorted(totals.items(), key=lambda value: value[1][0], reverse=True)),
        "reparse_points": links,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan", help="Read-only size/file-count scan")
    commands.add_parser("releases", help="Read-only latest stable assets, separately by platform/format")
    commands.add_parser("verify", help="Check all retained historical content against SHA-256")
    locator = commands.add_parser(
        "locate", help="Search current/former paths, including the September migration"
    )
    locator.add_argument("query")
    locator.add_argument("--limit", type=int, default=30)
    restorer = commands.add_parser("restore", help="Restore one file into a separate project directory")
    restorer.add_argument("path")
    restorer.add_argument("--to", default="build/restored-history")
    restorer.add_argument("--download", action="store_true", help="Allow a verified public Release download")
    restorer.add_argument(
        "--tree", action="store_true", help="Restore a directory's associated files together"
    )
    arguments = parser.parse_args()
    if arguments.command == "scan":
        print(json.dumps(scan(ROOT), ensure_ascii=False, indent=2))
    elif arguments.command == "releases":
        releases = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/releases", "--paginate"]))
        for key, asset in latest_assets(releases).items():
            print(
                json.dumps(
                    {
                        "platform_arch_format": key,
                        "tag": asset["tag"],
                        "name": asset["name"],
                        "url": asset["browser_download_url"],
                        "digest": asset.get("digest"),
                    },
                    ensure_ascii=False,
                )
            )
    else:
        manifest = load_manifest()
        if arguments.command == "verify":
            print(json.dumps(verify_store(ROOT, manifest)))
        else:
            hits = matching(
                manifest,
                old_paths(ROOT, arguments.query if arguments.command == "locate" else arguments.path),
                exact=arguments.command == "restore",
            )
            if arguments.command == "locate":
                for item in hits[: arguments.limit]:
                    display = {key: value for key, value in item.items() if key != "segments"}
                    if "segments" in item:
                        display["segments"] = len(item["segments"])
                    print(json.dumps(display, ensure_ascii=False))
                print(f"matches={len(hits)}; displayed={min(len(hits), arguments.limit)}")
                live = inside(ROOT, arguments.query)
                if live.exists():
                    print(f"Current path also exists: {live}")
            elif arguments.tree:
                prefixes = old_paths(ROOT, arguments.path)
                hits = [
                    item
                    for item in manifest["files"]
                    if any(item["path"].startswith(prefix.rstrip("/") + "/") for prefix in prefixes)
                ]
                if not hits:
                    raise ValueError("No historical files found under this directory")
                restored = skipped = 0
                for item in hits:
                    if item["storage"] in {"regenerate", "link-record", "historical-reference"}:
                        skipped += 1
                        continue
                    existing = inside(ROOT, f"{arguments.to}/{item['path']}")
                    if existing.is_file() and sha256(existing) == item["sha256"]:
                        continue
                    restore_item(ROOT, item, arguments.to, allow_download=arguments.download)
                    restored += 1
                print(f"Restored {restored} files; skipped {skipped} regenerable/link/reference records")
            elif len(hits) != 1:
                raise ValueError(f"Expected one exact historical file, got {len(hits)}")
            else:
                print(restore_item(ROOT, hits[0], arguments.to, allow_download=arguments.download))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
