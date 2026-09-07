from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")


@pytest.fixture(scope="session")
def qapp() -> Iterator[QGuiApplication]:
    app = QGuiApplication.instance() or QGuiApplication([])
    assert isinstance(app, QGuiApplication)
    app.setOrganizationName("NetConfigLintTests")
    app.setApplicationName("NetConfigLintTests")
    yield app


@pytest.fixture(autouse=True)
def isolated_preferences(qapp: object, tmp_path: object) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
