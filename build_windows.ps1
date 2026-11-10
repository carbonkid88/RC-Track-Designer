[CmdletBinding()]
param(
    [string]$Python = ".venv\Scripts\python.exe",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot $Python
$SpecPath = Join-Path $ProjectRoot "packaging\rc-track-designer.spec"
$BuildRoot = Join-Path $ProjectRoot "build\pyinstaller"
$PytestTemp = Join-Path $ProjectRoot "build\pytest-temp"
$DistRoot = Join-Path $ProjectRoot "dist"
$ArtifactRoot = Join-Path $ProjectRoot "artifacts"
$DistributionName = "RC-Track-Designer_v0.4.0-beta2"
$PortableDirectory = Join-Path $DistRoot $DistributionName
$ZipPath = Join-Path $ArtifactRoot "RC-Track-Designer_v0.4.0-beta2_win64.zip"

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python wurde nicht gefunden: $PythonPath"
}

$PythonBits = (& $PythonPath -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($PythonBits -ne "64") {
    throw "Der Windows-Build erfordert 64-Bit-Python, gefunden wurden $PythonBits Bit."
}

$ApplicationVersion = (& $PythonPath -c "import sys; sys.path.insert(0, 'src'); from rc_track_designer import __version__; print(__version__)" ).Trim()
if ($ApplicationVersion -ne "0.4.0") {
    throw "Die Buildkonfiguration erwartet Anwendungsversion 0.4.0, gefunden wurde $ApplicationVersion."
}

& $PythonPath -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller fehlt. Installiere zuerst: $Python -m pip install -r requirements-build.txt"
}

if (-not $SkipTests) {
    if (Test-Path -LiteralPath $PytestTemp) {
        Remove-Item -LiteralPath $PytestTemp -Recurse -Force
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $PytestTemp) -Force | Out-Null
    & $PythonPath -m pytest -q -p no:cacheprovider --basetemp $PytestTemp
    if ($LASTEXITCODE -ne 0) {
        throw "Die automatisierten Tests sind fehlgeschlagen."
    }
}

foreach ($Target in @($BuildRoot, $PortableDirectory, $ZipPath, "$ZipPath.sha256")) {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null

& $PythonPath -m PyInstaller --noconfirm --clean `
    --workpath $BuildRoot `
    --distpath $DistRoot `
    $SpecPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller-Build fehlgeschlagen."
}

Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE.txt") -Destination $PortableDirectory
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\START_HERE.txt") -Destination $PortableDirectory
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $PortableDirectory
Copy-Item -LiteralPath (Join-Path $ProjectRoot "packaging\RELEASE_NOTES_v0.4.0-beta2.md") -Destination $PortableDirectory

$RequiredFiles = @(
    "RC-Track-Designer.exe",
    "LICENSE.txt",
    "START_HERE.txt",
    "README.md",
    "RELEASE_NOTES_v0.4.0-beta2.md",
    "_internal\LICENSE.txt",
    "_internal\README.md",
    "_internal\RELEASE_NOTES_v0.4.0-beta2.md",
    "_internal\rc_track_designer\locales\de.json",
    "_internal\rc_track_designer\locales\en.json",
    "_internal\rc_track_designer\assets\carbonkid_logo.png",
    "_internal\rc_track_designer\assets\software_icon_candidate.png",
    "_internal\rc_track_designer\assets\rc_track_designer.ico",
    "_internal\rc_track_designer\assets\fit_view.svg",
    "_internal\rc_track_designer\assets\plus_dark.svg",
    "_internal\rc_track_designer\assets\plus_light.svg",
    "_internal\rc_track_designer\assets\minus_dark.svg",
    "_internal\rc_track_designer\assets\minus_light.svg"
)
foreach ($RelativePath in $RequiredFiles) {
    $RequiredPath = Join-Path $PortableDirectory $RelativePath
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "Erforderliche Buildressource fehlt: $RequiredPath"
    }
}

$Tar = Join-Path $env:SystemRoot "System32\tar.exe"
if (-not (Test-Path -LiteralPath $Tar -PathType Leaf)) {
    throw "tar.exe wurde nicht gefunden; Windows 10 oder 11 wird für den ZIP-Schritt benötigt."
}
& $Tar -a -c -f $ZipPath -C $DistRoot $DistributionName
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
    throw "ZIP-Erzeugung fehlgeschlagen."
}
$Hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash
Set-Content -LiteralPath "$ZipPath.sha256" -Encoding ascii -Value "$Hash  $(Split-Path -Leaf $ZipPath)"

Write-Host "Portable Build: $PortableDirectory"
Write-Host "ZIP:            $ZipPath"
Write-Host "SHA256:         $Hash"
