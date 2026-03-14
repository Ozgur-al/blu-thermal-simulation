---
phase: 02-results
plan: "03"
subsystem: gui-comparison
tags: [gui, snapshot, comparison, pdf-export, probe-overlay, temperature-maps]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [ComparisonWidget, snapshot-management, pdf-export-button, comparison-tab]
  affects: [thermal_sim/ui/main_window.py]
tech_stack:
  added: []
  patterns:
    - "ComparisonWidget with QListWidget multi-selection and tab10 colormap per snapshot"
    - "_build_snapshot() copies all numpy arrays to prevent mutation across runs"
    - "FIFO eviction: _snapshots.pop(0) when 5th snapshot is saved"
    - "Shared vmin/vmax colorbar across all selected snapshot maps via im.set_clim()"
key_files:
  created:
    - thermal_sim/ui/comparison_tab.py
  modified:
    - thermal_sim/ui/main_window.py
decisions:
  - "ComparisonWidget imports MplCanvas from plot_manager with defensive fallback for forward compatibility"
  - "probe_values for transient snapshots stores full time-series arrays (not just final scalar)"
  - "Steady-state probes in comparison rendered as horizontal axhline rather than skipped — still useful for visual comparison"
  - "axes.ravel() + np.array() used for uniform iteration regardless of subplot grid shape"
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  completed_date: "2026-03-14"
---

# Phase 2 Plan 03: Snapshot Comparison and PDF Export Summary

**One-liner:** ComparisonWidget with metric table, probe overlay, and side-by-side maps; snapshot FIFO queue with named saves; PDF export button generating multi-page reportlab report.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create ComparisonWidget with snapshot selection, metric table, probe overlay, and side-by-side maps | 5ddf845 | thermal_sim/ui/comparison_tab.py |
| 2 | Wire snapshot save, PDF export, and Comparison tab into MainWindow | ed0e285 | thermal_sim/ui/main_window.py |

## What Was Built

**ComparisonWidget** (`thermal_sim/ui/comparison_tab.py`):
- `QListWidget` in multi-selection mode showing snapshot names; "Compare" button triggers rendering
- `QComboBox` for layer selection populated from first selected snapshot's layer_names
- Metric comparison `QTableWidget`: bold layer separator rows, four metric rows per layer (T_max/avg/min/DeltaT), one column per snapshot, final delta column with `+/-.2f` format
- Probe Overlay tab: single `MplCanvas` with `tab10` colormap cycling per snapshot, distinct line styles per probe; handles both transient (time series) and steady-state (horizontal lines)
- Temperature Maps tab: single `MplCanvas` with dynamic 1x2/2x2 subplot grid, `plot_temperature_map_annotated()` per snapshot, shared vmin/vmax via `im.set_clim()`
- Public API: `set_snapshots(snapshots)` and `_on_compare_clicked()`

**MainWindow integration** (`thermal_sim/ui/main_window.py`):
- New imports: `datetime`, `QInputDialog`, `generate_pdf_report`, `ResultSnapshot`, `ComparisonWidget`
- New state: `self._snapshots: list[ResultSnapshot] = []`
- Two new buttons in control panel (row 2): "Save Snapshot" and "Export PDF" — both disabled until simulation result exists
- Comparison tab added to `self.result_tabs` via `ComparisonWidget`
- `_build_snapshot(name)`: copies all numpy arrays, extracts layer stats and hotspots, stores full probe time-series for transient
- `_save_snapshot()`: QInputDialog for name, FIFO eviction at 4 snapshots, calls `set_snapshots()`
- `_export_pdf()`: QFileDialog for path, calls `generate_pdf_report()`, shows status bar message
- `_on_sim_finished()`: enables both buttons after result is processed

## Verification

- `py -m pytest -q tests/ -x` — 48 tests pass, no regression
- `from thermal_sim.ui.comparison_tab import ComparisonWidget` — import OK
- `from thermal_sim.ui.main_window import MainWindow` — import OK

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- thermal_sim/ui/comparison_tab.py — FOUND
- thermal_sim/ui/main_window.py — FOUND (modified)
- Commits 5ddf845, ed0e285 — both present
