---
phase: 11-voxel-3d-solver
plan: "06"
subsystem: voxel-solver
tags: [bugfix, boundary-conditions, gui, tdd]
dependency_graph:
  requires: []
  provides:
    - BoundaryGroup.faces field with per-face BC assignment
    - _face_matches_group and _find_group_for_face helpers in network builder
    - _refresh_block_combos stub method on BlockEditorWidget
    - Correct CLI transient plot attribute (time_points)
  affects:
    - thermal_sim/models/voxel_project.py
    - thermal_sim/solvers/voxel_network_builder.py
    - thermal_sim/ui/block_editor.py
    - thermal_sim/app/cli.py
tech_stack:
  added: []
  patterns:
    - TDD red/green for boundary face grouping
    - First-match face assignment in boundary group list
key_files:
  created: []
  modified:
    - thermal_sim/ui/block_editor.py
    - thermal_sim/app/cli.py
    - thermal_sim/models/voxel_project.py
    - thermal_sim/solvers/voxel_network_builder.py
    - tests/test_voxel_solver.py
decisions:
  - BoundaryGroup.faces defaults to ["all"] for backward compat — existing single-group projects unchanged
  - First-match semantics in _find_group_for_face — earlier groups take priority; "all" matches any face
  - _face_matches_group defined as nested closure inside build_voxel_network to retain access to project.boundary_groups without extra parameters
  - GUI Faces column stores comma-separated string ("all", "top,bottom", etc.) for human-readable display
  - _refresh_block_combos is a no-op stub — no source-block linking exists yet; reserved for future use
metrics:
  duration: 4 min
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_changed: 5
---

# Phase 11 Plan 06: Fix Critical Voxel Solver Bugs and Add Independent Boundary Face Grouping

**One-liner:** Fixed BlockEditorWidget AttributeError, CLI transient plot attribute, and implemented per-face boundary group assignment with "all" backward compatibility.

## What Was Built

Three critical bugs fixed and one feature added:

1. **Block editor AttributeError** (`block_editor.py`): `_refresh_block_combos()` was called at lines 318 and 325 but never defined. Added a no-op stub method with a docstring reserving it for future source-block linking.

2. **CLI transient plot bug** (`cli.py`): `_plot_slice_transient` used `result.times_s` which does not exist on `VoxelTransientResult`. Fixed to `result.time_points` (the correct attribute name from the dataclass).

3. **Independent boundary face grouping** (`voxel_project.py`, `voxel_network_builder.py`):
   - Added `faces: list[str]` field to `BoundaryGroup` with `default_factory=lambda: ["all"]`
   - Updated `to_dict()` and `from_dict()` for full round-trip support with backward compat
   - Refactored Step 4 in `build_voxel_network` with `_face_matches_group` and `_find_group_for_face` helpers
   - Each of the 6 grid-boundary faces now independently selects the first matching boundary group
   - Single `faces=["all"]` group produces identical results to the pre-existing behavior

4. **GUI Faces column** (`block_editor.py`):
   - Added column 5 "Faces" to boundary table (6 columns total)
   - `_add_boundary_row` accepts `faces: list[str] | None = None` parameter
   - `_read_boundaries` parses comma-separated faces string from column 5
   - `load_project` passes `bg.faces` when populating boundary rows

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Fix block editor AttributeError and CLI transient plot bug | a17a102 |
| 2 (RED) | Add failing tests for boundary face grouping | 44f2b86 |
| 2 (GREEN) | Implement boundary face grouping in model and builder | 6eed3e8 |

## Test Results

- 87 tests pass (up from 80 before this plan)
- 7 new tests in `TestBoundaryGroupFaces`:
  - `test_boundary_group_faces_default_is_all`
  - `test_boundary_group_faces_to_dict_includes_faces`
  - `test_boundary_group_faces_from_dict_without_key_defaults_to_all`
  - `test_boundary_group_faces_from_dict_with_key`
  - `test_independent_boundary_groups`
  - `test_multi_cell_independent_boundary_groups`
  - `test_boundary_group_faces_backward_compat`

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files exist:
- thermal_sim/ui/block_editor.py — FOUND
- thermal_sim/app/cli.py — FOUND
- thermal_sim/models/voxel_project.py — FOUND
- thermal_sim/solvers/voxel_network_builder.py — FOUND
- tests/test_voxel_solver.py — FOUND

Commits exist: a17a102, 44f2b86, 6eed3e8 — all confirmed in git log.

## Self-Check: PASSED
