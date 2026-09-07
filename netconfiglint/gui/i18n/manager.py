from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QLocale, QObject, QSettings, Signal, Slot


class TranslationController(QObject):
    languageChanged = Signal()
    catalogChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        system_locale: str | None = None,
        persist_settings: bool = True,
    ) -> None:
        super().__init__(parent)
        self._persist_settings = persist_settings
        self._catalogs = self._load_catalogs()
        saved = str(QSettings().value("ui/language", "")) if persist_settings else ""
        locale = system_locale or QLocale.system().name()
        default = "zh_CN" if locale.lower().startswith("zh") else "en"
        self._language = saved if saved in self._catalogs else default

    @staticmethod
    def _load_catalogs() -> dict[str, dict[str, str]]:
        root = Path(__file__).parent
        catalogs = {}
        for code in ("en", "zh_CN"):
            value: dict[str, Any] = json.loads((root / f"{code}.json").read_text(encoding="utf-8"))
            catalogs[code] = {str(key): str(text) for key, text in value.items()}
        if set(catalogs["en"]) != set(catalogs["zh_CN"]):
            raise ValueError("Translation catalogs must contain identical keys")
        return catalogs

    def _get_language(self) -> str:
        return self._language

    def _set_language(self, value: str) -> None:
        if value not in self._catalogs or value == self._language:
            return
        self._language = value
        if self._persist_settings:
            QSettings().setValue("ui/language", value)
        self.languageChanged.emit()
        self.catalogChanged.emit()

    language = Property(str, _get_language, _set_language, notify=languageChanged)

    def _get_catalog(self) -> dict[str, str]:
        return self._catalogs[self._language]

    catalog = Property("QVariantMap", _get_catalog, notify=catalogChanged)  # type: ignore[arg-type]

    def _get_available_languages(self) -> list[dict[str, str]]:
        return [
            {"code": "en", "label": "English"},
            {"code": "zh_CN", "label": "简体中文"},
        ]

    availableLanguages = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_available_languages,
        constant=True,
    )

    @Slot(str, result=str)
    def text(self, key: str) -> str:
        return self._catalogs[self._language].get(key, self._catalogs["en"].get(key, key))

    @Slot(str, result=str)
    def diagnostic(self, value: str) -> str:
        from netconfiglint.gui.i18n.diagnostics import translate_diagnostic

        return translate_diagnostic(value) if self._language == "zh_CN" else value
