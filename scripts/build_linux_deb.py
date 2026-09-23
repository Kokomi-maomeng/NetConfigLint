"""Build a Debian 13 compatible amd64 package from the compiled distribution."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

if __package__:
    from .prepare_linux_runtime import _elf_metadata
else:
    from prepare_linux_runtime import _elf_metadata


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def debian_dependencies(app: Path) -> list[str]:
    """Map every non-bundled ELF dependency to its Debian binary package."""
    bundled: set[str] = set()
    needed: set[str] = set()
    for path in app.rglob("*"):
        if not path.is_file():
            continue
        metadata = _elf_metadata(path)
        if metadata is None:
            continue
        soname, dependencies = metadata
        bundled.add(path.name)
        if soname:
            bundled.add(soname)
        needed.update(dependencies)

    ldconfig = subprocess.run(["/sbin/ldconfig", "-p"], text=True, capture_output=True, check=True).stdout
    library_paths: dict[str, str] = {}
    for line in ldconfig.splitlines():
        match = re.match(r"^\s*(\S+) \([^)]*\) => (\S+)$", line)
        if match and (match[1] not in library_paths or "x86_64-linux-gnu" in match[2]):
            library_paths[match[1]] = os.path.realpath(match[2])

    packages: set[str] = set()
    for library in sorted(needed - bundled):
        path = library_paths.get(library)
        if path is None:
            raise RuntimeError(f"No Debian runtime library satisfies {library}")
        result = subprocess.run(["dpkg-query", "-S", path], text=True, capture_output=True, check=True)
        owner = next((line.split(":", 1)[0] for line in result.stdout.splitlines() if ": " in line), None)
        if not owner:
            raise RuntimeError(f"No Debian package owns {path}")
        packages.add(owner)
    return sorted(packages)


def installed_size_kib(stage: Path) -> int:
    """Estimate installed payload size like Debian's Installed-Size field."""
    total_bytes = 0
    for path in stage.rglob("*"):
        relative = path.relative_to(stage)
        if relative.parts and relative.parts[0] == "DEBIAN":
            continue
        metadata = path.lstat()
        blocks = getattr(metadata, "st_blocks", 0)
        total_bytes += blocks * 512 if blocks else metadata.st_size
    return max(1, (total_bytes + 1023) // 1024)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="2.0.0")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    distributions = [item for item in (root / "dist").glob("*.dist") if item.is_dir()]
    if len(distributions) != 1 or not (distributions[0] / "NetConfigLint").is_file():
        raise RuntimeError("Expected one compiled Linux distribution containing NetConfigLint")
    stage = root / "build/deb/root"
    build_root = (root / "build/deb").resolve()
    if stage.exists():
        resolved = stage.resolve()
        if not resolved.is_relative_to(build_root):
            raise RuntimeError("Refusing to replace a package stage outside build/deb")
        shutil.rmtree(resolved)
    app = stage / "opt/netconfiglint"
    shutil.copytree(distributions[0], app)
    for legal in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / legal, app / legal)
    subprocess.run(
        [
            os.fspath(Path(os.sys.executable)),
            os.fspath(root / "scripts/assemble_licenses.py"),
            os.fspath(app),
        ],
        check=True,
    )
    dependencies = debian_dependencies(app)
    (stage / "DEBIAN").mkdir(parents=True)
    bin_dir = stage / "usr/bin"
    bin_dir.mkdir(parents=True)
    write_executable(bin_dir / "netconfiglint-gui", '#!/bin/sh\nexec /opt/netconfiglint/NetConfigLint "$@"\n')
    write_executable(
        bin_dir / "netconfiglint-uninstall",
        """#!/bin/sh
set -eu
printf 'Remove NetConfigLint user data and history too? [y/N] '
read answer
case "$answer" in
  y|Y|yes|YES) /opt/netconfiglint/NetConfigLint --remove-all-data; purge='--purge' ;;
  *) purge='' ;;
esac
exec sudo apt-get remove -y $purge netconfiglint
""",
    )
    applications = stage / "usr/share/applications"
    applications.mkdir(parents=True)
    (applications / "netconfiglint.desktop").write_text(
        """[Desktop Entry]
Type=Application
Name=NetConfigLint
Comment=Offline network configuration analyzer
Exec=/usr/bin/netconfiglint-gui
Icon=netconfiglint
Terminal=false
Categories=Network;Utility;
StartupWMClass=NetConfigLint
""",
        encoding="utf-8",
        newline="\n",
    )
    icons = stage / "usr/share/icons/hicolor/256x256/apps"
    icons.mkdir(parents=True)
    shutil.copy2(root / "netconfiglint/resources/icons/generated/app-256.png", icons / "netconfiglint.png")
    (stage / "DEBIAN/control").write_text(
        "\n".join(
            (
                "Package: netconfiglint",
                f"Version: {args.version}",
                "Section: net",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: NetConfigLint contributors",
                f"Installed-Size: {installed_size_kib(stage)}",
                "Depends: " + ", ".join(dependencies),
                "Description: Offline Huawei VRP and H3C Comware configuration analyzer",
                " Static analysis with source-linked diagnostics and explicit unknown coverage.",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    release = root / "release"
    release.mkdir(exist_ok=True)
    output = release / f"NetConfigLint-{args.version}-linux-amd64.deb"
    if output.exists():
        output.unlink()
    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", os.fspath(stage), os.fspath(output)], check=True
    )
    subprocess.run(["dpkg-deb", "--info", os.fspath(output)], check=True)
    print(output)


if __name__ == "__main__":
    main()
