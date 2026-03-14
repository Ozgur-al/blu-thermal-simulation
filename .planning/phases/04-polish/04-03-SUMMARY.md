---
phase: 04-polish
plan: 03
subsystem: ui
tags: [inline-validation, cellChanged, run-button, status-bar, QBrush, QColor]

# Dependency graph
requires:
  - phase: 04-polish
    provides: QDockWidget layout and View menu (04-02)
  - phase: 04-polish
    provides: qt-material dark_amber theme (04-01)
provides:
  - Per-cell inline validation feedback on all numeric table fields (dark red bg + tooltip)
  - _validation_errors dict tracking invalid cells in MainWindow
  - Run button disabled when any validation errors exist
  - Status bar shows error count when errors exist
  - Project load/new clears all validation state and re-validates
  - Row removal triggers re-validation of entire table
affects: [04-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline cell validation: cellChanged -> _validate_cell -> setBackground(QBrush(QColor(#8B0000))) + setToolTip"
    - "Validation state: dict[(id(table), row, col), error_str] drives run-button enable/disable"
    - "Safe population: blockSignals(True) during populate, then _validation_errors.clear() + _revalidate_table()"

key-files:
  created: []
  modified:
    - thermal_sim/ui/table_data_parser.py
    - thermal_sim/ui/main_window.py

key-decisions:
  - "validate_cell() skips non-numeric columns by exact lowercased header name to avoid false positives on Name/Material/Layer/Shape/Type/LED footprint columns"
  - "cellChanged connects in _build_editor_tabs() after all five tables are constructed — single clean connection point"
  - "_remove_table_row() wrapper replaces direct TableDataParser.remove_selected_row() calls so row removal always triggers _revalidate_table()"
  - "_on_run_ended() uses _update_validation_status() instead of setEnabled(True) — prevents run button re-enabling when errors still exist after sim completes"

patterns-established:
  - "Per-cell error tracking pattern: (id(table), row, col) tuple key prevents cross-table key collision without needing table references in dict"

requirements-completed: [PLSH-03]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 4 Plan 03: Inline Cell Validation Summary

**Per-cell validation with dark red background and tooltip on cell exit; run button disabled and status bar shows error count when any validation errors exist**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T14:09:51Z
- **Completed:** 2026-03-14T14:12:17Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `validate_cell()` static method to `TableDataParser` — returns descriptive error string for invalid cells, empty string for valid; enforces positive/non-negative domain rules and emissivity [0,1] range; skips non-numeric columns by header name
- Added `_validation_errors: dict[tuple[int,int,int], str]` to `MainWindow.__init__` to track all invalid cells across all tables
- Connected `cellChanged` on all 5 editor tables (materials, layers, sources, led_arrays, probes) in `_build_editor_tabs()` using `t=table` default argument for correct closure capture
- `_validate_cell()` applies dark red `#8B0000` background + light pink `#ffcccc` foreground + tooltip message on error; clears all styling on valid
- `_update_validation_status()` calls `self._run_action.setEnabled(n == 0 and not is_running)` and sets status bar to `"N validation error(s)"` or `"Ready"`
- `_revalidate_table()` clears stale error entries for the table and re-validates all cells (signals blocked during revalidation loop)
- `_remove_table_row()` wrapper calls `remove_selected_row` then `_revalidate_table` — all Remove buttons updated to use this
- `_populate_ui_from_project()`: clears `_validation_errors` and calls `_revalidate_table` on all tables after unblocking signals
- `_new_project()` (manual reset branch): clears `_validation_errors` and calls `_update_validation_status`
- `_on_run_ended()`: replaced `setEnabled(True)` with `_update_validation_status()` so run stays disabled after sim if errors remain
- Undo/redo naturally triggers re-validation via `cellChanged` — no extra wiring needed since `_undoing` flag only guards undo command push, not validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add validate_cell() static method to TableDataParser** - `1f8a7f0` (feat)
2. **Task 2: Wire inline validation into MainWindow** - `261033a` (feat)

**Plan metadata:** (final docs commit follows)

## Files Created/Modified
- `thermal_sim/ui/table_data_parser.py` — `validate_cell()` static method with domain rules for all 5 table types
- `thermal_sim/ui/main_window.py` — `QBrush`/`QColor` imports, `_validation_errors` dict, `_validate_cell()`, `_update_validation_status()`, `_revalidate_table()`, `_remove_table_row()`, `cellChanged` connections, project load/new revalidation, `_on_run_ended` update

## Decisions Made
- `validate_cell()` uses exact lowercased header matching — avoids false positives and is consistent with the actual headers set in `_build_*_tab()` methods
- `_remove_table_row()` wrapper added rather than patching `TableDataParser.remove_selected_row()` — keeps the static helper stateless and pure
- `_on_run_ended()` delegates to `_update_validation_status()` rather than calling `setEnabled(True)` directly — single source of truth for run button state

## Deviations from Plan

### Auto-fixed Issues

None — the plan matched the actual column headers after careful inspection. The plan's example column names (e.g., "Density [kg/m3]") used ASCII approximations; the actual table headers use Unicode characters (e.g., "Density [kg/m³]"). The implementation correctly uses Unicode strings to match the actual headers.

## Issues Encountered

None — all 111 existing tests pass without regression.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All three Phase 4 polish plans (01: dark theme, 02: dockable layout, 03: inline validation) are complete
- PLSH-01, PLSH-02, and PLSH-03 requirements satisfied
- Phase 4 is ready for final verification

---
*Phase: 04-polish*
*Completed: 2026-03-14*

## Self-Check: PASSED

- thermal_sim/ui/table_data_parser.py — FOUND
- thermal_sim/ui/main_window.py — FOUND
- .planning/phases/04-polish/04-03-SUMMARY.md — FOUND
- Commit 1f8a7f0 — FOUND
- Commit 261033a — FOUND
