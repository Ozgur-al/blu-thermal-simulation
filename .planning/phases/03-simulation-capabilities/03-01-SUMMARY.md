---
phase: 03-simulation-capabilities
plan: 01
subsystem: solvers
tags: [power-profile, transient-solver, network-builder, numpy, piecewise-linear]

requires:
  - phase: 02-results
    provides: TransientSolver with cancel/progress callbacks, ThermalNetwork dataclass

provides:
  - PowerBreakpoint dataclass with time_s/power_w fields and to_dict/from_dict
  - HeatSource.power_at_time(t) with piecewise-linear interpolation and looping
  - ThermalNetwork.b_boundary and b_sources (split from b_vector)
  - ThermalNetwork.b_vector backward-compatible @property
  - build_heat_source_vector() public function for per-timestep power scaling
  - TransientSolver per-step power scaling using power_at_time(t)

affects: [03-02-sweep-engine, 03-04-gui-power-profile]

tech-stack:
  added: []
  patterns:
    - "PowerBreakpoint uses same to_dict/from_dict round-trip pattern as all other model dataclasses"
    - "ThermalNetwork b_vector split: b_boundary (boundary G*T_amb terms) + b_sources (heat source power)"
    - "Transient solver detects _has_profiles once before the loop; no overhead per-step if all sources are constant"
    - "build_heat_source_vector() mirrors _apply_heat_sources logic but accepts time_s argument"

key-files:
  created:
    - tests/test_power_profile.py
  modified:
    - thermal_sim/models/heat_source.py
    - thermal_sim/solvers/network_builder.py
    - thermal_sim/solvers/transient.py

key-decisions:
  - "power_at_time single-breakpoint edge case falls back to power_w (profile_end <= 0 guard)"
  - "First breakpoint enforced at time_s=0 in HeatSource.__post_init__ to prevent looping bugs"
  - "TransientSolver detects time-varying profiles once before the loop (_has_profiles flag) to avoid rebuilding b_power on constant-only runs"
  - "Square-wave benchmark (Benchmark B) uses epsilon-gap step approximation in np.interp rather than trying to represent discontinuities"
  - "dt=0.001s used for Benchmark B to achieve <1% error with implicit Euler (dt/tau ~0.0016)"

requirements-completed: [SIM-03, SIM-04]

duration: 8min
completed: 2026-03-14
---

# Phase 3 Plan 01: Power Profile Support Summary

**PowerBreakpoint + power_at_time piecewise-linear interpolation on HeatSource, ThermalNetwork b_vector split into b_boundary/b_sources, and TransientSolver per-timestep power scaling via build_heat_source_vector()**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-14T13:26:14Z
- **Completed:** 2026-03-14T13:34:09Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4

## Accomplishments

- Added PowerBreakpoint dataclass (time_s, power_w) with serialization; added optional power_profile field to HeatSource; power_at_time(t) uses np.interp with looping via t % profile_end
- Split ThermalNetwork.b_vector into b_boundary (boundary G*T_amb terms) + b_sources (heat source contributions at nominal power_w); backward-compatible b_vector @property preserves all existing callers
- Added build_heat_source_vector(project, grid, time_s) public function; TransientSolver detects time-varying profiles and calls it per step using power_at_time(t) for each source
- All 107 tests pass including new power profile tests and all existing validation tests

## Task Commits

Each task was committed atomically:

1. **Task 1: PowerBreakpoint dataclass and power_at_time** - `d8ffb4d` (feat)
2. **Task 2: b_vector split + transient per-step power scaling** - `0e47fca` (feat)

## Files Created/Modified

- `thermal_sim/models/heat_source.py` - Added PowerBreakpoint dataclass; optional power_profile field on HeatSource; power_at_time() method; updated to_dict/from_dict; __post_init__ validates first breakpoint at t=0
- `thermal_sim/solvers/network_builder.py` - ThermalNetwork gains b_boundary/b_sources fields with b_vector @property; build_heat_source_vector() public function; _apply_heat_sources unchanged for initial build
- `thermal_sim/solvers/transient.py` - _has_profiles detection before loop; per-step b_power rebuild via build_heat_source_vector when profiles present; fast path using network.b_vector for constant-power runs
- `tests/test_power_profile.py` - 18 tests covering: PowerBreakpoint round-trip, power_at_time interpolation/looping/edge cases, serialization, b_vector split, backward-compatible steady-state, Benchmark D (constant profile), Benchmark B (square-wave RC transient vs. analytical)

## Decisions Made

- power_at_time single-breakpoint edge case: profile_end <= 0 guard falls back to power_w (correct behavior since a single breakpoint has zero period)
- First breakpoint enforced at time_s=0 in __post_init__ to prevent looping discontinuities
- TransientSolver detects profiles once (_has_profiles flag) to avoid overhead on constant-power simulations
- Square-wave Benchmark B uses epsilon-gap step approximation (eps=1e-9 s between Q and 0) since np.interp cannot represent discontinuities
- Benchmark B uses dt=0.001s (not 0.01s) to achieve <1% error with implicit Euler (dt/tau ≈ 0.0016 is in the accurate regime)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Square-wave test profile used wrong breakpoint definition**
- **Found during:** Task 2 (Benchmark B test debugging)
- **Issue:** Original 3-point profile [(0,Q), (T_on,0), (T_period,Q)] produces a triangle wave via np.interp, not a square wave; analytical comparison was for a true step function
- **Fix:** Changed profile to 4 points with epsilon gap: [(0,Q), (T_on,Q), (T_on+eps,0), (T_period,0)]; reduced dt from 0.01s to 0.001s for adequate accuracy
- **Files modified:** tests/test_power_profile.py
- **Verification:** test_square_wave_profile_transient_matches_analytical passes with max_err < 1% tol
- **Committed in:** d8ffb4d (Task 1 test file, updated before Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test definition)
**Impact on plan:** Fix was essential for test correctness. No scope creep.

## Issues Encountered

- Files modified by prior session (stash) were already partially complete (network_builder.py had b_boundary/b_sources split, transient.py had _has_profiles detection). These changes were correct and consistent with the plan — committed as Task 2.

## Next Phase Readiness

- SIM-03 and SIM-04 complete: power_at_time() and per-step transient scaling are the physics foundation for all other Phase 3 features
- sweep engine (Plan 03-02) can now use power profiles in transient sweep runs
- GUI wiring for power profile editor (breakpoint table) can reference power_at_time() for live preview

---
*Phase: 03-simulation-capabilities*
*Completed: 2026-03-14*
