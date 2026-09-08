from time import perf_counter

import pytest
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QFontDatabase, QTextDocument
from PySide6.QtTest import QTest

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.bridge import HuaweiConfigHighlighter
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.fonts import load_fonts, make_font
from netconfiglint.gui.models import DiagnosticListModel
from netconfiglint.gui.models.diagnostics import DiagnosticRole


def descendants(item):
    return item.childItems() + [c for child in item.childItems() for c in descendants(child)]


def test_filter_preserves_source_row_jump_and_unfiltered_export(qapp: object) -> None:
    model = DiagnosticListModel()
    items = tuple(
        Diagnostic(
            severity, "TEST", SourceRange(line), "target", "message", "why", "fix", Confidence.INFERRED
        )
        for severity, line in [(Severity.ERROR, 10), (Severity.WARNING, 20), (Severity.ERROR, 30)]
    )
    model.replace(items)
    model.setSeverityFilter("WARNING")
    assert model.rowCount() == 1
    assert model.data(model.index(0), DiagnosticRole.SOURCE_ROW) == 1
    assert model.data(model.index(0), DiagnosticRole.LINE) == 20
    assert model.items == items
    model.replace(items[:1])
    assert model.rowCount() == 0
    model.setSeverityFilter("ALL")
    assert model.rowCount() == 1


@pytest.mark.parametrize("count", [4093, 12000])
def test_dense_filters_keep_delegates_and_event_delay_bounded(qapp: object, count: int) -> None:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    model = controller.diagnosticsModel
    model.replace(
        tuple(
            Diagnostic(
                Severity.ERROR,
                "TEST",
                SourceRange(i + 1),
                "synthetic",
                "message",
                "why",
                "fix",
                Confidence.INFERRED,
            )
            for i in range(count)
        )
    )
    QTest.qWait(100)
    panel = next(item for item in descendants(window.contentItem()) if item.objectName() == "analysisPanel")
    for severity in ["ERROR", "WARNING", "ALL", "WARNING", "ALL"]:
        started = perf_counter()
        delivered = []
        QTimer.singleShot(20, lambda target=delivered: target.append(perf_counter()))
        panel.setProperty("severityFilter", severity)
        while not delivered and perf_counter() - started < 2:
            QCoreApplication.processEvents()
            QTest.qWait(5)
        assert delivered and delivered[0] - started < 2
        assert model.rowCount() == (0 if severity == "WARNING" else count)
        cards = [
            item for item in descendants(window.contentItem()) if item.objectName() == "diagnosticIssueCard"
        ]
        assert len(cards) < 80
    window.close()
    controller.close()


@pytest.mark.parametrize(
    "prefix", ["description ", "description 中文 ", "description 😀 ", "description 😀𠮷😀 "]
)
def test_highlighter_uses_utf16_offsets(qapp: object, prefix: str) -> None:
    document = QTextDocument(prefix + "192.0.2.1")
    highlighter = HuaweiConfigHighlighter(document)
    highlighter.rehighlight()
    address = next(
        value
        for value in document.firstBlock().layout().formats()
        if value.format.foreground().color().name() == "#1b6d43"
    )
    assert address.start == len(prefix.encode("utf-16-le")) // 2
    assert address.length == len("192.0.2.1")


def test_actual_qt_fonts_supply_the_active_fallbacks(qapp: object) -> None:
    load_fonts()
    available = set(QFontDatabase.families())
    for mono in [True, False]:
        font = make_font(14, mono=mono)
        assert font.families()
        assert (
            set(font.families()) <= available
            or font.families() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).families()
        )
    assert "Noto Sans SC" in make_font(14).families()
