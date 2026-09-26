import os
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.models import HistoryStore


def _descendants(item: QQuickItem) -> list[QQuickItem]:
    return item.childItems() + [child for parent in item.childItems() for child in _descendants(parent)]


def test_sidebar_history_restores_then_branches_edited_source(tmp_path: Path, qapp: object) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore(path, enabled=True, persist_settings=False)
    controller = AnalysisController(async_enabled=False, history_store=store)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1440)
    window.setHeight(900)
    QTest.qWait(80)
    controller.vendor = "huawei"
    controller.sourceText = "sysname ORIGINAL\n"
    controller.analyzeConfig()
    assert len(store.entries) == 1
    original_id = store.entries[0].entry_id
    QTest.qWait(120)
    row = next(
        item
        for item in _descendants(window.contentItem())
        if item.objectName() == "historyEntry-" + original_id
    )
    point = row.mapToScene(QPointF(30, row.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
    assert controller.sourceText == "sysname ORIGINAL\n"
    assert controller.resultCurrent
    assert controller.coverage == store.get(original_id).coverage
    controller.analyzeConfig()
    assert len(store.entries) == 1
    controller.sourceText = "sysname MODIFIED\n"
    controller.analyzeConfig()
    assert len(store.entries) == 2
    assert store.get(original_id).source_text == "sysname ORIGINAL\n"
    QTest.qWait(120)
    rail = next(item for item in _descendants(window.contentItem()) if item.objectName() == "navigationRail")
    newest = next(
        item
        for item in _descendants(window.contentItem())
        if item.objectName() == "historyEntry-" + store.entries[0].entry_id
    )
    older = next(
        item
        for item in _descendants(window.contentItem())
        if item.objectName() == "historyEntry-" + original_id
    )
    QTest.mouseClick(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=newest.mapToScene(QPointF(30, 28)).toPoint(),
    )
    QTest.mouseClick(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        pos=older.mapToScene(QPointF(30, 28)).toPoint(),
    )
    selected = rail.property("selectedHistory")
    if hasattr(selected, "toVariant"):
        selected = selected.toVariant()
    assert len(selected) == 2
    button = next(
        item
        for item in _descendants(window.contentItem())
        if item.objectName() == "deleteSelectedHistoryButton"
    )
    QTest.mouseClick(
        window,
        Qt.MouseButton.LeftButton,
        pos=button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint(),
    )
    assert len(store.entries) == 0
    window.close()
    controller.close()


def test_disabling_history_requires_confirmation_and_deletes_saved_source(
    tmp_path: Path, qapp: object
) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore(path, enabled=True, persist_settings=False)
    controller = AnalysisController(async_enabled=False, history_store=store)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    controller.vendor = "huawei"
    controller.sourceText = "sysname PRIVATE-SYNTHETIC\n"
    controller.analyzeConfig()
    assert path.exists()

    def click(name: str) -> None:
        item = next(item for item in _descendants(window.contentItem()) if item.objectName() == name)
        if name == "historySwitch" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            # The separate switch interaction test covers pointer input; this
            # case verifies the confirmation flow across offscreen backends.
            assert QMetaObject.invokeMethod(item, "clicked")
            return
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        if not (0 <= point.x() < window.width() and 0 <= point.y() < window.height()):
            # Offscreen windows can expose controls in a taller virtual viewport.
            assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"
            assert QMetaObject.invokeMethod(item, "clicked")
            return
        QTest.mouseClick(
            window,
            Qt.MouseButton.LeftButton,
            pos=point,
        )

    click("settingsButton")
    QTest.qWait(150)
    section = window.findChild(QObject, "privacySettingsSection")
    assert section is not None
    section.setProperty("expanded", True)
    scroll = window.findChild(QObject, "settingsScrollView")
    assert scroll is not None
    viewport = scroll.property("contentItem")
    QTest.qWait(100)
    viewport.setProperty("contentY", viewport.property("contentHeight") - viewport.property("height"))
    QTest.qWait(200)
    click("historySwitch")
    dialog = window.findChild(QObject, "disableHistoryDialog")
    assert dialog is not None and dialog.property("visible")
    click("disableHistoryCancel")
    QTest.qWait(150)
    assert controller.historyEnabled and path.exists()
    viewport.setProperty("contentY", viewport.property("contentHeight") - viewport.property("height"))
    QTest.qWait(200)
    click("historySwitch")
    click("disableHistoryConfirm")
    assert not controller.historyEnabled
    assert not path.exists()
    window.close()
    controller.close()
