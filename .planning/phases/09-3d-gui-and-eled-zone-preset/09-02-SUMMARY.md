---
phase: 09-3d-gui-and-eled-zone-preset
plan: 02
subsystem: ui
tags: [gui, zones, layers-tab, temperature-map, material-zone]
requirements: [GUI3D-04, GUI3D-05]

dependency_graph:
  requires: [Phase 07 MaterialZone dataclass, Phase 07 Layer.zones field, Phase 09-01 nz spinbox column]
  provides: [zone sub-table per layer, zone preview canvas, zone overlay on temperature map, zone PDF export]
  affects: [thermal_sim/ui/main_window.py, thermal_sim/visualization/plotting.py, thermal_sim/models/snapshot.py, thermal_sim/io/pdf_export.py]

tech_stack:
  added: []
  patterns:
    - QGroupBox sub-panel below QTableWidget (same pattern as _profile_panel in Heat Sources tab)
    - QComboBox cell widget in zone table for material selection (not a table item — read via cellWidget())
    - _updating_zones boolean guard prevents recursive cellChanged signal chains during populate
    - matplotlib.patches.Rectangle for zone preview and temperature map overlay
    - getattr(snapshot, "layer_zones", {}) for backward-compat zone lookup in PDF export

key_files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py
    - thermal_sim/visualization/plotting.py
    - thermal_sim/models/snapshot.py
    - thermal_sim/io/pdf_export.py

decisions:
  - _layer_zones dict (layer_row -> list[dict]) mirrors _source_profiles pattern; stores SI metres internally
  - Zone table uses x_start/x_end/y_start/y_end columns in mm (more intuitive than x/y/width/height for engineers)
  - _updating_zones flag (not blockSignals) guards recursive cellChanged — blockSignals would also suppress the combo changes
  - Zone preview uses colored translucent fill (not facecolor=none) to distinguish multiple zones by index color
  - zones= parameter on plot_temperature_map_annotated defaults to None — fully backward-compatible
  - ResultSnapshot.layer_zones dict added to carry zones into PDF export; getattr for older snapshots

metrics:
  duration: ~5 min
  completed_date: "2026-03-16"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 9 Plan 02: Zone Editor and Temperature Map Overlay Summary

**One-liner:** Zone sub-table per layer (add/edit/remove in mm, inline preview canvas) + dashed zone rectangles overlaid on temperature map and PDF export via zones= parameter on plot_temperature_map_annotated.

## What Was Built

### Task 1: Zone sub-table with preview canvas in Layers tab

- `MaterialZone` imported at top of `main_window.py`.
- `_layer_zones: dict[int, list]` added to `__init__` — stores `{"material", "x", "y", "width", "height"}` dicts in SI metres per layer row index (mirrors `_source_profiles` pattern).
- `_updating_zones: bool` guard flag prevents recursive signal chains during zone table population.
- `_build_layers_tab()` now appends a hidden `self._zone_panel` (QGroupBox "Material Zones") below the layers table with:
  - `self._zone_table` (5 columns: Material, X start [mm], X end [mm], Y start [mm], Y end [mm]), max height 150px
  - "+ Add Zone" / "- Remove Zone" buttons
  - `self._zone_preview_canvas` (MplCanvas 3.5x2.5 dpi=80), max height 200px
- `layers_table.itemSelectionChanged` connected to `_on_layer_selected_for_zones()` which shows/hides the panel and calls `_populate_zone_table(row)` + `_refresh_zone_preview(row)`.
- `_make_zone_material_combo()` creates a QComboBox populated from the materials table; connects `currentTextChanged` to `_on_zone_combo_changed()`.
- `_add_zone_row()` appends a default full-panel zone; `_remove_zone_row()` pops by selected row.
- `_read_zone_table_into_store(layer_row)` reads all rows and converts mm back to SI metres.
- `_refresh_zone_preview(layer_row)` draws the layer footprint (gray rectangle) and each zone as a dashed white-edged colored rectangle with material label.
- `_populate_ui_from_project()` populates `_layer_zones` from `layer.zones` and hides the zone panel.
- `_build_project_from_ui()` reads `_layer_zones` and constructs `MaterialZone` objects for `layer.zones`.
- `_add_layer_row()` initializes `_layer_zones[row] = []` for new rows.
- `_remove_table_row()` shifts `_layer_zones` keys down when a layer row is removed.

### Task 2: Zone overlay on temperature map and PDF export

- `plot_temperature_map_annotated()` extended with `zones: list | None = None` parameter.
- Zone overlay: for each zone, draws a `matplotlib.patches.Rectangle` (dashed white, no fill, zorder=6) and a text label at the zone corner (zorder=7).
- `_plot_map()` in main_window: looks up `current_zones` from `self.last_project.layers` by matching the physical layer name (stripped of z-suffix); passes `zones=current_zones` to the annotated plot function.
- `ResultSnapshot` extended with `layer_zones: dict = field(default_factory=dict)` — maps layer name to list of MaterialZone objects.
- `_build_snapshot()` populates `layer_zones` from `project.layers`.
- `_make_temperature_map_page()` in pdf_export uses `getattr(snapshot, "layer_zones", {})` for backward compatibility, then passes zones to the annotated plot call.

## Verification

202 tests pass (`py -m pytest -q tests/`).

## Deviations from Plan

### Auto-added: ResultSnapshot.layer_zones field

**Found during:** Task 2

**Issue:** PDF export calls `plot_temperature_map_annotated()` but snapshot carried no zone data. Plan said to pass zones to PDF export as well.

**Fix:** Added `layer_zones: dict` field to `ResultSnapshot`; populated in `_build_snapshot()`; consumed in `_make_temperature_map_page()` via `getattr` for backward compat. No test impact — new optional field with default.

**Files modified:** `thermal_sim/models/snapshot.py`, `thermal_sim/ui/main_window.py`, `thermal_sim/io/pdf_export.py`

**Rule:** Rule 2 (missing critical functionality — PDF export would silently drop zones without this)

## Self-Check: PASSED

- `thermal_sim/ui/main_window.py`: FOUND
- `thermal_sim/visualization/plotting.py`: FOUND
- `thermal_sim/models/snapshot.py`: FOUND
- `thermal_sim/io/pdf_export.py`: FOUND
- Commit 5af4423 (Task 1): FOUND
- Commit 3e8909b (Task 2): FOUND
- 202 tests: PASS
