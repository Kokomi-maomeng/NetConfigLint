import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from netconfiglint.cli.main import main


@pytest.mark.parametrize("encoding", ["gbk", "ascii", "utf-8"])
@pytest.mark.parametrize("format", ["json", "text"])
def test_f18_cli_unicode_output_is_complete(tmp_path: Path, encoding: str, format: str) -> None:
    path = tmp_path / "synthetic.cfg"
    path.write_text("interface Object-😀\n ip address INVALID 24\n", "utf-8")
    environment = {
        **os.environ,
        "PYTHONUTF8": "0",
        "PYTHONIOENCODING": encoding,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }
    result = subprocess.run(
        [sys.executable, "-m", "netconfiglint", "check", str(path), "--vendor", "huawei", "--format", format],
        env=environment,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 1 and not result.stderr
    if format == "json":
        assert json.loads(result.stdout)["diagnostics"][0]["object_name"] == "Object-😀"
    else:
        assert "HUA-IF-005" in result.stdout.decode(encoding)


@pytest.mark.parametrize("error", [BrokenPipeError, OSError])
def test_f18_io_failure_is_distinct_from_diagnostic_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[OSError]
) -> None:
    path = tmp_path / "synthetic.cfg"
    path.write_text("sysname SYNTHETIC", "utf-8")

    class BrokenStream(io.StringIO):
        def write(self, text: str) -> int:
            raise error("synthetic I/O failure")

    monkeypatch.setattr(sys, "stdout", BrokenStream())
    assert main(["check", str(path), "--vendor", "huawei", "--format", "json"]) == 2
