"""Exercise the actual QML confirmation and its file/dirty-state consequences."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt, QUrl
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QSignalSpy, QTest

import netconfiglint.gui.completion as completion_module
import netconfiglint.gui.controllers.analysis as analysis_module
from netconfiglint.gui.app.main import create_engine, dispose_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.file_saving import SaveRecoveryError, inspect_destination
from netconfiglint.gui.models.history import HistoryStore


def _wait(predicate: Callable[[], bool], message: str) -> None:
    for _ in range(250):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate(), message


def _find(parent: QObject, name: str) -> QObject:
    item = parent.findChild(QObject, name)
    assert item is not None, name
    return item


def _click(window: QObject, name: str) -> None:
    item = _find(window, name)
    assert isinstance(item, QQuickItem)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    assert 0 <= point.x() < window.width() and 0 <= point.y() < window.height(), name
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point.toPoint())


@pytest.fixture
def desktop(qapp: object, tmp_path: Path):
    controller = AnalysisController(
        async_enabled=False,
        history_store=HistoryStore(tmp_path / "history.json", enabled=False, persist_settings=False),
    )
    controller._temporary_path = tmp_path / "scratch.txt"
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


def _edit_and_change_disk(window: QObject, controller: AnalysisController, directory: Path) -> Path:
    path = directory / "configuration.txt"
    path.write_text("sysname SYNTHETIC-BASE\n", encoding="utf-8")
    controller.loadFile(str(path))
    QTest.qWait(30)
    editor = _find(window, "configurationTextArea")
    editor.forceActiveFocus()
    editor.setProperty("cursorPosition", editor.property("length"))
    QTest.keyClick(window, Qt.Key.Key_X)
    assert controller.sourceText.endswith("\nx") and controller.sourceDirty
    path.write_text("sysname SYNTHETIC-EXTERNAL-ONE\n", encoding="utf-8")
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    dialog = _find(window, "saveConflictDialog")
    _wait(lambda: bool(dialog.property("opened")), "The save confirmation did not open")
    assert controller.fileConflict["reason"] == "changed"
    return path


def test_cancel_and_repeated_external_change_require_fresh_confirmation(desktop: tuple) -> None:
    window, _engine, controller, directory = desktop
    prompts = QSignalSpy(controller.fileConflictRequested)
    path = _edit_and_change_disk(window, controller, directory)
    edited = controller.sourceText
    assert prompts.count() == 1
    # A modal confirmation must not allow Ctrl+S to start a second save.
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert prompts.count() == 1
    _click(window, "fileConflictCancel")
    dialog = _find(window, "saveConflictDialog")
    _wait(lambda: not dialog.property("visible"), "Cancel did not dismiss the confirmation")
    assert controller.sourceText == edited and controller.sourceDirty
    assert path.read_text(encoding="utf-8") == "sysname SYNTHETIC-EXTERNAL-ONE\n"

    editor = _find(window, "configurationTextArea")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    _wait(lambda: bool(dialog.property("opened")), "The second confirmation did not open")
    latest = "sysname SYNTHETIC-EXTERNAL-TWO\n"
    path.write_text(latest, encoding="utf-8")
    _click(window, "fileConflictOverwrite")
    _wait(lambda: prompts.count() == 3, "A changed destination was not confirmed again")
    _wait(lambda: bool(dialog.property("opened")), "The updated confirmation did not remain open")
    assert path.read_text(encoding="utf-8") == latest and controller.sourceDirty
    assert controller._conflict_identity == inspect_destination(path)
    _click(window, "fileConflictOverwrite")
    _wait(lambda: not dialog.property("visible"), "Confirmed overwrite did not close the dialog")
    assert path.read_text(encoding="utf-8") == edited and not controller.sourceDirty
    assert controller._file_identity == inspect_destination(path)


def test_reload_updates_editor_and_next_save_uses_reloaded_identity(desktop: tuple) -> None:
    window, _engine, controller, directory = desktop
    prompts = QSignalSpy(controller.fileConflictRequested)
    path = _edit_and_change_disk(window, controller, directory)
    latest = "sysname SYNTHETIC-LATEST\n"
    path.write_text(latest, encoding="utf-8")
    _click(window, "fileConflictReload")
    dialog = _find(window, "saveConflictDialog")
    _wait(lambda: not dialog.property("visible"), "Reload did not close the confirmation")
    assert controller.sourceText == latest and not controller.sourceDirty
    assert controller._file_identity == inspect_destination(path)
    editor = _find(window, "configurationTextArea")
    editor.forceActiveFocus()
    editor.setProperty("cursorPosition", editor.property("length"))
    QTest.keyClick(window, Qt.Key.Key_Y)
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert prompts.count() == 1 and not controller.sourceDirty
    assert path.read_text(encoding="utf-8") == latest + "y"


@pytest.mark.parametrize("accept", [False, True], ids=["cancel", "save-new-file"])
def test_conflict_save_as_routes_picker_acceptance_and_cancellation(desktop: tuple, accept: bool) -> None:
    window, _engine, controller, directory = desktop
    original = _edit_and_change_disk(window, controller, directory)
    edited = controller.sourceText
    _click(window, "fileConflictSaveAs")
    picker = _find(window, "sourceSaveDialog")
    _wait(lambda: bool(picker.property("visible")), "Save as did not open the source file picker")
    dialog = _find(window, "saveConflictDialog")
    _wait(lambda: not dialog.property("visible"), "Save as did not close the conflict dialog")
    assert original.read_text(encoding="utf-8") == "sysname SYNTHETIC-EXTERNAL-ONE\n"
    destination = directory / "saved-copy.cfg"
    if accept:
        # Exercise the actual FileDialog signal wiring without operating a native
        # OS picker, which runs outside the offscreen test window on some systems.
        picker.setProperty("selectedFile", QUrl.fromLocalFile(str(destination)))
        QMetaObject.invokeMethod(picker, "accepted")
        assert destination.read_text(encoding="utf-8") == edited
        assert controller._file_path == destination and not controller.sourceDirty
    else:
        QMetaObject.invokeMethod(picker, "rejected")
        assert not destination.exists() and controller.sourceDirty
        assert controller.sourceText == edited and controller._file_path == original
    QMetaObject.invokeMethod(picker, "close")


def test_confirmation_language_changes_live_and_buttons_fit_narrow_window(desktop: tuple) -> None:
    window, engine, controller, directory = desktop
    window.setWidth(640)
    window.setHeight(400)
    _edit_and_change_disk(window, controller, directory)
    dialog = _find(window, "saveConflictDialog")
    translator = engine.rootContext().contextProperty("i18n")
    for language in ("zh_CN", "en", "zh_CN"):
        translator.language = language
        QTest.qWait(50)
        catalog = translator.catalog
        assert dialog.property("title") == catalog["file.conflict.title"]
        for name, key in (
            ("fileConflictCancel", "common.cancel"),
            ("fileConflictSaveAs", "file.conflict.save_as"),
            ("fileConflictReload", "file.conflict.reload"),
            ("fileConflictOverwrite", "file.conflict.overwrite"),
        ):
            button = _find(window, name)
            assert button.property("text") == catalog[key]
            assert isinstance(button, QQuickItem)
            start = button.mapToScene(QPointF())
            end = button.mapToScene(QPointF(button.width(), button.height()))
            assert start.x() >= 0 and start.y() >= 0, (language, name, start)
            assert end.x() <= window.width() and end.y() <= window.height(), (language, name, end)
    _click(window, "fileConflictCancel")


@pytest.mark.parametrize("name", ["configurationTextArea", "temporaryTextArea"])
def test_editor_worker_failure_preserves_text_and_shows_retryable_feedback(
    desktop: tuple, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    window, engine, controller, _directory = desktop
    editor = _find(window, name)
    original = "sysname SYNTHETIC-UNCHANGED"
    editor.setProperty("text", original)
    editor.setProperty("cursorPosition", editor.property("length"))
    editor.forceActiveFocus()
    monkeypatch.setattr(completion_module, "interactive_requires_async", lambda *_: True)

    def fail_worker(*_args, **_kwargs):
        raise OSError("Synthetic worker failure")

    monkeypatch.setattr(completion_module, "complete", fail_worker)
    QTest.keyClick(window, Qt.Key.Key_Tab)
    message = _find(window, name + "CompletionMessage")
    translator = engine.rootContext().contextProperty("i18n")
    _wait(
        lambda: (
            bool(message.property("visible"))
            and message.property("text") == translator.catalog["completion.failed"]
        ),
        "The worker failure did not produce visible editor feedback",
    )
    assert editor.property("text") == original
    assert (
        controller.sourceText if name == "configurationTextArea" else controller.temporaryText
    ) == original
    assert not _find(window, name + "CompletionBusy").property("running")
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.keyClick(window, Qt.Key.Key_X)
    assert editor.property("text") == original + "x"


def test_recovery_paths_remain_readable_and_cancel_reachable_in_narrow_window(
    desktop: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    window, engine, controller, directory = desktop
    window.setWidth(640)
    window.setHeight(400)
    translator = engine.rootContext().contextProperty("i18n")
    translator.language = "en"
    path = directory / "configuration.txt"
    path.write_text("sysname SYNTHETIC-BASE\n", encoding="utf-8")
    controller.loadFile(str(path))
    QTest.qWait(30)
    editor = _find(window, "configurationTextArea")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_X)
    recovery = tuple(directory / ("synthetic-recovery-" + str(index) + ".cfg") for index in range(3))
    for item in recovery:
        item.write_text("synthetic recovery data", encoding="utf-8")

    def fail_save(*_args, **_kwargs):
        raise SaveRecoveryError(recovery)

    monkeypatch.setattr(analysis_module, "save_configuration", fail_save)
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    dialog = _find(window, "saveConflictDialog")
    _wait(lambda: bool(dialog.property("opened")), "Recovery confirmation did not open")
    assert controller.fileConflict["reason"] == "recovery" and controller.sourceDirty
    assert all(str(item) in controller.fileConflict["target"] for item in recovery)
    assert dialog.property("height") <= window.height() - 16
    scroll = _find(window, "saveConflictScrollView")
    flickable = scroll.property("contentItem")
    assert flickable.property("contentHeight") > flickable.height()
    targets = _find(window, "fileConflictTarget")
    assert all(str(item) in targets.property("text") for item in recovery)
    metadata = _find(window, "fileConflictMetadata")
    flickable.setProperty("contentY", flickable.property("contentHeight") - flickable.height())
    QTest.qWait(30)
    bottom = metadata.mapToScene(QPointF(0, metadata.height()))
    viewport_bottom = scroll.mapToScene(QPointF(0, scroll.height()))
    assert bottom.y() <= viewport_bottom.y() + 1
    _click(window, "fileConflictCancel")
    _wait(lambda: not dialog.property("visible"), "Recovery cancellation did not close the dialog")
    assert controller.sourceDirty and all(item.exists() for item in recovery)
