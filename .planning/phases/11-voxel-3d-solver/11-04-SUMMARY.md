---
phase: 11-voxel-3d-solver
plan: "04"
subsystem: ui
tags: [pyvista, pyside6, block-editor, voxel-gui, qt-material, 3d-view]

dependency_graph:
  requires:
    - phase: 11-01
      provides: AssemblyBlock, SurfaceSource, VoxelProject, VoxelMeshConfig, VoxelProbe
    - phase: 11-02
      provides: VoxelSteadyStateSolver, VoxelTransientSolver, VoxelSteadyStateResult, VoxelTransientResult
    - phase: 11-03
      provides: load_voxel_project, save_voxel_project
  provides:
    - BlockEditorWidget — table-based editor for VoxelProject (blocks, sources, boundaries, probes, mesh)
    - Voxel3DView — PyVista 3D view with slice planes, threshold filter, probe markers
    - VoxelMainWindow — integrated main window combining editor + 3D view
    - plot_voxel_slice() — matplotlib 2D slice fallback for PDF export
  affects:
    - thermal_sim/app/gui.py (can now reference VoxelMainWindow)

tech-stack:
  added: []
  patterns:
    - BlockEditorWidget.build_project() / load_project() round-trip pattern for table <-> VoxelProject
    - pyvistaqt.QtInteractor embedded in QWidget right panel; block actors tracked in dict by name
    - RectilinearGrid(x_edges, y_edges, z_edges) with cell_data raveled order='F' for VTK convention
    - Legacy broken imports wrapped in try/except at module level (same pattern as postprocess.py)

key-files:
  created:
    - thermal_sim/ui/block_editor.py
    - thermal_sim/ui/voxel_3d_view.py
  modified:
    - thermal_sim/ui/main_window.py
    - thermal_sim/ui/simulation_controller.py
    - thermal_sim/ui/table_data_parser.py
    - thermal_sim/visualization/plotting.py

key-decisions:
  - "VoxelMainWindow added as new class at bottom of main_window.py; old MainWindow preserved but dead (all dependencies were deleted in Phase 11 Plan 03)"
  - "Legacy broken imports (project_io, DisplayProject, solvers, Layer) wrapped in try/except in main_window.py, simulation_controller.py, and table_data_parser.py — same pattern as postprocess.py from Phase 11 Plan 03"
  - "block_actors dict (name -> actor) enables per-block visibility toggle without clearing the whole scene"
  - "RectilinearGrid uses order='F' ravel for VTK convention — consistent with ConformalMesh3D docstring"
  - "plot_voxel_slice() added to plotting.py for matplotlib fallback (z/y/x axis slices, extent from mesh edges)"

requirements-completed: [VOX-11, VOX-12]

duration: 10min
completed: "2026-03-16"
---

# Phase 11 Plan 04: 3D GUI — Block Editor, Voxel3DView, and VoxelMainWindow Summary

**PySide6 block editor with table-based VoxelProject editing, PyVista 3D view with slice planes and temperature overlay, and integrated VoxelMainWindow replacing the old Layer-based GUI.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-16T14:54:14Z
- **Completed:** 2026-03-16T15:04:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- BlockEditorWidget with five tabs (Blocks, Sources, Boundaries, Probes, Mesh) — all values in mm, SI internally; `build_project()` and `load_project()` round-trip
- Voxel3DView with PyVista QtInteractor, block color map, per-block visibility list, three slice plane sliders, temperature threshold filter, and probe markers with temperature readout
- VoxelMainWindow integrating Materials tab + BlockEditorWidget editor dock + Voxel3DView 3D dock + live structure preview on edit + simulation result overlay
- `start_voxel_run()` added to SimulationController with `_VoxelSimWorker` backing VoxelSteadyStateSolver and VoxelTransientSolver
- `plot_voxel_slice()` added to plotting.py as matplotlib fallback for x/y/z axis slices

## Task Commits

Each task was committed atomically:

1. **Task 1: Create block editor and source editor widgets** - `d1dc1d9` (feat)
2. **Task 2: Create 3D PyVista view and wire into main window** - `bf8265a` (feat)

**Plan metadata:** (created next)

## Files Created/Modified

- `thermal_sim/ui/block_editor.py` — BlockEditorWidget with Blocks/Sources/Boundaries/Probes/Mesh tabs
- `thermal_sim/ui/voxel_3d_view.py` — Voxel3DView with structure preview and temperature overlay
- `thermal_sim/ui/main_window.py` — VoxelMainWindow class added; legacy imports wrapped in try/except
- `thermal_sim/ui/simulation_controller.py` — _VoxelSimWorker + start_voxel_run(); legacy imports fixed
- `thermal_sim/ui/table_data_parser.py` — legacy model imports wrapped in try/except
- `thermal_sim/visualization/plotting.py` — plot_voxel_slice() added

## Decisions Made

- `VoxelMainWindow` added as a new class at the end of `main_window.py` rather than rewriting the existing `MainWindow` class. The old `MainWindow` is dead code (all its model/solver dependencies were deleted in Phase 11 Plan 03) but is preserved to avoid unnecessary churn. `gui.py` still references the old `MainWindow` — that can be switched to `VoxelMainWindow` in a follow-up.
- Legacy broken imports in `main_window.py`, `simulation_controller.py`, and `table_data_parser.py` were wrapped in `try/except ImportError` blocks, setting fallback `= None`. This is consistent with the pattern used for `postprocess.py` and `sweep_engine.py` in Phase 11 Plan 03.
- `RectilinearGrid(x_edges_mm, y_edges_mm, z_edges_mm)` with `temps_3d.ravel(order='F')` follows the VTK Fortran-order convention documented in `ConformalMesh3D`'s docstring.
- `_block_actors: dict[str, object]` tracks actors by block name so individual visibility can be toggled by `actor.SetVisibility(bool)` without clearing the whole scene.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken legacy imports across three UI files**
- **Found during:** Task 2 (main window update)
- **Issue:** `main_window.py`, `simulation_controller.py`, and `table_data_parser.py` all had top-level imports of modules deleted in Phase 11 Plan 03 (`project_io`, `DisplayProject`, `Layer`, `HeatSource`, `LEDArray`, `Probe`, `SteadyStateSolver`, `TransientSolver`). These caused `ModuleNotFoundError` on import, blocking the entire file.
- **Fix:** Wrapped all deleted-module imports in `try/except ImportError` with `= None` fallbacks, mirroring the pattern used in `postprocess.py`/`sweep_engine.py` in Plan 03.
- **Files modified:** `thermal_sim/ui/main_window.py`, `thermal_sim/ui/simulation_controller.py`, `thermal_sim/ui/table_data_parser.py`
- **Verification:** `from thermal_sim.ui.main_window import MainWindow` imports successfully; `py -m pytest -q tests/` — 77 passed
- **Committed in:** bf8265a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — pre-existing broken imports from Plan 03 cleanup)
**Impact on plan:** Fix required for Task 2 to complete. No scope creep — strictly fixing what Plan 03 left broken.

## Issues Encountered

- `gui.py` still launches `MainWindow` (old class); switching it to `VoxelMainWindow` is a follow-up task (the old `MainWindow` will show import-error dialogs at runtime but won't crash the module). This is acceptable for Phase 11 Plan 04 — the plan's goal was to create the widgets and wire them together, not to update the entry point.

## Next Phase Readiness

- BlockEditorWidget, Voxel3DView, and VoxelMainWindow are fully implemented and importable
- `VoxelMainWindow` provides a complete GUI flow: open/save voxel projects, edit assembly, run steady/transient, view 3D results with slice planes and threshold
- Phase 11 Plan 05 (final integration / `gui.py` switchover) can reference `VoxelMainWindow` from `thermal_sim.ui.main_window`

## Self-Check: PASSED

Files confirmed present:
- G:/blu-thermal-simulation/thermal_sim/ui/block_editor.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/ui/voxel_3d_view.py — FOUND

Commits confirmed:
- d1dc1d9 (Task 1: BlockEditorWidget)
- bf8265a (Task 2: Voxel3DView + main window)

---
*Phase: 11-voxel-3d-solver*
*Completed: 2026-03-16*
