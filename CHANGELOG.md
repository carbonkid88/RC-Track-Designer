# Changelog

## [0.1.1] - 2026-11-07

### Behoben

- Laufzeitfehler durch das in PySide6 nicht vorhandene `Qt.KeyboardModifier.SpaceModifier`
- Zuverlässiges Verschieben der Zeichenfläche mit Leertaste und linker Maustaste
- Rücksetzen des Tastatur-, Pan- und Drag-Zustands bei Fokusverlust
- Sichtbare Plus-/Minus-Schaltflächen an numerischen Eingabefeldern
- Direkt zugängliche Hallenmaße in der Werkzeugleiste
- Tooltip zur Funktion „Halle einpassen“ und Regressionstest der Maßstabstreue
- Hallenmaße kompakt neben „Halle einpassen“ und passendes Einpassen-Symbol

## [0.1.0] - 2026-11-07

### Hinzugefügt

- Maßstabsgetreue Hallenansicht mit Meterraster, Zoom und Pan
- Geraden sowie Links- und Rechtskurven von 5° bis 90°
- Auswahl, Verschieben, Drehen und Löschen von Streckenelementen
- Einstellbare Fahrbahnbreite, Geradenlänge und Mittellinienradius
- Geometriemodell mit Anschlussposen und Tangentenrichtungen
- Versioniertes JSON-Projektformat und automatisierte Tests
- Umschaltbares helles und dunkles Theme im anthrazit-blauen Bedienkonzept
- Erweiterbare Deutsch-/Englisch-Lokalisierung über JSON-Sprachdateien
- Automatische Zentrierung der eingepassten Hallenansicht
- Zweizeilige Kurvenpalette für kleinere Laptop-Fenster
