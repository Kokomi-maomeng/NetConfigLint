"""Reject a portable archive that does not belong to the requested release commit."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile


def verify(archive: Path, tag: str) -> dict[str, str]:
    expected = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{commit}}"], check=True, capture_output=True, text=True
    ).stdout.strip()
    with ZipFile(archive) as bundle:
        manifests = [name for name in bundle.namelist() if name.endswith("/SBOM.json")]
        if len(manifests) != 1:
            raise ValueError("Expected one distribution manifest")
        info = bundle.getinfo(manifests[0])
        if info.file_size > 16 * 1024 * 1024:
            raise ValueError("Manifest exceeds size limit")
        manifest = json.loads(bundle.read(info))
    version = tag.removeprefix("v")
    if manifest.get("source_commit") != expected or manifest.get("application_version") != version:
        raise ValueError("Archive source commit/version differs from the release tag")
    if archive.name != f"NetConfigLint-{version}-windows-x64-portable.zip":
        raise ValueError("Archive name differs from the release version")
    return {"source_commit": expected, "application_version": version}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.tag)))


if __name__ == "__main__":
    main()
