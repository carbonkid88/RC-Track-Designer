# Changelog

## [0.2.0] - 2026-11-07

### Hinzugefügt

- Magnetisches Andocken über freie Anfangs- und Endanschlüsse mit zoomunabhängiger Fangdistanz
- Smart Track Building vorwärts und rückwärts ab jedem ausgewählten freien Anschluss
- Unterschiedliche Markierungen für freie, aktive und verbundene Anschlüsse
- Undo/Redo für Platzieren, Verschieben, Drehen, Löschen, Eigenschaften und Verbindungen
- Numerisches Eigenschaftenfenster für Position, Drehung und Elementgeometrie
- Persistente Verbindungen im abwärtskompatiblen JSON-Format Version 2
- Hallengrenzenprüfung für die vollständige Fahrbahnfläche
- Deutlichere magnetische Fangvorschau und größerer Fangbereich

### Geändert

- Beim manuellen Verschieben werden bestehende Verbindungen des Elements gelöst; Nachbarelemente bleiben stehen
- Beim Löschen werden angeschlossene Nachbaranschlüsse automatisch wieder freigegeben
- Verbundene Fahrbahnflächen werden ohne sichtbaren Antialiasing-Spalt gezeichnet
- Verschieben wird bereits während des Ziehens an der Hallengrenze begrenzt, ohne Zurückspringen
- Kompaktere Anschlussmarker verdecken auch sehr kurze 5°-Kurven nicht mehr
- Kollisionsschutz verhindert überlappende Geraden und Kurven bereits während Platzieren und Ziehen
- Mehrfachauswahl mit Umschalt-Klick und gemeinsames Verschieben verbundener Elementgruppen
- Gezieltes Lösen einer Verbindung per Doppelklick oder Kontextmenü am verbundenen Anschluss
- Kollisionsgeprüfte Drehung mit verständlicher Rückmeldung statt überlappender Elemente
- Flüssigeres Ziehen durch Wiederverwendung der Kollisionskonturen unbewegter Elemente
- Zuverlässigere Auswahl kleiner Kurven durch getrennte Toleranzen für Anschlussklicks und magnetisches Fangen
- Glatte Kurvendarstellung und präzisere Treffer-/Kollisionskonturen durch echte Kreisbögen
- Bereits geometrisch überlappende Elemente können wieder aus der Kollision herausgezogen werden
- Weniger aggressives magnetisches Andocken mit ausgewogener Fangdistanz und begrenzter Tangentenkorrektur
- Sichtbarer Elementtyp (Gerade, Links- oder Rechtskurve) im Eigenschaftenfenster
- Auswahlrahmen für die gemeinsame Auswahl und Bewegung mehrerer Streckenelemente
- Manuelle Kurvendrehung dynamisch und symmetrisch begrenzt: je Richtung höchstens `90° − Kurvenwinkel`
- Saubere Auswahlkontur ohne breite Zeichenstift-Artefakte an 75°–90°-Kurven; Darstellung und Kollisionskontur verwenden dieselbe Fahrbahnfläche
- Proportional skalierter carbonKID-Markenbereich am rechten Fensterrand über Hauptwerkzeugleiste und Kurvenpalette
- Schaltflächen des Ungespeichert-Dialogs folgen der gewählten Sprache

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
