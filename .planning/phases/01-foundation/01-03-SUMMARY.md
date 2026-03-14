---
phase: 01-foundation
plan: 03
subsystem: ui
tags: [PySide6, QUndoStack, QSettings, keyboard-shortcuts, dirty-tracking]

# Dependency graph
requires:
  - phase: 01-02
    provides: SimulationController with run_started/run_ended signals and three-zone status bar

provides:
  - QUndoStack with 100-command limit wired to all five editable tables
  - Cell-level undo/redo via _CellEditCommand(QUndoCommand)
  - Window title and status bar asterisk for unsaved changes
  - Menu bar: File (New/Open/Save/Save As), Edit (Undo/Redo), Run (Run F5, Cancel Esc, Set Output Dir, Export CSV)
  - Always-visible toolbar with mode combo dropdown and Run/Cancel actions
  - QSettings-backed output directory persistence across sessions
  - closeEvent unsaved-changes prompt (Save/Discard/Cancel)
  - _maybe_save_changes() guard on Open, New, and close

affects:
  - 01-04 (human-verify checkpoint will test all undo/redo and menu features)
  - Any future plan modifying main_window.py

# Tech tracking
tech-stack:
  added:
    - QUndoStack, QUndoCommand (PySide6.QtGui) — undo/redo command pattern
    - QSettings (PySide6.QtCore) — persistent output directory storage
    - QAction (PySide6.QtGui) — menu and toolbar actions
  patterns:
    - Command pattern via _CellEditCommand(QUndoCommand) for table cell edits
    - Signal-blocking during programmatic table population (blockSignals + undo_stack.clear())
    - Pre-edit value capture via currentCellChanged before cellChanged fires
    - Undo macro (beginMacro/endMacro) for compound row additions

key-files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py

key-decisions:
  - "_CellEditCommand captures pre-edit value via currentCellChanged (before edit) rather than cellPressed — more reliable across all input methods"
  - "Run/Cancel are QActions in both menu and toolbar — single source of enabled state, no duplication"
  - "Toolbar mode_combo moved out of _build_top_controls() into _build_toolbar(); top controls panel simplified to Top-N, Layer combo, Structure Preview only"
  - "_save_project() (Ctrl+S) saves to current path silently; _save_project_as_dialog() always shows dialog — VS Code behavior"
  - "_maybe_save_changes() is the single guard called from closeEvent, _new_project(), and _load_project_dialog()"

patterns-established:
  - "Table undo pattern: _wire_table_undo() connects currentCellChanged + cellChanged; _undoing guard prevents recursion"
  - "Signal-block pattern: blockSignals(True) on all tables, populate, blockSignals(False), then undo_stack.clear() + setClean()"

requirements-completed: [GUI-02, GUI-05, GUI-06, GUI-07]

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 1 Plan 3: Undo/Redo, Menus, Shortcuts, and Dirty Tracking Summary

**QUndoStack with cell-level undo/redo, full menu bar (File/Edit/Run), F5/Ctrl+Z/Ctrl+S shortcuts, QSettings output dir, and close-window unsaved-changes prompt**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-14T08:54:31Z
- **Completed:** 2026-03-14T08:58:24Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- QUndoStack with 100-command limit wired to all five editable tables (materials, layers, sources, led_arrays, probes) via _CellEditCommand pattern
- Full menu bar: File (New/Open/Save/Save As), Edit (Undo/Redo via stack built-ins), Run (Run Simulation F5, Cancel Esc, Set Output Directory, Export CSV)
- Always-visible toolbar with mode dropdown, Run, and Cancel actions
- Window title and status bar path label show asterisk prefix when project has unsaved changes; cleared on save or undo-to-clean
- QSettings-backed output directory persists across sessions; _export_csv_dialog() exports all result CSVs to that dir in one click
- closeEvent, _new_project(), and _load_project_dialog() all go through _maybe_save_changes() (Save/Discard/Cancel dialog)
- keyPressEvent() intercepts Escape as fallback cancel for focused-widget scenarios

## Task Commits

Both tasks modify the same file; implemented atomically in a single commit:

1. **Task 1: QUndoStack with dirty tracking and window title** - `967e511` (feat)
2. **Task 2: Menu bar, toolbar, shortcuts, output dir, unsaved-changes prompt** - included in `967e511` (feat)

## Files Created/Modified

- `thermal_sim/ui/main_window.py` - Added _CellEditCommand, _build_menus(), _build_toolbar(), _wire_table_undo(), _update_title(), _maybe_save_changes(), _save_project(), _save_project_as_dialog(), _new_project(), _set_output_directory(), _export_csv_dialog(), closeEvent(), keyPressEvent(); simplified _build_top_controls()

## Decisions Made

- _CellEditCommand uses currentCellChanged to capture pre-edit text (before cellChanged fires) — more reliable than cellPressed which misses keyboard navigation
- Run/Cancel are QActions shared between menu and toolbar; single enabled-state source eliminates duplication with the old _run_btn QPushButton approach
- toolbar mode_combo taken from _build_top_controls() so it appears in the toolbar first; _build_top_controls() simplified to view-only controls (Top-N, Layer combo, Structure Preview button)
- _save_project() (Ctrl+S) saves silently to current path; _save_project_as_dialog() always shows dialog — matches VS Code / Word behavior expected by engineers
- _maybe_save_changes() is a single reusable guard; called from closeEvent, _new_project(), and _load_project_dialog()

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MainWindow now has complete keyboard-driven workflow: F5 runs, Escape cancels, Ctrl+Z/Y undo/redo, Ctrl+S saves
- Ready for Plan 04 (human-verify checkpoint) to test undo/redo, dirty tracking, and menus interactively
- No blockers

## Self-Check: PASSED

- `thermal_sim/ui/main_window.py` — FOUND
- `.planning/phases/01-foundation/01-03-SUMMARY.md` — FOUND
- commit `967e511` — FOUND in git log

---
*Phase: 01-foundation*
*Completed: 2026-03-14*
