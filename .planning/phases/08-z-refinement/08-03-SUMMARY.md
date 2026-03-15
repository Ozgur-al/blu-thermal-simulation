---
phase: 08-z-refinement
plan: 03
subsystem: postprocessing
tags: [numpy, thermal-simulation, z-refinement, csv-export, cli]

# Dependency graph
requires:
  - phase: 08-02
    provides: "SteadyStateResult/TransientResult with z_offsets and nz_per_layer; [total_z, ny, nx] temperature array shape"

provides:
  - "z-aware postprocessing: probe_temperatures, layer_stats, top_n_hottest_cells all use z_offsets-based per-layer slicing"
  - "z-aware CSV export: exports top sublayer per physical layer"
  - "z-aware CLI: resolves correct z-slice for plotting and CSV, prints z-node count for nz>1 projects"
  - "ZREF-04 backward compat tests passing (no xfail): all example JSONs produce valid nz=1 results"
  - "mixed-nz test: nz=[1,3,2] project solves with total_z=6 and correct z_offsets=[0,1,4,6]"

affects: [09-3d-gui-and-eled-zone-preset, thermal_sim/core/postprocess.py, thermal_sim/io/csv_export.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_z_offsets_for_result() fallback helper returns list(range(n_layers+1)) when z_offsets is None"
    - "_z_node_for_probe() resolves top/bottom/center/int z_position to absolute z-node index"
    - "_z_to_layer_idx() maps z-node indices back to physical layer names for hotspot reporting"
    - "layer_stats() and layer_average_temperatures() accept optional z_offsets with warning log for nz>1 without offsets"
    - "CSV export and CLI pass z_offsets=getattr(result, 'z_offsets', None) for backward compat"

key-files:
  created: []
  modified:
    - thermal_sim/core/postprocess.py
    - thermal_sim/io/csv_export.py
    - thermal_sim/app/cli.py
    - tests/test_validation_cases.py

key-decisions:
  - "CSV export writes top sublayer per physical layer (not all z-sublayers) — consistent with default visualization convention"
  - "layer_stats() fallback logs a warning (not raises) when z_offsets is None and total_z > n_layers — allows GUI callers to work with nz=1 projects while documenting the Phase 9 fix path"
  - "probe z_position resolution: top=nz-1, bottom=0, center=nz//2, int=min(z_pos, nz-1) to clamp out-of-range indices"
  - "xfail removed from test_zref04_backward_compat_nz1_identical — Plan 02 wired z_offsets so the test now passes cleanly"

patterns-established:
  - "z_offsets slicing: temperature_map_c[z_offsets[idx]:z_offsets[idx+1]] gives [nz, ny, nx] for a physical layer"
  - "All downstream consumers follow: get z_offsets from result, pass to helper, use z-node not layer_idx"

requirements-completed: [ZREF-04, ZREF-05]

# Metrics
duration: 12min
completed: 2026-03-16
---

# Phase 8 Plan 03: Z-Refinement Downstream Consumers Summary

**Z-aware postprocessing, CSV export, and CLI for [total_z, ny, nx] result shapes with backward-compatible z_offsets=None fallback**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-16T22:45:00Z
- **Completed:** 2026-03-16T22:57:37Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Updated all postprocess functions to use z_offsets-based per-layer slicing instead of direct layer_idx indexing
- Updated CSV export to handle [total_z, ny, nx] shape by exporting top sublayer per physical layer
- Updated CLI to resolve correct z-plot index from z_offsets and print z-node count for nz>1 projects
- Removed xfail from ZREF-04 backward compat test; added parametrized example JSON tests and mixed-nz test — 202 tests pass

## Task Commits

1. **Task 1: Update postprocessing for z-refined results** - `be955d2` (feat)
2. **Task 2: Update CSV export, CLI, and plotting** - `5c056ea` (feat)
3. **Task 3: Backward compat regression test and full validation** - `6c11584` (test)

## Files Created/Modified

- `thermal_sim/core/postprocess.py` - z-aware probe resolution, layer_stats, hotspot ranking with z_offsets; warning for nz>1 fallback
- `thermal_sim/io/csv_export.py` - export_temperature_map_array accepts z_offsets; exports top sublayer per layer
- `thermal_sim/app/cli.py` - z_plot index from z_offsets in steady and transient; z-node count in mesh print
- `tests/test_validation_cases.py` - xfail removed, 3 new ZREF-04 tests added

## Decisions Made

- CSV export writes top sublayer per physical layer (not all z-sublayers) — consistent with default visualization convention documented in CONTEXT.md
- layer_stats() fallback logs a warning (not raises) when z_offsets is None and total_z > n_layers — allows GUI callers (Phase 9 scope) to function correctly with nz=1 projects
- Probe z_position clamped: int z_pos is `min(z_pos, nz-1)` to prevent index out-of-bounds for any sublayer count
- xfail removed from test_zref04 — Plan 02 fully implemented z_offsets so strict=False xfail was now an xpass

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 8 z-refinement complete: all three plans done, full pipeline (build → solve → postprocess → export → plot) works end-to-end for both nz=1 and nz>1 projects
- Phase 9 GUI can add z-slice selector (already identified in plan as Phase 9 scope)
- Blocker from STATE.md: verify Phase 6 ELED stack template fields before committing to ELED preset implementation approach

---
*Phase: 08-z-refinement*
*Completed: 2026-03-16*
