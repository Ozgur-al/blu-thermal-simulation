---
phase: 01-foundation
plan: 01
subsystem: ui
tags: [pyside6, matplotlib, refactor, tdd, table-parser, plot-manager]

# Dependency graph
requires: []
provides:
  - TableDataParser: stateless table-to-model and model-to-table conversion
  - PlotManager: matplotlib canvas ownership and all plot rendering methods
  - MainWindow reduced from 939 to 727 lines with all helpers extracted
affects:
  - 01-02 (SimulationController extraction depends on slimmed MainWindow)
  - All future GUI feature plans (undo, threading, menus)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Stateless collaborator classes with static methods for UI helpers
    - Property-based widget dict accessors to eliminate repetition in MainWindow
    - _build_table_tab helper factory to collapse repetitive tab builder methods
    - TDD for table-to-model parsing: RED commit then GREEN implementation

key-files:
  created:
    - thermal_sim/ui/table_data_parser.py
    - thermal_sim/ui/plot_manager.py
    - tests/test_table_data_parser.py
  modified:
    - thermal_sim/ui/main_window.py

key-decisions:
  - "TableDataParser uses all-static methods — no instance needed, maximally testable without MainWindow"
  - "PlotManager takes explicit arguments (layer_name, width_m, height_m) rather than reading MainWindow widgets — clean interface boundary"
  - "MplCanvas moved to plot_manager.py where it belongs (canvas is a plotting concern)"
  - "populate_tables_from_project added to TableDataParser to also cover the model-to-table direction"
  - "_tables_dict/_spinboxes_dict/_boundary_widgets_dict properties added to reduce dict repetition without over-abstracting"
  - "Line count 727 vs plan target 650: plan based its estimate on incorrect 1064-line count; actual original was 939"

patterns-established:
  - "Collaborator pattern: extract stateless helper class with static methods, delegate from MainWindow"
  - "TableDataParser.parse_xxx_table(table) -> model: parse returns model objects, never writes to MainWindow"
  - "PlotManager.plot_xxx(data, ..., width_m, height_m): plot methods are pure matplotlib, no widget reads"

requirements-completed:
  - GUI-01

# Metrics
duration: 13min
completed: 2026-03-14
---

# Phase 1 Plan 1: MainWindow Decomposition (TableDataParser + PlotManager) Summary

**TableDataParser and PlotManager extracted from 939-line MainWindow monolith using TDD; MainWindow reduced to 727 lines with all table and plotting logic delegated to standalone collaborators**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-14T08:29:13Z
- **Completed:** 2026-03-14T08:42:24Z
- **Tasks:** 2 tasks complete
- **Files modified:** 4 files (2 created, 2 modified)

## Accomplishments

- Extracted `TableDataParser` with 12 static methods covering table-to-model parsing, model-to-table population, validation, boundary widget I/O, and row management
- Extracted `PlotManager` owning all three MplCanvas instances and rendering `plot_temperature_map`, `plot_layer_profile`, `plot_probe_history`, `refresh_summary`, `fill_probe_table`
- Moved `MplCanvas` class from main_window.py to plot_manager.py
- Added `populate_tables_from_project` to TableDataParser for inverse model-to-table direction
- Added `_build_table_tab` helper to MainWindow, collapsing 5 repetitive tab builders into single-line calls
- 10 new unit tests pass for TableDataParser round-trips and validate_tables logic

## Task Commits

Each task was committed atomically:

1. **Task 1: RED phase — failing tests** - `4c2216c` (test)
2. **Task 1: TableDataParser GREEN + MainWindow delegation** - `09a439b` (feat)
3. **Task 2: PlotManager + further MainWindow slimming** - `d5f5aeb` (feat)

## Files Created/Modified

- `thermal_sim/ui/table_data_parser.py` - Stateless TableDataParser with all parse/validate/populate methods
- `thermal_sim/ui/plot_manager.py` - PlotManager class + MplCanvas (moved from main_window)
- `tests/test_table_data_parser.py` - 10 unit tests for parse_materials_table, parse_layers_table, validate_tables
- `thermal_sim/ui/main_window.py` - Reduced from 939 to 727 lines; all helpers and plot methods removed

## Decisions Made

- Used all-static methods in TableDataParser so it requires no instance — fully testable in headless pytest with only a QApplication fixture
- PlotManager methods take dimensions as float arguments rather than reading MainWindow spin boxes — enables future independent testing and reuse
- Added `populate_tables_from_project` (model-to-table inverse) to TableDataParser because `_populate_ui_from_project` in MainWindow needed it — cleaner than keeping the row-building loops in MainWindow
- Property accessors `_tables_dict`, `_spinboxes_dict`, `_boundary_widgets_dict` introduced to avoid repeating the same dict literal three times

## Deviations from Plan

### Documented Deviations

**1. [Documentation - Plan estimate incorrect] MainWindow line count target 650 not met; actual 727**
- **Found during:** Task 2 (PlotManager extraction)
- **Issue:** Plan stated original file was 1064 lines; actual was 939 (verified via `git show`). The 650-line target was calculated from the incorrect baseline. After extracting all specified content, the file is 727 lines — a 23% reduction from 939.
- **Root cause:** The tab-builder methods (_build_setup_tab, _build_top_controls, _build_boundaries_tab, etc.) are pure UI layout code that must remain in MainWindow and account for ~350 lines. These were not planned to be extracted in Plan 01 — SimulationController (which includes _run_simulation and related) is deferred to Plan 02.
- **Impact:** All structural extractions specified in the plan were completed. The 727-line count still represents a significant decomposition. The remaining code in MainWindow is correct UI layout that belongs there.

**2. [Rule 2 - Enhancement] Added `populate_tables_from_project` to TableDataParser**
- **Found during:** Task 2 — `_populate_ui_from_project` needed model-to-table conversion
- **Issue:** Plan only specified parse (table-to-model) methods; the reverse direction (model-to-table) was also needed to simplify MainWindow
- **Fix:** Added `populate_tables_from_project(project, tables_dict)` static method to TableDataParser
- **Files modified:** thermal_sim/ui/table_data_parser.py
- **Committed in:** d5f5aeb (Task 2 commit)

**3. [Rule 2 - Enhancement] Added `_build_table_tab` helper to MainWindow**
- **Found during:** Task 2 — 5 tab builder methods were identical except for headers and table attribute
- **Issue:** Repetitive pattern was adding ~50 lines of near-identical code
- **Fix:** Added `_build_table_tab(headers, extra_buttons)` helper method, collapsed 5 builders into 1-3 line delegations
- **Files modified:** thermal_sim/ui/main_window.py
- **Committed in:** d5f5aeb (Task 2 commit)

---

**Total deviations:** 3 (1 plan-estimate issue, 2 beneficial enhancements)
**Impact on plan:** The plan's line count target missed due to incorrect baseline estimate. All specified code was extracted. Enhancements #2 and #3 reduced MainWindow further than the strict plan specified.

## Issues Encountered

None — all extractions worked cleanly on the first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TableDataParser and PlotManager collaborators are in place — MainWindow is now safe to further decompose
- Plan 02 (SimulationController) can proceed: `_run_simulation`, `_on_sim_finished`, `_sim_thread` management are the next logical extraction
- All 22 tests pass (10 new + 12 existing)
- No circular imports

---
*Phase: 01-foundation*
*Completed: 2026-03-14*
