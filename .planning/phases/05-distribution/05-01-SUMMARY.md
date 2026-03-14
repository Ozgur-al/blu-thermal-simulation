---
phase: "05-distribution"
plan: "01"
subsystem: "resource-paths"
tags: [paths, pyinstaller, frozen-mode, splash-screen, crash-handler, migration]
dependency_graph:
  requires: []
  provides: [paths-module, app-version-constant, splash-screen, crash-handler]
  affects: [material-library, main-window, gui-launcher]
tech_stack:
  added: []
  patterns:
    - "sys.frozen + sys._MEIPASS detection for PyInstaller frozen vs dev mode"
    - "QPainter-drawn splash screen (no external asset)"
    - "main() crash wrapper + _run_app() separation for windowed mode safety"
key_files:
  created:
    - thermal_sim/core/paths.py
    - tests/test_paths.py
  modified:
    - thermal_sim/core/material_library.py
    - thermal_sim/ui/main_window.py
    - thermal_sim/app/gui.py
decisions:
  - "paths.py uses Path(__file__).resolve().parent.parent.parent (3 levels up) as dev root — exact package depth from thermal_sim/core/paths.py to project root"
  - "SystemExit re-raised in crash handler (normal app.exec() exit must not be treated as a crash)"
  - "splash.showMessage placed after splash.show() + app.processEvents() — ensures first paint before heavy imports begin"
  - "gui.py top-level imports limited to sys, traceback, and paths (no PySide6) — crash handler can display dialog even if PySide6 import partially fails"
metrics:
  duration: "3 min"
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 5
---

# Phase 5 Plan 1: Resource Path Centralization and GUI Launch Experience Summary

**One-liner:** Centralized `paths.py` for PyInstaller frozen/dev path detection + QPainter splash screen with amber branding + crash handler that writes crash.log and shows Qt dialog.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 (RED) | TDD failing tests for paths.py | 6c3bb0d | tests/test_paths.py |
| 1 (GREEN) | Create paths.py and migrate all callers | 2b3bffb | thermal_sim/core/paths.py, material_library.py, main_window.py |
| 2 | Rewrite gui.py with splash and crash handler | abec5b0 | thermal_sim/app/gui.py |

## What Was Built

### thermal_sim/core/paths.py (NEW)

Single source of truth for all resource path resolution:
- `_bundle_root()` — returns `sys._MEIPASS` in frozen mode, project root in dev
- `_exe_dir()` — returns `Path(sys.executable).parent` in frozen mode, project root in dev
- `get_resources_dir()` — `_bundle_root() / "thermal_sim" / "resources"`
- `get_examples_dir()` — `_exe_dir() / "examples"`
- `get_output_dir()` — `~/Documents/ThermalSim/outputs/`
- `get_crash_log_path()` — `_exe_dir() / "crash.log"`
- `APP_VERSION = "1.0"`

### Migrations

**material_library.py:** Replaced `from importlib.resources import files` + `files("thermal_sim.resources").joinpath(...)` with `from thermal_sim.core.paths import get_resources_dir` + `get_resources_dir() / "materials_builtin.json"`.

**main_window.py:** 5 call sites updated:
1. `_output_dir` default: `Path.cwd() / "outputs"` → `get_output_dir()`
2. `_update_title()`: title strings now include `v{APP_VERSION}`
3. `setWindowTitle` in `__init__`: also includes version
4. `_load_startup_project()`: bare `Path("examples/...")` → `get_examples_dir() / ...`
5. `_load_project_dialog()`: `Path.cwd()` → QSettings `last_open_dir` defaulting to `get_examples_dir()`; saves last-used dir on successful load
6. `_save_project_as_dialog()`: fallback `Path.cwd() / "project.json"` → `get_examples_dir() / "project.json"`

### thermal_sim/app/gui.py (REWRITTEN)

Restructured from single `main()` to `main()` + `_run_app()`:

- `main()`: Crash wrapper — catches all non-SystemExit exceptions, writes full traceback to `get_crash_log_path()`, shows `QMessageBox.critical` with first 800 chars + "See crash.log". No `print()` calls (safe for `--windowed` mode where stdout/stderr are None).
- `_run_app()`: Full launch sequence — QApplication, qt-material theme, QPainter splash (480x280, dark bg `#212121`, amber text `#FFB300`, title + version + "Loading..."), mpl rcParams, deferred MainWindow construction, `splash.finish(window)`.

## Verification Results

```
122 passed in 21.15s
```

- `get_resources_dir()` → `G:\blu-thermal-simulation\thermal_sim\resources` (exists)
- `get_examples_dir()` → `G:\blu-thermal-simulation\examples` (exists)
- `APP_VERSION` → `"1.0"`
- `load_builtin_library()` → 15 materials loaded
- No `importlib.resources` imports remaining in source files

## Deviations from Plan

None — plan executed exactly as written. The TDD flow (RED → GREEN) was followed for Task 1. Task 2 was implemented directly per the plan spec.

## Self-Check

- [x] `thermal_sim/core/paths.py` exists — FOUND
- [x] `tests/test_paths.py` exists — FOUND (108 lines, 11 tests)
- [x] `thermal_sim/app/gui.py` rewritten (139 lines, >60 min_lines) — FOUND
- [x] Commits exist: 6c3bb0d, 2b3bffb, abec5b0 — VERIFIED via git log
- [x] 122 tests pass — VERIFIED

## Self-Check: PASSED
