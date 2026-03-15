---
phase: 08-z-refinement
plan: 01
subsystem: models
tags: [z-refinement, dataclass, serialization, thermal, validation-tests]

# Dependency graph
requires:
  - phase: 07-3d-solver-core
    provides: NodeLayout abstraction and network builder foundation that Plan 02 will extend with z-links
provides:
  - Layer.nz field with backward-compat default=1 and __post_init__ validation
  - HeatSource.z_position field ('top'|'bottom'|'distributed') propagated through all LEDArray expand methods
  - Probe.z_position field (str|int) with smart from_dict int-or-string parsing
  - SteadyStateResult.nz_per_layer and z_offsets metadata fields with layer_temperatures() helper
  - TransientResult.nz_per_layer and z_offsets metadata fields with layer_temperatures() helper
  - ZREF-05 analytical test: 5-node tridiagonal RED target for Plan 02
  - ZREF-03 analytical test: 6-node inter-layer resistance RED target for Plan 02
  - ZREF-04 backward compat test: nz=1 produces all-1 nz_per_layer RED target for Plan 02
affects: [08-02-network-builder, 08-03-postprocessing, 09-3d-gui-and-eled-zone-preset]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backward-compat field pattern: new optional fields default to sentinel (1 for nz, 'top' for z_position, None for metadata) and from_dict uses .get() with same default"
    - "xfail(strict=False) for RED test scaffolds that define physics contract before implementation"

key-files:
  created: []
  modified:
    - thermal_sim/models/layer.py
    - thermal_sim/models/heat_source.py
    - thermal_sim/models/probe.py
    - thermal_sim/solvers/steady_state.py
    - thermal_sim/solvers/transient.py
    - tests/test_validation_cases.py

key-decisions:
  - "z_position validation on HeatSource uses __post_init__ (consistent with existing shape validation pattern)"
  - "Probe.z_position accepts str|int; from_dict converts digit strings to int for JSON round-trip fidelity"
  - "Result dataclasses carry nz_per_layer/z_offsets as None until Plan 02 wires solver — None is valid backward-compat state"
  - "layer_temperatures() helper on result dataclasses falls back to single-slice when z_offsets is None"

patterns-established:
  - "New domain fields are appended after existing optional fields to avoid positional argument breaks in existing test code"
  - "xfail test scaffolds define exact physics expectations (concrete numbers, matrix setup) before solver implementation — not vague placeholders"

requirements-completed: [ZREF-01, ZREF-03, ZREF-05]

# Metrics
duration: 4min
completed: 2026-03-16
---

# Phase 08 Plan 01: Z-Refinement Data Contracts Summary

**z-refinement model fields (nz, z_position) added to all domain models with backward-compat serialization; result dataclasses extended with nz_per_layer/z_offsets metadata; ZREF-05 and ZREF-03 analytical RED-target tests written**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T22:39:38Z
- **Completed:** 2026-03-15T22:43:53Z
- **Tasks:** 3 of 3
- **Files modified:** 6

## Accomplishments

- Added `nz: int = 1` to Layer with `__post_init__` validation and backward-compat JSON serialization
- Added `z_position: str = "top"` to HeatSource and LEDArray; propagated to all three LEDArray.expand() paths (_expand_custom, _expand_grid, _expand_edge)
- Added `z_position: str | int = "top"` to Probe with smart from_dict int-or-string parsing
- Extended SteadyStateResult and TransientResult with `nz_per_layer`, `z_offsets` (both None by default) and `layer_temperatures()` helper method
- Added ZREF-05 (5-node tridiagonal), ZREF-03 (6-node interface resistance), and ZREF-04 (backward compat nz=1) analytical test scaffolds — all marked xfail, all syntactically correct, 196 existing tests still pass

## Task Commits

1. **Task 1: Add z-refinement fields to domain models** - `c84cdc0` (feat)
2. **Task 2: Extend result dataclasses with z-metadata** - `03b314e` (feat)
3. **Task 3: Write ZREF-05 and ZREF-03 analytical validation tests** - `7ea9ec1` (test)

**Plan metadata:** (docs commit — see final commit)

## Files Created/Modified

- `thermal_sim/models/layer.py` - Added `nz: int = 1` field with validation and to_dict/from_dict
- `thermal_sim/models/heat_source.py` - Added `z_position` to HeatSource and LEDArray; propagated through expand methods
- `thermal_sim/models/probe.py` - Added `z_position: str | int = "top"` with validation and smart parsing
- `thermal_sim/solvers/steady_state.py` - Added `nz_per_layer`, `z_offsets` fields and `layer_temperatures()` helper to SteadyStateResult
- `thermal_sim/solvers/transient.py` - Added `nz_per_layer`, `z_offsets` fields and `layer_temperatures()` helper to TransientResult
- `tests/test_validation_cases.py` - Added three xfail ZREF test functions

## Decisions Made

- `z_position` validation on HeatSource uses `__post_init__` consistent with existing `shape` validation pattern — no external validator needed
- Probe.z_position accepts `str | int`; from_dict converts digit strings to int for JSON round-trip fidelity
- Result dataclasses carry `nz_per_layer`/`z_offsets` as `None` until Plan 02 wires solver — `None` is a valid backward-compat state that `layer_temperatures()` handles gracefully via single-slice fallback
- New fields appended after existing optional fields to avoid positional argument breaks in existing test code

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Data contracts fully established; Plan 02 (network builder z-refinement) can now implement against Layer.nz, HeatSource.z_position, and the ZREF-05/ZREF-03 RED test targets
- Three xfail tests define the exact physics expectations Plan 02 must satisfy
- All 196 existing tests pass — no regressions introduced

---
*Phase: 08-z-refinement*
*Completed: 2026-03-16*
