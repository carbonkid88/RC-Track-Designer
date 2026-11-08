# RC Track Designer

RC Track Designer v0.2.0 ist ein maßstabsgetreuer 2D-Layouteditor für RC-Car-Rennstrecken. Die Anwendung verwendet intern Meter; Kurvenradien beziehen sich auf die Fahrbahnmittellinie.

## Installation und Start

Vorausgesetzt wird Python 3.11 oder neuer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m rc_track_designer
```

Im Entwicklungs-Checkout geht es auch ohne Installation:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python -m rc_track_designer
```

## Bedienung

- `Datei > Neu` legt eine Halle mit Länge und Breite an.
- Oben Gerade oder Links-/Rechtskurve wählen und zum Platzieren in die Halle klicken. `Esc` beendet den Platziermodus.
- Klicken wählt ein Element; Ziehen verschiebt es. Werkzeugleiste oder `Strg+Links`/`Strg+Rechts` dreht um 5°. `Entf` löscht.
- Fahrbahnbreite, Geradenlänge und Mittellinienradius gelten für neue Elemente und ändern zugleich das ausgewählte Element.
- Hallenlänge und Hallenbreite sind jederzeit in der Werkzeugleiste änderbar; die Ansicht wird anschließend neu eingepasst.
- Mausrad zoomt. Mittlere Maustaste oder `Leertaste` + linke Maustaste verschiebt die Ansicht. `F` passt die Halle ein.
- Projekte werden als versioniertes `*.rct.json` gespeichert und geladen.
- Unter `Ansicht > Einstellungen` kann zwischen hellem und dunklem Theme sowie Deutsch und Englisch gewechselt werden. Die Auswahl wird gespeichert.

## Smart Track Building

- Freie Anschlüsse sind blau, der aktive freie Anschluss orange und verbundene Anschlüsse grün markiert.
- Einen freien Anfangs- oder Endanschluss anklicken und danach ein Element aus der Palette wählen. Das neue Element wird tangential korrekt angefügt; sein gegenüberliegender freier Anschluss wird automatisch aktiv.
- Manuell verschobene Elemente docken innerhalb einer festen Bildschirmdistanz an passende freie Gegenanschlüsse an. Die Fangdistanz bleibt beim Zoomen gleich; orange Ringe zeigen ein bevorstehendes Einrasten an.
- Beim Einrasten wird eine bereits ungefähr passende Tangente exakt ausgerichtet. Absichtlich deutlich anders gedrehte Elemente werden nicht zurückgedreht. Die Eigenschaften zeigen den unveränderlichen Elementtyp als Gerade, Links- oder Rechtskurve an.
- Nur geometrisch und in Fahrtrichtung passende Anfang-Ende-Paare können verbunden werden.
- Neue oder bearbeitete Elemente müssen einschließlich ihrer vollständigen Fahrbahnbreite innerhalb der Halle liegen.
- Nicht miteinander verbundene Fahrbahnflächen dürfen sich nicht überlappen; Ziehbewegungen stoppen unmittelbar vor einer Kollision.
- Beim Verschieben eines verbundenen Elements werden dessen Verbindungen gelöst, ohne Nachbarelemente mitzubewegen. Beim Löschen werden Nachbaranschlüsse wieder frei.
- Eine bestehende Verbindung lässt sich gezielt durch Doppelklick oder Rechtsklick auf ihren grünen Anschluss lösen. Das Lösen kann mit Undo/Redo rückgängig gemacht werden.
- Mit `Umschalt + Klick` lassen sich mehrere Elemente auswählen. Ziehen verschiebt die gesamte Auswahl; interne Verbindungen bleiben erhalten.
- Auf freier Hallenfläche kann mit gedrückter linker Maustaste ein Auswahlrahmen aufgezogen werden. `Umschalt` ergänzt die eingerahmten Elemente zur bestehenden Auswahl.
- Kurvenwinkel und manuelle Drehung folgen einer symmetrischen 90°-Regel: Eine 40°-Kurve kann aus ihrer Ausgangslage zwischen −50° und +50°, eine 30°-Kurve zwischen −60° und +60° gedreht werden. Automatisches tangentiales Ausrichten beim Andocken bleibt davon unberührt.
- Das Eigenschaftenfenster erlaubt numerische Position, Drehung, Breite, Länge, Radius und Kurvenwinkel.
- `Strg+Z` macht Bearbeitungen rückgängig, `Strg+Y` stellt sie wieder her.

Anfangs- und Endpunkte sind blau markiert. Jedes Element speichert Anfangsposition und Anfangstangente; Endposition und Endtangente werden exakt berechnet. Das Modell ist damit auf späteres magnetisches Verbinden vorbereitet.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

## Weitere Sprachen beitragen

Die englischen Texte sind die stabilen Schlüssel. Übersetzungen liegen als UTF-8-JSON-Dateien in `src/rc_track_designer/locales`. Eigene Sprachdateien können zusätzlich im vom Einstellungsdialog angezeigten Benutzerordner abgelegt werden und erscheinen danach in der Sprachauswahl.

Eine Sprachdatei hat dieses Format:

```json
{
  "code": "fr",
  "name": "Français",
  "translations": {
    "Save": "Enregistrer",
    "Open…": "Ouvrir…"
  }
}
```

Fehlende Einträge fallen automatisch auf Englisch zurück. Dadurch können Übersetzungen schrittweise ergänzt werden, ohne den Programmstart zu verhindern.

## Bekannte Einschränkungen in v0.2.0

- Keine Kollisions-, Hallengrenzen- oder Geschlossenheitsprüfung.
- Kurven werden nur zur Anzeige fein polygonal angenähert; Anschlussgeometrie und Speicherung bleiben exakt.
