---
phase: 08-z-refinement
plan: 02
subsystem: solver
tags: [thermal, z-refinement, network-builder, sparse-matrix, numpy, scipy]

# Dependency graph
requires:
  - phase: 08-z-refinement/08-01
    provides: "Layer.nz field, HeatSource.z_position field, SteadyStateResult/TransientResult with nz_per_layer/z_offsets metadata, xfail ZREF-05 and ZREF-03 test scaffolds"
  - phase: 07-3d-solver-core/07-02
    provides: "NodeLayout abstraction, zone rasterization, harmonic-mean conductance assembly"
provides:
  - "Z-refined thermal network builder: intra-layer z-z links (ZREF-02), inter-layer half-dz formula (ZREF-03)"
  - "ThermalNetwork carries n_z_nodes, nz_per_layer, z_offsets"
  - "SteadyStateSolver and TransientSolver reshape to [total_z, ny, nx]"
  - "Heat source z_position dispatch (top/bottom/distributed) in both _apply_heat_sources and build_heat_source_vector"
  - "Side BCs use sublayer area (dz_sub * edge_length) not full layer thickness"
  - "ZREF-05 and ZREF-03 analytical tests confirmed passing to 1e-9 tolerance"
affects: [08-03, 09-3d-gui-and-eled-zone-preset]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "z_offsets[l] * n_per_layer replaces l * n_per_layer for all node index calculations"
    - "Intra-layer z-z links use G = k_through * area / dz_sub (no interface resistance)"
    - "Inter-layer z-z links use G = 1 / (dz_lower/(2*k*A) + R_int/A + dz_upper/(2*k*A))"
    - "All loops over z-sublayers use: z_global = z_offsets[l_idx] + k; base = z_global * n_per_layer"

key-files:
  created: []
  modified:
    - thermal_sim/solvers/network_builder.py
    - thermal_sim/solvers/steady_state.py
    - thermal_sim/solvers/transient.py
    - tests/test_validation_cases.py

key-decisions:
  - "NodeLayout.layer_offsets updated to use z_offsets[l]*n_per_layer so node() method works correctly for nz>1 layers"
  - "Intra-layer z-z links use per-cell k_through_map from zone_maps (supports heterogeneous layers)"
  - "Inter-layer z-z links also use per-cell k_through_map for both lower and upper layers"
  - "Side BC area = dz_sub * edge_length (not layer.thickness); g_x_left/g_y_bottom computed once per layer, applied per sublayer"
  - "build_heat_source_vector recomputes z_offsets locally (does not take network as argument)"

patterns-established:
  - "z_global = z_offsets[l_idx] + k is the canonical sublayer index pattern"
  - "All within-layer links (lateral and intra-z) use dz_sub = thickness / nz for cross-section/distance"
  - "nz=1 backward compat: z_offsets = [0,1,...,n_layers], dz_sub = thickness, all formulas reduce to pre-Phase-8"

requirements-completed: [ZREF-02, ZREF-03, ZREF-04]

# Metrics
duration: 4min
completed: 2026-03-16
---

# Phase 8 Plan 02: Z-Refinement Core Physics Summary

**Z-refined RC network builder with intra-layer conductance (G=k*A/dz), inter-layer half-dz+R_interface formula, and per-sublayer side BCs; both solvers reshape to [total_z, ny, nx]; ZREF-05 and ZREF-03 pass to 1e-9**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-16T22:46:20Z
- **Completed:** 2026-03-16T22:50:09Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Network builder now produces n_z_nodes = sum(layer.nz) total z-sublayer nodes per (ix, iy) column
- Intra-layer z-z links connect adjacent sublayers within a layer with G = k_through * area / dz_sub (no interface resistance)
- Inter-layer z-z links connect topmost sublayer of lower layer to bottommost sublayer of upper layer using the half-dz + R_interface + half-dz resistance formula
- Side BCs scaled to sublayer area (dz_sub * edge_length) so side heat loss is proportional to sublayer, not full layer
- Both SteadyStateSolver and TransientSolver updated to reshape to [n_z_nodes, ny, nx]
- ZREF-05 (nz=5 slab, distributed heat) and ZREF-03 (2-layer nz=3+3 with R_interface) analytical tests pass to 1e-9

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ThermalNetwork and build_thermal_network for z-refinement** - `83eeb3f` (feat)
2. **Task 2: Update steady-state and transient solvers for z-refined reshape** - `049e280` (feat)

## Files Created/Modified
- `thermal_sim/solvers/network_builder.py` - Z-refined network assembly: z_offsets, intra/inter-layer z-z links, sublayer side BCs, z_position heat source dispatch
- `thermal_sim/solvers/steady_state.py` - Reshape to (n_z_nodes, ny, nx); populate nz_per_layer and z_offsets on result
- `thermal_sim/solvers/transient.py` - state_shape uses n_z_nodes; populate nz_per_layer and z_offsets on result
- `tests/test_validation_cases.py` - Removed xfail from ZREF-05 and ZREF-03 (both now pass)

## Decisions Made
- NodeLayout.layer_offsets is updated to `z_offsets[l] * n_per_layer` so the existing `.node()` method works correctly for nz>1 layers without changing call sites in the builder
- Per-cell k_through_map from zone_maps is used for intra-layer z conductance, supporting heterogeneous (zoned) layers
- Side BC conductance computed once per physical layer (g_x_left, g_y_bottom etc.) and then applied identically to each sublayer in a for-k loop — correct because each sublayer has the same material map
- build_heat_source_vector recomputes z_offsets locally (does not take ThermalNetwork as argument) to keep the public API unchanged

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Z-refinement physics implementation is complete and analytically validated
- Plan 03 (postprocessing and GUI adaptation) can proceed; it needs to handle z-sliced result shapes in probe readout, hotspot ranking, and temperature map selection
- The ZREF-04 xfail test (backward compat metadata) is already xpassed — Plan 03 should remove that xfail mark as part of its validation

---
*Phase: 08-z-refinement*
*Completed: 2026-03-16*
