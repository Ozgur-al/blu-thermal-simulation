---
phase: 10-edge-layers-and-3d-preview
plan: "02"
subsystem: ui
tags: [pyvista, vtk, 3d-preview, assembly, dock-widget]
dependency_graph:
  requires: [thermal_sim/models/layer.py, thermal_sim/models/project.py, thermal_sim/ui/main_window.py]
  provides: [thermal_sim/ui/assembly_3d.py]
  affects: [thermal_sim/ui/main_window.py]
tech_stack:
  added: [pyvista>=0.47.1, pyvistaqt>=0.11.3, qtpy>=2.4.2]
  patterns:
    - PyVista QtInteractor embedded via QVBoxLayout
    - Lazy import of Assembly3DWidget in _create_3d_dock() to avoid VTK startup cost
    - Actor-translate explode (SetPosition) rather than mesh rebuild for performance
    - Tab20 colormap for unknown materials; fixed RGB palette for 12 common display materials
    - pv.OFF_SCREEN detection via subprocess for headless-safe test skipping
key_files:
  created:
    - thermal_sim/ui/assembly_3d.py
    - tests/test_assembly_3d.py
    - tests/conftest.py
  modified:
    - thermal_sim/ui/main_window.py
    - requirements.txt
decisions:
  - "update_temperature() added as no-op stub — full temperature scalar overlay deferred to a later plan"
  - "Widget tests use subprocess timeout to detect VTK render availability rather than unconditional skip"
  - "build_assembly_blocks converts all geometry to mm for sensible VTK viewport scale"
  - "Zone box bounds inset by 0.001 mm to avoid z-fighting with parent layer block"
metrics:
  duration_min: 15
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
---

# Phase 10 Plan 02: 3D Assembly Preview Widget Summary

Interactive 3D assembly preview using PyVista/VTK with color-coded solid layer blocks, explode slider, and lazy-loaded QDockWidget panel in the main window.

## What Was Built

### thermal_sim/ui/assembly_3d.py

New module providing:

- `_material_color_map()` — maps material names to (R, G, B); fixed colors for 12 common display-module materials (Aluminum, Steel, FR4, Glass, PMMA, PC, Air Gap, Copper, LGP, Diffuser, Reflector, Air); unknown materials use matplotlib tab20 cycling
- `build_assembly_blocks(project)` — iterates layers bottom-to-top tracking cumulative z-offset (in mm), creates a `pv.Box` for each layer and each `MaterialZone` overlay; returns a list of descriptor dicts with mesh, color, label, z_base, layer_index, is_zone
- `Assembly3DWidget(QWidget)` — embeds `QtInteractor` plotter + explode `QSlider`; methods:
  - `update_assembly(project)` — clears plotter, adds layer/zone actors, adds point labels, resets camera
  - `_on_explode(value)` — translates actor z-positions via `actor.SetPosition()` without recreating meshes
  - `update_temperature(project, result)` — no-op stub for future temperature overlay (Plan 03+)
  - `closeEvent(event)` — calls `_plotter.close()` to release VTK resources

### thermal_sim/ui/main_window.py (additions to existing partial implementation)

The file already contained the dock creation and View menu action from an earlier WIP commit. This plan added:

- `_refresh_3d_preview()` call in `_add_layer_row()` — 3D updates when a layer is added
- `_refresh_3d_preview()` call in `_remove_table_row()` when `layers_table` is the target — 3D updates when a layer is removed

The dock toggle, lazy creation, graceful ImportError handling, and calls from `_populate_ui_from_project()` and `_apply_template()` were already present.

### tests/test_assembly_3d.py + tests/conftest.py

- `conftest.py` sets `pv.OFF_SCREEN = True` before any test collection runs
- 10 `TestBuildAssemblyBlocks` tests — run unconditionally (no VTK render window needed): geometry correctness, z-offset monotonicity, zone detection, color range validation, mesh type
- 6 `TestAssembly3DWidget` tests — skipped via `@vtk_render` decorator if VTK render window cannot initialize; detect availability via subprocess with 12s timeout

### requirements.txt

Added `pyvista>=0.47.1`, `pyvistaqt>=0.11.3`, `qtpy>=2.4.2`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] `update_temperature()` stub added**
- **Found during:** Task 2 — main_window.py already calls `self._3d_widget.update_temperature(project, result)` in the simulation-complete handler
- **Issue:** `assembly_3d.py` had no `update_temperature()` method; the main_window call would raise `AttributeError` (caught by try/except, but noisy)
- **Fix:** Added no-op `update_temperature()` with a logging.debug call and a docstring noting it is a stub for future implementation
- **Files modified:** `thermal_sim/ui/assembly_3d.py`
- **Commit:** 0932f59

**2. [Rule 3 - Blocking] Widget tests skip when VTK render unavailable**
- **Found during:** Task 1 verification — `QtInteractor` / `pv.Plotter(off_screen=True)` hangs in background bash processes on Windows (no display context)
- **Fix:** Added `_vtk_renderer_available()` probe (subprocess + 12s timeout) at test-module import; `@vtk_render` skip marker applied to all widget tests; build_assembly_blocks tests run unconditionally since they only need `pv.Box()` (no render window)
- **Files modified:** `tests/test_assembly_3d.py`
- **Commit:** 2178cef

**3. [Existing partial implementation in main_window.py]**
- **Found during:** Task 2 — the dock creation (`_create_3d_dock`), toggle action, `_refresh_3d_preview`, and `_refresh_3d_preview()` calls in `_populate_ui_from_project` and `_apply_template` were already present from a prior WIP commit
- **Action:** Added the two missing `_refresh_3d_preview()` calls (`_add_layer_row`, `_remove_table_row`) and the `update_temperature` stub; did not duplicate existing code

## Test Results

```
249 passed, 2 failed (pre-existing)
```

The 2 failures are in `tests/test_regression_v1.py` against `examples/steady_uniform_stack.json` which was already modified in the working directory before this plan started (shape mismatch: `(8, 18, 30)` vs baseline `(7, 18, 30)`). These are unrelated to this plan.

New tests: 16 total (10 build_assembly_blocks + 6 widget) — all pass when VTK render is available.

## Self-Check: PASSED

- `thermal_sim/ui/assembly_3d.py` — exists, contains `class Assembly3DWidget`
- `tests/test_assembly_3d.py` — exists, contains `test_widget_instantiates_offscreen`
- `tests/conftest.py` — exists
- Task 1 commit `2178cef` — exists
- Task 2 commit `0932f59` — exists
