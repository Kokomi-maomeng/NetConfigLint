"""Build, optionally sign, and optionally notarize the macOS installer package."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
from pathlib import Path


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="2.2.0")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    app = root / "dist/NetConfigLint.app"
    plist = app / "Contents/Info.plist"
    if not plist.is_file():
        raise RuntimeError("dist/NetConfigLint.app is required")
    with plist.open("rb") as stream:
        info = plistlib.load(stream)
        if info.get("CFBundleIdentifier") != "online.castorice.netconfiglint":
            raise RuntimeError("Unexpected macOS bundle identity")
    entry = app / "Contents/MacOS" / info["CFBundleExecutable"]
    architectures = set(
        subprocess.run(["lipo", "-archs", str(entry)], check=True, capture_output=True, text=True)
        .stdout.strip()
        .split()
    )
    architecture = (
        "universal"
        if {"arm64", "x86_64"} <= architectures
        else "arm64"
        if "arm64" in architectures
        else "x64"
        if "x86_64" in architectures
        else "unknown"
    )
    if architecture == "unknown":
        raise RuntimeError(f"Unsupported macOS executable architectures: {sorted(architectures)}")
    stage = root / "build/macos-pkg/root"
    build_root = (root / "build/macos-pkg").resolve()
    if stage.exists():
        resolved = stage.resolve()
        if not resolved.is_relative_to(build_root):
            raise RuntimeError("Refusing to replace a package stage outside build/macos-pkg")
        shutil.rmtree(resolved)
    applications = stage / "Applications"
    applications.mkdir(parents=True)
    shutil.copytree(app, applications / app.name, symlinks=True)
    uninstall = applications / "Uninstall NetConfigLint.command"
    uninstall.write_text(
        """#!/bin/zsh
set -eu
read "answer?Delete NetConfigLint user data and history too? [y/N] "
case "$answer" in
  y|Y|yes|YES) /Applications/NetConfigLint.app/Contents/MacOS/NetConfigLintApp --remove-all-data ;;
esac
sudo rm -rf -- /Applications/NetConfigLint.app '/Applications/Uninstall NetConfigLint.command'
echo 'NetConfigLint was removed.'
read "reply?Press Return to close."
""",
        encoding="utf-8",
        newline="\n",
    )
    uninstall.chmod(uninstall.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    release = root / "release"
    release.mkdir(exist_ok=True)
    component = root / "build/macos-pkg/NetConfigLint-component.pkg"
    identity = os.environ.get("MACOS_APPLICATION_IDENTITY", "")
    if identity:
        run(
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--timestamp",
            "--sign",
            identity,
            str(applications / app.name),
        )
        run("codesign", "--verify", "--deep", "--strict", str(applications / app.name))
    package_identity = os.environ.get("MACOS_INSTALLER_IDENTITY", "")
    pkgbuild = [
        "pkgbuild",
        "--root",
        str(stage),
        "--identifier",
        "online.castorice.netconfiglint.pkg",
        "--version",
        args.version,
        "--install-location",
        "/",
        str(component),
    ]
    run(*pkgbuild)
    suffix = "" if identity and package_identity else "-unsigned"
    output = release / f"NetConfigLint-{args.version}-macos-{architecture}{suffix}.pkg"
    command = ["productbuild", "--package", str(component)]
    if package_identity:
        command += ["--sign", package_identity]
    command.append(str(output))
    run(*command)
    if package_identity:
        run("pkgutil", "--check-signature", str(output))
    notary_key = os.environ.get("MACOS_NOTARY_KEY_PATH", "")
    notary_key_id = os.environ.get("MACOS_NOTARY_KEY_ID", "")
    notary_issuer = os.environ.get("MACOS_NOTARY_ISSUER_ID", "")
    if any((notary_key, notary_key_id, notary_issuer)):
        if not identity or not package_identity:
            raise RuntimeError("Notarization requires both application and installer signing identities")
        if not all((notary_key, notary_key_id, notary_issuer)):
            raise RuntimeError("Notarization key path, key ID, and issuer ID must be supplied together")
        run(
            "xcrun",
            "notarytool",
            "submit",
            str(output),
            "--key",
            notary_key,
            "--key-id",
            notary_key_id,
            "--issuer",
            notary_issuer,
            "--wait",
        )
        run("xcrun", "stapler", "staple", str(output))
        run("spctl", "--assess", "--type", "install", "--verbose=2", str(output))
    print(output)


if __name__ == "__main__":
    main()
