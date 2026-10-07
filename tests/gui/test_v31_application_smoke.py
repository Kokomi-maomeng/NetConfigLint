"""Exercise the shipping acceptance flow, including cold asynchronous completion."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.app.smoke import run_smoke
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def test_shipping_smoke_handles_both_editors_and_writes_real_acceptance_evidence(
    qapp: QGuiApplication,
    tmp_path: Path,
) -> None:
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    startup_warnings: list[str] = []
    engine = create_engine(controller, startup_warnings)
    output = tmp_path / "smoke"
    output.mkdir()
    try:
        exit_code = run_smoke(qapp, engine, controller, output, startup_warnings)
        report = json.loads((output / "smoke-result.json").read_text(encoding="utf-8"))
        assert exit_code == 0 and report["passed"], report
        assert report["qml_errors"] == []
        assert report["default_mode"] == "snippet"
        assert report["exports"] == 3
        assert len(report["completion"]) == 4
        for name in ("configurationTextArea", "temporaryTextArea"):
            assert sum(row["editor"] == name and row["passed"] for row in report["completion"]) == 2
        for extension in ("json", "md", "txt"):
            assert "HUA-VLAN-001" in (output / f"synthetic-report.{extension}").read_text(encoding="utf-8")
        for image in ("workspace-light-zh.png", "export-light-zh.png", "settings-dark-en.png"):
            assert (output / image).stat().st_size > 1000
    finally:
        controller._saved_source = controller.sourceText
        controller._saved_temporary = controller.temporaryText
        dispose_engine(qapp, engine, controller)
