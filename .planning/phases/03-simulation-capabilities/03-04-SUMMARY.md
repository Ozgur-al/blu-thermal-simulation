---
phase: 03-simulation-capabilities
plan: 04
subsystem: ui
tags: [PySide6, parametric-sweep, power-profile, matplotlib, csv-export]

requires:
  - phase: 03-simulation-capabilities
    provides: SweepEngine, SweepConfig, SweepResult, PowerBreakpoint from plans 03-01 and 03-02

provides:
  - SweepDialog QDialog — parameter category/target dropdowns, comma or min:step:max value entry, mode selector
  - _SweepWorker QObject — runs SweepEngine off main thread with Run N of M progress
  - SimulationController.start_sweep() and sweep_finished Signal
  - SweepResultsWidget — comparison table (param vs T_max/T_avg per layer) + plot with dropdowns + Export CSV/PNG
  - export_sweep_results() function in csv_export.py
  - MainWindow "Parametric Sweep..." menu action (Run menu, Ctrl+Shift+P)
  - MainWindow Sweep Results tab that auto-activates after sweep
  - Heat Sources tab: Time-varying checkbox + breakpoint QTableWidget (Time/Power) + Add/Remove + live MplCanvas preview
  - Power profiles persisted in _source_profiles and applied in _build_project_from_ui

affects: [04-polish, any future GUI work touching heat sources or results tabs]

tech-stack:
  added: []
  patterns:
    - Same QThread worker-object pattern as SimulationController._SimWorker extended to _SweepWorker
    - Per-row profile storage in dict[row_index, list[PowerBreakpoint]] keyed by sources_table row
    - SweepResultsWidget lazy-imports csv_export inside _export_csv to avoid circular at module load

key-files:
  created:
    - thermal_sim/ui/sweep_dialog.py
    - thermal_sim/ui/sweep_results_widget.py
  modified:
    - thermal_sim/ui/simulation_controller.py
    - thermal_sim/ui/main_window.py
    - thermal_sim/io/csv_export.py

key-decisions:
  - "SweepDialog validates minimum 2 values and rejects empty target (no layer/material/source in project)"
  - "Power profile stored in dict[int, list] keyed by sources_table row index — simple, no extra dataclass"
  - "_source_profiles initialized in __init__ (not _build_sources_tab) so it survives tab rebuild"
  - "_build_project_from_ui patches power_profile onto heat_sources after TableDataParser builds the base project"
  - "SweepResultsWidget uses lazy import of export_sweep_results inside _export_csv slot"

requirements-completed: [SIM-01, SIM-02]

duration: 6min
completed: 2026-03-14
---

# Phase 3 Plan 4: Sweep GUI and Power Profile UI Summary

**Parametric sweep GUI wired end-to-end: SweepDialog -> _SweepWorker -> SweepResultsWidget with table/plot/export; power profile breakpoint editor with live preview in Heat Sources tab**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-14T14:01:30Z
- **Completed:** 2026-03-14T14:07:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- SweepDialog (QDialog) with category/target dropdowns populated from the live project, comma or min:step:max value entry, mode selector
- _SweepWorker runs SweepEngine.run() off the main thread emitting "Run N of M" progress; SimulationController.start_sweep() + sweep_finished Signal added following existing QThread pattern
- SweepResultsWidget shows comparison table + parameter-vs-metric plot (layer/metric dropdowns) + Export CSV/PNG buttons; wired to Run > Parametric Sweep... menu action and Sweep Results tab that auto-activates
- export_sweep_results() added to csv_export.py producing columns: parameter_value, Layer_t_max_c, Layer_t_avg_c
- Heat Sources tab rebuilt with time-varying power profile sub-panel: QCheckBox, breakpoint QTableWidget, Add/Remove buttons, live MplCanvas preview that redraws on every cell change
- _build_project_from_ui patches power_profile onto HeatSource objects from _source_profiles dict; _populate_ui_from_project restores profiles when loading a JSON project

## Task Commits

1. **Task 1: SweepDialog and _SweepWorker** - `5fd8f6d` (feat)
2. **Task 2: SweepResultsWidget, power profile UI, and MainWindow wiring** - `283edd5` (feat)

## Files Created/Modified

- `thermal_sim/ui/sweep_dialog.py` — SweepDialog QDialog with parameter category/target/values/mode
- `thermal_sim/ui/sweep_results_widget.py` — SweepResultsWidget with table, plot, and export
- `thermal_sim/ui/simulation_controller.py` — _SweepWorker, start_sweep(), sweep_finished signal
- `thermal_sim/ui/main_window.py` — Sweep menu action, Sweep Results tab, power profile sub-panel in Heat Sources tab
- `thermal_sim/io/csv_export.py` — export_sweep_results() function

## Decisions Made

- SweepDialog validates minimum 2 values and rejects empty target dropdown (no layers/materials/sources defined)
- Power profile state stored in `dict[int, list[PowerBreakpoint]]` keyed by sources_table row index — avoids adding any extra dataclass or modifying TableDataParser
- `_source_profiles` initialized in `__init__` (not `_build_sources_tab`) so the state survives tab construction and persists across the session
- `_build_project_from_ui` patches power_profile onto heat_sources *after* TableDataParser builds the base project, so TableDataParser needs no changes
- SweepResultsWidget uses lazy import of `export_sweep_results` inside the export slot to avoid potential circular import at module level

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- SIM-01 and SIM-02 requirements satisfied — sweep GUI and results display complete
- Power profile breakpoint UI satisfies SIM-03 GUI surface requirement
- All 111 pre-existing tests pass unchanged
- Phase 3 GUI features ready for Phase 4 polish / packaging

---
*Phase: 03-simulation-capabilities*
*Completed: 2026-03-14*
