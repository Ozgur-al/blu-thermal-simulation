---
phase: 01-foundation
plan: 02
subsystem: ui
tags: [pyside6, qthread, simulation-controller, progress-bar, status-bar, transient-solver]

# Dependency graph
requires:
  - phase: 01-01
    provides: PlotManager and TableDataParser extracted from MainWindow (foundation for further decoupling)

provides:
  - SimulationController QObject managing QThread worker lifecycle with progress and cancel signals
  - TransientSolver with on_progress and cancel_check callbacks for cooperative cancellation
  - Three-zone status bar (file path, solver state + progress bar, run metrics)
  - _SimWorker moved out of main_window.py into simulation_controller.py

affects:
  - 01-03 (dirty-flag / unsaved-changes indicator hooks into left zone path label)
  - 01-04 (sweep engine will use SimulationController or reuse worker pattern)
  - Any GUI feature that needs to report async operation progress

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Worker-object threading pattern: _SimWorker lives on QThread via moveToThread; signals cross thread boundary safely
    - Progress callback throttling: progress_every = max(1, n_steps // 100) caps cross-thread signal calls to ~100 per simulation
    - Cooperative cancellation: cancel_check lambda polled inside solver loop, returns valid partial TransientResult on cancel
    - Three-zone status bar: addPermanentWidget with stretch values for left/center/right layout

key-files:
  created:
    - thermal_sim/ui/simulation_controller.py
    - tests/test_simulation_controller.py
  modified:
    - thermal_sim/solvers/transient.py
    - thermal_sim/ui/main_window.py

key-decisions:
  - "SimulationController is a separate QObject (not nested in MainWindow) so simulation lifecycle is independently testable"
  - "Progress capped at ~100 cross-thread signal emissions per simulation via progress_every = n_steps // 100"
  - "TransientSolver returns valid partial TransientResult on cancel rather than raising an exception"
  - "Three-zone status bar uses addPermanentWidget (not showMessage) to prevent transient messages from hiding state"
  - "test_start_run_while_running uses MagicMock to simulate running state rather than spinning a real QThread to avoid test hangs"

patterns-established:
  - "Worker-object pattern: _SimWorker.moveToThread(QThread) for GUI-safe background work"
  - "Controller-signal pattern: SimulationController proxies worker signals to GUI without exposing thread internals"
  - "Progress throttle pattern: cap cross-thread emissions to ~100 regardless of iteration count"

requirements-completed: [GUI-03, GUI-04]

# Metrics
duration: 6min
completed: 2026-03-14
---

# Phase 1 Plan 02: SimulationController + Three-Zone Status Bar Summary

**SimulationController QObject with QThread worker pattern, transient solver cooperative cancel via callbacks, and three-zone permanent status bar showing file path, live progress, and run metrics**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-14T08:45:56Z
- **Completed:** 2026-03-14T08:51:36Z
- **Tasks:** 2 (Task 1 + Task 2 with TDD)
- **Files modified:** 4

## Accomplishments

- Added `on_progress` and `cancel_check` callbacks to `TransientSolver.solve()` with no impact on existing callers
- Created `SimulationController` with five signals (`run_started`, `run_ended`, `progress_updated`, `run_finished`, `run_error`) and clean QThread worker lifecycle
- Removed `_SimWorker` from `main_window.py` entirely; replaced manual QThread setup with `self._sim_controller.start_run()`
- Built three-zone permanent status bar: left (file path), center (solver state + progress bar), right (T_max / elapsed / mesh dimensions after run)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add progress and cancel hooks to transient solver** - `a387e22` (feat)
2. **TDD RED: Failing tests for SimulationController API** - `cf86b5e` (test)
3. **Task 2: Create SimulationController and wire three-zone status bar** - `82c231c` (feat)

## Files Created/Modified

- `thermal_sim/ui/simulation_controller.py` - New: SimulationController + _SimWorker with progress/cancel signals
- `tests/test_simulation_controller.py` - New: 6 tests covering signal presence, is_running, cancel safety, no-duplicate-thread guard, cancel flag
- `thermal_sim/solvers/transient.py` - Added on_progress/cancel_check callback parameters; returns partial result on cancel
- `thermal_sim/ui/main_window.py` - Removed _SimWorker and QThread management; added SimulationController wiring; built three-zone status bar; replaced showMessage calls with zone label updates

## Decisions Made

- `SimulationController` is a standalone `QObject` rather than nested in `MainWindow` so it can be unit-tested without a full window. Tests verify signal presence and API contracts without spinning real solver threads.
- `progress_every = max(1, n_steps // 100)` throttles cross-thread signal emissions to approximately 100 calls per simulation regardless of timestep count, per the research recommendation.
- `TransientSolver` returns a valid `TransientResult` with whatever timesteps were completed on cancel, rather than raising. The `final_temperatures_c` property always returns the last sampled state (initial state minimum).
- Three-zone status bar uses `addPermanentWidget` with stretch values instead of `showMessage` so solver state is persistent and not overwritten by transient messages.
- The TDD no-duplicate-thread guard test uses `MagicMock` to simulate an already-running state rather than starting a real background thread, avoiding test hangs in a headless environment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test for start_run-while-running guard redesigned to avoid real QThread hang**
- **Found during:** Task 2, TDD RED phase
- **Issue:** The initial test spun a real QThread running the steady-state solver, then checked `is_running`. In a headless test environment without a Qt event loop, `QThread.quit()` never processes and the test hangs indefinitely.
- **Fix:** Replaced real thread with `MagicMock(spec=QThread)` where `isRunning()` returns `True`. This isolates the `is_running` property guard check from actual threading behavior, which is correct for a unit test.
- **Files modified:** `tests/test_simulation_controller.py`
- **Verification:** All 6 controller tests pass without hangs; 28 total tests pass.
- **Committed in:** `82c231c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test approach)
**Impact on plan:** Necessary for test reliability in headless CI environment. No scope creep; the behavioral requirement (no duplicate threads) is still fully verified.

## Issues Encountered

None — tests and implementation aligned cleanly after the test redesign.

## Next Phase Readiness

- `SimulationController` is wired and tested; Plan 03 (dirty-flag / unsaved-changes) can hook into `_update_path_label()` directly
- The progress bar infrastructure is in place; any future async operation can emit `progress_updated` through the same controller pattern
- No blockers for Plan 03

---
*Phase: 01-foundation*
*Completed: 2026-03-14*
