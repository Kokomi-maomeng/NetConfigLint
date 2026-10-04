"""Compile a platform-native Linux directory or macOS application bundle."""

import configparser
import os
import plistlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from check_build_environment import check
from prepare_linux_runtime import prune as prune_linux_runtime
from prepare_macos_runtime import prune as prune_macos_runtime

APP_NAME = "NetConfigLint"
APP_VERSION = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
)["project"]["version"]
MACOS_EXECUTABLE = "NetConfigLintApp"


def compilation_environment(root: Path) -> dict[str, str]:
    """Remove build-machine paths from compiler diagnostics and debug strings."""
    environment = {**os.environ, "PYTHONUTF8": "1"}
    # Nuitka passes inherited CFLAGS to GCC/Clang. This changes compiler-emitted
    # __FILE__/debug paths, without exempting the compiled program from audit.
    prefixes = (
        (Path.home(), "/usr/src/build-user"),
        (Path(sys.base_prefix), "/usr/local"),
        (root, "/usr/src/netconfiglint"),
    )
    flags = []
    for original, replacement in prefixes:
        value = str(original.resolve())
        if any(character.isspace() for character in value):
            raise ValueError("Unix compiler path mapping requires build paths without whitespace")
        flags.append(f"-ffile-prefix-map={value}={replacement}")
    environment["CFLAGS"] = " ".join(filter(None, (environment.get("CFLAGS", ""), *flags)))
    return environment


def _make_macos_icon(root: Path) -> Path:
    source = root / "netconfiglint/resources/icons/generated"
    iconset = root / "build/NetConfigLint.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    mappings = {
        "icon_16x16.png": "app-16.png",
        "icon_16x16@2x.png": "app-32.png",
        "icon_32x32.png": "app-32.png",
        "icon_32x32@2x.png": "app-64.png",
        "icon_128x128.png": "app-128.png",
        "icon_128x128@2x.png": "app-256.png",
        "icon_256x256.png": "app-256.png",
        "icon_256x256@2x.png": "app-512.png",
        "icon_512x512.png": "app-512.png",
        "icon_512x512@2x.png": "app-1024.png",
    }
    for destination, original in mappings.items():
        shutil.copy2(source / original, iconset / destination)
    target = root / "build/NetConfigLint.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)
    return target


def _qualify_macos_bundle(distribution: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    target = distribution.with_name(f"{APP_NAME}.app")
    if target.exists() and target != distribution:
        shutil.rmtree(target)
    if target != distribution:
        distribution.rename(target)
    plist_path = target / "Contents/Info.plist"
    with plist_path.open("rb") as stream:
        info = plistlib.load(stream)
    original_entry = info["CFBundleExecutable"]
    entry_path = target / "Contents/MacOS" / original_entry
    if not entry_path.is_file():
        raise RuntimeError("Compiled macOS bundle entry point missing")
    # The case-insensitive macOS filesystem already contains the bundled
    # ``netconfiglint`` package directory.  Using the display name for the
    # executable would collide with that directory, so keep a distinct bundle
    # entry point while retaining NetConfigLint as the user-facing app name.
    qualified_entry = target / "Contents/MacOS" / MACOS_EXECUTABLE
    if entry_path != qualified_entry:
        entry_path.rename(qualified_entry)
    info.update(
        {
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": "online.castorice.netconfiglint",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleIconFile": "NetConfigLint.icns",
            "CFBundleExecutable": MACOS_EXECUTABLE,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
        }
    )
    with plist_path.open("wb") as stream:
        plistlib.dump(info, stream, sort_keys=True)
    shutil.copy2(root / "build/NetConfigLint.icns", target / "Contents/Resources/NetConfigLint.icns")
    return target


def main() -> None:
    check()
    if sys.platform not in {"linux", "darwin"}:
        raise ValueError("Use build_windows.ps1 on Windows")
    root = Path(__file__).resolve().parents[1]
    spec = configparser.ConfigParser()
    spec.read(root / "pysidedeploy.spec", encoding="utf-8")
    for section in spec.sections():
        for key, value in spec[section].items():
            spec[section][key] = value.replace("\\", "/")
    spec["app"]["project_dir"] = str(root)
    spec["app"]["input_file"] = str(root / "netconfiglint/deploy_main.py")
    spec["app"]["exec_directory"] = str(root / "dist")
    spec["app"]["icon"] = str(_make_macos_icon(root)) if sys.platform == "darwin" else ""
    spec["python"]["python_path"] = sys.executable
    spec["nuitka"]["extra_args"] = (
        " ".join(
            item
            for item in spec["nuitka"]["extra_args"].split()
            if not item.startswith(("--windows-", "--product-", "--file-"))
        )
        + " --report=build/nuitka-compilation.xml"
        + " --user-plugin=scripts/nuitka_build_privacy.py"
    )
    build = root / "build"
    build.mkdir(exist_ok=True)
    path = build / "desktop-deploy.spec"
    with path.open("w", encoding="utf-8") as stream:
        spec.write(stream)
    dist = root / "dist"
    suffix = ".app" if sys.platform == "darwin" else ".dist"
    for generated in dist.glob("*" + suffix):
        if generated.is_symlink() or not generated.resolve().is_relative_to(dist.resolve()):
            raise ValueError("Unsafe generated distribution path")
        shutil.rmtree(generated)
    deploy = Path(sys.executable).with_name("pyside6-deploy")
    subprocess.run(
        [
            str(deploy),
            "-c",
            str(path),
            "--force",
            "--extra-ignore-dirs=.venv,build,dist,release,tests,docs,experiments,licenses,scripts",
        ],
        cwd=root,
        env=compilation_environment(root),
        check=True,
    )
    distributions = list(dist.glob("*" + suffix))
    if len(distributions) != 1:
        raise RuntimeError("Expected exactly one compiled standalone distribution")
    distribution = distributions[0]
    if sys.platform == "darwin":
        distribution = _qualify_macos_bundle(distribution)
        result = prune_macos_runtime(distribution)
        print(f"Pruned {result['removed_count']} unused macOS runtime entries")
        subprocess.run(
            [sys.executable, str(root / "scripts/assemble_licenses.py"), str(distribution)], check=True
        )
        subprocess.run(
            [sys.executable, str(root / "scripts/assemble_licenses.py"), str(distribution), "--verify"],
            check=True,
        )
        print(distribution.name)
        return
    executable = next(
        (
            p
            for p in distribution.iterdir()
            if p.is_file()
            and p.name in {"deploy_main", "deploy_main.bin", "NetConfigLint", "NetConfigLint.bin"}
        ),
        None,
    )
    if executable is None:
        raise RuntimeError("Compiled entry point missing")
    target = distribution / "NetConfigLint"
    if executable != target:
        executable.rename(target)
    result = prune_linux_runtime(distribution)
    print(f"Pruned {result['removed_count']} unused Linux runtime entries")
    print(distribution.name)


if __name__ == "__main__":
    main()
