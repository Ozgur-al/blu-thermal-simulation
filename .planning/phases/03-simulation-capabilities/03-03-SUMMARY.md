---
phase: 03-simulation-capabilities
plan: 03
subsystem: material-library
tags: [materials, json, import-export, gui, tdd]
dependency_graph:
  requires: []
  provides: [MAT-01, MAT-02]
  affects: [thermal_sim/ui/main_window.py, thermal_sim/core/material_library.py]
tech_stack:
  added: [importlib.resources, dataclasses.replace]
  patterns: [resource-bundling, conflict-rename, read-only-table-rows]
key_files:
  created:
    - thermal_sim/resources/__init__.py
    - thermal_sim/resources/materials_builtin.json
    - tests/test_material_library.py
  modified:
    - thermal_sim/core/material_library.py
    - thermal_sim/ui/main_window.py
    - thermal_sim/ui/table_data_parser.py
decisions:
  - import_materials returns a new merged dict and does not mutate either input
  - Built-in rows use Qt.ItemFlag.ItemIsEditable cleared — simpler than clone-on-edit which would conflict with undo system
  - load_builtin_library uses importlib.resources.files for PyInstaller bundle compatibility
  - Type column placed last (col 6) so parse_materials_table cols 0-5 need no change
metrics:
  duration: 6 min
  completed: "2026-03-14"
  tasks_completed: 2
  files_changed: 6
---

# Phase 3 Plan 3: Material Library Summary

Built-in material JSON resource, import/export library functions, and GUI integration with Type column distinguishing built-in vs user materials.

## What Was Built

**material_library.py extensions:**
- `load_builtin_library()` — reads `thermal_sim/resources/materials_builtin.json` via `importlib.resources.files()` for bundle-safe loading
- `load_materials_json(path)` — loads arbitrary material JSON file
- `export_materials(materials, path)` — writes materials dict to JSON in round-trip-safe format
- `import_materials(existing, incoming, builtin_names)` — merges without mutation; conflict-renames to `Name_imported`, `Name_imported_2`, etc.
- `default_materials()` preserved verbatim for backward compatibility

**materials_builtin.json:** 15 materials (original 10 + Solder SnAgCu, BT Substrate, Polyimide, Silicone Rubber, Air Gap)

**Materials tab GUI:**
- Added "Type" column (last, col 6) showing "Built-in" or "User"
- Load Presets uses `load_builtin_library()` and sets `Qt.ItemFlag.ItemIsEditable` off on all built-in cells
- Import button: file dialog → `load_materials_json` → `import_materials` → add rows → notify user of renames
- Export button: selected rows (or all User rows) → `export_materials` to JSON file
- `populate_tables_from_project()` emits "User" in the Type column when loading saved projects

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Built-in JSON + library functions | 111cfbb | resources/__init__.py, materials_builtin.json, material_library.py, test_material_library.py |
| 2 | Materials tab GUI | 5ac8ea1 | main_window.py, table_data_parser.py |

## Test Results

- 14 new tests in `tests/test_material_library.py` — all pass
- 106 total tests pass
- 1 pre-existing failure in `test_power_profile.py` (out of scope — plan 03-02 transient power scaling)

## Deviations from Plan

None — plan executed exactly as written.

The plan offered a simpler alternative for built-in row protection (non-editable flags vs clone-on-edit). The simpler approach was chosen as the plan recommended it: "Choose this approach if the clone-on-edit is too entangled with the undo system."

## Deferred Items

- `test_power_profile.py::test_square_wave_profile_transient_matches_analytical` — pre-existing failure from plan 03-02. The transient solver is not applying per-step power scaling. Out of scope for this plan.

## Self-Check: PASSED

All required files exist. Both task commits verified in git log.

| Check | Status |
|-------|--------|
| thermal_sim/resources/__init__.py | FOUND |
| thermal_sim/resources/materials_builtin.json | FOUND |
| tests/test_material_library.py | FOUND |
| 03-03-SUMMARY.md | FOUND |
| Commit 111cfbb | FOUND |
| Commit 5ac8ea1 | FOUND |
