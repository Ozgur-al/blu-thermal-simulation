---
phase: 04-polish
plan: 02
subsystem: ui
tags: [QDockWidget, QSettings, layout-persistence, view-menu, dockable-panels]

# Dependency graph
requires:
  - phase: 04-polish
    provides: qt-material dark_amber theme applied to all Qt widgets (04-01)
  - phase: 03-simulation-capabilities
    provides: GUI structure (MainWindow, PlotManager, SweepResultsWidget) to refactor
provides:
  - Three QDockWidgets replacing QSplitter: Editor (left), Result Plots (top-right), Results Summary (bottom-right)
  - View menu with toggleViewAction for each dock and Reset Layout action
  - Dock state and window geometry persisted via QSettings across sessions
  - _reset_layout() factory-default dock arrangement method
  - _restore_layout() restores saved dock state on startup
affects: [04-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "QDockWidget layout: addDockWidget + splitDockWidget replaces QSplitter"
    - "Layout persistence: saveState/saveGeometry in closeEvent, restoreState/restoreGeometry in __init__"
    - "View menu: dock.toggleViewAction() auto-syncs menu toggle with dock visibility"

key-files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py

key-decisions:
  - "QDockWidget.setObjectName is required for saveState/restoreState to work correctly across sessions"
  - "_build_result_tabs() split into _build_plot_tabs() and _build_summary_tabs() — clean separation matches dock structure"
  - "self._summary_tabs replaces self.result_tabs for widget references — _results_widget and _sweep_results_widget live in summary dock"
  - "_restore_layout() called after _load_startup_project() in __init__ so dock state can override default after startup populates the UI"

patterns-established:
  - "Dock layout pattern: addDockWidget(area, dock) then splitDockWidget(parent_dock, child_dock, orientation) for tabbed arrangement"
  - "Layout save pattern: QSettings setValue dock_state/window_geometry in closeEvent before save-changes prompt"

requirements-completed: [PLSH-02]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 4 Plan 02: Dockable Panel Layout Summary

**QDockWidget-based three-panel layout replacing QSplitter, with View menu toggles, Reset Layout action, and QSettings persistence for dock arrangement across sessions**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-14T14:01:00Z
- **Completed:** 2026-03-14T14:06:36Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Replaced fixed QSplitter with three named QDockWidgets: Editor (left), Result Plots (top-right), Results Summary (bottom-right) stacked via `splitDockWidget`
- Refactored `_build_result_tabs()` into `_build_plot_tabs()` (Temperature Map, Layer Profile, Probe History) and `_build_summary_tabs()` (Summary, Results, Comparison, Sweep Results)
- Added View menu with `toggleViewAction()` for each dock (auto-syncs visibility state) plus Reset Layout action
- Added `_reset_layout()` to restore factory default arrangement and `_restore_layout()` to recover saved state from QSettings
- Dock state and window geometry saved in `closeEvent()` and restored in `__init__` after `_build_ui()`
- Updated `_on_hotspot_navigate` to use `_plot_tabs.setCurrentIndex(0)` and raise the plots dock

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert QSplitter layout to QDockWidgets with View menu** - `fd50d9d` (feat)

**Plan metadata:** (final docs commit follows)

## Files Created/Modified
- `thermal_sim/ui/main_window.py` - QDockWidget layout, _build_plot_tabs(), _build_summary_tabs(), View menu, _reset_layout(), _restore_layout(), closeEvent persistence, __init__ restore call

## Decisions Made
- `QDockWidget.setObjectName` is required for `saveState`/`restoreState` to correctly identify docks (all three docks given unique object names: EditorDock, PlotsDock, SummaryDock)
- `_build_result_tabs()` split into two builders matching the new dock structure — keeps each builder focused and avoids a single oversized method
- `self.result_tabs` removed entirely; `_plot_tabs` and `_summary_tabs` are the two named tab widget attributes
- `_restore_layout()` called after `_load_startup_project()` so default dock positions are first established by `_build_ui()`, then overridden by saved state

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — all 111 existing tests pass without regression. Import verification and grep checks all passed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Dockable layout is complete; users can undock, float, reposition, and resize all three panels
- Layout persistence via QSettings means user arrangements survive application restarts
- 04-03 (final polish plan) can build on this flexible layout foundation

---
*Phase: 04-polish*
*Completed: 2026-03-14*

## Self-Check: PASSED

- thermal_sim/ui/main_window.py — FOUND
- .planning/phases/04-polish/04-02-SUMMARY.md — FOUND
- Commit fd50d9d — FOUND
