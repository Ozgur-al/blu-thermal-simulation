---
phase: 10-edge-layers-and-3d-preview
plan: "01"
subsystem: data-model + solver
tags: [edge-layers, material-zones, serialization, network-builder]
dependency_graph:
  requires: []
  provides: [EdgeLayer-dataclass, generate_edge_zones, solver-edge-zone-merging]
  affects: [thermal_sim/models/layer.py, thermal_sim/models/stack_templates.py, thermal_sim/solvers/network_builder.py]
tech_stack:
  added: []
  patterns: [frozen-dataclass-validation, center-coord-material-zones, tdd-red-green]
key_files:
  created:
    - tests/test_edge_layers.py
  modified:
    - thermal_sim/models/layer.py
    - thermal_sim/models/stack_templates.py
    - thermal_sim/solvers/network_builder.py
decisions:
  - "Bottom/top edge zones span full panel width to cover corners; left/right zones span interior height only"
  - "Edge zones prepended before manual zones in solver so manual zones win on overlap (last-defined-wins)"
  - "Layer.to_dict() omits edge_layers key when empty — consistent with existing zones omission pattern"
  - "generate_edge_zones() uses lazy import of MaterialZone inside function body (avoids circular import)"
  - "network_builder uses getattr(layer, 'edge_layers', {}) for forward-compat, then imports generate_edge_zones inline"
metrics:
  duration: "5 min"
  completed: "2026-03-16"
  tasks_completed: 2
  files_modified: 4
---

# Phase 10 Plan 01: EdgeLayer Data Model and generate_edge_zones() Summary

**One-liner:** EdgeLayer frozen dataclass + generate_edge_zones() converting per-edge lateral stacks to center-coord MaterialZone rectangles, wired into the network builder.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add EdgeLayer dataclass and Layer.edge_layers field | 5723c58 | layer.py, test_edge_layers.py |
| 2 | Implement generate_edge_zones() and wire solver | 34e2249 | stack_templates.py, network_builder.py |

## What Was Built

### EdgeLayer Dataclass (`thermal_sim/models/layer.py`)

Frozen dataclass with:
- `material: str` — validated non-empty (including whitespace-only)
- `thickness: float` — validated > 0
- `to_dict()` / `from_dict()` round-trip

### Layer.edge_layers Field (`thermal_sim/models/layer.py`)

- `edge_layers: dict[str, list[EdgeLayer]]` with `field(default_factory=dict)`
- `to_dict()` omits `edge_layers` key when empty (backward-compatible with old JSON)
- `from_dict()` uses `.get("edge_layers", {})` for old JSON without the key

### generate_edge_zones() (`thermal_sim/models/stack_templates.py`)

Pure function converting a layer's `edge_layers` dict + panel dimensions to `MaterialZone` rectangles:
- **Bottom/top zones**: full panel width, stacked from their respective edges inward
- **Left/right zones**: interior height only (`panel_height - bottom_total - top_total`), stacked from lateral edges inward
- **Corner handling**: bottom/top zones cover corners because they span full width
- **Validation**: raises `ValueError` when left+right total >= panel_width or bottom+top total >= panel_height
- Returns `[]` when `layer.edge_layers` is empty

### Solver Integration (`thermal_sim/solvers/network_builder.py`)

At the rasterization loop (formerly line 256):
```python
if getattr(layer, "edge_layers", {}):
    edge_zones = generate_edge_zones(layer, project.width, project.height)
    effective_zones = edge_zones + list(layer.zones)
    layer = dataclasses.replace(layer, zones=effective_zones)
maps = _rasterize_zones(layer, project.materials, grid)
```
Edge zones prepended → manual zones appended last → manual zones win on overlap.

## Tests

28 new tests in `tests/test_edge_layers.py`:
- EdgeLayer validation (empty material, whitespace, negative/zero thickness, frozen)
- EdgeLayer to_dict / from_dict round-trip
- Layer.edge_layers serialization (omit when empty, include when set, multiple edges)
- Layer.from_dict backward compat (no edge_layers key → empty dict)
- generate_edge_zones empty, symmetric 4-edge, zone count, bottom/top full-width, left/right interior height
- Corner coverage by bottom/top zones
- Overflow validation (width, height)
- Material correctness, center coordinates
- Solver integration: manual zone wins over edge zone at overlap

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Test correctness] Fixed test filter for left/right zone height check**
- **Found during:** Task 2 test run
- **Issue:** `[z for z in zones if z.height != 0.200]` filtered out all zones including bottom/top zones (which have height=0.003, not 0.200), causing false failure
- **Fix:** Changed filter to `z.width != pytest.approx(0.300)` — correctly identifies left/right zones by their narrow width
- **Files modified:** tests/test_edge_layers.py

**2. [Linter auto-applied] Layer.py, stack_templates.py, network_builder.py, test_edge_layers.py**
- The project linter auto-applied style/formatting passes during the session. All linter-applied changes were verified to be correct and non-breaking.

## Self-Check: PASSED

### Files Exist
- FOUND: thermal_sim/models/layer.py
- FOUND: thermal_sim/models/stack_templates.py
- FOUND: thermal_sim/solvers/network_builder.py
- FOUND: tests/test_edge_layers.py

### Commits Exist
- FOUND: 5723c58 — feat(10-01): add EdgeLayer dataclass and Layer.edge_layers field
- FOUND: 34e2249 — feat(10-01): implement generate_edge_zones() and wire solver integration

### Tests Pass
- 28 new tests: all passed
- Full suite (235 tests): all passed
