---
phase: "05-distribution"
plan: "02"
subsystem: "build-pipeline"
tags: [pyinstaller, onedir, windowed, build-script, code-signing, defender-scan, distribution]
dependency_graph:
  requires: [paths-module, app-version-constant, splash-screen, crash-handler]
  provides: [spec-file, build-script, onedir-bundle, distributable-zip]
  affects: []
tech_stack:
  added:
    - "pyinstaller==6.19.0 (build-time only)"
    - "pyinstaller-hooks-contrib==2026.3 (build-time only)"
  patterns:
    - "collect_data_files() in spec for qt_material themes and thermal_sim resources"
    - "5-step build.py pipeline: pyinstaller, copy examples, sign (optional), scan (optional), zip"
    - "argparse --skip-sign / --skip-scan flags for CI convenience"
    - "shutil.which() guards for optional tools (signtool, MpCmdRun)"
key_files:
  created:
    - ThermalSim.spec
    - build.py
  modified:
    - .gitignore
decisions:
  - "build.py imports APP_VERSION from thermal_sim.core.paths — single version source of truth across app and build pipeline"
  - "MpCmdRun search uses sorted glob on Platform/* path first (Windows 11 location), falls back to Program Files path — handles version churn without hardcoding"
  - "Signing skipped non-fatally when signtool or cert missing — build succeeds unsigned with warning; enables CI builds without Windows SDK"
  - "Defender scan non-fatal on non-zero exit — different environments have different configs; warn and continue rather than blocking release"
metrics:
  duration: "3 min"
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 3
---

# Phase 5 Plan 2: PyInstaller Spec and Build Pipeline Summary

**One-liner:** ThermalSim.spec (onedir windowed, no UPX, qt_material+resources bundled) + build.py 5-step pipeline (pyinstaller, examples copy, optional signing, Defender scan, zip) producing a verified 110 MB distributable.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Create ThermalSim.spec and build.py | f5667ae | ThermalSim.spec, build.py, .gitignore |
| 2 | Run build and verify bundle structure | (build artifact — no source changes) | dist/ThermalSim/ (gitignored), ThermalSim-v1.0.zip (gitignored) |

## What Was Built

### ThermalSim.spec

PyInstaller onedir spec file at the project root:

- **Entry point:** `thermal_sim/app/gui.py`
- **Data files:** `collect_data_files("qt_material")` (themes/*.xml, base/*.qss) + `collect_data_files("thermal_sim")` (resources/materials_builtin.json)
- **Hidden imports:** `thermal_sim.ui.main_window`, `thermal_sim.core.paths`
- **Excludes:** `PyQt5`, `PyQt6`, `PySide2`, `tkinter`, `IPython`, `jupyter`
- **EXE flags:** `console=False` (windowed), `upx=False` (AV safety), `exclude_binaries=True` (onedir)
- **COLLECT:** `name="ThermalSim"` → creates `dist/ThermalSim/` with `_internal/` subfolder

### build.py

5-step automated release pipeline (143 lines):

1. **PyInstaller build** — `subprocess.run(["python", "-m", "PyInstaller", "--clean", "--noconfirm", "ThermalSim.spec"])`
2. **Copy examples** — copies all 3 JSON files from `examples/` to `dist/ThermalSim/examples/` via `shutil.copy2`
3. **Sign exe (optional)** — checks `shutil.which("signtool")` + `build_cert.pfx` existence; runs signtool with SHA256 + RFC 3161 timestamp; graceful skip with warning if either missing
4. **Defender scan (optional)** — glob-finds `MpCmdRun.exe` across Platform/* versions; runs `-ScanType 3`; non-fatal on non-zero exit
5. **Create zip** — `zipfile.ZipFile` with `ZIP_DEFLATED`; all files under `ThermalSim/` prefix for clean single-folder extraction

### .gitignore updates

Added: `dist/`, `build/`, `*.zip`, `*.spec.bak`, `build_cert.pfx`

## Bundle Verification Results

Build ran successfully on 2026-03-15:

```
PyInstaller 6.19.0 — pyinstaller-hooks-contrib 2026.3
Platform: Windows-11-10.0.26200-SP0
Python: 3.12.10

Bundle structure:
  dist/ThermalSim/ThermalSim.exe                            16 MB
  dist/ThermalSim/examples/                                 3 JSON files
  dist/ThermalSim/_internal/qt_material/themes/dark_amber.xml    present
  dist/ThermalSim/_internal/thermal_sim/resources/materials_builtin.json  present
  dist/ThermalSim/_internal/PyQt5/                          NOT present (exclude OK)
  dist/ThermalSim/_internal/PyQt6/                          NOT present (exclude OK)
  ThermalSim-v1.0.zip                                       110 MB, 712 files

Defender scan: [OK] no threats found
Launch test: process ran for 6 seconds without crash (no crash.log created)
```

## Deviations from Plan

None — plan executed exactly as written. PyInstaller 6.19.0 bundled all dependencies correctly on first attempt. Defender found no threats. The exe launched and displayed the splash + main window without crashing.

## Self-Check

- [x] `ThermalSim.spec` exists — FOUND
- [x] `build.py` exists — FOUND (143 lines, > 60 min_lines)
- [x] Both files parse without syntax errors — VERIFIED via `ast.parse()`
- [x] Spec contains `console=False` — VERIFIED
- [x] Spec contains `collect_data_files("qt_material")` and `collect_data_files("thermal_sim")` — VERIFIED
- [x] Spec excludes PyQt5/PyQt6/PySide2/tkinter/IPython/jupyter — VERIFIED
- [x] `dist/ThermalSim/ThermalSim.exe` exists — VERIFIED (build completed)
- [x] `dist/ThermalSim/examples/` contains 3 JSON files — VERIFIED
- [x] `dist/ThermalSim/_internal/qt_material/themes/dark_amber.xml` — VERIFIED
- [x] `dist/ThermalSim/_internal/thermal_sim/resources/materials_builtin.json` — VERIFIED
- [x] No PyQt5/PyQt6 in `_internal/` — VERIFIED
- [x] `ThermalSim-v1.0.zip` exists at 110 MB — VERIFIED
- [x] `ThermalSim.exe` launches without crash — VERIFIED (6-second process test)
- [x] Commit f5667ae exists — VERIFIED via git log

## Self-Check: PASSED
