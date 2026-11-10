# -*- mode: python ; coding: utf-8 -*-
"""Reproducible PyInstaller one-folder configuration for Windows x64."""

from pathlib import Path


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
package_root = source_root / "rc_track_designer"
entry_point = project_root / "packaging" / "rc_track_designer_entry.py"
distribution_name = "RC-Track-Designer_v0.4.0-beta2"

datas = [
    (str(package_root / "locales"), "rc_track_designer/locales"),
    (str(package_root / "assets"), "rc_track_designer/assets"),
    (str(project_root / "LICENSE.txt"), "."),
    (str(project_root / "packaging" / "START_HERE.txt"), "."),
    (str(project_root / "README.md"), "."),
    (str(project_root / "packaging" / "RELEASE_NOTES_v0.4.0-beta2.md"), "."),
]

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RC-Track-Designer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(package_root / "assets" / "rc_track_designer.ico"),
    disable_windowed_traceback=False,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=distribution_name,
)
