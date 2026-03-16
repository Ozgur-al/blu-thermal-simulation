---
phase: 11-voxel-3d-solver
plan: "07"
subsystem: voxel-solver-diagnostics
tags: [diagnostics, validation, block-editor, voxel-solver, thermal-path]
dependency_graph:
  requires: [11-01, 11-02, 11-04]
  provides: [diagnose_powered_block_contacts, validate_blocks]
  affects: [thermal_sim/solvers/voxel_network_builder.py, thermal_sim/ui/block_editor.py]
tech_stack:
  added: []
  patterns:
    - "diagnose_powered_block_contacts: cell-centre containment + 6-face neighbor walk with vectorised area accumulation"
    - "validate_blocks: pure AABB geometry checks — no mesh/solver, returns list[str] for caller to present"
key_files:
  created: []
  modified:
    - thermal_sim/solvers/voxel_network_builder.py
    - thermal_sim/ui/block_editor.py
    - tests/test_voxel_solver.py
decisions:
  - "diagnose_powered_block_contacts uses the same cell-centre containment bounds (cx >= blk.x and cx < blk.x + blk.width) as _apply_block_power for consistency"
  - "Grid-boundary faces (no neighbor voxel in-grid) are attributed to _DEFAULT_AIR (_DEFAULT_AIR = 'Air Gap') to keep the air-total correct"
  - "validate_blocks reads blocks via self._read_blocks() without building VoxelProject — keeps it GUI-only and decoupled from the solver pipeline"
  - "_share_face uses abs() tolerance 1e-12 for floating-point boundary alignment (mm inputs converted to SI metres)"
  - "Air gap check (check 3) only fires when a metal block exists and has a gap — does NOT fire when the metal block is face-touching the powered block"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_modified: 3
---

# Phase 11 Plan 07: Powered Block Contact Diagnostics and Block Geometry Validation Summary

**One-liner:** Solver-side `diagnose_powered_block_contacts()` reports neighbor materials and shared face areas per powered block; editor-side `validate_blocks()` returns AABB overlap and thermal-path gap warnings without running the solver.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for powered block diagnostic | b6a91eb | tests/test_voxel_solver.py |
| 1 (GREEN) | Implement diagnose_powered_block_contacts() | fce78d8 | thermal_sim/solvers/voxel_network_builder.py |
| 2 | Add validate_blocks() to BlockEditorWidget | 5325dcc | thermal_sim/ui/block_editor.py |

## What Was Built

### Task 1: `diagnose_powered_block_contacts()` (TDD)

Added a public function to `thermal_sim/solvers/voxel_network_builder.py` that:

1. Builds the conformal mesh and material grid (reusing existing helpers).
2. For each powered block (`power_w > 0`), finds the block's voxel extent via cell-centre containment.
3. Walks each of the 6 faces: retrieves the neighbor voxel layer just outside the block boundary, reads material names, and accumulates face area per (direction, material) pair.
4. Handles grid-boundary faces (where no in-grid neighbor exists) by attributing their area to `_DEFAULT_AIR`.
5. Returns `list[dict]` with `block_name`, `power_w`, and `neighbors` (each `{material, face_area_m2, direction}`).

Also added `_log_powered_block_contacts()` (called at end of `build_voxel_network()`) that logs a one-line summary per powered block at `INFO` level.

Three tests in `TestPoweredBlockDiagnostic`:
- `test_powered_block_contact_diagnostic`: LED block on aluminum slab — confirms Aluminum in `-z` direction with correct face area (50mm x 50mm = 0.0025 m²).
- `test_powered_block_isolated_in_air`: Solo powered block — confirms only air neighbors.
- `test_diagnostic_return_structure`: Validates contract (all required keys, valid direction strings).

### Task 2: `BlockEditorWidget.validate_blocks()`

Added a public method to `thermal_sim/ui/block_editor.py` that reads blocks via `self._read_blocks()` and checks:

1. **AABB overlap**: For each (i, j) pair where j > i, warns if blocks overlap with last-defined-wins message.
2. **Powered block without face contact**: Warns if a powered block shares no face with any other block.
3. **Air gap to metal**: Warns if a powered block has a gap between it and a metal block (Aluminum/Copper/Steel/Metal in material name).

Returns `list[str]` — caller is responsible for display. No GUI, no solver, no mesh needed.

## Verification Results

```
python -m pytest -xvs tests/test_voxel_solver.py -k "powered_block"  — 2 passed
python -m pytest -xvs tests/test_voxel_solver.py -k "diagnostic"     — 3 passed
python -c "... assert hasattr(BlockEditorWidget, 'validate_blocks')"  — PASS
python -m pytest -q tests/                                            — 87 passed
```

## Deviations from Plan

None — plan executed exactly as written. The `_accumulate()` inner function in `diagnose_powered_block_contacts()` uses a Python loop per face (not fully vectorised) because the face neighbor sets are small (O(nx*nz) per face call, called 6 times). This is correct for the diagnostic use case (called once per solve, not in a hot path).

## Self-Check: PASSED

All files present: voxel_network_builder.py, block_editor.py, test_voxel_solver.py, 11-07-SUMMARY.md
All commits present: b6a91eb (RED), fce78d8 (GREEN), 5325dcc (Task 2)
87 tests pass (0 failures)
