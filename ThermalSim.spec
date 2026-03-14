# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ThermalSim onedir windowed Windows build.

Produces:
    dist/ThermalSim/ThermalSim.exe   -- windowed launcher (no console)
    dist/ThermalSim/_internal/       -- PyInstaller runtime (Qt DLLs, Python stdlib, etc.)

After the build, run build.py to copy examples/ and create the distributable zip.

Reference: https://pyinstaller.org/en/stable/spec-files.html
"""

import os
from PyInstaller.utils.hooks import collect_data_files

# Collect qt_material themes and base stylesheets (not auto-detected by PyInstaller).
# This captures themes/*.xml (e.g. dark_amber.xml) and base/*.qss.
qt_material_datas = collect_data_files("qt_material")

# Collect thermal_sim package data (resources/materials_builtin.json and any other
# non-Python files under the package).  JSON files are invisible to static analysis.
thermal_sim_datas = collect_data_files("thermal_sim")

a = Analysis(
    ["thermal_sim/app/gui.py"],
    pathex=[],
    binaries=[],
    datas=[
        *qt_material_datas,    # dark_amber.xml + all theme XML/QSS
        *thermal_sim_datas,    # materials_builtin.json
    ],
    hiddenimports=[
        "thermal_sim.ui.main_window",
        "thermal_sim.core.paths",
    ],
    hookspath=[],
    hooksconfig={},
    excludes=[
        # Remove competing Qt bindings — saves ~100 MB and prevents the
        # pyinstaller-hooks-contrib "multiple Qt bindings" hard error.
        "PyQt5",
        "PyQt6",
        "PySide2",
        # Unused packages that add bulk.
        "tkinter",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: binaries go in COLLECT, not embedded in EXE
    name="ThermalSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # IMPORTANT: UPX corrupts Qt DLLs with CFG on Windows 11
    console=False,                  # --windowed / --noconsole — no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                      # add .ico path here when icon asset is available
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,                      # Disable UPX in COLLECT as well (AV safety)
    upx_exclude=[],
    name="ThermalSim",              # creates dist/ThermalSim/ folder
)
