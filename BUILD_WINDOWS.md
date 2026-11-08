# Portable Windows-Beta bauen

Die Windows-Distribution wird mit PyInstaller im One-Folder-Modus erzeugt. Die
Anwendung und sämtliche Qt-Bibliotheken bleiben dabei in einem gemeinsamen
portablen Programmordner. Es wird kein Installer erstellt.

## Voraussetzungen

- Windows 10 oder 11, 64 Bit
- 64-Bit-Python 3.11 oder neuer in `.venv`
- installierte Projekt- und Testabhängigkeiten

```powershell
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

## Build

```powershell
.\build_windows.ps1
```

Das Skript führt standardmäßig alle Tests aus, leert ausschließlich die
projektspezifischen PyInstaller-Ausgaben, baut die One-Folder-Distribution,
prüft die erforderlichen Ressourcen und erzeugt anschließend:

`artifacts\RC-Track-Designer_v0.3.0-beta1_win64.zip`

Zusätzlich wird eine gleichnamige `.sha256`-Datei geschrieben. Für einen rein
technischen Wiederholungsbuild nach einem bereits erfolgreichen Testlauf kann
`-SkipTests` angegeben werden.

Die ZIP-Erzeugung verwendet das in Windows 10/11 enthaltene `tar.exe`, damit
auch die verschachtelte PyInstaller-Datei `base_library.zip` zuverlässig
verarbeitet wird.

## Enthaltene Ressourcen

- deutsche und englische JSON-Sprachdateien
- SVG-Schaltflächensymbole und Einpassen-Symbol
- carbonKID-Logo
- `LICENSE.txt`
- `START_HERE.txt`

PyInstaller legt Laufzeitdateien im Unterordner `_internal` ab. Lizenz und
Startanleitung werden zusätzlich gut sichtbar in den Programmordner kopiert.

## Schreiborte zur Laufzeit

Die Anwendung schreibt keine Einstellungen in den Programmordner. `QSettings`
verwendet das Windows-Benutzerprofil beziehungsweise die Registry. Zusätzliche
Sprachdateien liegen unter dem von Qt ermittelten benutzerspezifischen
AppData-Verzeichnis. Projektdateien werden ausschließlich am im Dateidialog
gewählten Ort gespeichert.

## Externe Verifikation

Vor einer öffentlichen Beta sollte die ZIP-Datei zusätzlich auf einem frischen
Windows-10- und Windows-11-64-Bit-System ohne Python und ohne PySide6 getestet
werden. Der Build ist nicht digital signiert; Windows SmartScreen kann daher
eine Warnung anzeigen.
