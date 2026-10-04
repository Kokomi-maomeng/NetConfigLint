"""Editor regressions use the actual QML components and complete source text."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QPointF, Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QTextCharFormat, QTextDocument
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

import netconfiglint.gui.fonts as font_module
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.bridge import NetworkConfigHighlighter
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


def _items(item: QQuickItem) -> list[QQuickItem]:
    return [item] + [child for direct in item.childItems() for child in _items(direct)]


def _find(window: QQuickWindow, name: str) -> QObject:
    return window.findChild(QObject, name) or next(
        item for item in _items(window.contentItem()) if item.objectName() == name
    )


def _wait_for(predicate: Callable[[], bool], message: str) -> None:
    for _ in range(150):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate(), message


@pytest.fixture
def desktop(qapp: object, tmp_path: Path):
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    engine = create_engine(controller)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.show()
    window.requestActivate()
    assert QTest.qWaitForWindowExposed(window, 2000)
    assert QTest.qWaitForWindowActive(window, 2000)
    window.setWidth(1600)
    QTest.qWait(200)
    yield window, engine, controller
    dispose_engine(qapp, engine, controller)


def test_full_source_search_crosses_pages_and_paged_edits_write_back(desktop: tuple) -> None:
    window, engine, controller = desktop
    source = "description 🐱 SYNTHETIC-LINE-123456789\n" * 9000 + "UNIQUE_LAST_PAGE_TOKEN"
    controller.sourceText = source
    QTest.qWait(100)
    editor = _find(window, "configurationTextArea")
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    assert editor.property("pagedPreview") and not editor.property("readOnly")
    assert len(editor.property("text")) <= 82_768
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    _find(window, "editorSearchField").setProperty("text", "UNIQUE_LAST_PAGE_TOKEN")
    overlay = _find(window, "editorSearchOverlay")
    _wait_for(
        lambda: len(overlay.property("searchResult").toVariant()["positions"]) == 1,
        "Full-source search did not find the last-page token",
    )
    assert len(overlay.property("searchResult").toVariant()["positions"]) == 1
    QMetaObject.invokeMethod(overlay, "find", Q_ARG("QVariant", 1))
    assert editor.property("selectedText") == "UNIQUE_LAST_PAGE_TOKEN"
    assert editor.property("previewPage") == editor.property("previewPageCount")
    assert _find(window, "editorSearchScope").property("text")
    QMetaObject.invokeMethod(overlay, "closeSearch")
    editor.setProperty("cursorPosition", editor.property("length"))
    for key in (Qt.Key.Key_X, Qt.Key.Key_Y, Qt.Key.Key_Z):
        QTest.keyClick(window, key)
    assert controller.sourceText == source + "xyz"
    assert bridge.fullText(editor) == controller.sourceText
    QMetaObject.invokeMethod(editor, "undo")
    assert controller.sourceText == source
    bridge.stepPreviewPage(editor, -1)
    bridge.stepPreviewPage(editor, 1)
    assert bridge.fullText(editor) == source


def test_paged_gutter_and_goto_use_global_lines(desktop: tuple) -> None:
    window, engine, controller = desktop
    controller.sourceText = "description SYNTHETIC-1234567890\n" * 11_001
    QTest.qWait(80)
    editor = _find(window, "configurationTextArea")
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    bridge.stepPreviewPage(editor, 1)
    start = editor.property("previewStartLine")
    assert start > 1
    assert _find(window, f"configurationTextAreaLine{start}").property("text") == str(start)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    field = _find(window, "configurationTextAreaLineField")
    field.setProperty("text", "11000")
    assert field.property("acceptableInput")
    QMetaObject.invokeMethod(field, "accepted")
    assert editor.property("previewPage") == editor.property("previewPageCount")
    card = _find(window, "configurationEditor")
    QTest.qWait(20)
    assert card.property("currentLine") + editor.property("previewStartLine") - 1 == 11000


def test_deleting_page_boundary_keeps_full_source_and_global_line_origin(desktop: tuple) -> None:
    window, engine, controller = desktop
    controller.sourceText = "description SYNTHETIC-1234567890\n" * 11_001
    QTest.qWait(80)
    editor = _find(window, "configurationTextArea")
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    first_page = editor.property("text")
    assert first_page.endswith("\n")
    page_last_line = first_page.count("\n")
    editor.setProperty("cursorPosition", editor.property("length"))
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Backspace)
    expected = first_page[:-1] + "description SYNTHETIC-1234567890\n" * (11_001 - page_last_line)
    assert bridge.fullText(editor) == controller.sourceText == expected
    bridge.stepPreviewPage(editor, 1)
    assert editor.property("previewStartLine") == page_last_line
    relative = bridge.lineInPreview(editor, page_last_line)
    assert relative == page_last_line
    assert editor.property("previewPage") == 1


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_backtab_navigates_without_completing_and_ctrl_tab_leaves_editor(desktop: tuple, name: str) -> None:
    window, engine, _ = desktop
    engine.rootContext().contextProperty("commandCompletion").toggleVendor("h3c")
    editor = _find(window, name)
    editor.setProperty("text", "sysnam")
    editor.setProperty("cursorPosition", 6)
    QTest.qWait(10)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Backtab)
    assert editor.property("text") == "sysnam"
    assert not editor.property("activeFocus")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert editor.property("text") == "sysnam"
    assert not editor.property("activeFocus")


def test_actual_error_has_gutter_feedback_and_clears_after_edit(desktop: tuple) -> None:
    window, engine, controller = desktop
    controller.vendor = "h3c"
    controller.sourceText = (
        "sysname SYNTHETIC\ninterface GigabitEthernet1/0/1\n ip address 999.1.1.1 255.255.255.0"
    )
    controller.analyzeConfig()
    QTest.qWait(30)
    assert any(marker["rule_id"] == "H3C-IF-005" for marker in controller.diagnosticMarkers)
    marker = _find(window, "configurationTextAreaDiagnostic3")
    assert marker.property("visible")
    document = _find(window, "configurationTextArea").property("textDocument").textDocument()
    highlighter = next(
        item
        for item in engine.rootContext().contextProperty("syntaxHighlighter")._highlighters
        if item.document() is document
    )
    assert any(
        item.format.background().color().isValid()
        for item in highlighter.document().findBlockByNumber(2).layout().formats()
    )
    controller.sourceText += "\n# edited"
    QTest.qWait(20)
    assert not _find(window, "configurationTextAreaDiagnostic3").property("visible")
    assert not highlighter._diagnostics


@pytest.mark.parametrize("dark", [False, True])
def test_highlighter_keeps_descriptions_and_quoted_strings_out_of_command_lexing(
    qapp: object, dark: bool
) -> None:
    document = QTextDocument(
        "stp mode mstp\nsnmp-agent sys-info version v3\n"
        "description peer shutdown 192.0.2.5 password\n"
        'description "password keyword"\nsnmp-agent community "password peer"'
    )
    highlighter = NetworkConfigHighlighter(document, dark=dark)
    highlighter.rehighlight()
    for index, tokens in ((0, ("mode", "mstp")), (1, ("sys-info", "version", "v3"))):
        block = document.findBlockByNumber(index)
        for token in tokens:
            start = block.text().index(token)
            assert any(
                part.start <= start < part.start + part.length
                and part.format.foreground().color() == highlighter._formats["keyword"].foreground().color()
                for part in block.layout().formats()
            )
    for index in (2, 3):
        block = document.findBlockByNumber(index)
        assert all(
            part.format.foreground().color() == highlighter._formats["quoted"].foreground().color()
            for part in block.layout().formats()
            if part.start >= len("description")
        )
    block = document.findBlockByNumber(4)
    quote_start = block.text().index('"')
    assert all(
        part.format.foreground().color() == highlighter._formats["quoted"].foreground().color()
        for part in block.layout().formats()
        if part.start >= quote_start
    )


def test_diagnostic_ranges_use_wave_underline_independent_of_address_color(qapp: object) -> None:
    document = QTextDocument("ip address 999.1.1.1 255.255.255.0")
    highlighter = NetworkConfigHighlighter(document)
    highlighter.set_diagnostics({1: {"severity": "ERROR", "column": 12, "end_column": 20}})
    assert any(
        part.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
        and part.format.foreground().color() == highlighter._formats["address"].foreground().color()
        for part in document.firstBlock().layout().formats()
    )
    highlighter.set_diagnostics({})
    assert not any(
        part.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
        for part in document.firstBlock().layout().formats()
    )


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_all_parameter_hints_and_query_remain_available_readonly_at_narrow_width(
    desktop: tuple, name: str
) -> None:
    window, engine, _ = desktop
    engine.rootContext().contextProperty("commandCompletion").toggleVendor("huawei")
    window.setWidth(640)
    QTest.qWait(50)
    editor = _find(window, name)
    editor.setProperty("text", "peer ")
    editor.setProperty("cursorPosition", 5)
    editor.setProperty("readOnly", True)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    card = _find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    result = card.property("completionResult")
    result = result.toVariant() if hasattr(result, "toVariant") else result
    assert len(result["arguments"]) > 8
    QTest.keyClick(window, Qt.Key.Key_F2)
    dialog = _find(window, name + "ArgumentDialog")
    assert dialog.property("visible")
    for _ in range(50):
        if dialog.property("opened"):
            break
        QTest.qWait(10)
    assert dialog.property("opened")
    hints = _find(window, name + "ArgumentList")
    assert hints.property("count") == len(result["argumentDetails"])
    shown = {alias for detail in result["argumentDetails"] for alias in detail["aliases"]}
    assert set(result["arguments"]) <= shown
    assert dialog.property("width") <= window.width()
    assert dialog.property("height") <= window.height()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert hints.property("activeFocus")
    for _ in range(hints.property("count") - 1):
        QTest.keyClick(window, Qt.Key.Key_Down)
    assert hints.property("currentIndex") == hints.property("count") - 1
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert _find(window, name + "CompletionDetails").property("visible")
    QMetaObject.invokeMethod(_find(window, name + "CompletionDetails"), "close")
    QMetaObject.invokeMethod(dialog, "close")
    QMetaObject.invokeMethod(card, "openCommandQuery")
    query = _find(window, name + "CommandQuery")
    assert query.property("visible")
    field = _find(window, name + "CommandQueryField")
    field.setProperty("text", "stp m")
    QTest.qWait(200)
    assert _find(window, name + "CommandQueryList").property("count") > 0
    QMetaObject.invokeMethod(card, "showQueryDetail", Q_ARG("QVariant", 0))
    detail = _find(window, name + "CompletionDetails")
    assert detail.property("visible")
    selected = card.property("completionDetail")
    selected = selected.toVariant() if hasattr(selected, "toVariant") else selected
    assert selected["sources"] and selected["syntaxDetails"]
    assert _find(window, name + "CompletionSyntaxes").property("text")
    assert _find(window, name + "CompletionViews").property("text")
    assert _find(window, name + "CompletionSyntaxes").width() > 100
    assert _find(window, name + "CompletionSyntaxes").height() > 0
    assert editor.property("text") == "peer "


@pytest.mark.parametrize("font_scale", [1.0, 1.5])
def test_small_english_blank_window_keeps_scrollable_workspace_and_real_editor_input(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, font_scale: float
) -> None:
    original = font_module.make_font

    def larger_font(size: int, weight: int = 400, *, mono: bool = False):
        return original(round(size * font_scale), weight, mono=mono)

    monkeypatch.setattr(font_module, "make_font", larger_font)
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    warnings = []

    def collect_warning(kind, _context, message):
        if kind in {QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg}:
            warnings.append(message)

    # Initialize the bundled font database before measuring QML layout warnings.
    font_module.load_fonts()
    font_module.make_font(15)
    previous_handler = qInstallMessageHandler(collect_warning)
    engine = None
    try:
        engine = create_engine(controller)
        window = engine.rootObjects()[0]
        window.show()
        window.requestActivate()
        assert QTest.qWaitForWindowExposed(window, 2000)
        assert QTest.qWaitForWindowActive(window, 2000)
        engine.rootContext().contextProperty("i18n").language = "en"
        engine.rootContext().contextProperty("preferences").setValue("reduceMotion", True)
        window.setWidth(640)
        window.setHeight(400)
        QTest.qWait(150)
        scroll = _find(window, "workspaceScrollView")
        _wait_for(
            lambda: (
                scroll.height() > 40
                and scroll.mapToScene(QPointF(0, scroll.height())).y() <= window.height() + 1
                and scroll.mapToScene(QPointF(scroll.width(), 0)).x() <= window.width() + 1
            ),
            "The resized workspace did not settle inside the actual window",
        )
        assert scroll.height() > 40
        assert scroll.mapToScene(QPointF(0, scroll.height())).y() <= window.height() + 1
        editor = _find(window, "configurationTextArea")
        editor.forceActiveFocus()

        def input_point():
            return editor.mapToScene(
                QPointF(editor.property("leftPadding") + 8, editor.property("topPadding") + 4)
            ).toPoint()

        _wait_for(
            lambda: scroll.mapToScene(QPointF()).y() <= input_point().y() < window.height(),
            "The real editor input point did not settle inside the viewport",
        )
        point = editor.mapToScene(
            QPointF(editor.property("leftPadding") + 8, editor.property("topPadding") + 4)
        ).toPoint()
        assert 0 <= point.x() < window.width()
        assert scroll.mapToScene(QPointF()).y() <= point.y() < window.height()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        QTest.keyClick(window, Qt.Key.Key_X)
        QTest.qWait(30)
        assert controller.sourceText == "x"

        def caret_visible():
            rect = editor.property("cursorRectangle")
            point = editor.mapToScene(QPointF(rect.x(), rect.y()))
            return (
                scroll.mapToScene(QPointF()).y() <= point.y() and point.y() + rect.height() <= window.height()
            )

        _wait_for(caret_visible, "The real editor caret did not settle inside the viewport")
        identity = _find(window, "sourceIdentityLabel")
        assert identity.mapToScene(QPointF()).y() >= 0
        assert identity.mapToScene(QPointF(0, identity.height())).y() <= scroll.mapToScene(QPointF()).y()
        caret = editor.property("cursorRectangle")
        position = editor.mapToScene(QPointF(caret.x(), caret.y()))
        assert scroll.mapToScene(QPointF()).y() <= position.y()
        assert position.y() + caret.height() <= window.height()
        for name in ("configurationEditor", "analysisPanel", "temporaryEditor"):
            panel = _find(window, name)
            if panel.property("visible"):
                assert panel.height() >= 479
        more = _find(window, "toolbarMoreButton")
        point = more.mapToScene(QPointF(more.width() / 2, more.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        QTest.qWait(20)
        assert _find(window, "supportScopeButton").property("visible")
    finally:
        if engine is not None:
            dispose_engine(qapp, engine, controller)
        qInstallMessageHandler(previous_handler)
    assert not warnings, "\n".join(warnings)
