"""Real QFont fallback stacks shared by QML and every native control."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, Slot
from PySide6.QtGui import QFont, QFontDatabase


@lru_cache(maxsize=1)
def load_fonts() -> None:
    for path in (Path(__file__).parents[1] / "resources" / "fonts").glob("*.ttf"):
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            raise RuntimeError(f"Could not load bundled font: {path.name}")


def make_font(size: int, weight: int = 400, *, mono: bool = False) -> QFont:
    font = QFont()
    candidates = (
        ["Cascadia Mono", "SFMono-Regular", "Consolas", "Noto Sans Mono", "DejaVu Sans Mono"]
        if mono
        else ["Roboto", "Noto Sans SC", "Segoe UI", "sans-serif"]
    )
    available = set(QFontDatabase.families())
    families = [name for name in candidates if name in available]
    if not families and mono:
        families = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).families()
    font.setFamilies(families)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight(weight))
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


class FontPalette(QObject):
    def _get_fonts(self) -> dict[str, Any]:
        fonts = {
            "display": make_font(34, 650),
            "title": make_font(22, 650),
            "subtitle": make_font(17, 650),
            "body": make_font(14),
            "label": make_font(13, 650),
            "caption": make_font(12),
            "monospace": make_font(14, mono=True),
        }
        fonts["display"].setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -1)
        fonts["subtitle"].setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.2)
        return fonts

    fonts = Property("QVariantMap", _get_fonts, constant=True)  # type: ignore[arg-type]

    @Slot(int, result=QFont)
    def editorFont(self, size: int) -> QFont:
        return make_font(size, mono=True)
