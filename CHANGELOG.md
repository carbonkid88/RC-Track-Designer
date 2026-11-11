# Changelog

## [0.4.0-beta.2] - 2026-11-10

### Geändert

- Fenstertitel „RC Track Designer 0.4.0 Beta 2“ mit eigenem RC-Track-Designer-Logo im Fenstersymbol
- Der Name eines geladenen oder gespeicherten Projekts steht nun direkt neben Streckenbereich und Rasterangabe auf der Zeichenfläche
- Das bisherige Menü „Ansicht“ heißt jetzt treffender „Einstellungen“
- Im Hallenmodus bleiben Verbindungen an zusätzlichen Magnetpunkten beim Verschieben ihrer Trägergeraden als Gelenkkette erhalten; eine verbindende Gerade richtet sich zwischen den Gelenken neu aus, ohne den übrigen Verlauf mitzubewegen
- Sämtliche Anschlüsse im Hallenmodus unterstützen mehrere gleichzeitig verbundene Geraden und Kurven als frei kombinierbare Abzweige
- Verbundene Begrenzungsendpunkte lassen sich als Gelenke direkt ziehen; angrenzende Geraden und Kurven passen ihre Geometrie zwischen den feststehenden Gegenpunkten an
- Projektformat Version 5 speichert Mehrfachverbindungen; ältere Formate 1 bis 4 bleiben ladbar

## [0.4.0] - 2026-11-09

### Hinzugefügt

- Zusätzlicher Hallenmodus innerhalb derselben Anwendung mit umschaltbarer Begrenzungspalette
- Anthrazitfarbener Hallenteppich, dezentes weißes Raster und durchgehend gelbe Begrenzungsgeometrie unabhängig vom Anwendungstheme
- Gerade und neutrale Kurvenbegrenzungen von 5° bis 90° mit frei wählbarer Bogenlage
- Begrenzungsbreiten 5, 10, 15, 20 und 25 cm; intern werden alle Abmessungen weiterhin in Metern gespeichert
- Freistehende Begrenzungen, mehrere unabhängige Ketten, magnetisches Andocken und Smart Building an freien Anschlüssen
- Projektformat Version 4 mit Bearbeitungsmodus und expliziter Elementkategorie
- Zusätzliche, entlang gerader Begrenzungen verschiebbare Magnetpunkte mit Kontextmenü, gezielter Mitführung nur des direkt angedockten Elements, Undo/Redo und Projektspeicherung
- Reproduzierbare portable Windows-64-Bit-Beta-1-Konfiguration mit zweisprachigen Release Notes und vollständiger Ressourcenprüfung

### Geändert

- Projektdateien mit veralteten, geometrisch widersprüchlichen Verbindungsreferenzen werden wieder geöffnet; nur die ungültige Verbindung wird gelöst, sämtliche Elemente bleiben erhalten
- Ein Moduswechsel verlangt bei ungespeicherten Änderungen zuerst das Speichern und öffnet den Zielmodus anschließend mit einem leeren Streckenbereich gleicher Abmessungen
- Fahrbahn- und Begrenzungselemente verwenden gemeinsame Geometrie-, Auswahl-, Verbindungs- und Undo/Redo-Mechanismen, können aber nicht versehentlich miteinander verbunden werden
- Projekte der Formatversionen 1 bis 3 werden weiterhin als normale Fahrbahnprojekte geladen, ohne Elemente umzuwandeln
- Anwendungsversion zur Vorbereitung der getrennten v0.4.0-Entwicklung angehoben

## [0.3.0] - 2026-11-08

### Hinzugefügt

- Neutrale Kurvenpalette mit einem Winkel pro Schaltfläche statt getrennter Links-/Rechtskurven
- Richtungsunabhängige Anschlüsse: Anfang kann mit Anfang und Ende mit Ende verbunden werden, wenn die gerichteten Tangenten entgegengesetzt liegen
- JSON-Projektformat Version 3 für die neuen Anschlusskombinationen; Projekte der Versionen 1 und 2 bleiben ladbar
- Regressionstests für beidseitiges Kurven-Andocken, neutrale Palette, 360°-Drehung und JSON-Roundtrips
- Direkte Segmentdrehung in 5°-Schritten mit den Pfeiltasten einschließlich kontinuierlicher Tastaturwiederholung
- Undo/Redo-fähiges Löschen der aktuellen Elementauswahl über das Rechtsklick-Menü

### Geändert

- Kurven lassen sich frei um 360° um ihre Fahrbahnmitte drehen und über beide Anschlüsse magnetisch anfügen
- Beim automatischen Weiterbauen prüft der Editor beide Bogenlagen und Anschlussseiten und bevorzugt eine passende, möglichst konfliktarme Variante
- Der Eigenschaftenbereich bezeichnet Kurven unabhängig von ihrer internen Geometrievariante einheitlich als „Kurve“
- Anwendungsversion und gespeicherte Projektmetadaten auf 0.3.0 angehoben

### Lizenz

- Die zweisprachige nicht-kommerzielle Lizenz bleibt als `LICENSE.txt` Bestandteil des Projekts und ist weiterhin unter `Hilfe > Lizenz` vollständig einsehbar

### Build

- Reproduzierbarer portabler Windows-64-Bit-One-Folder-Build mit PyInstaller-Spec und PowerShell-Buildskript
- Automatische Beta-ZIP-Erzeugung einschließlich Startanleitung, Lizenz, Sprachdateien, Icons und SHA256-Prüfsumme
- Build-Ausgaben werden aus der Versionsverwaltung ausgeschlossen; Laufzeiteinstellungen bleiben im Windows-Benutzerprofil

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
- Zoomabhängige Meterlineale an X- und Y-Achse des Streckenbereichs
- Persistente magentafarbene Hilfslinien, in 0,5-m-Schritten aus den Linealen ziehbar und per Undo/Redo bearbeitbar
- Kopieren und Einfügen von Einzel- und Mehrfachauswahlen mit neuen IDs, internen Verbindungen und Undo/Redo
- Integrierte deutsch-/englischsprachige Bedienungsanleitung unter Hilfe beziehungsweise F1
- Allgemeiner Assistent zum exakten Schließen offener Strecken mit Auswahl zweier freier Anschlüsse, lokaler Geometrieoptimierung und Änderungsvorschau
- Zweisprachige Lizenz für private und nicht-kommerzielle Vereinsnutzung einschließlich integriertem Lizenzdialog unter Hilfe

### Geändert

- Kurvenradien werden abhängig von der Fahrbahnbreite begrenzt, sodass keine keilförmigen oder selbstüberschneidenden Fahrbahnflächen entstehen können
- Präzisere Elementauswahl in engen und überlappenden Bereichen anhand des Abstands zur jeweiligen Mittellinie
- Der größere magnetische Fangbereich gilt nun auch beim Loslassen eines gezogenen freien Anschlusses und erleichtert das Schließen kleiner Lücken
- Gemeinsam verschobene, intern verbundene Elementgruppen können als starre Einheit an einen äußeren freien Anschluss andocken
- Escape beendet Platzierung oder Auswahl nun zuverlässig, auch wenn ein Werkzeugleisten-Eingabefeld den Tastaturfokus besitzt
- Der Schließassistent verändert erst nach Bestätigung und fasst sämtliche lokalen Anpassungen einschließlich der neuen Verbindung in einem Undo/Redo-Schritt zusammen
- Bei zwei markierten freien Anschlüssen ist „Strecke schließen…“ zusätzlich direkt über das Rechtsklick-Menü erreichbar
- Exaktes Andocken an der Streckenbereichsgrenze scheitert nicht mehr an Gleitkomma-Rundungsfehlern; der zulässige Mindestradius entspricht nun ohne zusätzlichen 0,10-m-Aufschlag der halben Fahrbahnbreite
- Beim manuellen Verschieben werden bestehende Verbindungen des Elements gelöst; Nachbarelemente bleiben stehen
- Beim Löschen werden angeschlossene Nachbaranschlüsse automatisch wieder freigegeben
- Verbundene Fahrbahnflächen werden ohne sichtbaren Antialiasing-Spalt gezeichnet
- Verschieben wird bereits während des Ziehens an der Hallengrenze begrenzt, ohne Zurückspringen
- Kompaktere Anschlussmarker verdecken auch sehr kurze 5°-Kurven nicht mehr
- Überlappungen bleiben beim Platzieren, Ziehen, Drehen und Andocken erlaubt und werden durch rot-weiße Warnkonturen hervorgehoben
- Mehrfachauswahl mit Umschalt-Klick und gemeinsames Verschieben verbundener Elementgruppen
- Gezieltes Lösen einer Verbindung per Doppelklick oder Kontextmenü am verbundenen Anschluss
- Drehungen bleiben auch bei entstehenden Überschneidungen möglich
- Flüssigeres Ziehen durch Wiederverwendung der Kollisionskonturen unbewegter Elemente
- Zuverlässigere Auswahl kleiner Kurven durch getrennte Toleranzen für Anschlussklicks und magnetisches Fangen
- Glatte Kurvendarstellung und präzisere Treffer-/Kollisionskonturen durch echte Kreisbögen
- Magnetisches Andocken richtet nahe kompatible Anschlüsse unabhängig von ihrer vorherigen Tangentenabweichung exakt aus
- Geradenlänge und Kurvenradius in 0,5-m-Schritten einstellbar
- Einseitig verbundene Elemente behalten bei Geometrieänderungen ihren verbundenen Anschluss; nur die freie Seite bewegt sich
- Freie Anschlüsse dienen als Ziehgriffe für Länge beziehungsweise Radius und Winkel und können eine geometrisch passende Lücke direkt schließen
- Sichtbarer Elementtyp (Gerade, Links- oder Rechtskurve) im Eigenschaftenfenster
- Auswahlrahmen für die gemeinsame Auswahl und Bewegung mehrerer Streckenelemente
- Starrkörperdrehung um die Mitte der Fahrbahnmittellinie mit sichtbarer Drehpunktmarkierung; Kurven bleiben innerhalb ±90° ihrer Einbaurichtung
- Saubere Auswahlkontur ohne breite Zeichenstift-Artefakte an 75°–90°-Kurven; Darstellung und Kollisionskontur verwenden dieselbe Fahrbahnfläche
- Proportional skalierter carbonKID-Markenbereich am rechten Fensterrand über Hauptwerkzeugleiste und Kurvenpalette
- Schaltflächen des Ungespeichert-Dialogs folgen der gewählten Sprache
- Neutrale Bezeichnung „Streckenbereich“ statt „Halle“ für Innen- und Außenstrecken
- Kollisionsfreie Randbeschriftungen der Meterlineale und dezentere, durchgehende Hilfslinien
- Kompaktere Streckenbereichsmaße in der Werkzeugleiste; der Kurvenwinkel steht direkt unter dem Elementtyp
- Zweizeiliger Streckenbereichsblock schafft Platz für wieder gut lesbare Drehtasten
- Stabile Beschriftung der Drehtasten bei Auswahländerungen; der Kurvenwinkel erscheint nur für ausgewählte Kurven
- Ruhiges Eigenschaftenlayout mit dauerhaft sichtbarem Kurvenwinkel (`0°` ohne Kurve) und Abwahl per `Esc`
- Hilfslinien lassen sich per Rechtsklick löschen und über Undo/Redo wiederherstellen
- Streckenbereichs- und Rasterangabe bleibt beim Zoomen und Verschieben links oben im Zeichenbereich verankert
- Der Eigenschaftenbereich lässt sich über `Ansicht > Eigenschaften` wieder einblenden

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
