from rc_track_designer.i18n import TranslationManager


def test_builtin_languages_are_discoverable():
    manager = TranslationManager("en")
    codes = {language.code for language in manager.available_languages()}
    assert {"de", "en"} <= codes


def test_german_translation_and_formatting():
    manager = TranslationManager("de")
    assert manager.tr("Save") == "Speichern"
    assert manager.tr("Saved: {path}", path="layout.json") == "Gespeichert: layout.json"


def test_english_source_strings_are_fallback():
    manager = TranslationManager("en")
    assert manager.tr("Unknown source") == "Unknown source"
