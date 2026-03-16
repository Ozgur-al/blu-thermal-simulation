---
phase: 11-voxel-3d-solver
plan: "03"
subsystem: io-cli-examples
tags: [io, cli, examples, cleanup]
dependency_graph:
  requires: [11-01]
  provides: [load_voxel_project, save_voxel_project, CLI, DLED example, ELED example]
  affects: [thermal_sim/app/cli.py, thermal_sim/io/voxel_project_io.py, thermal_sim/io/csv_export.py]
tech_stack:
  added: []
  patterns: [TYPE_CHECKING for removed-module stubs, lazy solver imports in CLI]
key_files:
  created:
    - thermal_sim/io/voxel_project_io.py
    - examples/dled_voxel.json
    - examples/eled_voxel.json
  modified:
    - thermal_sim/app/cli.py
    - thermal_sim/io/csv_export.py
    - thermal_sim/core/postprocess.py
    - thermal_sim/core/sweep_engine.py
  deleted:
    - thermal_sim/models/layer.py
    - thermal_sim/models/material_zone.py
    - thermal_sim/models/project.py
    - thermal_sim/models/stack_templates.py
    - thermal_sim/models/heat_source.py
    - thermal_sim/solvers/network_builder.py
    - thermal_sim/solvers/steady_state.py
    - thermal_sim/solvers/transient.py
    - thermal_sim/core/geometry.py
    - thermal_sim/io/project_io.py
    - 18 old test files
decisions:
  - CLI uses lazy solver imports with ImportError message referencing Phase 11 Plan 02 — allows CLI to function before solvers are wired
  - Broken top-level imports in postprocess.py and sweep_engine.py moved to TYPE_CHECKING — these old-GUI modules survive but will not be invoked at runtime
  - DLED example: 4x3 LED grid (12 LEDs x 0.5W = 6W total) on Metal Frame top face
  - ELED example: left and right FR4 PCB strips with 10+10 LEDs firing inward at LGP edges
metrics:
  duration_min: 5
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_changed: 14
---

# Phase 11 Plan 03: VoxelProject IO, CLI, Example Files, and Old Code Removal Summary

VoxelProject JSON IO, rewritten CLI for 3D voxel format, DLED and ELED example files, and complete removal of old Layer-based DisplayProject code.

## What Was Built

### Task 1: VoxelProject IO and CLI rewrite (840b216)

**`thermal_sim/io/voxel_project_io.py`** — new module providing:
- `load_voxel_project(path)` — loads JSON, delegates to `VoxelProject.from_dict()`
- `save_voxel_project(project, path)` — serialises via `VoxelProject.to_dict()` with `indent=2`

**`thermal_sim/app/cli.py`** — complete rewrite, now exclusively for VoxelProject:
- `--project PATH` — loads VoxelProject JSON
- `--mode steady|transient` — solver selection
- `--output-dir DIR` — output folder
- `--plot` — generates x-y temperature slice PNG at chosen z
- `--plot-z METRES` — z position for slice plot (defaults to mid-height)
- `--csv` — exports per-voxel temperatures as CSV
- `--save-project-copy` — normalised JSON copy
- Solver imports are lazy with clear `ImportError` messages referencing Plan 02

**`thermal_sim/io/csv_export.py`** — added `export_voxel_csv(result, mesh, path)`:
- Writes one row per voxel: `x_mm, y_mm, z_mm, temperature_c`
- Cell centres computed from mesh `x_edges/y_edges/z_edges` arrays

### Task 2: Example files and old code removal (7f564a5)

**`examples/dled_voxel.json`** — direct-lit DLED stack:
- Metal frame (Aluminum 6061) 450mm x 300mm x 3mm
- Reflector (PET) 440mm x 290mm x 0.1mm centered on frame
- LGP (PMMA) 440mm x 290mm x 4mm on top of reflector
- Diffuser (PET) 440mm x 290mm x 0.5mm on top of LGP
- 4x3 grid of 12 SurfaceSources on Metal Frame top face, each 0.5W (6W total)
- Natural convection BC (h=8 W/m²K, T_amb=25°C)

**`examples/eled_voxel.json`** — edge-lit ELED module:
- Metal frame (Steel) 450mm x 300mm x 3mm
- LGP (PMMA) 430mm x 280mm x 4mm, centered inside frame (10mm gap each side)
- Left FR4 PCB strip 1.6mm x 280mm x 4mm in left gap
- Right FR4 PCB strip 1.6mm x 280mm x 4mm in right gap
- 10 LEDs on left PCB "right" face, 10 on right PCB "left" face, each 0.3W (6W total)
- Natural convection BC (h=8 W/m²K, T_amb=25°C)

**Deleted old Layer-based code:** 10 model/solver/core/io files removed entirely via `git rm`.

**Deleted 18 old test files** that depended on removed modules.

**Cleaned up surviving modules:**
- `thermal_sim/core/postprocess.py` — `DisplayProject`, `SteadyStateResult`, `TransientResult` imports moved to `TYPE_CHECKING`
- `thermal_sim/core/sweep_engine.py` — `DisplayProject` import moved to `TYPE_CHECKING`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Fixed broken top-level imports in postprocess.py and sweep_engine.py**
- **Found during:** Task 2
- **Issue:** Deleting `project.py`, `steady_state.py`, `transient.py` would break `postprocess.py` and `sweep_engine.py` at module load time (top-level imports). These files are in the keep list.
- **Fix:** Moved `DisplayProject`, `SteadyStateResult`, `TransientResult` imports under `TYPE_CHECKING` guard — functions still have correct type hints, runtime behaviour unchanged.
- **Files modified:** `thermal_sim/core/postprocess.py`, `thermal_sim/core/sweep_engine.py`
- **Commit:** 7f564a5

**2. [Rule 1 - Bug] Deleted two additional test files not listed in plan**
- **Found during:** Task 2
- **Issue:** `tests/test_assembly_3d.py` and `tests/test_power_profile.py` imported from deleted modules (`project.py`, `layer.py`, `heat_source.py`) but were NOT in the plan's deletion list. Leaving them would break `pytest`.
- **Fix:** Deleted both files; their test coverage is superseded by `test_voxel_assignment.py` and `test_conformal_mesh.py`.
- **Commit:** 7f564a5

## Verification Results

All plan verification checks passed:
- `load_voxel_project('examples/dled_voxel.json')` → 4 blocks, 12 sources
- `load_voxel_project('examples/eled_voxel.json')` → 4 blocks, 20 sources
- `python -m thermal_sim.app.cli --help` → shows new voxel options
- `import thermal_sim` → no errors
- Old model files confirmed deleted
- `pytest -q tests` → 76 passed, 1 failed (pre-existing voxel solver accuracy issue from Plan 02)

## Self-Check: PASSED

- thermal_sim/io/voxel_project_io.py: FOUND
- examples/dled_voxel.json: FOUND
- examples/eled_voxel.json: FOUND
- Commit 840b216: FOUND
- Commit 7f564a5: FOUND
