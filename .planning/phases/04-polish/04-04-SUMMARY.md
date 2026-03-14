---
phase: 04-polish
plan: 04
subsystem: ui
tags: [human-verification, uat, polish]

# Dependency graph
requires:
  - phase: 04-polish/plan-01
    provides: Dark amber theme, matplotlib dark style, monospace fonts
  - phase: 04-polish/plan-02
    provides: QDockWidget layout, View menu, layout persistence
  - phase: 04-polish/plan-03
    provides: Inline cell validation, run-button disable, error status
provides:
  - Human verification that all PLSH requirements work correctly in live GUI
---

## Self-Check: PASSED

## What was built
Human verification checkpoint for all Phase 4 Polish requirements. The tester launched the GUI and confirmed:

- **PLSH-01 (Theme):** Dark amber Material Design theme applied consistently, matplotlib dark plots with inferno colormap, monospace fonts on tables/status bar — approved.
- **PLSH-02 (Dockable layout):** Three QDockWidgets (Editor, Result Plots, Results Summary) undock/resize/persist correctly, View menu with toggles and Reset Layout works — approved.
- **PLSH-03 (Inline validation):** Invalid cells show dark red background with tooltips, run button disabled on errors, status bar shows error count, errors clear on fix/load/delete — approved.

## Additional feedback addressed
Three additional issues were identified and fixed during verification:
1. **Plot scaling:** Temperature map changed from `aspect="auto"` to `aspect="equal"` so rectangular models display with correct proportions
2. **Display units:** All dimensional UI fields changed from meters to millimeters with conversion at UI boundary (internal model stays SI)
3. **Tooltips:** Added tooltips to all table column headers, spinboxes, boundary controls, and buttons
4. **Crash fix:** QResizeEvent C++ object deletion fixed by copying event data before deferred timer fires

## key-files
### created
(none)

### modified
- thermal_sim/ui/main_window.py — mm headers, tooltips, spinbox ranges
- thermal_sim/ui/table_data_parser.py — mm conversion in parse/populate, updated validation rules
- thermal_sim/ui/plot_manager.py — mm axis labels/extents, aspect="equal", resize crash fix
- thermal_sim/visualization/plotting.py — mm axis labels/extents in standalone plots
- thermal_sim/ui/structure_preview.py — mm axis labels in plan view
- tests/test_table_data_parser.py — updated test headers/values for mm

## Deviations
- Three additional fixes (mm units, tooltips, plot scaling) went beyond the original checkpoint scope but were requested by the human tester during verification
- QResizeEvent crash fix was reported during testing and fixed immediately
