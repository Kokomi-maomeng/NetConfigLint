from netconfiglint.gui.i18n import TranslationController


def test_chinese_system_locale_is_selected(qapp: object) -> None:
    controller = TranslationController(system_locale="zh_CN", persist_settings=False)
    assert controller.language == "zh_CN"
    assert controller.catalog["nav.check"] == "配置检查"


def test_unsupported_system_locale_falls_back_to_english(qapp: object) -> None:
    controller = TranslationController(system_locale="fr_FR", persist_settings=False)
    assert controller.language == "en"
    assert controller.catalog["nav.check"] == "Configuration Check"


def test_language_change_is_immediate_and_catalogs_are_complete(qapp: object) -> None:
    controller = TranslationController(system_locale="en_US", persist_settings=False)
    english_keys = set(controller.catalog)
    controller.language = "zh_CN"
    assert set(controller.catalog) == english_keys
    assert controller.text("settings.language") == "语言"
