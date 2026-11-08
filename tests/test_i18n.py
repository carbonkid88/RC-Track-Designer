from rc_track_designer.i18n import TranslationManager


def test_builtin_languages_are_discoverable():
    manager = TranslationManager("en")
    codes = {language.code for language in manager.available_languages()}
    assert {"de", "en"} <= codes


def test_german_translation_and_formatting():
    manager = TranslationManager("de")
    assert manager.tr("Save") == "Speichern"
    assert manager.tr("Saved: {path}", path="layout.json") == "Gespeichert: layout.json"
    assert manager.tr("Discard") == "Verwerfen"
    assert manager.tr("Cancel") == "Abbrechen"
    assert manager.tr("Element snapped into place.") == "Element magnetisch eingerastet."
    assert manager.tr("Element type:") == "Elementtyp:"
    assert manager.tr("Left curve") == "Linkskurve"
    assert manager.tr("Right curve") == "Rechtskurve"
    assert manager.tr("{count} elements selected.", count=2) == "2 Elemente ausgewählt."
    assert manager.tr("Track area") == "Streckenbereich"
    assert manager.tr("Fit track area") == "Streckenbereich einpassen"
    assert manager.tr("Guide: {value} m", value="2.5") == "Hilfslinie: 2.5 m"
    assert manager.tr("Close track…") == "Strecke schließen…"
    assert manager.tr("Track closed successfully.") == "Strecke erfolgreich geschlossen."


def test_english_source_strings_are_fallback():
    manager = TranslationManager("en")
    assert manager.tr("Unknown source") == "Unknown source"
