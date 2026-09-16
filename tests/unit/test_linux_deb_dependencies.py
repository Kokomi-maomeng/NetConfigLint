from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts import build_linux_deb as deb


def test_debian_dependencies_exclude_bundled_libraries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    executable = app / "NetConfigLint"
    bundled = app / "libQt6Core.so.6"
    executable.write_bytes(b"app")
    bundled.write_bytes(b"qt")
    graph = {
        executable: (None, ("libQt6Core.so.6", "libc.so.6")),
        bundled: ("libQt6Core.so.6", ("libstdc++.so.6", "libc.so.6")),
    }
    monkeypatch.setattr(deb, "_elf_metadata", graph.get)

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command == ["/sbin/ldconfig", "-p"]:
            output = """\
    libc.so.6 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libc.so.6
    libstdc++.so.6 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libstdc++.so.6
"""
        elif command[-1].endswith("libc.so.6"):
            output = "libc6:amd64: /usr/lib/x86_64-linux-gnu/libc.so.6\n"
        else:
            output = "libstdc++6:amd64: /usr/lib/x86_64-linux-gnu/libstdc++.so.6\n"
        return CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(deb.subprocess, "run", run)
    assert deb.debian_dependencies(app) == ["libc6", "libstdc++6"]


def test_debian_dependencies_fail_when_soname_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "app"
    executable = app / "NetConfigLint"
    executable.parent.mkdir()
    executable.write_bytes(b"app")
    monkeypatch.setattr(deb, "_elf_metadata", lambda path: (None, ("libmissing.so.1",)))
    monkeypatch.setattr(
        deb.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "", ""),
    )
    with pytest.raises(RuntimeError, match="No Debian runtime library"):
        deb.debian_dependencies(app)


def test_installed_size_counts_payload_but_not_control_metadata(tmp_path: Path) -> None:
    payload = tmp_path / "opt/netconfiglint"
    control = tmp_path / "DEBIAN"
    payload.mkdir(parents=True)
    control.mkdir()
    (payload / "application.bin").write_bytes(b"a" * 2048)
    (control / "control").write_bytes(b"x" * 1024 * 1024)

    size = deb.installed_size_kib(tmp_path)

    assert 2 <= size < 1024
