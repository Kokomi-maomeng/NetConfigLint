from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from PySide6.QtGui import QGuiApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")


@pytest.fixture(scope="session")
def qapp() -> Iterator[QGuiApplication]:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert isinstance(app, QGuiApplication)
    yield app
