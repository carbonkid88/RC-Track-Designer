# RC Track Designer

RC Track Designer v0.1.1 ist ein maßstabsgetreuer 2D-Layouteditor für RC-Car-Rennstrecken. Die Anwendung verwendet intern Meter; Kurvenradien beziehen sich auf die Fahrbahnmittellinie.

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

## Bekannte Einschränkungen in v0.1.1

- Noch kein magnetisches Einrasten oder automatisches Verbinden.
- Keine Kollisions-, Hallengrenzen- oder Geschlossenheitsprüfung.
- Kein Undo/Redo und keine numerische Positionseingabe.
- Kurven werden nur zur Anzeige fein polygonal angenähert; Anschlussgeometrie und Speicherung bleiben exakt.
