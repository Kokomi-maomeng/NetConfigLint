from __future__ import annotations

from pathlib import Path

from netconfiglint.gui.app.main import create_engine, qml_root
from netconfiglint.gui.controllers import AnalysisController


def test_main_qml_loads_offscreen(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    assert engine.rootObjects(), "Main.qml failed to create an ApplicationWindow"
    controller.close()


def test_theme_defines_required_design_tokens() -> None:
    colors = (qml_root() / "theme" / "Colors.qml").read_text(encoding="utf-8")
    spacing = (qml_root() / "theme" / "Spacing.qml").read_text(encoding="utf-8")
    typography = (qml_root() / "theme" / "Typography.qml").read_text(encoding="utf-8")

    for token in ("primary", "surfaceContainer", "error", "warning", "success", "info"):
        assert f"property color {token}" in colors
    for token in ("xxs", "xs", "sm", "md", "lg", "xl", "radiusCard"):
        assert f"property int {token}" in spacing
    assert "monoFamilies" in typography
    assert "sansFamilies" in typography


def test_qml_resources_are_package_relative() -> None:
    main = (qml_root() / "Main.qml").read_text(encoding="utf-8")
    assert "C:\\Users" not in main
    assert Path(qml_root() / "Main.qml").is_file()
