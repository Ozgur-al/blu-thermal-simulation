---
phase: 03-simulation-capabilities
plan: 05
subsystem: testing
tags: [pytest, validation, analytical-benchmarks, matplotlib, power-profile, transient, steady-state]

# Dependency graph
requires:
  - phase: 03-01
    provides: PowerBreakpoint dataclass, power_at_time(), split b_vector, per-step transient power
provides:
  - 4 new analytical validation test cases covering multi-layer, time-varying power, lateral spreading, and backward compat
  - plot_validation_comparison() for steady-state bar chart benchmarks
  - plot_validation_transient_comparison() for transient line plots
  - generate_all_validation_plots() utility producing 3 PNG comparison plots
affects: [04-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Validation test builds DisplayProject directly in code, calls solver, compares to numpy.linalg.solve hand calc"
    - "Near-square-wave power profile uses 4 breakpoints with one-timestep-wide transitions"
    - "Plot utilities use lazy matplotlib import (inside function body) for headless compatibility"

key-files:
  created: []
  modified:
    - tests/test_validation_cases.py
    - thermal_sim/visualization/plotting.py

key-decisions:
  - "Near-square-wave profile uses 4 breakpoints [(0,Q),(T_on-dt,Q),(T_on,0),(T_period-dt,0)] to stay within 1% of analytical step-change solution"
  - "generate_all_validation_plots is a utility function (not test_-prefixed) in test_validation_cases.py, callable from CLI via python -c"
  - "Tolerance for lateral spreading test (rel_tol=1e-6) is tighter than transient (1%) because steady-state is an exact solve"

patterns-established:
  - "Analytical hand calc uses np.linalg.solve for 3+ node systems, Cramer's rule for 2-node"
  - "Plot comparison PNGs go to outputs/validation/ by default"

requirements-completed: [MAT-03]

# Metrics
duration: 20min
completed: 2026-03-14
---

# Phase 3 Plan 05: Analytical Validation Tests and Comparison Plots Summary

**Four analytical benchmark tests covering 3-layer steady conduction, RC square-wave transient, 2-node lateral spreading, and constant-profile backward compat, plus matplotlib comparison plot utility generating 3 PNGs**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-14
- **Completed:** 2026-03-14
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- Added 4 new analytical validation test functions to `tests/test_validation_cases.py`, each comparing solver output against a hand-calculated exact solution
- Added `plot_validation_comparison()` (bar chart) and `plot_validation_transient_comparison()` (line plot) to `thermal_sim/visualization/plotting.py`
- Added `generate_all_validation_plots()` utility that runs all benchmarks and saves 3 PNG comparison plots
- All 111 tests pass including the pre-existing power profile tests from plan 03-01

## Task Commits

1. **Task 1: Four new analytical validation test cases** - `358b766` (test)
2. **Task 2: Validation comparison plot utility** - `0f74943` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_validation_cases.py` - Added 4 test functions + generate_all_validation_plots utility + plot imports
- `thermal_sim/visualization/plotting.py` - Added plot_validation_comparison() and plot_validation_transient_comparison()

## Decisions Made

- Near-square-wave power profile: used a 4-breakpoint pattern `[(0,Q),(T_on-dt,Q),(T_on,0),(T_period-dt,0)]` so that the piecewise-linear interpolation approximates a true step-change within one timestep, keeping the error well within 1% of the analytical piecewise-exponential solution
- `generate_all_validation_plots` placed in `test_validation_cases.py` (not a separate module) since it shares all the project setup boilerplate and is callable via `python -c` per the plan specification
- Lazy `import matplotlib.pyplot as plt` inside each plot function to handle headless environments gracefully

## Deviations from Plan

None — plan executed exactly as written. Prerequisites from plan 03-01 (PowerBreakpoint, power_at_time, split b_vector, per-step transient power) were already committed before this plan started.

## Issues Encountered

The pre-existing `test_power_profile.py::test_square_wave_profile_transient_matches_analytical` test was failing before execution (plan 03-01 changes hadn't been reflected in git at the time of initial read). After confirming the 03-01 commits were already in HEAD, the test passes correctly with the implemented per-step power scaling in the transient solver.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- MAT-03 (additional analytical validation tests with comparison plots) is satisfied
- Phase 3 simulation capabilities track is complete: SIM-01 through SIM-04 (sweep engine, power profiles, b_vector split), MAT-01 through MAT-03 (material library, type distinction, validation tests)
- Ready for Phase 4 polish

---
*Phase: 03-simulation-capabilities*
*Completed: 2026-03-14*
