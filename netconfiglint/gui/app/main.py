from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from netconfiglint import __version__
from netconfiglint.gui.bridge import SyntaxHighlighterBridge
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.i18n import TranslationController


def qml_root() -> Path:
    return Path(__file__).resolve().parents[1] / "qml"


def create_engine(controller: AnalysisController) -> QQmlApplicationEngine:
    QQuickStyle.setStyle("Material")
    engine = QQmlApplicationEngine()
    i18n = TranslationController(engine)
    highlighter = SyntaxHighlighterBridge(engine)
    engine.addImportPath(str(qml_root()))
    engine.rootContext().setContextProperty("analysisController", controller)
    engine.rootContext().setContextProperty("i18n", i18n)
    engine.rootContext().setContextProperty("syntaxHighlighter", highlighter)
    engine.load(QUrl.fromLocalFile(str(qml_root() / "Main.qml")))
    return engine


def main(argv: Sequence[str] | None = None) -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
    QQuickStyle.setStyle("Material")
    QCoreApplication.setOrganizationName("NetConfigLint")
    QCoreApplication.setApplicationName("NetConfigLint")
    QCoreApplication.setApplicationVersion(__version__)
    app = QGuiApplication(list(argv) if argv is not None else sys.argv)
    controller = AnalysisController()
    engine = create_engine(controller)
    if not engine.rootObjects():
        controller.close()
        return 1
    app.aboutToQuit.connect(controller.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
