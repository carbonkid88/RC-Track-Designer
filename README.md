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

- `Datei > Neu` legt einen Streckenbereich mit Länge und Breite an.
- Oben Gerade oder Links-/Rechtskurve wählen und zum Platzieren in den Streckenbereich klicken. `Esc` beendet den Platziermodus.
- Klicken wählt ein Element; Ziehen verschiebt es. Werkzeugleiste oder `Strg+Links`/`Strg+Rechts` dreht um 5°. `Entf` löscht.
- Fahrbahnbreite, Geradenlänge und Mittellinienradius gelten für neue Elemente und ändern zugleich das ausgewählte Element.
- Geradenlängen und Kurvenradien lassen sich über die Plus-/Minus-Schaltflächen in 0,5-m-Schritten ändern.
- Der kleinste zulässige Mittellinienradius wird aus der Fahrbahnbreite berechnet. Dadurch kann die innere Fahrbahnkante einer Kurve nicht über den Kurvenmittelpunkt hinauslaufen oder sich selbst überschneiden.
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
- Beim Einrasten wird ein naher kompatibler Anfang-/Endanschluss exakt tangential ausgerichtet, auch wenn das bewegte Element vorher deutlich anders gedreht war. Die Eigenschaften zeigen den unveränderlichen Elementtyp als Gerade, Links- oder Rechtskurve an.
- Nur geometrisch und in Fahrtrichtung passende Anfang-Ende-Paare können verbunden werden.
- Neue oder bearbeitete Elemente müssen einschließlich ihrer vollständigen Fahrbahnbreite innerhalb des Streckenbereichs liegen.
- Überlappungen blockieren Platzieren, Ziehen, Drehen oder Andocken nicht. Alle beteiligten Elemente erhalten stattdessen eine rot-weiße Warnkontur; regulär miteinander verbundene Nachbarelemente gelten nicht als Konflikt.
- Beim Verschieben eines verbundenen Elements werden dessen Verbindungen gelöst, ohne Nachbarelemente mitzubewegen. Beim Löschen werden Nachbaranschlüsse wieder frei.
- Bei einer einseitig verbundenen Geraden verlängert oder verkürzt eine Längenänderung ausschließlich den freien Anschluss; der verbundene Anschluss bleibt fest. Radius- und Winkeländerungen einseitig verbundener Kurven folgen derselben Regel.
- Der freie Anschluss eines einseitig verbundenen Elements kann mit der Maus gezogen werden. Geraden rasten dabei in 0,5-m-Längen, Kurven in 0,5-m-Radien und 5°-Winkeln ein. Wird der Griff auf einem geometrisch passenden freien Gegenanschluss losgelassen, schließt der Editor die Verbindung.
- Zum automatischen Schließen einer offenen Strecke werden ihre beiden freien Anschlüsse mit `Strg+Klick` markiert und anschließend `Bearbeiten > Strecke schließen…` gewählt. Ein allgemeiner lokaler Geometriesolver passt bei Bedarf benachbarte Längen, Radien und Kurvenwinkel innerhalb ihrer gültigen Grenzen an. Eine Vorschau listet alle Änderungen; übernommen werden sie gemeinsam als ein Undo/Redo-Schritt.
- Eine bestehende Verbindung lässt sich gezielt durch Doppelklick oder Rechtsklick auf ihren grünen Anschluss lösen. Das Lösen kann mit Undo/Redo rückgängig gemacht werden.
- Mit `Umschalt + Klick` lassen sich mehrere Elemente auswählen. Ziehen verschiebt die gesamte Auswahl; interne Verbindungen bleiben erhalten.
- Eine gemeinsam verschobene Auswahl kann über einen ihrer freien äußeren Anschlüsse magnetisch an ein Element außerhalb der Auswahl andocken. Die Gruppe wird dafür als starre Einheit ausgerichtet; interne Verbindungen bleiben erhalten.
- Auf freier Fläche des Streckenbereichs kann mit gedrückter linker Maustaste ein Auswahlrahmen aufgezogen werden. `Umschalt` ergänzt die eingerahmten Elemente zur bestehenden Auswahl.
- `Strg+C` kopiert die Auswahl, `Strg+V` fügt sie um 0,5 m versetzt mit neuen IDs ein. Bei kopierten Gruppen bleiben interne Verbindungen erhalten; Verbindungen zu nicht kopierten Elementen werden nicht übernommen.
- Elemente drehen als starrer Körper um die Mitte ihrer Fahrbahnmittellinie. Beide Anschlüsse bewegen sich dabei mit; verbundene Elemente werden vor dem Drehen automatisch gelöst. Geraden sind frei um 360° drehbar. Links- und Rechtskurven sind auf ±90° um ihre Einbau- oder letzte Andockrichtung begrenzt, damit ihre Anschlüsse nicht die relative Seite tauschen. Ein kleines orangefarbenes Kreuz markiert bei Einzelauswahl das Drehzentrum.
- Das Eigenschaftenfenster erlaubt numerische Position, Drehung, Breite, Länge, Radius und Kurvenwinkel.
- `Strg+Z` macht Bearbeitungen rückgängig, `Strg+Y` stellt sie wieder her.
- `Esc` funktioniert auch bei Fokus in einem Eingabefeld: Ein laufender Platziermodus wird beendet beziehungsweise die aktuelle Auswahl aufgehoben. Unter `Hilfe > Bedienungsanleitung` (`F1`) steht eine integrierte Kurzanleitung bereit.

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

- Verbundene Elementgruppen können gemeinsam verschoben, aber noch nicht als Gruppe gedreht werden.
- Hilfslinien können noch nicht gesperrt werden.
