"""Maintainer-only fetch of pinned official Qt license/attribution sources.

No application input is accessed. Release builds use the checked-in output offline.
"""

import hashlib
import json
import posixpath
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.11.2"


def fetch(url: str) -> bytes:
    return subprocess.run(
        ["curl", "-fsSL", "--max-time", "30", "--retry", "2", url], capture_output=True, check=True
    ).stdout


def collect(module: str) -> dict:
    repo = f"pyside/{module}" if module == "pyside-setup" else f"qt/{module}"
    cache = ROOT / "build" / "source-cache" / f"{module}-tree.json"
    tree = json.loads(
        cache.read_bytes()
        if cache.exists()
        else fetch(f"https://api.github.com/repos/{repo}/git/trees/v{VERSION}?recursive=1")
    )
    if tree.get("truncated"):
        raise ValueError("Incomplete upstream source tree")
    candidates = [
        entry
        for entry in tree["tree"]
        if entry["type"] == "blob"
        and (
            entry["path"].startswith("LICENSES/")
            or entry["path"].endswith("qt_attribution.json")
            or (
                "src/3rdparty/" in entry["path"]
                and re.search(
                    r"(?:^|/)(?:LICENSE|COPYING|COPYRIGHT|NOTICE)(?:\.[^/]*)?$", entry["path"], re.I
                )
            )
        )
    ]
    destination = ROOT / "licenses" / "upstream" / module

    def copy(entry: dict) -> dict:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe upstream license path")
        target = destination / relative
        data = (
            target.read_bytes()
            if target.exists()
            else fetch(f"https://raw.githubusercontent.com/{repo}/v{VERSION}/{relative}")
        )
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if blob != entry["sha"]:
            raise ValueError("Upstream license blob hash mismatch")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "file": target.relative_to(ROOT / "licenses").as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    with ThreadPoolExecutor(8) as executor:
        files = list(executor.map(copy, candidates))
    indexed = {entry["path"]: entry for entry in tree["tree"] if entry["type"] == "blob"}
    selected = {entry["path"] for entry in candidates}
    referenced = set()
    for entry in candidates:
        if not entry["path"].endswith("qt_attribution.json"):
            continue
        records = json.loads((destination / entry["path"]).read_text("utf-8"), strict=False)
        for record in records if isinstance(records, list) else [records]:
            names = record.get("LicenseFiles", []) + (
                [record["LicenseFile"]] if record.get("LicenseFile") else []
            )
            for name in names:
                relative = posixpath.normpath(posixpath.join(posixpath.dirname(entry["path"]), name))
                if relative not in indexed:
                    raise ValueError(f"Missing declared license source: {module}/{relative}")
                referenced.add(relative)
    with ThreadPoolExecutor(8) as executor:
        files.extend(executor.map(copy, [indexed[name] for name in sorted(referenced - selected)]))
    files.sort(key=lambda record: record["file"])
    return {
        "component": module,
        "version": VERSION,
        "source_tree_sha1": tree["sha"],
        "source_url": f"https://github.com/{repo}/tree/v{VERSION}",
        "source_archive": (
            f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{VERSION}-src/"
            f"pyside-setup-everywhere-src-{VERSION}.tar.xz"
            if module == "pyside-setup"
            else f"https://download.qt.io/archive/qt/6.11/{VERSION}/submodules/{module}-everywhere-src-{VERSION}.tar.xz"
        ),
        "files": files,
    }


def main() -> None:
    records = []
    for module in ("qtbase", "qtdeclarative", "qtsvg", "qtshadertools", "pyside-setup"):
        record = collect(module)
        records.append(record)
        print(module, len(record["files"]), flush=True)
    (ROOT / "licenses" / "sources.json").write_text(json.dumps(records, indent=2) + "\n", "utf-8")


if __name__ == "__main__":
    main()
