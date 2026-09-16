from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from netconfiglint import __version__
from netconfiglint.gui.bridge import SyntaxHighlighterBridge
from netconfiglint.gui.controllers import AnalysisController
from netconfiglint.gui.fonts import FontPalette, load_fonts, make_font
from netconfiglint.gui.i18n import TranslationController
from netconfiglint.gui.models import HistoryStore
from netconfiglint.gui.preferences import Preferences


def qml_root() -> Path:
    return Path(__file__).resolve().parents[1] / "qml"


def create_engine(controller: AnalysisController) -> QQmlApplicationEngine:
    if QQuickStyle.name() != "Material":
        QQuickStyle.setStyle("Material")
    engine = QQmlApplicationEngine()
    i18n = TranslationController(engine)
    controller.translator = i18n
    preferences = Preferences(engine)
    load_fonts()
    QGuiApplication.setFont(make_font(14))
    font_palette = FontPalette(engine)
    highlighter = SyntaxHighlighterBridge(engine)
    engine.addImportPath(str(qml_root()))
    engine.rootContext().setContextProperty("analysisController", controller)
    engine.rootContext().setContextProperty("i18n", i18n)
    engine.rootContext().setContextProperty("preferences", preferences)
    engine.rootContext().setContextProperty("fontPalette", font_palette)
    engine.rootContext().setContextProperty("syntaxHighlighter", highlighter)
    engine.load(QUrl.fromLocalFile(str(qml_root() / "Main.qml")))
    return engine


def dispose_engine(
    app: QGuiApplication, engine: QQmlApplicationEngine, controller: AnalysisController
) -> None:
    """Destroy QML roots while their context objects are still alive."""
    for root in engine.rootObjects():
        root.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    engine.clearComponentCache()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    controller.close()
    app.processEvents()


def main(argv: Sequence[str] | None = None) -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
    QQuickStyle.setStyle("Material")
    QCoreApplication.setOrganizationName("NetConfigLint")
    QCoreApplication.setApplicationName("NetConfigLint")
    QCoreApplication.setApplicationVersion(__version__)
    arguments = list(argv) if argv is not None else list(sys.argv)
    if "--remove-all-data" in arguments:
        from netconfiglint.gui.app.cleanup import remove_all_user_data

        app = QCoreApplication(arguments)
        remove_all_user_data(Path(QCoreApplication.applicationDirPath()))
        app.quit()
        return 0
    smoke_output: Path | None = None
    if "--smoke-test" in arguments:
        index = arguments.index("--smoke-test")
        if index + 1 >= len(arguments):
            return 2
        smoke_output = Path(arguments[index + 1]).resolve()
        smoke_output.mkdir(parents=True, exist_ok=True)
        del arguments[index : index + 2]
        QCoreApplication.setOrganizationName("NetConfigLintSmoke")
        QCoreApplication.setApplicationName("SyntheticAcceptance")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(smoke_output / "settings")
        )
    app = QGuiApplication(arguments)
    app.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parents[2] / "resources" / "icons" / "app-master.png"))
    )
    controller = AnalysisController(
        async_enabled=smoke_output is None,
        history_store=HistoryStore(enabled=False, persist_settings=False) if smoke_output else None,
    )
    engine = create_engine(controller)
    if not engine.rootObjects():
        controller.close()
        return 1
    if smoke_output is not None:
        from netconfiglint.gui.app.smoke import run_smoke

        exit_code = run_smoke(app, engine, controller, smoke_output)
        dispose_engine(app, engine, controller)
        return exit_code
    exit_code = app.exec()
    dispose_engine(app, engine, controller)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
