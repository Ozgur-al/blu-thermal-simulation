---
phase: 10-edge-layers-and-3d-preview
plan: 03
subsystem: ui
tags: [pyvista, pyvistaqt, edge-layers, 3d-preview, temperature-overlay]

# Dependency graph
requires:
  - phase: 10-01
    provides: EdgeLayer dataclass, Layer.edge_layers field, generate_edge_zones()
  - phase: 10-02
    provides: Assembly3DWidget with update_assembly() and explode slider

provides:
  - Edge layer editor panel in Layers tab (4-edge tabs, Add/Remove/Copy-From)
  - ELED template auto-populates LGP edge_layers (Steel+Air+FR4 LED, Steel+Air non-LED)
  - Temperature overlay in 3D widget via update_temperature() with hot colormap
  - Structure/Results toggle button in 3D widget
  - Edge layer data round-trips through JSON save/load

affects:
  - future-phases

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_layer_edge_layers dict pattern mirrors _layer_zones for per-layer dict storage"
    - "update_temperature uses pv.ImageData with cell_data scalars for temperature mapping"
    - "Toggle button stores _in_results_mode / _last_project / _last_result for bidirectional switching"

key-files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py
    - thermal_sim/ui/assembly_3d.py
    - thermal_sim/models/stack_templates.py
    - tests/test_stack_templates.py

key-decisions:
  - "_layer_edge_layers dict keyed by layer_row -> dict[edge, list[dict]] mirrors _layer_zones pattern"
  - "_updating_edge_layers flag guards recursive cellChanged in edge table (same pattern as _updating_zones)"
  - "eled_template edge_layers: LED edges get 3 layers (Steel+Air Gap+FR4), non-LED edges get 2 (Steel+Air Gap)"
  - "_filter_materials updated to scan layer.edge_layers so ELED edge materials auto-included"
  - "update_temperature uses pv.ImageData for each layer (structured grid approach)"
  - "Toggle button starts disabled; enabled after first solve result available"
  - "3D dock lazy-created on first View menu activation; pyvista ImportError handled gracefully"

requirements-completed:
  - EDGE-03
  - VIS3D-03

# Metrics
duration: 30min
completed: 2026-03-16
---

# Phase 10 Plan 03: Edge Layer GUI, ELED Template, and 3D Temperature Overlay Summary

**Per-edge lateral layer editor with 4-tab panel in Layers tab, ELED LGP auto-populated with Steel+Air+FR4 structure, and temperature colormap overlay on 3D assembly view with show/hide toggle**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-03-16T06:06:21Z
- **Completed:** 2026-03-16T06:33:36Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `_edge_layer_panel` QGroupBox below Material Zones in Layers tab with 4-edge tabs (Bottom/Top/Left/Right), edge layer table (Material + Thickness [mm]), Add/Remove/Copy-From controls
- Updated `eled_template()` to add `edge_layers` to LGP layer — LED edges get Steel+Air Gap+FR4, non-LED edges get Steel+Air Gap, driven by `edge_config` parameter
- Updated `_filter_materials()` to scan `layer.edge_layers` values so ELED edge materials (Steel, Air Gap, FR4) are included in the template materials dict
- Implemented `update_temperature()` on Assembly3DWidget using `pv.ImageData` with "hot" colormap and a shared colorbar for the first layer
- Added Show Results/Show Structure toggle button to Assembly3DWidget with bidirectional switching
- Wired `update_temperature()` call in `_on_sim_finished` when 3D dock is visible
- Added tests: `test_eled_template_edge_layers_populated`, `test_eled_template_edge_layers_round_trip`, `test_eled_template_materials_include_edge_layer_materials`

## Task Commits

1. **Task 1: Edge layer editor panel + ELED auto-populate** - `1f913ff` (feat)
2. **Task 2: Temperature overlay + structure/results toggle** - `0a49adf` (feat)

## Files Created/Modified

- `G:\blu-thermal-simulation\thermal_sim\ui\main_window.py` — Edge layer panel, edge methods, 3D dock wiring, temperature overlay on solve
- `G:\blu-thermal-simulation\thermal_sim\ui\assembly_3d.py` — update_temperature(), toggle button, state tracking
- `G:\blu-thermal-simulation\thermal_sim\models\stack_templates.py` — eled_template with edge_layers, _filter_materials scan
- `G:\blu-thermal-simulation\tests\test_stack_templates.py` — 3 new ELED edge_layers tests

## Decisions Made

- `_layer_edge_layers` dict (layer_row -> dict[edge, list[dict]]) mirrors `_layer_zones` pattern for consistency with existing UI data patterns
- Edge layer table uses `_updating_edge_layers` flag (not blockSignals) to prevent recursive cellChanged — same as `_updating_zones`
- `eled_template` LED edge structure: Steel frame (3mm) + Air Gap (1mm) + FR4 PCB (5mm) on LED edges; Steel frame + Air Gap on non-LED edges
- `_filter_materials` updated to also scan `layer.edge_layers` so the ELED template materials dict automatically includes Steel, Air Gap, and FR4
- `update_temperature` renders each layer as `pv.ImageData` with `clim=(t_min, t_max)` — consistent colormap range across all layers
- Toggle button starts disabled; becomes enabled after first `update_temperature` call
- 3D dock lazy-created with `pyvista` ImportError handled gracefully — app still works without pyvista installed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing regression test failures in test_regression_v1.py**
- **Found during:** Verification run after Plan 10-01
- **Issue:** `examples/steady_uniform_stack.json` was modified by a prior session (WIP), causing shape mismatch with stored baselines. The failure was pre-existing before any Phase 10 changes.
- **Fix:** Confirmed pre-existing via git stash; no fix applied (out-of-scope pre-existing issue)
- **Committed in:** Not applicable — out of scope

**2. [Rule 1 - Bug] test_edge_zone_manual_zone_coexistence used wrong import path**
- **Found during:** Task 1 (running test_edge_layers.py)
- **Issue:** Test imported `solve_steady_state` (non-existent) and `thermal_sim.models.mesh.MeshConfig` (wrong path)
- **Fix:** Changed to `SteadyStateSolver` and `from thermal_sim.models.project import MeshConfig`
- **Files modified:** tests/test_edge_layers.py
- **Verification:** All 28 edge layer tests pass
- **Committed in:** 34e2249

---

**Total deviations:** 1 auto-fixed (Rule 1 bug in test imports), 1 pre-existing out-of-scope regression
**Impact on plan:** The test fix was necessary for correctness. No scope creep.

## Issues Encountered

- `pyvistaqt.QtInteractor` import requires QApplication to be running; handled in conftest.py via `pv.OFF_SCREEN = True` before any import
- `Assembly3DWidget.update_temperature` previously a stub — fully implemented in Task 2

## Self-Check

### Files Exist
- `G:\blu-thermal-simulation\thermal_sim\ui\assembly_3d.py`: EXISTS (has update_temperature method)
- `G:\blu-thermal-simulation\thermal_sim\ui\main_window.py`: EXISTS (has _edge_layer_panel, _layer_edge_layers, _toggle_3d_preview)
- `G:\blu-thermal-simulation\thermal_sim\models\stack_templates.py`: EXISTS (eled_template with edge_layers)
- `G:\blu-thermal-simulation\tests\test_stack_templates.py`: EXISTS (3 new ELED edge_layers tests)

### Commits Exist
- `1f913ff`: feat(10-03): add edge layer editor panel and wire ELED auto-populate
- `0a49adf`: feat(10-03): add temperature overlay and structure/results toggle to 3D widget

## Self-Check: PASSED

## Next Phase Readiness

- Edge layer data model, GUI editor, ELED template, and 3D visualization are complete
- Phase 10 plans 10-01, 10-02, and 10-03 are all complete
- The edge layer solver integration (from 10-01) enables thermal simulation with perimeter structure
- 3D temperature overlay enables visual result verification on the assembly geometry
- Remaining: any future phases can build on the complete edge layers + 3D preview foundation

---
*Phase: 10-edge-layers-and-3d-preview*
*Completed: 2026-03-16*
