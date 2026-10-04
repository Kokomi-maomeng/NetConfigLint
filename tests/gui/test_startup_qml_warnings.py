"""A binding loop during QML load must reach the package smoke result."""

from pathlib import Path

import pytest

from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models import HistoryStore


def test_qml_warnings_are_connected_before_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: object
) -> None:
    (tmp_path / "Main.qml").write_text(
        "import QtQuick\nWindow { property real first: second + 1; property real second: first + 1 }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("netconfiglint.gui.app.main.qml_root", lambda: tmp_path)
    controller = AnalysisController(
        async_enabled=False, history_store=HistoryStore(tmp_path / "history.json", enabled=False)
    )
    warnings: list[str] = []
    engine = create_engine(controller, warnings)
    try:
        assert engine.rootObjects()
        assert any("Binding loop" in warning for warning in warnings), warnings
    finally:
        dispose_engine(qapp, engine, controller)
