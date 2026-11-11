# RC Track Designer – Roadmap v0.5.0

> **Planungsstand:** Alle in diesem Dokument beschriebenen Funktionen sind für
> v0.5.0 geplant und noch nicht implementiert. Umfang und technische Umsetzung
> können sich nach Architekturtests und Rückmeldungen aus der öffentlichen
> v0.4.0-Beta noch ändern.

## Zielsetzung

v0.5.0 erweitert den RC Track Designer um allgemeine Planungs-, Mess- und
Ausgabefunktionen für den Classic Track Mode und den Indoor Carpet Track Mode.
Die vorhandene Geometrie, das metrische Weltkoordinatensystem, beide
Bearbeitungsmodi sowie bestehende Projekte bleiben erhalten.

Für die neuen Inhalte wird eine gemeinsame Infrastruktur für Planungsobjekte
vorgesehen. Ziellinien, Zählschleifen, Startplätze, Fahrerstände und
Sperrflächen werden nicht als künstliche `TrackElement`-Geraden oder -Kurven
modelliert. Alle geometrischen Maße werden intern in Metern gespeichert und
berechnet; Pixel dienen ausschließlich der Bildschirmdarstellung und
Trefferprüfung.

## Übergreifende Anforderungen

- Neue Objekte und notwendige Eingabedaten müssen gespeichert und geladen
  werden können.
- Alle Bearbeitungsaktionen müssen in Undo/Redo integriert werden.
- Neue Oberflächentexte müssen auf Deutsch und Englisch verfügbar sein und das
  bestehende Übersetzungssystem verwenden.
- Die Projektformate 1 bis 5 bleiben lesbar. Alte Projekte erhalten beim Laden
  keine erfundenen Planungsobjekte und werden nicht stillschweigend verändert.
- Light Theme, Dark Theme, Classic Track Mode und Indoor Carpet Track Mode
  müssen berücksichtigt werden.
- Rendering, Hit-Testing und Objektbearbeitung sollen möglichst aus dem bereits
  umfangreichen `TrackCanvas` ausgelagert werden.
- Editorhilfen wie Auswahlrahmen, Griffe und Fangmarkierungen gehören nicht in
  Druck- oder PDF-Ausgaben.

## Geplante Funktionen

### 01 – Drucken und PDF-Export

**Status: geplant, nicht implementiert**

Die Ausgabe steht in beiden Bearbeitungsmodi zur Verfügung.

- Druckvorschau, Windows-Druckdialog und PDF-Export
- Papierformate A4 und A3
- Hoch- und Querformat
- automatische Anpassung des vollständigen Layouts auf eine Seite
- Raster optional ein- oder ausblendbar
- wahlweise farbige oder tintensparende Ausgabe in Graustufen auf weißem
  Hintergrund
- Projekttitel und Abmessungen des Streckenbereichs optional ausgeben
- keine Auswahlrahmen, Bearbeitungsgriffe, Snap-Markierungen oder sonstigen
  Editorhilfen in der Ausgabe
- möglichst vektorbasierte Ausgabe, beispielsweise mit `QPrinter` und
  `QPrintPreviewDialog`

Ziel ist ein gut lesbarer Streckenaufbauplan. Eine zwingend maßstäbliche
technische Zeichnung ist nicht Bestandteil dieser Funktion. Die
Streckengeometrie bleibt innerhalb der Ausgabe proportional; Texte und wichtige
Linien erhalten auf A4 und A3 lesbare Mindestgrößen.

### 02 – Maßband

**Status: geplant, nicht implementiert**

Das Maßband steht in beiden Modi zur Verfügung und ist insbesondere für die
Planung temporärer Hallenstrecken vorgesehen.

- Werkzeug aktivieren und ersten sowie zweiten Messpunkt anklicken
- Abstand in Metern anzeigen
- Messlinie nach dem zweiten Punkt sichtbar lassen, solange das Maßband aktiv
  ist und weder **„Messung auflösen“** noch **„Messung beenden“** gewählt wurde
- magnetisches Fangen an Endpunkten, geraden Kanten und Kurvenkonturen
- freie Fahrbahnbreite zwischen Begrenzungen messbar machen
- Kontextmenü **„Messung auflösen“**: aktuelle Messung entfernen, Werkzeug aktiv
  lassen und eine neue Messung ermöglichen
- Kontextmenü **„Messung beenden“**: Messung entfernen, Werkzeug deaktivieren
  und zur normalen Bearbeitung zurückkehren

Für das Fangen sollen gemeinsame, wiederverwendbare Funktionen für Punkte,
Kanten und Konturen entstehen. Dadurch können spätere Werkzeuge dieselbe
Snap-Geometrie verwenden.

Messungen sind ausschließlich temporärer Werkzeugzustand. Sie werden nicht in
der Projektdatei gespeichert.

### 03 – Sperrflächen

**Status: geplant, nicht implementiert**

Sperrflächen stehen im Indoor Carpet Track Mode zur Verfügung. Sie werden
neutral grau und schraffiert dargestellt.

#### Rechteck

- Länge und Breite in Metern numerisch einstellbar
- Abmessungen alternativ durch Ziehen an den Seiten veränderbar
- als vollständiges Objekt auswählbar und verschiebbar
- Drehung um den Mittelpunkt per Pfeiltasten

#### Kreis

- Durchmesser in Metern numerisch einstellbar
- Durchmesser alternativ durch Ziehen am Kreisumfang veränderbar
- als vollständiges Objekt auswählbar und verschiebbar

#### Freiform

- CAD-ähnliches Polygon durch nacheinander angeklickte Eckpunkte
- fortlaufende Verbindung der gesetzten Punkte
- Schließen durch Anklicken des ersten Punktes
- laufende Eingabe mit `Esc` abbrechen
- Schraffur erst nach dem Schließen der Kontur
- geschlossene Eckpunkte nachträglich verschieben
- Eckpunkte über das Kontextmenü auf einer Kante einfügen und über das
  Kontextmenü eines Eckpunktes entfernen
- als vollständiges Objekt auswählbar und verschiebbar
- Drehung um den Mittelpunkt per Pfeiltasten

Für alle Sperrflächen gelten außerdem:

- Kontextmenü zum Fixieren, Aufheben der Fixierung und Löschen
- fixierte Flächen bleiben auswählbar und ihre Eigenschaften sichtbar, aber
  schreibgeschützt; Position, Größe und Drehung lassen sich erst nach dem
  Entsperren wieder verändern
- Position, Abmessungen beziehungsweise Kontur, Drehwinkel und Fixierungszustand
  speichern
- Undo/Redo für Erzeugung und Bearbeitung
- bevorzugter Drehschritt 1°, mit `Shift` + Pfeiltaste 5°, sofern dies ohne
  Widerspruch zur bestehenden Tastatursteuerung integrierbar ist

### 04 – Start-/Ziellinie

**Status: geplant, nicht implementiert**

Die Start-/Ziellinie steht in beiden Modi zur Verfügung.

- schwarz-weiß karierte Darstellung
- Standardbreite von 0,10 m in Fahrtrichtung
- Standardlänge aus der aktuell eingestellten Fahrbahnbreite, andernfalls
  2,00 m
- Länge bleibt editierbar und an die Fahrbahnbreite anpassbar
- freie Positionierung und Verschiebung
- Drehung um den Mittelpunkt
- Speicherung und vollständiges Undo/Redo

### 05 – Zählschleife

**Status: geplant, nicht implementiert**

Die Zählschleife ist in beiden Modi ein eigenständiges Objekt und bleibt
semantisch unabhängig von der Start-/Ziellinie.

- gleiche Bedienung und Grundgeometrie wie die Start-/Ziellinie
- Standardbreite von 0,10 m
- Standardlänge aus der aktuell eingestellten Fahrbahnbreite, andernfalls
  2,00 m; Länge bleibt editierbar
- grüne Darstellung
- frei platzierbar, verschiebbar und drehbar
- Speicherung und vollständiges Undo/Redo

### 06 – Startplätze

**Status: geplant, nicht implementiert**

Startplätze stehen in beiden Modi zur Verfügung und werden einzeln bearbeitet.

- drei verbundene weiße Linien in einer seitlich offenen U-Form
- Grundausrichtung: links eine vertikale lange Linie, oben und unten je eine
  kurze Linie nach rechts, rechte Seite offen
- geschlossene lange Seite: 0,50 m
- obere und untere kurze Schenkel: jeweils 0,20 m
- mittige Startnummer innerhalb der U-Form
- einzelne Startplätze hinzufügen und frei positionieren
- automatisch fortlaufende und eindeutige Nummerierung ab 1
- stabile Nummerierung in Erzeugungsreihenfolge; Verschieben und Drehen ändern
  die Nummern nicht
- Nummerierung nach dem Löschen wieder lückenlos aktualisieren, ohne die
  verbleibende Erzeugungsreihenfolge zu verändern
- jeden Startplatz einzeln mit der Maus verschieben
- Drehung um den Mittelpunkt der gesamten Geometrie per Pfeiltasten
- Startnummer gemeinsam mit der Geometrie drehen
- Position, Drehwinkel und Nummer speichern
- vollständiges Undo/Redo

Eine automatisch erzeugte komplette Startaufstellung ist für v0.5.0 nicht
zwingend vorgesehen und kann später ergänzt werden.

### 07 – Fahrerstand

**Status: geplant, nicht implementiert**

Der Fahrerstand steht in beiden Modi zur Verfügung und verwendet möglichst
dieselbe Rechteck-Geometriegrundlage wie rechteckige Sperrflächen.

- rechteckige Fläche
- Standardgröße 4,00 × 1,00 m
- halbtransparente blaugraue Darstellung
- Länge und Breite in Metern numerisch einstellbar
- Größenänderung alternativ durch Ziehen an den Seiten
- frei verschiebbar
- Drehung um den Mittelpunkt
- mittige Beschriftung **„Fahrerstand“** beziehungsweise **„Drivers' Stand“**
- Beschriftung mit der Fläche skalieren, dabei lesbar halten
- Kontextmenü zum Fixieren, Entsperren und Löschen
- Speicherung und vollständiges Undo/Redo

### 08 – Ideallinie

**Status: geplant, nicht implementiert**

Die Ideallinie kann in beiden Modi über eine Checkbox ein- und ausgeblendet
werden. Eine kompakte Längenanzeige und die Validitätsmeldung erscheinen in der
Statusleiste; zusätzliche Bearbeitungsoptionen werden nur bei Bedarf
eingeblendet.

- hellblaue Linie mit dezentem Kontur-Leuchteffekt
- geometrisch sinnvolle und möglichst flüssige Linie
- keine Fahrzeugklassen, Maßstabseingaben oder physikalische Rennsimulation
- nicht als nachweislich schnellste Rennlinie bezeichnen
- normale Auswahl und Bearbeitung anderer Objekte nicht behindern
- Linie und erforderliche Eingabedaten speichern

#### Classic Track Mode

- Fahrbahnkorridor automatisch aus den vorhandenen Streckenelementen ableiten
- eine eindeutige zusammenhängende Strecke automatisch erkennen
- bei mehrdeutigem Verlauf keine willkürliche Strecke wählen, sondern eine
  verständliche Meldung anzeigen
- bei einer eindeutigen offenen Strecke eine offene Ideallinie zulassen
- geglättete Linie innerhalb der verfügbaren Fahrbahnbreite berechnen
- keine manuell gesetzten Führungspunkte

#### Indoor Carpet Track Mode

- Führungspunkte durch Mausklicks entlang des gewünschten Verlaufs setzen
- Führungspunkte definieren nur den Verlauf, nicht die endgültige Linie
- Punkte automatisch zu einer geglätteten Linie verbinden
- Führungspunkte in einem eigenen Bearbeitungsmodus verschieben, auf der Linie
  einfügen und löschen
- eine für offene beziehungsweise geschlossene Linien gültige Mindestpunktzahl
  einhalten und alle Änderungen in Undo/Redo integrieren

Für geschlossene Rundkurse wird der Übergang vom letzten zum ersten Punkt
geglättet. Offensichtliche Überschneidungen mit Begrenzungen und Sperrflächen
sollen möglichst verhindert oder als ungültiger Verlauf gemeldet werden. Die
konkrete geometrische Glättungsmethode wird erst nach technischer Bewertung der
vorhandenen Architektur festgelegt. Fahrbahngrenzen und Sperrflächen werden
geprüft; kann kein gültiger Verlauf erzeugt werden, wird dies gemeldet.

### 09 – Streckenlänge entlang der Ideallinie

**Status: geplant, nicht implementiert**

Die Streckenlänge wird in beiden Modi aus der tatsächlich berechneten und
geglätteten Ideallinie ermittelt.

- Ausgabe in Metern
- bei geschlossenem Rundkurs Länge einer vollständigen Runde
- bei einer offenen Ideallinie darf deren Linienlänge angezeigt werden; sie
  darf nicht als vollständige Rundenlänge bezeichnet werden
- keine bloße Summe gerader Abstände zwischen Führungspunkten
- vollständige Neuberechnung nach abgeschlossenen Geometrieänderungen,
  Undo/Redo und Laden
- während einer Drag-Bewegung höchstens eine leichte Vorschau
- Zoom, Pan, Auswahl und Themewechsel lösen keine Neuberechnung aus
- bei ungültigem oder mehrdeutigem Verlauf keine irreführende Zahl anzeigen
- deutsche Ausgabe: **„Streckenlänge entlang der Ideallinie: 257,34 m“**
- englische Ausgabe: **„Track length along racing line: 257.34 m“**

## Vorgeschlagene Architektur

### Gemeinsames Planungsobjekt-Modell

`TrackElement` bleibt für Fahrbahnelemente und Streckenbegrenzungen zuständig.
Für die neuen Inhalte wird eine davon unabhängige Modellfamilie vorgesehen,
beispielsweise mit folgenden Verantwortlichkeiten:

- stabile Objekt-ID
- Objekttyp
- Position in Weltkoordinaten
- Drehwinkel
- modusspezifische Sichtbarkeit oder Zulässigkeit
- Sperr- beziehungsweise Fixierungszustand
- typspezifische Geometriedaten
- Serialisierung und Validierung

Mögliche fachliche Typen sind Rechteck, Kreis, Polygon, Linie/Markierung,
Startplatz und Fahrerstand. Gemeinsame Geometrie soll über Komposition oder
kleine spezialisierte Datenklassen wiederverwendet werden, nicht über eine
einzige Klasse mit vielen ungenutzten Feldern.

Messungen gehören nicht zum Planungsobjekt-Modell und nicht zum Projektformat.
Sie bleiben temporärer Zustand des Maßbandwerkzeugs.

### Projektformat 6

Für v0.5.0 ist eine neue Projektformatversion 6 vorgesehen.

- bestehende Felder und `TrackElement`-Daten unverändert weiterführen
- zusätzliche, klar getrennte Sammlung für Planungsobjekte
- separate Daten für Ideallinie und manuelle Indoor-Führungspunkte
- abgeleitete Werte wie Streckenlänge nach Möglichkeit neu berechnen, statt sie
  als alleinige Wahrheit zu speichern
- Formate 1 bis 5 weiterhin mit leeren neuen Sammlungen laden
- keine automatische Umwandlung alter Streckenelemente in Planungsobjekte
- unbekannte oder ungültige neue Objektdaten mit klarer Fehlermeldung behandeln

Die genaue JSON-Struktur wird vor der Implementierung durch Roundtrip- und
Rückwärtskompatibilitätstests festgelegt.

### Geometrie- und Snap-Dienste

Aus dem Canvas sollen framework-unabhängige oder Qt-arme Geometriefunktionen
herausgelöst werden:

- nächste Punkte auf Geraden, Kreisbögen, Kurvenkonturen und Polygonkanten
- Abstand Punkt–Kontur und Punkt–Segment
- transformierte Rechteck-, Kreis-, Polygon- und U-Geometrie
- Objektgrenzen und Drehmittelpunkte
- Glättung und Längenbestimmung von Linienzügen
- Kollision beziehungsweise Schnitt mit Begrenzungen und Sperrflächen

Diese Dienste werden vom Maßband, vom Hit-Testing, von Bearbeitungsgriffen und
später von der Ideallinienprüfung gemeinsam verwendet.

### Rendering

Die Darstellung wird in getrennte Ebenen beziehungsweise Renderer aufgeteilt:

1. Streckenbereich, Raster, Lineale und Hilfslinien
2. Fahrbahnelemente oder Begrenzungen
3. Planungsobjekte
4. Ideallinie
5. temporäre Werkzeuge und Editorhilfen

Renderer sollen einen Ausgabekontext erhalten, der Bildschirm, Druck oder PDF
unterscheidet. So können Editorhilfen für Druck und Export zuverlässig
ausgeschlossen und möglichst dieselben Vektorgeometrien wiederverwendet werden.

### Hit-Testing, Auswahl und Bearbeitung

Planungsobjekte erhalten gemeinsame Schnittstellen für:

- Trefferprüfung in einer bildschirmbezogenen Toleranz
- Auswahl und Mehrfachauswahl
- Verschieben und Drehen
- optionale Größen- oder Punktgriffe
- Fixierung und Kontextaktionen
- Eigenschaften für das vorhandene Eigenschaftenfenster

`TrackCanvas` koordiniert Eingabe und Modus, delegiert aber Geometrie,
Objekttreffer, Rendering und objektspezifische Bearbeitung an eigene
Komponenten. Damit wächst die bestehende Ereignisbehandlung nicht um neun
weitere vollständige Sonderfallketten.

### Undo/Redo

Die bestehende `QUndoStack`-Integration bleibt die zentrale Historie. Neue
Aktionen müssen Erzeugen, Löschen, Verschieben, Drehen, Größenänderung,
Punktbearbeitung, Fixierung und Nummerierungsänderungen vollständig
rückgängig machen. Während einer Ziehbewegung soll nur ein logisch
zusammengehöriger Undo-Schritt entstehen.

Vor der Implementierung wird geprüft, ob das bestehende Speichern kompletter
Projektzustände für größere Polygon- und Idealliniendaten ausreichend bleibt
oder gezielte Befehle für Planungsobjekte sinnvoller sind.

## Entwicklungsreihenfolge und Feature-Branches

Die vorgeschlagene Reihenfolge berücksichtigt sowohl den gewünschten Ablauf
als auch technische Abhängigkeiten.

1. **`feature/0.5-print-pdf`**
   - gemeinsame saubere Renderausgabe ohne Editorhilfen
   - Druckvorschau, Druckdialog und PDF
   - schafft zugleich eine klarere Rendergrenze für spätere Objekte

2. **`feature/0.5-measuring-tool`**
   - Maßband und gemeinsame Snap-Geometriefunktionen
   - Geometriedienste werden später für Griffe und Kollisionsprüfungen genutzt

3. **`feature/0.5-planning-objects-core`**
   - Planungsobjekt-Modell und Projektformat 6
   - Rendering-, Hit-Test-, Auswahl-, Eigenschaften- und Undo-Schnittstellen
   - Rückwärtskompatibilität für Projektformate 1 bis 5

4. **`feature/0.5-restricted-areas`**
   - rechteckige, kreisförmige und freie Sperrflächen
   - Fixierung, Griffe, Polygonbearbeitung und Schraffur

5. **`feature/0.5-drivers-stand`**
   - Fahrerstand auf Basis der gemeinsamen Rechteck-Geometrie
   - lokalisierte, skalierende Beschriftung

6. **`feature/0.5-start-finish-line`**
   - karierte Start-/Ziellinie auf gemeinsamer Markierungsgeometrie

7. **`feature/0.5-timing-loop`**
   - eigenständige grüne Zählschleife auf derselben Grundgeometrie

8. **`feature/0.5-starting-grid`**
   - einzelne U-förmige Startplätze
   - lückenlose Nummerierung und Drehung

9. **`feature/0.5-racing-line`**
   - automatische Classic- und geführte Indoor-Ideallinie
   - Glättung, Validierung und Speicherung

10. **`feature/0.5-racing-line-length`**
    - Bogenlänge der tatsächlich geglätteten Ideallinie
    - Neuberechnung und lokalisierte Anzeige

11. **`chore/0.5-integration-docs-build`**
    - übergreifende Übersetzungs-, Dokumentations- und Buildintegration
    - Versionsumstellung erst im freigegebenen Releaseprozess

Obwohl neun Funktionen geplant sind, werden Sperrflächen und Fahrerstand sowie
Ideallinie und Streckenlänge bewusst getrennt entwickelt. Dadurch bleiben
fachliche Änderungen überprüfbar, während gemeinsame Grundlagen zuerst
integriert werden. Jeder Feature-Branch wird vom jeweils aktuellen `develop`
erstellt und nach Tests wieder dorthin integriert.

## Teststrategie

Für jedes Funktionspaket sind automatisierte Tests vorzusehen:

- Geometrie und Maße in Metern
- Transformation, Drehung und Hit-Testing
- Undo/Redo jeder Bearbeitungsaktion
- JSON-Roundtrip des Projektformats 6
- Laden der Formate 1 bis 5
- deutsche und englische Texte
- Verhalten in beiden Bearbeitungsmodi, soweit die Funktion dort zulässig ist
- Druckrenderer ohne Editorhilfen
- Snap-Punkte des Maßbands
- lückenlose Startplatznummerierung
- Glättung, Validität und Längenberechnung der Ideallinie

Zusätzlich bleiben sämtliche bestehenden Tests für Classic Track Mode und
Indoor Carpet Track Mode verpflichtend grün.

## Festgelegte technische Entscheidungen

Die zuvor offenen Grundsatzfragen sind für die Planung von v0.5.0 wie folgt
entschieden:

1. **Maßband:** Messungen sind temporär und werden nicht in der Projektdatei
   gespeichert. Die fertige Messung bleibt bei aktivem Maßband sichtbar, bis
   **„Messung auflösen“** oder **„Messung beenden“** gewählt wird.
2. **Druckgrößen:** Die Streckengeometrie bleibt proportional. Texte und
   wichtige Linien erhalten lesbare Mindestgrößen für A4 und A3.
3. **Tintensparender Druck:** Die Ausgabe verwendet Graustufen auf weißem
   Hintergrund.
4. **Freiformpolygone:** `Esc` bricht die laufende Eingabe ab, ein Klick auf den
   ersten Punkt schließt das Polygon. Eckpunkte lassen sich anschließend
   verschieben sowie über das Kontextmenü einfügen und entfernen.
5. **Fixierte Objekte:** Sie bleiben auswählbar und ihre Eigenschaften sichtbar,
   jedoch schreibgeschützt. Position, Größe und Drehung können erst nach dem
   Entsperren geändert werden.
6. **Start-/Ziellinie und Zählschleife:** Die Standardlänge folgt der aktuellen
   Fahrbahnbreite und beträgt ohne ableitbaren Wert 2,00 m. Die Länge bleibt
   editierbar.
7. **Startplätze:** Die Nummerierung folgt einer stabilen Erzeugungsreihenfolge.
   Verschieben und Drehen ändern sie nicht; nach dem Löschen werden Lücken
   geschlossen.
8. **Fahrerstand:** Die Standardgröße beträgt 4,00 × 1,00 m. Die Fläche wird
   halbtransparent blaugrau mit mittiger Beschriftung dargestellt.
9. **Classic-Ideallinie:** Eine eindeutige zusammenhängende Strecke wird
   automatisch erkannt. Mehrdeutige Verläufe erzeugen eine verständliche
   Meldung. Eine eindeutige offene Strecke darf eine offene Linie erhalten.
10. **Glättung und Gültigkeit:** Die geeignete geometrische Glättungsmethode wird
    anhand der vorhandenen Architektur technisch bewertet und nicht vorab auf
    einen bestimmten Spline-Typ festgelegt. Fahrbahngrenzen und Sperrflächen
    werden geprüft; ungültige Verläufe werden gemeldet.
11. **Indoor-Führungspunkte:** Sie werden in einem eigenen Bearbeitungsmodus
    verschoben, auf der Linie eingefügt und gelöscht. Mindestpunktzahl und
    Undo/Redo sind dabei einzuhalten.
12. **Neuberechnung:** Die vollständige Berechnung erfolgt nach abgeschlossenen
    Geometrieänderungen, Undo/Redo und Laden. Während Drag ist höchstens eine
    leichte Vorschau vorgesehen. Zoom, Pan, Auswahl und Themewechsel lösen
    keine Neuberechnung aus.
13. **Bedienoberfläche:** Eine Checkbox schaltet die Ideallinie. Kompakte
    Längenanzeige und Validitätsmeldung stehen in der Statusleiste; zusätzliche
    Bearbeitungsoptionen werden nur bei Bedarf eingeblendet.

Für offene Ideallinien darf eine Linienlänge angezeigt werden. Diese Ausgabe
darf jedoch weder sprachlich noch fachlich als vollständige Rundenlänge
bezeichnet werden.

## Noch offene Implementierungsdetails

Die Grundsatzentscheidungen oben sind verbindlich. Folgende Detailfragen werden
erst im jeweils betroffenen Feature-Branch anhand von Prototypen, Tests und der
vorhandenen Architektur entschieden:

- konkrete Punkt- und Linienmindestgrößen für A4 und A3 sowie die Kontrastwerte
  der Graustufenausgabe
- genaue Toleranzen für das Fangen des Maßbands an Punkten und Konturen
- Mindestabstände und Trefferbereiche für Polygonpunkte und Kontextaktionen
- Verhalten beim Entfernen eines Polygonpunktes an der zulässigen
  Mindestpunktzahl
- genaue visuelle Kennzeichnung ausgewählter, aber fixierter Objekte
- Darstellung und Bedienung der nur bei Bedarf eingeblendeten Zusatzoptionen
- Auswahl der mathematischen Glättungsmethode nach Vergleich mit der
  vorhandenen Geometrie- und Verbindungsarchitektur
- Kriterien und Toleranzen für gültige Fahrbahnkorridore sowie Kollisionen mit
  Sperrflächen
- Mindestpunktzahlen für offene und geschlossene Indoor-Ideallinien
- Umfang und Aktualisierungsrate einer leichten Vorschau während Drag
- Verhalten bei getrennten, verzweigten oder anderweitig mehrdeutigen
  Streckenketten über die festgelegte Fehlermeldung hinaus
- genaue Beschriftung einer offenen Linienlänge in deutscher und englischer
  Sprache

Diese Details dürfen nicht durch unbegründete Annahmen festgeschrieben werden.
Jede Entscheidung wird im zuständigen Feature-Branch dokumentiert und durch
geeignete Tests abgesichert.
