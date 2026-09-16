from __future__ import annotations

import json
from pathlib import Path

from netconfiglint.cli.main import main


def test_cli_json_output(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "config.cfg"
    path.write_text("sysname LAB\ninterface GE1/0/1\n port default vlan 100", encoding="utf-8")

    exit_code = main(["check", str(path), "--mode", "full", "--format", "json"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["rule_id"] == "HUA-VLAN-002"


def test_cli_reports_file_error(tmp_path: Path, capsys: object) -> None:
    exit_code = main(["check", str(tmp_path / "missing.cfg")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 2
    assert "missing.cfg" in captured.err


def test_cli_h3c_json_keeps_source_and_reports_semantic_boundary(tmp_path: Path, capsys: object) -> None:
    path = tmp_path / "h3c.cfg"
    path.write_text(
        "H3C Comware Software, Version 7.1.070, Release 6715P06\n"
        "interface GigabitEthernet1/0/1\n"
        " port trunk permit vlan 200\n"
        " telemetry\n",
        encoding="utf-8",
    )

    exit_code = main(["check", str(path), "--mode", "snippet", "--vendor", "auto", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert exit_code == 0
    assert payload["detection"]["vendor"] == "H3C"
    assert payload["coverage"]["semantic_complete"] is False
    assert {item["rule_id"] for item in payload["diagnostics"]} >= {
        "H3C-VLAN-001",
        "H3C-CMD-001",
        "H3C-CMD-002",
    }
