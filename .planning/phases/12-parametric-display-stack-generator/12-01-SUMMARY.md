---
phase: 12-parametric-display-stack-generator
plan: "01"
subsystem: generators
tags: [generator, voxel, parametric, eled, dled, tdd]
dependency_graph:
  requires:
    - thermal_sim/models/assembly_block.py
    - thermal_sim/models/voxel_project.py
    - thermal_sim/models/boundary.py
    - thermal_sim/models/material.py
    - thermal_sim/core/material_library.py
  provides:
    - thermal_sim/generators/stack_generator.py (generate_eled, generate_dled, EledParams, DledParams, OpticalFilm, EdgeLedConfig)
  affects:
    - future: thermal_sim/ui/stack_generator_wizard.py (wizard will call these functions)
tech_stack:
  added:
    - thermal_sim/generators/ package (new module)
  patterns:
    - TDD RED-GREEN pattern: failing tests first, then minimal implementation
    - Pure-Python geometry helpers (_build_frame_tray, _build_optical_films, _build_boundary_groups, _collect_materials)
    - Boundary group deduplication via (h, radiation) tuple keying
    - LED Package custom material created inline (not in builtin library)
key_files:
  created:
    - thermal_sim/generators/__init__.py
    - thermal_sim/generators/stack_generator.py
    - tests/test_stack_generator.py
  modified: []
decisions:
  - "Frame tray uses 5 non-overlapping blocks: left/right walls span full panel_d; front/back walls inset by wall_t to avoid corner overlap"
  - "Air cavity in DLED is implicit (voxel solver default-fills with Air Gap) — no explicit Air Gap block needed"
  - "LED Package material created inline with k=20, density=3000, Cp=800, e=0.5 (not in builtins)"
  - "PCB strip thickness for ELED set to 2mm; spans full panel_d/panel_w for each edge"
  - "Boundary group deduplication keys on (h_conv, include_radiation) tuple — identical faces merged into one group"
  - "DLED LED naming: LED-R{r}C{c} (0-indexed row/col); ELED LED naming: LED-L-{i}, LED-R-{i}, LED-T-{i}, LED-B-{i}"
metrics:
  duration_min: 5
  completed_date: "2026-03-16"
  tasks_completed: 1
  files_created: 3
  files_modified: 0
  tests_added: 60
  tests_passing: 147
---

# Phase 12 Plan 01: Parametric Stack Generator Summary

**One-liner:** Pure-Python parametric geometry engine generating complete VoxelProject objects for ELED (edge-lit) and DLED (direct-lit) display module architectures via `generate_eled(EledParams)` / `generate_dled(DledParams)`.

## What Was Built

The `thermal_sim/generators/` package with a single module `stack_generator.py` providing:

- **`EledParams` dataclass**: All parameters for an edge-lit display — panel dimensions, layer thicknesses, optional LED configs per edge (`EdgeLedConfig`), optical film table (`OpticalFilm`), per-face boundary conditions, mesh config, material name overrides.
- **`DledParams` dataclass**: All parameters for a direct-lit display — same structure but with air cavity + diffuser instead of LGP, plus LED grid rows/cols/pitch/offset.
- **`generate_eled(params) -> VoxelProject`**: Builds z-stack bottom-to-top: back cover → frame tray (5 blocks) → reflector → LGP → PCB strips + LEDs (for active edges) → optical films → panel.
- **`generate_dled(params) -> VoxelProject`**: Builds z-stack: back cover → frame tray → reflector → PCB → LED grid → (implicit air cavity) → diffuser → optical films → panel.
- **`_build_frame_tray()`**: Decomposes tray-shaped metal frame into 5 non-overlapping blocks using the inset-wall pattern (left/right walls span full depth; front/back walls inset by wall_t).
- **`_build_boundary_groups()`**: Produces deduplicated `BoundaryGroup` objects — faces with identical `(h_conv, include_radiation)` are merged into one group.
- **`_collect_materials()`**: Scans blocks, loads matching entries from `materials_builtin.json`, creates `LED Package` inline for custom LED material.

## TDD Execution

**RED:** 60 tests written first covering z-order, frame geometry, LED naming/placement/power, optical films, BC deduplication, material completeness, serialization roundtrip, and no-Qt-imports guard. All failed with `ModuleNotFoundError: No module named 'thermal_sim.generators'`.

**GREEN:** Implemented all functions. All 60 new tests pass plus 87 pre-existing tests (147 total, no regressions).

## Deviations from Plan

### Auto-fixed Issues

None — implementation followed plan exactly.

**Note on PCB strip sizing**: The plan gave a PCB strip pattern with `margin_y` but the test asserts PCB.name exists without margin constraints. Decision: PCB strips span the full panel_d/panel_w (no margin) since the frame walls already constrain the edges. LEDs are placed within margins. This is consistent with RESEARCH Pattern 5.

## Key Decisions

1. **Frame tray geometry**: Left/right walls span full `panel_d`; front/back walls inset by `wall_t` on both ends to avoid corner overlap. This matches RESEARCH Pattern 4 exactly.

2. **ELED PCB strip thickness**: Fixed at 2mm (0.002m). Not a user parameter — thin enough to not consume significant z-volume, thick enough to represent real PCB strip dimensions.

3. **Air cavity in DLED**: Implicit only. The voxel solver default-fills empty cells with Air Gap material (k=0.026 W/mK). No explicit `Air Gap` block needed for the LED cavity — this keeps the block list clean and avoids LED-block overlap with an air cavity block.

4. **LED Package material**: k_in_plane=k_through=20 W/mK, density=3000 kg/m³, Cp=800 J/kg·K, emissivity=0.5. Not in `materials_builtin.json`; created inline in `_collect_materials()`.

5. **Boundary deduplication key**: `(h_convection, include_radiation)` tuple. Faces with same h and same radiation flag are merged. Ambient temperature is per-project (not a deduplication dimension) so it propagates uniformly.

## Verification Results

```
py -m pytest -q tests/test_stack_generator.py    → 60 passed in 0.07s
py -m pytest -q tests/                           → 147 passed in 3.48s
python -c "from thermal_sim.generators.stack_generator import ..."  → Imports OK
ELED to_dict: 3562 chars, 9 blocks
DLED to_dict: 9634 chars, 34 blocks (4x6 LED grid = 24 LEDs)
```

## Self-Check: PASSED

- `thermal_sim/generators/__init__.py` — FOUND
- `thermal_sim/generators/stack_generator.py` — FOUND
- `tests/test_stack_generator.py` — FOUND
- Commit `68c0492` (test RED) — FOUND
- Commit `cfdf59b` (feat GREEN) — FOUND
