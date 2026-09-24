import json
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

from netconfiglint import analyze
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.exporting import render_report
from netconfiglint.gui.models.history import HistoryEntry, HistoryStore


@pytest.mark.parametrize("bad", [None, [], "wrong", 4, {"ERROR": -1}, {"ERROR": True}, {"ERROR": "2"}])
def test_f15_isolates_bad_history_and_preserves_original(tmp_path: Path, qapp: object, bad: object) -> None:
    valid = asdict(HistoryEntry.from_result(analyze("sysname SYNTHETIC", vendor="huawei")))
    malformed = {**valid, "summary": bad}
    data = json.dumps([malformed, valid]).encode()
    path = tmp_path / "history.json"
    path.write_bytes(data)
    store = HistoryStore(path, enabled=True, persist_settings=False)
    assert store.load_warning and len(store.entries) == 1
    with pytest.raises(OSError):
        store.append(analyze("sysname SYNTHETIC", vendor="huawei"))
    assert path.read_bytes() == data
    store.clear()
    store.append(analyze("sysname SYNTHETIC", vendor="huawei"))
    assert json.loads(path.read_text("utf-8"))["schema_version"] == 2


@pytest.mark.parametrize(
    "data",
    [
        b"[",
        b"null",
        b"4",
        b'"root"',
        b"{}",
        b"[{}]",
        b'{"schema_version":99,"entries":[]}',
        b" " * (2 * 1024 * 1024 + 1),
    ],
    ids=["truncated", "null", "number", "string", "object", "missing-fields", "future-schema", "oversize"],
)
def test_f15_invalid_history_does_not_prevent_controller_start(
    tmp_path: Path, qapp: object, data: bytes
) -> None:
    path = tmp_path / "history.json"
    path.write_bytes(data)
    store = HistoryStore(path, enabled=True, persist_settings=False)
    controller = AnalysisController(history_store=store)
    assert controller.historyLoadWarning
    assert path.read_bytes() == data
    controller.close()


def test_f15_disabled_history_does_not_read_disk(
    tmp_path: Path, qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(self):
        raise AssertionError("Disabled history loaded")

    monkeypatch.setattr(HistoryStore, "_load", forbidden)
    HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False)


def descendants(item):
    return item.childItems() + [c for child in item.childItems() for c in descendants(child)]


@pytest.mark.parametrize("language", ["en", "zh_CN"])
@pytest.mark.parametrize("width", [960, 1440])
def test_f16_sidebar_history_fits_and_disabled_state_is_visible(
    tmp_path: Path, qapp: object, language: str, width: int
) -> None:
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False)
    store.entries = [
        HistoryEntry(
            "synthetic",
            "2026-09-09T00:00:00+00:00",
            "full",
            "Huawei",
            50,
            100,
            {"ERROR": 50, "WARNING": 0, "INFO": 0, "UNKNOWN": 0},
            tuple(f"HUA-SYNTHETIC-{i:03}" for i in range(50)),
        )
    ]
    controller = AnalysisController(history_store=store)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.setWidth(width)
    window.setHeight(800)
    engine.rootContext().contextProperty("i18n").language = language
    rail = next(i for i in descendants(window.contentItem()) if i.objectName() == "navigationRail")
    if width == 960:
        QTest.qWait(120)
        engine.rootContext().contextProperty("preferences").setValue("sidebarExpanded", True)
        rail.setProperty("expandedInCompact", True)
    QTest.qWait(400)
    card = next(i for i in descendants(window.contentItem()) if i.objectName() == "historyEntry-synthetic")
    assert card.isVisible() and card.width() <= rail.width()
    assert card.height() == 56
    assert window.grabWindow().save(str(tmp_path / "history-long.png"))
    controller.historyEnabled = False
    QTest.qWait(120)
    expected = controller.translator.text("history.disabled")
    assert any(i.isVisible() and i.property("text") == expected for i in descendants(window.contentItem()))
    assert window.grabWindow().save(str(tmp_path / "history.png"))
    window.close()
    controller.close()


@pytest.mark.parametrize("format", ["json", "md", "txt"])
def test_f17_export_preserves_object_confidence_and_entire_range(format: str) -> None:
    diagnostics = tuple(
        Diagnostic(
            Severity.ERROR,
            "SYNTHETIC",
            SourceRange(2, 4, 3, 7),
            "Object-😀",
            "message",
            "explanation",
            "fix",
            confidence,
        )
        for confidence in (Confidence.VERIFIED, Confidence.LOW)
    )
    payload = render_report(
        "",
        diagnostics,
        scope="diagnostics",
        format=format,
        diagnostics_first=True,
        mode="full",
        vendor="Huawei",
        text=lambda key: key,
    )
    for item in diagnostics:
        assert item.object_name in payload and item.confidence.value in payload
    if format == "json":
        assert json.loads(payload)["diagnostics"][0]["source"] == asdict(diagnostics[0].source)
    else:
        assert '"end_line": 4' in payload and '"column": 3' in payload and '"end_column": 7' in payload


def test_f21_gui_and_export_share_coverage(qapp: object, tmp_path: Path) -> None:
    controller = AnalysisController(async_enabled=False)
    controller.vendor = "huawei"
    controller.sourceText = "sysname SYNTHETIC\nunsupported command"
    controller.analyzeConfig()
    assert controller.coverage["unparsed_lines"] == [2]
    assert controller.prepareExport("diagnostics", "json", True)
    path = tmp_path / "report.json"
    controller.exportReport(str(path))
    assert json.loads(path.read_text("utf-8"))["coverage"] == controller.coverage
    controller.sourceText += "\n#"
    assert not controller.coverage
    controller.close()


def test_f20_running_gui_analysis_cancels_without_publishing(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from threading import Event

    from netconfiglint.vendors.huawei.parser import config_parser

    entered, release = Event(), Event()
    original = config_parser.checkpoint

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        original(*args, **kwargs)

    monkeypatch.setattr(config_parser, "checkpoint", paused)
    controller = AnalysisController()
    controller.vendor = "huawei"
    controller.sourceText = "sysname SYNTHETIC\n" + "vlan batch 10\n" * 100
    controller.analyzeConfig()
    try:
        assert entered.wait(3) and controller.busy
        controller.cancelAnalysis()
    finally:
        release.set()
    for _ in range(100):
        QTest.qWait(10)
        if not controller.busy:
            break
    assert not controller.busy and not controller.resultCurrent
    assert controller.statusMessage == "analysis.cancelled"
    assert controller.diagnosticsModel.rowCount() == 0
    controller.close()
