"""Build a Debian 13 compatible amd64 package from the compiled distribution."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


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
    (stage / "DEBIAN").mkdir(parents=True)
    (stage / "DEBIAN/control").write_text(
        "\n".join(
            (
                "Package: netconfiglint",
                f"Version: {args.version}",
                "Section: net",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: NetConfigLint contributors",
                "Depends: libc6 (>= 2.36), libegl1, libgl1, libxkbcommon-x11-0, libxcb-cursor0",
                "Description: Offline Huawei VRP and H3C Comware configuration analyzer",
                " Static analysis with source-linked diagnostics and explicit unknown coverage.",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
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
exec sudo apt-get remove $purge netconfiglint
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
