---
phase: 09-3d-gui-and-eled-zone-preset
plan: 01
subsystem: ui
tags: [gui, z-refinement, layers-tab, status-bar, temperature-map]
requirements: [GUI3D-01, GUI3D-02, GUI3D-03]

dependency_graph:
  requires: [Phase 07 NodeLayout, Phase 08 Layer.nz / SteadyStateResult.nz_per_layer / z_offsets]
  provides: [nz spinbox in Layers tab, z-sublayer combo, node count status bar, 300k warning]
  affects: [thermal_sim/ui/main_window.py]

tech_stack:
  added: []
  patterns:
    - QSpinBox cell widget in QTableWidget column (not a table item — read via cellWidget())
    - addItem(..., userData=flat_z_index) for combo box with metadata
    - blockSignals on combo during repopulation to avoid spurious _refresh_map_and_profile calls

key_files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py

decisions:
  - nz column uses QSpinBox as cell widget (column 4) rather than a table item because spinboxes
    are not capturable by the undo system and need direct widget access; _build_project_from_ui
    reads cellWidget(row, 4).value() after parse_layers_table fills the other four columns
  - _refresh_layer_choices receives optional result parameter (None = no result yet = plain names);
    backward compat preserved by checking hasattr(result, 'nz_per_layer')
  - _plot_map uses currentData() as flat z-index (userData set during _refresh_layer_choices);
    falls back to layer_names.index() when userData is None (old code path)
  - 300k warning uses QMessageBox.warning with Ok/Cancel buttons; Cancel aborts solve without error

metrics:
  duration: ~10 min
  completed_date: "2026-03-15"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 9 Plan 01: z-Refinement GUI Controls Summary

**One-liner:** nz QSpinBox column in Layers tab + flat z-sublayer combo populated from result.nz_per_layer/z_offsets + live node count label with 300k warning dialog.

## What Was Built

### Task 1: nz spinbox column and node count status bar

- `_build_layers_tab()` now uses 5 columns: added `"nz"` header with tooltip "Number of z-sublayers through thickness (z-refinement)".
- Custom `_add_layer_row()` method replaces the generic add handler for the layers table — inserts a row and immediately calls `_set_layer_nz_spinbox(row, nz=1)` to install a fresh QSpinBox.
- `_set_layer_nz_spinbox(row, nz)`: creates a QSpinBox (range 1-50), connects `valueChanged` to `_update_node_count_label`, and calls `setCellWidget(row, 4, spin)`.
- `_populate_ui_from_project()`: loops over `project.layers` and calls `_set_layer_nz_spinbox(row, layer.nz)` after `TableDataParser.populate_tables_from_project`; calls `_update_node_count_label()` at end.
- `_build_project_from_ui()`: after `parse_layers_table`, loops over layers and reads `cellWidget(row, 4).value()` to set `layer.nz`.
- `_node_count_label` added to status bar (after `_run_info_label`); `nx_spin.valueChanged` and `ny_spin.valueChanged` connected to `_update_node_count_label` in `_build_ui()`.
- `_update_node_count_label()`: sums nz spinboxes * nx * ny; shows red text with warning symbol when > 300k.
- `_remove_table_row()`: calls `_update_node_count_label()` when `table is self.layers_table`.
- `_run_simulation()`: computes node_count from project.layers before starting; shows `QMessageBox.warning` with Ok/Cancel if > 300k — user can abort.

### Task 2: Flat z-sublayer combo and updated _plot_map

- `_refresh_layer_choices(project, result=None)`: signature extended with optional `result`.
  - With `result=None` or all nz=1: `addItem(layer.name, userData=layer_idx)` — plain names, backward compatible.
  - With `result.nz_per_layer` containing any nz>1: iterates sublayers, adds `"LayerName (z=N/M)"` with `userData=z_offset+z` for each.
  - Restores previous selection by text; falls back to last item.
- `_on_sim_finished()`: calls `_refresh_layer_choices(project, result=result)` after result is available, before plotting.
- `_plot_map()`: uses `currentData()` as flat z-index; strips `" (z=N/M)"` suffix to get physical layer name for probe/hotspot filtering; falls back to `layer_names.index()` when userData is None.
- `_on_hotspot_navigate()`: searches combo entries for first item whose base name (before `" (z="`) matches the hotspot layer name — handles multi-nz entries.

## Verification

202 tests pass (`py -m pytest -q tests/`).

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- `thermal_sim/ui/main_window.py`: FOUND
- Commit 993dc88: FOUND
- 202 tests: PASS
