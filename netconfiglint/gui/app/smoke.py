"""Opt-in, synthetic-only acceptance run for a source or portable application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMetaObject, QObject, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from netconfiglint import __version__
from netconfiglint.gui.controllers import AnalysisController


def run_smoke(
    app: QGuiApplication, engine: QQmlApplicationEngine, controller: AnalysisController, output: Path
) -> int:
    window = engine.rootObjects()[0]
    if not isinstance(window, QQuickWindow):
        return 1
    window.setWidth(1440)
    window.setHeight(900)
    preferences = engine.rootContext().contextProperty("preferences")
    translator = engine.rootContext().contextProperty("i18n")
    errors: list[str] = []
    report: dict[str, Any] = {"version": __version__, "passed": False}
    engine.warnings.connect(lambda warnings: errors.extend(str(w.description()) for w in warnings))
    preferences.setValue("themeMode", 1)
    translator.language = "zh_CN"

    def finish() -> None:
        report["qml_errors"] = errors
        report["passed"] = not errors and report.get("exports") == 3
        (output / "smoke-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        window.close()
        app.exit(0 if report["passed"] else 1)

    def dark() -> None:
        if not window.grabWindow().save(str(output / "settings-dark-en.png")):
            errors.append("Could not capture settings window")
        finish()

    def settings() -> None:
        dialog = window.findChild(QObject, "exportOptionsDialog")
        if dialog is None or not dialog.property("visible"):
            errors.append("Export dialog did not open")
        else:
            window.grabWindow().save(str(output / "export-light-zh.png"))
            QMetaObject.invokeMethod(dialog, "close")
        preferences.setValue("themeMode", 2)
        translator.language = "en"
        dialog = window.findChild(QObject, "settingsDialog")
        if dialog is None or not QMetaObject.invokeMethod(dialog, "open"):
            errors.append("Settings dialog did not open")
        QTimer.singleShot(400, dark)

    def capture() -> None:
        if not window.grabWindow().save(str(output / "workspace-light-zh.png")):
            errors.append("Could not capture workspace")
        dialog = window.findChild(QObject, "exportOptionsDialog")
        if dialog is None or not QMetaObject.invokeMethod(dialog, "open"):
            errors.append("Export dialog was unavailable")
        QTimer.singleShot(400, settings)

    def analyze_sample() -> None:
        try:
            if controller.property("mode") != "snippet":
                raise RuntimeError("Default analysis mode is not snippet")
            report["default_mode"] = controller.property("mode")
            controller.analyzeConfig()
            if controller.busy or controller.statusMessage:
                raise RuntimeError("Empty configuration started analysis")
            source = (
                "sysname SYNTHETIC-LAB\ninterface GigabitEthernet1/0/1\n port trunk allow-pass vlan 100\n"
            )
            controller.setProperty("sourceText", source)
            controller.setProperty("mode", "full")
            controller.analyzeConfig()
            if not controller.property("resultCurrent") or controller.property("summary")["ERROR"] != 1:
                raise RuntimeError("Synthetic analysis did not return the expected diagnostic")
            report["exports"] = 0
            for format in ("json", "md", "txt"):
                if not controller.prepareExport("full", format, True):
                    raise RuntimeError("Could not prepare export")
                path = output / f"synthetic-report.{format}"
                controller.exportReport(str(path))
                if "HUA-VLAN-001" not in path.read_text(encoding="utf-8"):
                    raise RuntimeError("Export did not contain the expected diagnostic")
                report["exports"] += 1
            report["vendor"] = controller.property("detection")["vendor"]
            report["summary"] = controller.property("summary")
            QTimer.singleShot(400, capture)
        except Exception as exc:
            errors.append(type(exc).__name__ + ": " + str(exc))
            finish()

    QTimer.singleShot(300, analyze_sample)
    return app.exec()
