---
phase: 11-voxel-3d-solver
plan: "02"
subsystem: voxel-solver
tags: [scipy, sparse, thermal, solver, network-builder, tdd]
dependency_graph:
  requires:
    - phase: 11-01
      provides: AssemblyBlock, SurfaceSource, VoxelProject, ConformalMesh3D, assign_voxel_materials
  provides:
    - VoxelThermalNetwork dataclass (thermal_sim/solvers/voxel_network_builder.py)
    - build_voxel_network function — COO sparse matrix assembly for 3D voxel grid
    - VoxelSteadyStateSolver with adaptive spsolve/bicgstab+ILU
    - VoxelTransientSolver with splu implicit Euler time-stepping
    - voxel_layer_stats() per-block statistics in postprocess.py
    - Analytical validation tests in tests/test_voxel_solver.py
  affects:
    - 11-03 (CLI/IO integration will call these solvers)
    - GUI integration for voxel solver

tech-stack:
  added: []
  patterns:
    - Vectorised NumPy COO triplet accumulation for 3D non-uniform grid conductance
    - Harmonic-mean conductance G = face_area / (d1/(2*k1) + d2/(2*k2)) for all axes
    - Adaptive solver selection (spsolve < 5k nodes, bicgstab+ILU for larger)
    - splu prefactoring for transient implicit Euler (C/dt + A) * T_{n+1} = b + (C/dt)*T_n
    - Single BoundaryGroup applies same BC to all 6 exposed grid-boundary faces
    - TDD: failing tests committed before implementation

key-files:
  created:
    - thermal_sim/solvers/voxel_network_builder.py
    - thermal_sim/solvers/steady_state_voxel.py
    - thermal_sim/solvers/transient_voxel.py
    - tests/test_voxel_solver.py
  modified:
    - thermal_sim/core/postprocess.py

key-decisions:
  - "Single BoundaryGroup design: all 6 exposed grid-boundary faces receive same h — analytical tests must account for all face conductances not just top/bottom"
  - "1D chain test corrected to include all 6-face convection in hand calculation (side faces contribute to G_env per node)"
  - "voxel_layer_stats uses inclusive-lower/exclusive-upper cell-centre containment (same convention as assign_voxel_materials)"
  - "VoxelThermalNetwork stores b_vector as combined BC+source term (no separate b_boundary/b_sources split needed for voxel solver)"

requirements-completed: [VOX-04, VOX-05, VOX-06, VOX-08, VOX-09]

duration: 6min
completed: "2026-03-16"
tasks_completed: 2
files_created: 4
files_modified: 1
tests_added: 20
---

# Phase 11 Plan 02: Voxel Network Builder and Solvers Summary

**Vectorised COO sparse thermal network builder for 3D non-uniform voxel grid, plus adaptive steady-state and implicit Euler transient solvers with 20 analytical validation tests.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-16T14:42:04Z
- **Completed:** 2026-03-16T14:47:59Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Network builder assembles conductance matrix from ConformalMesh3D using vectorised NumPy meshgrids — no Python loops over individual voxels
- Harmonic-mean conductance formula at material boundaries handles anisotropic k_in_plane/k_through correctly
- All 6 grid-boundary faces auto-detected as exposed; single BoundaryGroup BC applied uniformly
- SurfaceSource injection maps block-face voxels by cell-centre containment with shape masks (full/rectangle/circle)
- Analytical validation: 2-node steady-state exact match (rel_tol=1e-9), RC transient decay within 2%

## Task Commits

1. **Task 1: RED — failing tests** - `8dd314b` (test)
2. **Task 2: GREEN — implementation** - `5d6f8c7` (feat)

## Files Created/Modified

- `thermal_sim/solvers/voxel_network_builder.py` — COO sparse assembly, BC auto-detection, SurfaceSource injection
- `thermal_sim/solvers/steady_state_voxel.py` — VoxelSteadyStateSolver, adaptive spsolve/bicgstab+ILU
- `thermal_sim/solvers/transient_voxel.py` — VoxelTransientSolver, splu implicit Euler
- `thermal_sim/core/postprocess.py` — added voxel_layer_stats() function
- `tests/test_voxel_solver.py` — 20 tests: network structure, 1D chain, 2-node, RC transient, per-block stats

## Decisions Made

- Single BoundaryGroup applies to ALL 6 exposed grid-boundary faces (consistent with plan spec). The 1D chain test was updated to include all 6-face conductances in the analytical formula, matching solver output to 1e-9 tolerance.
- `b_vector` in VoxelThermalNetwork is a single combined BC+source term (unlike ThermalNetwork which splits b_boundary and b_sources). Simpler for the voxel use case.
- `voxel_layer_stats` uses inclusive-lower/exclusive-upper cell-centre containment (same convention as `assign_voxel_materials`), ensuring consistent block membership.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test analytical formula updated for 6-face BC**
- **Found during:** Task 2 (running GREEN tests)
- **Issue:** The 1D two-layer chain test's hand calculation only included G_bot + G_top, but the builder (per plan spec) applies BC to ALL 6 exposed faces including the 4 side faces. This caused a 1.5% error (sim=31.42 C vs expected=31.91 C).
- **Fix:** Rewrote the test's analytical formula to account for all 6 face conductances per node (bottom + sides for node 0; top + sides for node 1). The re-derived formula matches to rel_tol=1e-9.
- **Files modified:** tests/test_voxel_solver.py
- **Verification:** All 20 tests pass; exact match confirms the network builder is correct
- **Committed in:** 5d6f8c7 (Task 2 feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test analytical formula)
**Impact on plan:** No scope change. The builder implementation is correct; the test expectation was wrong. Fix brings test in line with the specified "all faces" BC assignment behaviour.

## Issues Encountered

None — implementation proceeded as planned after correcting the test formula.

## Self-Check

Files created:
- G:/blu-thermal-simulation/thermal_sim/solvers/voxel_network_builder.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/solvers/steady_state_voxel.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/solvers/transient_voxel.py — FOUND
- G:/blu-thermal-simulation/tests/test_voxel_solver.py — FOUND

Commits:
- 8dd314b test(11-02): add failing tests for voxel network builder and solvers — FOUND
- 5d6f8c7 feat(11-02): implement voxel network builder, steady-state and transient solvers — FOUND

## Self-Check: PASSED

## Next Phase Readiness

- Voxel physics engine complete: build_voxel_network, VoxelSteadyStateSolver, VoxelTransientSolver
- Per-block stats via voxel_layer_stats
- Ready for Plan 11-03 (CLI/IO integration, example projects)

---
*Phase: 11-voxel-3d-solver*
*Completed: 2026-03-16*
