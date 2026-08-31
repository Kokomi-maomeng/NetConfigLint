from __future__ import annotations

import json
from pathlib import Path

from netconfiglint.cli.main import main


def test_cli_json_output(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "config.cfg"
    path.write_text("sysname LAB\ninterface GE1/0/1\n port default vlan 100", encoding="utf-8")

    exit_code = main(["check", str(path), "--format", "json"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["rule_id"] == "HUA-VLAN-002"


def test_cli_reports_file_error(tmp_path: Path, capsys: object) -> None:
    exit_code = main(["check", str(tmp_path / "missing.cfg")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 2
    assert "missing.cfg" in captured.err
