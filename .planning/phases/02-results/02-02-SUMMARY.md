---
phase: 02-results
plan: "02"
subsystem: gui-results
tags: [gui, results, tables, hotspot, navigation, annotated-map]
dependency_graph:
  requires: [02-01]
  provides: [ResultsSummaryWidget, annotated-map-rendering, hotspot-navigation]
  affects: [thermal_sim/ui/main_window.py]
tech_stack:
  added: []
  patterns:
    - "ResultsSummaryWidget with Signal(int, str, float, float) for cross-tab navigation"
    - "plot_temperature_map_annotated() called from MainWindow._plot_map() for annotated rendering"
    - "Auto-activation via result_tabs.setCurrentWidget() after simulation completes"
key_files:
  created:
    - thermal_sim/ui/results_tab.py
  modified:
    - thermal_sim/ui/main_window.py
decisions:
  - "result_tabs stored as self.result_tabs (not local) so _on_hotspot_navigate can switch tabs"
  - "Selected hotspot rank reset to None after re-render so subsequent manual layer changes have no highlight"
  - "Old Summary tab retained for backward compatibility; Results tab is additive, not a replacement"
  - "_plot_map() now always does ax.clear() + fresh colorbar — simpler than in-place update when annotations change"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  completed_date: "2026-03-14"
---

# Phase 2 Plan 02: Results Tab and Annotated Maps Summary

**One-liner:** ResultsSummaryWidget with three structured tables and hotspot click-to-navigate, plus annotated temperature map rendering using per-layer crosshairs and probe markers.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create ResultsSummaryWidget with structured tables and click-to-navigate signal | 3308615 | thermal_sim/ui/results_tab.py |
| 2 | Integrate Results tab and annotated maps into MainWindow | 9b3aab1 | thermal_sim/ui/main_window.py |

## What Was Built

**ResultsSummaryWidget** (`thermal_sim/ui/results_tab.py`):
- Three `QGroupBox` sections: Layer Statistics, Top Hotspots, Probe Readings
- Layer Statistics table: Layer, T_max, T_avg, T_min, DeltaT (2 dp)
- Top Hotspots table: Rank, Layer, X [mm], Y [mm], Temperature — up to `max_hotspots=10`
- Probe Readings table: Probe, Layer, X [mm], Y [mm], Temperature
- `hotspot_clicked = Signal(int, str, float, float)` emitted on row click
- `update_data(layer_stats_data, hotspots, probe_values, probes)` populates all three tables
- All tables read-only, alternating row colors, stretched columns

**MainWindow integration** (`thermal_sim/ui/main_window.py`):
- Imports: `ResultsSummaryWidget`, `layer_stats`, `top_n_hottest_cells_for_layer`, `plot_temperature_map_annotated`
- New instance attributes: `self.result_tabs`, `self._results_widget`, `self._selected_hotspot_rank`, `self._last_final_map`, `self._last_layer_names`
- `_build_result_tabs()` adds Results tab alongside existing Summary tab; connects `hotspot_clicked`
- `_plot_map()` replaced with annotated rendering: computes per-layer top-3 hotspots, gathers layer probes, calls `plot_temperature_map_annotated()`, manages colorbar
- `_on_hotspot_navigate(rank, layer_name, x_m, y_m)`: switches layer combo, sets highlight rank, switches to Temperature Map tab (index 0), re-renders, then clears rank
- `_on_sim_finished()`: stores `_last_final_map`/`_last_layer_names`, calls `layer_stats()`, populates Results widget, auto-activates it
- `_refresh_map_and_profile()`: clears `_selected_hotspot_rank` on manual layer change

## Verification

- `py -m pytest -q tests/ -x` — 48 tests pass, no regression
- `from thermal_sim.ui.results_tab import ResultsSummaryWidget` — import OK
- `from thermal_sim.ui.main_window import MainWindow` — import OK

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- thermal_sim/ui/results_tab.py — FOUND
- thermal_sim/ui/main_window.py — FOUND (modified)
- Commits 3308615, 9b3aab1 — both present
