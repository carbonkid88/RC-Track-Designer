# RC Track Designer

RC Track Designer v0.3.0 ist ein maßstabsgetreuer 2D-Layouteditor für RC-Car-Rennstrecken. Die Anwendung verwendet intern Meter; Kurvenradien beziehen sich auf die Fahrbahnmittellinie.

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

- `Datei > Neu` legt einen Streckenbereich mit Länge und Breite an.
- Oben eine Gerade oder einen neutralen Kurvenwinkel wählen und zum Platzieren in den Streckenbereich klicken. `Esc` beendet den Platziermodus.
- Klicken wählt ein Element; Ziehen verschiebt es. Werkzeugleiste oder `Strg+Links`/`Strg+Rechts` dreht um 5°. Bei einem einzeln ausgewählten Segment drehen die Pfeiltasten `Links`/`Rechts` direkt; Gedrückthalten dreht kontinuierlich weiter. `Entf` oder `Auswahl löschen` im Rechtsklick-Menü löscht die Auswahl.
- Fahrbahnbreite, Geradenlänge und Mittellinienradius gelten für neue Elemente und ändern zugleich das ausgewählte Element.
- Geradenlängen und Kurvenradien lassen sich über die Plus-/Minus-Schaltflächen in 0,5-m-Schritten ändern.
- Der kleinste zulässige Mittellinienradius entspricht der halben Fahrbahnbreite. Die innere Fahrbahnkante darf dabei in einem Punkt zusammenlaufen, aber nicht über den Kurvenmittelpunkt hinauslaufen oder sich selbst überschneiden.
- Länge und Breite des Streckenbereichs sind jederzeit in der Werkzeugleiste änderbar; die Ansicht wird anschließend neu eingepasst.
- Mausrad zoomt. Mittlere Maustaste oder `Leertaste` + linke Maustaste verschiebt die Ansicht. `F` passt den Streckenbereich ein.
- Lineale an der oberen X- und linken Y-Achse zeigen die Meterpositionen passend zum aktuellen Zoom.
- Aus den Linealen lassen sich magentafarbene Hilfslinien in 0,5-m-Schritten in den Streckenbereich ziehen. Vorhandene Hilfslinien können erneut gezogen sowie durch Herausziehen oder Rechtsklick gelöscht werden.
- Projekte werden als versioniertes `*.rct.json` gespeichert und geladen.
- Unter `Ansicht > Einstellungen` kann zwischen hellem und dunklem Theme sowie Deutsch und Englisch gewechselt werden. Die Auswahl wird gespeichert.

## Smart Track Building

- Freie Anschlüsse sind blau, der aktive freie Anschluss orange und verbundene Anschlüsse grün markiert.
- Einen freien Anfangs- oder Endanschluss anklicken und danach ein Element aus der Palette wählen. Das neue Element wird tangential korrekt angefügt; sein gegenüberliegender freier Anschluss wird automatisch aktiv.
- Manuell verschobene Elemente docken innerhalb einer festen Bildschirmdistanz an passende freie Gegenanschlüsse an. Die Fangdistanz bleibt beim Zoomen gleich; orange Ringe zeigen ein bevorstehendes Einrasten an.
- Beim Ziehen eines freien Anschlusses gilt bis zum Loslassen derselbe gut sichtbare magnetische Fangbereich. Bei dicht nebeneinanderliegenden Fahrbahnen wird das Element mit der zum Klick nächstgelegenen Mittellinie ausgewählt.
- Beim Einrasten wird ein naher kompatibler Anschluss exakt tangential ausgerichtet, auch wenn das bewegte Element vorher deutlich anders gedreht war. Kurven werden im Eigenschaftenbereich einheitlich als „Kurve“ bezeichnet.
- Anschlüsse sind richtungsneutral: Anfang–Ende, Anfang–Anfang und Ende–Ende sind möglich. Bei gleichnamigen Anschlüssen berücksichtigt der Editor die entgegengesetzte gerichtete Tangente automatisch.
- Neue oder bearbeitete Elemente müssen einschließlich ihrer vollständigen Fahrbahnbreite innerhalb des Streckenbereichs liegen.
- Überlappungen blockieren Platzieren, Ziehen, Drehen oder Andocken nicht. Alle beteiligten Elemente erhalten stattdessen eine rot-weiße Warnkontur; regulär miteinander verbundene Nachbarelemente gelten nicht als Konflikt.
- Beim Verschieben eines verbundenen Elements werden dessen Verbindungen gelöst, ohne Nachbarelemente mitzubewegen. Beim Löschen werden Nachbaranschlüsse wieder frei.
- Bei einer einseitig verbundenen Geraden verlängert oder verkürzt eine Längenänderung ausschließlich den freien Anschluss; der verbundene Anschluss bleibt fest. Radius- und Winkeländerungen einseitig verbundener Kurven folgen derselben Regel.
- Der freie Anschluss eines einseitig verbundenen Elements kann mit der Maus gezogen werden. Geraden rasten dabei in 0,5-m-Längen, Kurven in 0,5-m-Radien und 5°-Winkeln ein. Wird der Griff auf einem geometrisch passenden freien Gegenanschluss losgelassen, schließt der Editor die Verbindung.
- Zum automatischen Schließen einer offenen Strecke werden ihre beiden freien Anschlüsse mit `Strg+Klick` markiert und anschließend `Bearbeiten > Strecke schließen…` oder der gleichnamige Eintrag im Rechtsklick-Menü gewählt. Ein allgemeiner lokaler Geometriesolver passt bei Bedarf benachbarte Längen, Radien und Kurvenwinkel innerhalb ihrer gültigen Grenzen an. Eine Vorschau listet alle Änderungen; übernommen werden sie gemeinsam als ein Undo/Redo-Schritt.
- Eine bestehende Verbindung lässt sich gezielt durch Doppelklick oder Rechtsklick auf ihren grünen Anschluss lösen. Das Lösen kann mit Undo/Redo rückgängig gemacht werden.
- Mit `Umschalt + Klick` lassen sich mehrere Elemente auswählen. Ziehen verschiebt die gesamte Auswahl; interne Verbindungen bleiben erhalten.
- Eine gemeinsam verschobene Auswahl kann über einen ihrer freien äußeren Anschlüsse magnetisch an ein Element außerhalb der Auswahl andocken. Die Gruppe wird dafür als starre Einheit ausgerichtet; interne Verbindungen bleiben erhalten.
- Auf freier Fläche des Streckenbereichs kann mit gedrückter linker Maustaste ein Auswahlrahmen aufgezogen werden. `Umschalt` ergänzt die eingerahmten Elemente zur bestehenden Auswahl.
- `Strg+C` kopiert die Auswahl, `Strg+V` fügt sie um 0,5 m versetzt mit neuen IDs ein. Bei kopierten Gruppen bleiben interne Verbindungen erhalten; Verbindungen zu nicht kopierten Elementen werden nicht übernommen.
- Elemente drehen als starrer Körper um die Mitte ihrer Fahrbahnmittellinie. Beide Anschlüsse bewegen sich dabei mit; verbundene Elemente werden vor dem Drehen automatisch gelöst. Geraden und Kurven sind frei um 360° drehbar und können anschließend über jeden freien Anschluss andocken. Ein kleines orangefarbenes Kreuz markiert bei Einzelauswahl das Drehzentrum.
- Das Eigenschaftenfenster erlaubt numerische Position, Drehung, Breite, Länge, Radius und Kurvenwinkel.
- `Strg+Z` macht Bearbeitungen rückgängig, `Strg+Y` stellt sie wieder her.
- `Esc` funktioniert auch bei Fokus in einem Eingabefeld: Ein laufender Platziermodus wird beendet beziehungsweise die aktuelle Auswahl aufgehoben. Unter `Hilfe > Bedienungsanleitung` (`F1`) steht eine integrierte Kurzanleitung bereit.

Anfangs- und Endpunkte sind blau markiert. Jedes Element speichert Anfangsposition und Anfangstangente; Endposition und Endtangente werden exakt berechnet. Verbindungen und Tangentenausrichtung werden im Projekt gespeichert.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

## Portable Windows-Beta bauen

Die reproduzierbare PyInstaller-One-Folder-Konfiguration und der vollständige
Buildablauf sind in [BUILD_WINDOWS.md](BUILD_WINDOWS.md) dokumentiert. Der
Build wird mit folgendem Befehl einschließlich Tests und ZIP-Erzeugung gestartet:

```powershell
.\build_windows.ps1
```

## Lizenz

RC Track Designer darf kostenlos für private, schulische, vereinsbezogene und
andere nicht-kommerzielle Zwecke verwendet und unter den in der Lizenz
genannten Bedingungen weitergegeben oder angepasst werden. Kommerzielle
Nutzung erfordert die vorherige schriftliche Genehmigung des Autors. Der
vollständige deutsch- und englischsprachige Text steht in [LICENSE.txt](LICENSE.txt)
und direkt im Programm unter `Hilfe > Lizenz`.

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

## Bekannte Einschränkungen in v0.3.0

- Verbundene Elementgruppen können gemeinsam verschoben, aber noch nicht als Gruppe gedreht werden.
- Hilfslinien können noch nicht gesperrt werden.
- Wenn beide möglichen Bogenlagen beim automatischen Weiterbauen gleich gut passen, wählt der Editor deterministisch eine davon. Die Kurve kann anschließend gelöst, frei gedreht und über den gewünschten Anschluss neu angedockt werden.

---

# RC Track Designer — English

RC Track Designer v0.3.0 is a scale-accurate 2D layout editor for RC car race
tracks. Metres are used internally, and curve radii refer to the track
centreline.

## Installation and startup

Python 3.11 or newer is required when running from source.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m rc_track_designer
```

The development checkout can also be started without installation:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python -m rc_track_designer
```

## Basic operation

- `File > New` creates a track area with the specified length and width.
- Select a straight or a neutral curve angle from the upper palette, then click inside the track area to place it. `Esc` ends placement mode.
- Click to select an element and drag to move it. The toolbar or `Ctrl+Left`/`Ctrl+Right` rotates by 5°. For one selected segment, the plain `Left`/`Right` arrow keys rotate directly; hold the key for continuous rotation. `Delete` or `Delete selection` in the context menu removes the selection.
- Track width, straight length and centreline radius apply to new elements and also change the selected element.
- Straight lengths and curve radii can be adjusted in 0.5 m steps with the plus/minus buttons.
- The minimum permitted centreline radius equals half the track width. The inner edge may converge at one point, but it may not pass the curve centre or intersect itself.
- Track-area length and width can be changed from the toolbar at any time; the view is fitted again afterwards.
- Use the mouse wheel to zoom. Pan with the middle mouse button or `Space` + left mouse button. Press `F` to fit the track area.
- Rulers along the upper X-axis and left Y-axis display metre positions for the current zoom level.
- Magenta guides can be dragged from the rulers and snap in 0.5 m steps. Existing guides can be moved again or removed by dragging them out of the area or by right-clicking.
- Projects are saved and loaded as versioned `*.rct.json` files.
- Under `View > Settings`, choose the light or dark theme and switch between German and English. The selection is retained.

## Smart Track Building

- Free connectors are blue, the active free connector is orange, and connected connectors are green.
- Click any free start or end connector and then select an element from the palette. The new element is appended with the correct tangent, and its opposite free connector becomes active.
- Manually moved elements snap to suitable free connectors within a fixed screen-pixel distance. This distance is independent of zoom; orange rings preview an upcoming snap.
- The same visible magnetic range applies while dragging a free connector. Where tracks are close together, selection is based on the centreline nearest to the click.
- Snapping aligns a nearby compatible connector exactly to the tangent, even if the moving element was previously rotated to a very different angle. Curves are consistently shown as `Curve` in the properties panel.
- Connectors are direction-neutral: start–end, start–start and end–end connections are supported. For two connectors of the same type, the editor automatically accounts for their opposite directed tangents.
- New and edited elements, including the complete track width, must remain within the track area.
- Overlaps do not block placement, dragging, rotation or snapping. Instead, all involved elements receive a red-and-white warning outline. Normally connected neighbours are not treated as conflicts.
- Moving one connected element releases its connections without moving neighbouring elements. Deleting it makes neighbouring connectors free again.
- Changing the length of a straight with one connected end moves only the free end; the connected end stays fixed. Radius and angle changes on one-sided connected curves follow the same rule.
- Drag the free connector of a one-sided connected element to resize it. Straights snap to 0.5 m lengths; curves snap to 0.5 m radii and 5° angles. Releasing the handle on a geometrically compatible free connector closes the connection.
- To close an open track automatically, mark its two free connectors with `Ctrl+click`, then choose `Edit > Close track…` or the matching context-menu command. A general local geometry solver adjusts neighbouring lengths, radii and curve angles within valid limits where necessary. A preview lists every change; all changes are applied as one Undo/Redo step.
- Release an existing connection by double-clicking or right-clicking its green connector. Releasing can be undone and redone.
- Select multiple elements with `Shift + click`. Dragging moves the complete selection while retaining internal connections.
- A moved selection can snap to an element outside the selection through one of its free outer connectors. The group is aligned as one rigid body and retains its internal connections.
- On empty space, hold the left mouse button and draw a selection rectangle. Hold `Shift` to add the enclosed elements to the current selection.
- `Ctrl+C` copies the selection and `Ctrl+V` pastes it with new IDs and a 0.5 m offset. Internal connections in copied groups are retained; connections to elements outside the copied selection are not copied.
- Elements rotate as rigid bodies around the midpoint of their track centreline. Both connectors move with the element, and existing connections are released before rotation. Straights and curves rotate freely through 360° and can then snap through either free connector. A small orange cross marks the rotation centre for a single selected element.
- The properties panel provides numerical position, rotation, width, length, radius and curve angle.
- `Ctrl+Z` undoes changes and `Ctrl+Y` redoes them.
- `Esc` also works while an input field has focus: it ends placement mode or clears the current selection. An integrated quick guide is available under `Help > User guide` (`F1`).

Start and end points are marked in blue. Each element stores its start position
and start tangent; the end position and end tangent are calculated exactly.
Connections and tangent alignment are persisted in the project file.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

## Building the portable Windows beta

The reproducible PyInstaller one-folder configuration and full build procedure
are documented in [BUILD_WINDOWS.md](BUILD_WINDOWS.md). Run the build,
including tests and ZIP creation, with:

```powershell
.\build_windows.ps1
```

A ready-to-use portable Windows 64-bit package is also available from the
[GitHub Releases page](https://github.com/carbonkid88/RC-Track-Designer/releases).
It does not require a separate Python or PySide6 installation.

## License

RC Track Designer may be used free of charge for private, educational,
club-related and other non-commercial purposes. Redistribution and modification
are permitted under the conditions stated in the license. Commercial use
requires the author's prior written permission. The complete German and English
license text is available in [LICENSE.txt](LICENSE.txt) and in the application
under `Help > License`.

## Contributing additional languages

English source strings are the stable translation keys. Translations are stored
as UTF-8 JSON files in `src/rc_track_designer/locales`. Additional language
files can also be placed in the user directory shown by the Settings dialog and
will then appear in the language selector.

A language file has this structure:

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

Missing entries fall back to English, so translations can be completed
incrementally without preventing application startup.

## Known limitations in v0.3.0

- Connected element groups can be moved together, but they cannot yet be rotated as a group.
- Guides cannot yet be locked.
- If both possible curve orientations are equally suitable during automatic continuation, the editor deterministically chooses one. The curve can then be released, freely rotated and snapped through the desired connector.
