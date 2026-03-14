---
phase: 03-simulation-capabilities
plan: 02
subsystem: simulation
tags: [sweep, parametric, dataclass, cli, tdd, scipy, numpy]

requires:
  - phase: 03-simulation-capabilities
    provides: "Phase 3 research and plan structure for simulation capabilities"

provides:
  - "SweepConfig dataclass with from_dict/to_dict and explicit validation"
  - "SweepRunResult and SweepResult dataclasses for serializable sweep output"
  - "_apply_parameter function handling layers, heat_sources, boundaries, frozen materials"
  - "SweepEngine.run() with deep-copy safety, progress callback, and memory-safe design"
  - "load_sweep_config() JSON loader helper"
  - "CLI --sweep flag wired to _run_sweep with stdout table and CSV export"

affects:
  - 03-04  # GUI sweep wiring (deferred to this plan)
  - future-reporting  # PDF export of sweep results

tech-stack:
  added: []
  patterns:
    - "Deep copy base project before each sweep run — never mutate the original"
    - "dataclasses.replace() for frozen Material fields instead of setattr"
    - "Discard full solver result after extracting layer stats — memory-safe sweep"
    - "Progress callback on_progress(n, m) fires after each completed run (1-indexed)"
    - "Lazy imports inside SweepEngine.run() to avoid circular imports at module level"

key-files:
  created:
    - thermal_sim/core/sweep_engine.py
    - thermal_sim/models/sweep_result.py
    - tests/test_sweep_engine.py
  modified:
    - thermal_sim/app/cli.py

key-decisions:
  - "SweepEngine discards full solver result (del result) after stats extraction — prevents ~350 MB accumulation for large transient sweeps"
  - "Material mutation uses dataclasses.replace() since Material is frozen=True — setattr raises FrozenInstanceError"
  - "_apply_parameter raises ValueError with human-readable messages for all invalid path cases"
  - "SweepResult imports SweepConfig lazily inside from_dict() to avoid circular import between sweep_engine and sweep_result modules"
  - "CLI --sweep early-returns before the try/except steady/transient block to keep sweep as a first-class mode"

patterns-established:
  - "Parametric sweep: SweepConfig -> SweepEngine.run() -> SweepResult with per-run SweepRunResult"
  - "Parameter path syntax: dot-separated with [N] index notation for list fields"

requirements-completed: [SIM-01]

duration: 5min
completed: 2026-03-14
---

# Phase 3 Plan 02: Parametric Sweep Engine Summary

**SweepEngine with deep-copy-per-run, frozen-Material-safe _apply_parameter, and CLI --sweep flag exporting tabular results and sweep_results.csv**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-14T13:26:16Z
- **Completed:** 2026-03-14T13:30:24Z
- **Tasks:** 2 (TDD — 4 commits total: 2 RED + 2 GREEN)
- **Files modified:** 4

## Accomplishments

- Built SweepConfig and SweepResult dataclass hierarchy with full to_dict/from_dict round-trips
- Implemented _apply_parameter supporting all 4 sweepable path patterns including frozen Material via dataclasses.replace
- SweepEngine.run() deep-copies project per value, solves steady or transient, extracts layer_stats, discards full arrays — memory-safe by design
- CLI --sweep flag loads sweep JSON, prints progress and formatted result table to stdout, exports sweep_results.csv
- 27 new tests, all passing; no regressions in the 76 pre-existing tests

## Task Commits

Each task was committed atomically (TDD pattern: RED then GREEN):

1. **Task 1 RED: Failing tests for SweepConfig, _apply_parameter, SweepResult** - `fde2e92` (test)
2. **Task 1 GREEN: SweepConfig, SweepResult, SweepEngine, _apply_parameter** - `96a8700` (feat)
3. **Task 2 GREEN: CLI --sweep flag and _run_sweep function** - `bce2d8d` (feat)

_Note: Task 2 tests were written together with Task 1 tests (single RED commit) since they share the same test file._

## Files Created/Modified

- `thermal_sim/core/sweep_engine.py` - SweepConfig, SweepEngine, _apply_parameter, load_sweep_config
- `thermal_sim/models/sweep_result.py` - SweepRunResult and SweepResult dataclasses
- `thermal_sim/app/cli.py` - Added --sweep argument and _run_sweep function
- `tests/test_sweep_engine.py` - 27 tests covering all sweep functionality

## Decisions Made

- SweepEngine discards full solver result (explicit `del result`) after extracting stats — prevents ~350 MB accumulation for 10-run transient sweeps (noted as a Phase 3 concern in STATE.md blockers)
- Material mutation uses `dataclasses.replace()` since `Material` is `frozen=True` — `setattr` would raise `FrozenInstanceError`
- SweepResult imports SweepConfig lazily inside `from_dict()` to avoid circular import between the two modules
- CLI `--sweep` early-returns before the try/except steady/transient block to keep sweep as a fully independent mode

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

A pre-existing test failure was discovered in `tests/test_power_profile.py::test_square_wave_profile_transient_matches_analytical`. This file is untracked (created by plan 03-01) and its failure predates this plan. It is out of scope — logged to deferred-items.md and not fixed here.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SweepEngine backend complete; ready for GUI wiring in 03-04
- sweep_results.csv export format is stable — PDF report can consume it in a later phase
- SIM-01 requirement satisfied

---
*Phase: 03-simulation-capabilities*
*Completed: 2026-03-14*

## Self-Check: PASSED

- FOUND: thermal_sim/core/sweep_engine.py
- FOUND: thermal_sim/models/sweep_result.py
- FOUND: tests/test_sweep_engine.py
- FOUND: .planning/phases/03-simulation-capabilities/03-02-SUMMARY.md
- FOUND commit: fde2e92 (RED tests)
- FOUND commit: 96a8700 (GREEN sweep engine)
- FOUND commit: bce2d8d (GREEN CLI)
