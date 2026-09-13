"""Compile Linux/macOS runtimes for CI smoke tests, not release redistribution.

The release artifact is the Windows portable ZIP. Unix compiler relocation and
signing change library bytes, so its ephemeral smoke builds must not claim the
Windows exact-wheel provenance/license qualification.
"""

import configparser
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from check_build_environment import check


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
    spec["app"]["icon"] = ""
    spec["python"]["python_path"] = sys.executable
    spec["nuitka"]["extra_args"] = (
        " ".join(
            item
            for item in spec["nuitka"]["extra_args"].split()
            if not item.startswith(("--windows-", "--product-", "--file-"))
        )
        + " --report=build/nuitka-compilation.xml"
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
        env={**os.environ, "PYTHONUTF8": "1"},
        check=True,
    )
    distributions = list(dist.glob("*" + suffix))
    if len(distributions) != 1:
        raise RuntimeError("Expected exactly one compiled standalone distribution")
    distribution = distributions[0]
    if sys.platform == "darwin":
        with (distribution / "Contents/Info.plist").open("rb") as stream:
            entry = plistlib.load(stream)["CFBundleExecutable"]
        if not (distribution / "Contents/MacOS" / entry).is_file():
            raise RuntimeError("Compiled macOS bundle entry point missing")
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
    print(distribution.name)


if __name__ == "__main__":
    main()
