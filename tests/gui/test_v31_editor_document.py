"""Document actions must retain their meaning across the two paged editors."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models.history import HistoryStore


@pytest.fixture
def desktop(qapp: object, tmp_path: Path):
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    controller._temporary_path = tmp_path / "draft.txt"
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    window.show()
    window.requestActivate()
    assert QTest.qWaitForWindowExposed(window, 2000)
    assert QTest.qWaitForWindowActive(window, 2000)
    QTest.qWait(100)
    yield window, engine, controller, tmp_path
    controller._saved_source = controller.sourceText
    controller._saved_temporary = controller.temporaryText
    dispose_engine(qapp, engine, controller)


def _find(window: QObject, name: str) -> QObject:
    item = window.findChild(QObject, name)
    assert item is not None, name
    return item


def _text(controller: AnalysisController, name: str) -> str:
    return controller.sourceText if name == "configurationTextArea" else controller.temporaryText


def _load(controller: AnalysisController, name: str, source: str, directory: Path) -> None:
    if name == "configurationTextArea":
        target = directory / "source.txt"
        target.write_text(source, encoding="utf-8")
        controller.loadFile(str(target))
    else:
        controller.saveTemporaryText(source)
    QTest.qWait(30)


def _undo(window: QObject) -> None:
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)


def _redo(window: QObject) -> None:
    QTest.keyClick(
        window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    )


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_global_history_survives_navigation_completion_delete_and_goto(desktop: tuple, name: str) -> None:
    window, engine, controller, directory = desktop
    source = "description 🐱 SYNTHETIC-123456789\n" * 11_000 + "sysnam"
    _load(controller, name, source, directory)
    editor = _find(window, name)
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    editor.forceActiveFocus()
    editor.setProperty("cursorPosition", 0)
    for key in (Qt.Key.Key_X, Qt.Key.Key_Y, Qt.Key.Key_Z):
        QTest.keyClick(window, key)
    changed = "xyz" + source
    assert _text(controller, name) == changed
    assert editor.property("documentCanUndo")

    # Search/jump navigation does not become an edit or erase the previous edit.
    bridge.positionInPreview(editor, len(changed.encode("utf-16-le")) // 2)
    assert editor.property("previewPage") > 1
    _undo(window)
    assert _text(controller, name) == source
    assert not (controller.sourceDirty if name == "configurationTextArea" else controller.temporaryDirty)
    _redo(window)
    assert _text(controller, name) == changed

    # A completion replacement is one global edit even after moving to another page.
    bridge.positionInPreview(editor, len(changed.encode("utf-16-le")) // 2)
    editor.setProperty("cursorPosition", editor.property("length"))
    engine.rootContext().contextProperty("commandCompletion").toggleVendor("h3c")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    for _ in range(200):
        if _text(controller, name) == changed + "e ":
            break
        QTest.qWait(10)
    assert _text(controller, name) == changed + "e "
    completed = _text(controller, name)
    bridge.lineInPreview(editor, 4000)
    _undo(window)
    assert _text(controller, name) == changed
    _redo(window)
    assert _text(controller, name) == completed
    QTest.keyClick(window, Qt.Key.Key_Backspace)
    deleted = completed[:-1]
    assert _text(controller, name) == deleted
    bridge.stepPreviewPage(editor, -1)
    _undo(window)
    assert _text(controller, name) == completed
    _redo(window)
    assert _text(controller, name) == deleted


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
@pytest.mark.parametrize("page", [0, 3, 100])
def test_entire_document_copy_clear_replace_and_page_actions(desktop: tuple, name: str, page: int) -> None:
    window, engine, controller, directory = desktop
    source = "description 🐱 SYNTHETIC-123456789\n" * 11_000 + "END"
    _load(controller, name, source, directory)
    editor = _find(window, name)
    card = _find(window, "configurationEditor" if name == "configurationTextArea" else "temporaryEditor")
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    bridge.stepPreviewPage(editor, page)
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert editor.property("fullDocumentSelected")
    QTest.keyClick(window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text() == source
    QTest.keyClick(window, Qt.Key.Key_Delete)
    assert _text(controller, name) == bridge.fullText(editor) == ""
    assert not editor.property("pagedPreview")
    _undo(window)
    assert _text(controller, name) == source
    _redo(window)
    assert _text(controller, name) == ""
    _undo(window)

    # Explicit current-page actions retain the other pages and are also undoable.
    bridge.stepPreviewPage(editor, page)
    visible = editor.property("text")
    QMetaObject.invokeMethod(card, "selectCurrentPage")
    QTest.keyClick(window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text() == visible
    QMetaObject.invokeMethod(card, "clearCurrentPage")
    assert len(_text(controller, name)) == len(source) - len(visible)
    if name == "configurationTextArea":
        assert _find(card, "analyzeButton").property("enabled")
    _undo(window)
    assert _text(controller, name) == source

    # Paste/typing over a whole-document selection replaces the entire document.
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QGuiApplication.clipboard().setText("replacement 🐱\r\nsecond line")
    QTest.keyClick(window, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert _text(controller, name) == "replacement 🐱\nsecond line"
    _undo(window)
    assert _text(controller, name) == source
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_X)
    assert _text(controller, name) == "x"
    _undo(window)
    assert _text(controller, name) == source
    QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert _text(controller, name) == "\n"
    _undo(window)
    assert _text(controller, name) == source
    QMetaObject.invokeMethod(card, "clearDocument")
    assert bridge.fullText(editor) == ""
    if name == "configurationTextArea":
        assert not _find(card, "analyzeButton").property("enabled")
    _undo(window)
    assert _text(controller, name) == source


def test_ctrl_s_saves_focused_draft_search_target_and_respects_modal_query(desktop: tuple) -> None:
    window, _engine, controller, directory = desktop
    _load(controller, "configurationTextArea", "source baseline", directory)
    _load(controller, "temporaryTextArea", "draft baseline", directory)
    draft = _find(window, "temporaryTextArea")
    source = _find(window, "configurationTextArea")
    draft.setProperty("text", "draft edited")
    source.setProperty("text", "source edited")
    QTest.qWait(20)
    draft.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert controller._temporary_path.read_text(encoding="utf-8") == "draft edited"
    assert not controller.temporaryDirty and controller.sourceDirty
    assert (directory / "source.txt").read_text(encoding="utf-8") == "source baseline"

    draft.setProperty("text", "draft search saved")
    QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert controller._temporary_path.read_text(encoding="utf-8") == "draft search saved"
    QMetaObject.invokeMethod(_find(window, "editorSearchOverlay"), "closeSearch")
    draft.setProperty("text", "draft query unsaved")
    QMetaObject.invokeMethod(_find(window, "temporaryEditor"), "openCommandQuery")
    QTest.qWait(40)
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert controller.temporaryDirty and controller.sourceDirty
    assert controller._temporary_path.read_text(encoding="utf-8") == "draft search saved"
    QMetaObject.invokeMethod(_find(window, "temporaryTextAreaCommandQuery"), "close")
    QTest.qWait(300)
    source.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert (directory / "source.txt").read_text(encoding="utf-8") == "source edited"
    assert not controller.sourceDirty
