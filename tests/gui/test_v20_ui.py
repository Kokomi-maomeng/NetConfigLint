from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImageReader
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.controllers import AnalysisController


def descendants(item: QQuickItem) -> list[QQuickItem]:
    return item.childItems() + [child for parent in item.childItems() for child in descendants(parent)]


def find(window: QQuickWindow, name: str) -> QQuickItem:
    return next(item for item in descendants(window.contentItem()) if item.objectName() == name)


def center(item: QQuickItem) -> object:
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


@pytest.fixture
def gui(qapp: object) -> Iterator[tuple[QQuickWindow, AnalysisController, object]]:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    window.setWidth(1440)
    window.setHeight(900)
    QTest.qWait(350)
    yield window, controller, engine
    window.close()
    controller.close()


def test_integrated_title_bar_and_about_horizontal_scrollbar(gui: tuple) -> None:
    window, _controller, _engine = gui
    title_bar = find(window, "appTitleBar")
    assert title_bar.isVisible() and title_bar.width() == window.width()
    flags = window.flags()
    assert flags & Qt.WindowType.ExpandedClientAreaHint
    assert flags & Qt.WindowType.NoTitleBarBackgroundHint
    if sys.platform == "win32":
        assert title_bar.property("titleInset") >= 32
    window.setProperty("currentPage", 2)
    QTest.qWait(300)
    horizontal = find(window, "aboutHorizontalScrollBar")
    assert not horizontal.isVisible()
    vertical = find(window, "aboutVerticalScrollBar")
    assert vertical.isVisible()
    assert vertical.height() > 700
    assert vertical.mapToScene(QPointF()).x() > window.width() - 50


def test_drag_uses_a_full_card_proxy_then_settles(gui: tuple) -> None:
    window, _controller, _engine = gui
    source = find(window, "configurationEditor")
    start = center(find(window, "configurationTextAreaHeaderGrip"))
    end = center(find(window, "temporaryTextAreaHeaderGrip"))
    proxy = find(window, "panelDragProxy")
    QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=start)
    for part in range(1, 7):
        QTest.mouseMove(window, start + (end - start) * (part / 7), delay=30)
    assert proxy.isVisible()
    assert proxy.width() == pytest.approx(source.width(), abs=2)
    assert proxy.height() == pytest.approx(source.height(), abs=2)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=end)
    QTest.qWait(400)
    assert not proxy.isVisible()
    assert source.isVisible()


def test_generated_icons_cover_ui_and_native_sizes() -> None:
    root = Path(__file__).resolve().parents[2]
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024)
    for size in sizes:
        path = root / f"netconfiglint/resources/icons/generated/app-{size}.png"
        reader = QImageReader(str(path))
        assert reader.canRead()
        assert reader.size().width() == size and reader.size().height() == size
    ico = QImageReader(str(root / "netconfiglint/resources/icons/app.ico"))
    assert ico.canRead()
    assert ico.imageCount() >= 7


def test_meaningless_text_glyphs_and_old_outline_drag_are_absent() -> None:
    root = Path(__file__).resolve().parents[2] / "netconfiglint/gui/qml"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.qml"))
    assert "⠿" not in source
    assert "⌄" not in source
    assert "panelDragIndicator" not in source
