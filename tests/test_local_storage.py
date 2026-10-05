"""Safety and recovery checks for the local evidence locator."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "local_storage", Path(__file__).parents[1] / "scripts/local_storage.py"
)
assert SPEC and SPEC.loader
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


def test_platform_retention_preserves_missing_platforms_and_formats() -> None:
    def release(version: str, names: list[str], published: str) -> dict:
        return {
            "tag_name": version,
            "draft": False,
            "prerelease": False,
            "published_at": published,
            "assets": [{"name": name} for name in names],
        }

    releases = [
        release(
            "v2.0.0",
            [
                "NetConfigLint-2.0.0-linux-amd64.deb",
                "NetConfigLint-2.0.0-macos-arm64-unsigned.pkg",
                "NetConfigLint-2.0.0-windows-x64-portable.zip",
                "NetConfigLint-2.0.0-windows-x64-unsigned.msi",
            ],
            "2026-10-06",
        ),
        release("v2.1.0", ["NetConfigLint-2.1.0-windows-x64-portable.zip"], "2026-10-05"),
    ]
    names = {value["name"] for value in storage.latest_assets(releases).values()}
    assert "NetConfigLint-2.1.0-windows-x64-portable.zip" in names
    assert "NetConfigLint-2.0.0-windows-x64-portable.zip" not in names
    assert len(names) == 4
    assert "NetConfigLint-2.0.0-linux-amd64.deb" in names
    assert "NetConfigLint-2.0.0-macos-arm64-unsigned.pkg" in names
    assert "NetConfigLint-2.0.0-windows-x64-unsigned.msi" in names


@pytest.mark.parametrize(
    "path", ["../outside.txt", "build/../../outside.txt", "C:/outside.txt", "/outside.txt"]
)
def test_traversal_and_absolute_paths_are_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        storage.inside(tmp_path, path)


def test_symlink_ancestor_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError, match="Reparse"):
        storage.inside(tmp_path, "link/evidence.json")


def test_unicode_restore_refuses_overwrite_and_detects_corruption(tmp_path: Path) -> None:
    data = "历史操作记录\n".encode()
    archive = tmp_path / storage.STORE / "content.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("old/记录.txt", data)
    item = {
        "path": "build/旧目录 空格/记录.txt",
        "storage": "blob",
        "member": "old/记录.txt",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    result = storage.restore_item(tmp_path, item, "build/recovered")
    assert result.read_bytes() == data
    with pytest.raises(ValueError, match="overwrite"):
        storage.restore_item(tmp_path, item, "build/recovered")
    with pytest.raises(ValueError, match="verification"):
        storage.restore_item(tmp_path, {**item, "sha256": "0" * 64}, "build/corrupt")
    assert not (tmp_path / "build/corrupt" / item["path"]).exists()


def test_zip_delta_reconstructs_exact_bytes_without_download(tmp_path: Path) -> None:
    data = b"local header" + b"shared compressed content" + b"local directory"
    shared = b"shared compressed content"
    package = tmp_path / "release/source.zip"
    package.parent.mkdir()
    package.write_bytes(b"PREFIX" + shared + b"SUFFIX")
    asset = {
        "name": package.name,
        "url": f"https://github.com/{storage.REPO}/releases/download/v0/source.zip",
        "bytes": package.stat().st_size,
        "sha256": storage.sha256(package),
    }
    archive = tmp_path / storage.STORE / "content.zip"
    archive.parent.mkdir(parents=True)
    segments = []
    with zipfile.ZipFile(archive, "w") as output:
        for member, content in [("head", b"local header"), ("tail", b"local directory")]:
            output.writestr(member, content)
            segments.append(
                {
                    "storage": "blob",
                    "member": member,
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    segments.insert(
        1,
        {
            "storage": "release-range",
            "asset": asset,
            "offset": 6,
            "bytes": len(shared),
            "sha256": hashlib.sha256(shared).hexdigest(),
        },
    )
    item = {
        "path": "release/candidate.zip",
        "storage": "package-delta",
        "segments": segments,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    assert storage.restore_item(tmp_path, item, "build/recovered").read_bytes() == data


def test_same_name_candidate_is_preserved_and_official_cache_is_used(tmp_path: Path) -> None:
    candidate = tmp_path / "release/package.zip"
    candidate.parent.mkdir()
    candidate.write_bytes(b"a modified local candidate")
    cached = tmp_path / "build/recovery/.downloads/package.zip"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"official package")
    asset = {
        "name": "package.zip",
        "url": f"https://github.com/{storage.REPO}/releases/download/v1/package.zip",
        "bytes": cached.stat().st_size,
        "sha256": storage.sha256(cached),
    }
    assert storage.resolve_asset(tmp_path, "build/recovery", asset, allow_download=False) == cached
    assert candidate.read_bytes() == b"a modified local candidate"


def test_migrated_paths_and_packaged_member_remain_searchable(tmp_path: Path) -> None:
    mapping = tmp_path / "archive/build-path-map-2026-09-24.csv"
    mapping.parent.mkdir()
    mapping.write_text("Original,Archived,Category\nbuild/old,archive/evidence/old,v1\n", encoding="utf-8")
    manifest = {"files": [{"path": "archive/evidence/old/result.json", "storage": "blob"}]}
    assert storage.matching(manifest, storage.old_paths(tmp_path, "build/old/result.json"), exact=True)

    archive = tmp_path / storage.STORE / "content.zip"
    archive.parent.mkdir(parents=True)
    data = b"synthetic evidence"
    import io

    container = io.BytesIO()
    with zipfile.ZipFile(container, "w") as output:
        output.writestr("payload/report.txt", data)
    package_data = container.getvalue()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("candidate.zip", package_data)
    package_item = {
        "path": "release/candidate.zip",
        "storage": "blob",
        "member": "candidate.zip",
        "bytes": len(package_data),
        "sha256": hashlib.sha256(package_data).hexdigest(),
    }
    with gzip.open(archive.parent / "paths.json.gz", "wt", encoding="utf-8") as output:
        json.dump({"files": [package_item]}, output)
    item = {
        "path": "build/extracted/report.txt",
        "storage": "archive-member",
        "member": "payload/report.txt",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "package": {
            "storage": "indexed-package",
            "path": package_item["path"],
            "sha256": package_item["sha256"],
        },
    }
    assert storage.restore_item(tmp_path, item, "build/recovered").read_bytes() == data


def test_tree_restore_preserves_associated_files_and_skips_cache(tmp_path: Path, monkeypatch) -> None:
    import sys

    archive = tmp_path / storage.STORE / "content.zip"
    archive.parent.mkdir(parents=True)
    entries = []
    with zipfile.ZipFile(archive, "w") as output:
        for path, content in [
            ("build/session/probe.py", b"import json\n"),
            ("build/session/evidence/result.json", b'{"synthetic":true}\n'),
        ]:
            output.writestr(path, content)
            entries.append(
                {
                    "path": path,
                    "storage": "blob",
                    "member": path,
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    entries.append({"path": "build/session/__pycache__/probe.pyc", "storage": "regenerate", "bytes": 0})
    with gzip.open(archive.parent / "paths.json.gz", "wt", encoding="utf-8") as output:
        json.dump({"files": entries}, output)
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["local_storage.py", "restore", "build/session", "--tree", "--to", "build/recovered"]
    )
    assert storage.main() == 0
    for item in entries[:2]:
        assert storage.sha256(tmp_path / "build/recovered" / item["path"]) == item["sha256"]
    assert not (tmp_path / "build/recovered/build/session/__pycache__").exists()


def test_absent_historical_evidence_returns_origin_without_creating_output(tmp_path: Path) -> None:
    item = {
        "path": "build/old.log",
        "storage": "historical-reference",
        "bytes": 0,
        "document": "docs/old.md",
        "line": 12,
        "task_id": "original-chat",
    }
    with pytest.raises(ValueError, match=r"docs/old\.md:12.*original-chat"):
        storage.restore_item(tmp_path, item, "build/recovered")
    assert not (tmp_path / "build").exists()
