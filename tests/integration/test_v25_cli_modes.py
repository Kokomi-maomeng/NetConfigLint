import json
from pathlib import Path

import pytest

from netconfiglint.cli.main import main


@pytest.mark.parametrize("mode", ["snippet", "full", "snapshot", "message", "view"])
def test_all_documented_cli_modes(tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str) -> None:
    path = tmp_path / "synthetic.cfg"
    path.write_text("sysname SYNTHETIC\n", encoding="utf-8")
    assert main(["check", str(path), "--mode", mode, "--vendor", "huawei", "--format", "json"]) == 0
    assert '"mode"' in capsys.readouterr().out


def test_cli_limit_returns_controlled_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "synthetic-overlong.cfg"
    path.write_text("x" * 32769, encoding="utf-8")
    assert main(["check", str(path), "--vendor", "huawei"]) == 2
    output = capsys.readouterr()
    assert "Traceback" not in output.err


def test_incomplete_unknown_only_report_is_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "synthetic-diagnostic-budget.cfg"
    path.write_text("".join(f"unsupported-command-{index}\n" for index in range(2100)), encoding="utf-8")
    code = main(["check", str(path), "--vendor", "h3c", "--format", "json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 2 and not result["coverage"]["complete"]
    assert all(item["severity"] == "UNKNOWN" for item in result["diagnostics"])
