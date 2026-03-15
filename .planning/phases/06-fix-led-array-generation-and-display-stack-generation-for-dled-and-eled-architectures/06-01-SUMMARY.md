---
phase: 06-fix-led-array-generation-and-display-stack-generation-for-dled-and-eled-architectures
plan: 01
subsystem: models
tags: [led-array, stack-templates, dled, eled, serialization, tdd]
dependency_graph:
  requires: []
  provides:
    - thermal_sim/models/heat_source.py:LEDArray (extended with mode/zone/edge fields)
    - thermal_sim/models/stack_templates.py:dled_template
    - thermal_sim/models/stack_templates.py:eled_template
  affects:
    - thermal_sim/models/project.py (via expanded_heat_sources())
    - GUI LED array tab (future phase 06-02)
tech_stack:
  added: []
  patterns:
    - TDD (RED-GREEN for both tasks)
    - dataclass field extension with backward-compat defaults
    - expand() dispatch pattern (mode enum routing)
    - builtin library filtering for template materials
key_files:
  created:
    - thermal_sim/models/stack_templates.py
    - tests/test_stack_templates.py
  modified:
    - thermal_sim/models/heat_source.py
    - tests/test_led_array.py
decisions:
  - LEDMode dispatches in expand() via if/elif — no dict lookup, explicit and debuggable
  - mode='custom' is the default (backward compat) — old JSON files load without changes
  - _expand_edge() names LEDs with tag in name (bot/top/left/right) — avoids corner ambiguity in tests
  - stack_templates uses _filter_materials() helper — templates only ship materials they actually use
  - Both templates use load_builtin_library() (importlib.resources path) — PyInstaller compatible
  - DLED offset_x/y = 10% of panel dimensions — centers grid within active area
  - ELED count_x=20, count_y=15 — typical edge LED density for automotive/display panels
metrics:
  duration: 5 min
  completed_date: "2026-03-15"
  tasks: 2
  files_changed: 4
---

# Phase 06 Plan 01: LED Array Modes and Stack Templates Summary

Extended LEDArray with grid/edge/custom modes and zone-based power, plus new pure-Python stack_templates module providing dled_template() and eled_template() factory functions.

## What Was Built

### Task 1: Extended LEDArray Model (TDD)

Added three expansion modes to `thermal_sim/models/heat_source.py`:

- **mode="custom"** (default): existing center_x/center_y grid placement — zero behavior change
- **mode="grid"**: panel-aware 2D grid using `offset_{top,bottom,left,right}` to define the active area, centering the grid within it. Supports `zone_count_x/y` and `zone_powers` for per-zone LED brightness control.
- **mode="edge"**: places discrete LEDs along panel edges controlled by `edge_config` ("bottom", "top", "left_right", "all"). All positions clamped to `[0, panel_width] x [0, panel_height]`.

New type aliases: `LEDMode`, `EdgeConfig`.

New fields on LEDArray (all optional with backward-compat defaults):
`mode`, `offset_top`, `offset_bottom`, `offset_left`, `offset_right`, `zone_count_x`, `zone_count_y`, `zone_powers`, `edge_config`, `edge_offset`, `panel_width`, `panel_height`.

`total_power_w` updated to handle zone power sums (grid mode) and edge LED counts.

`to_dict()`/`from_dict()` fully updated; `from_dict()` uses `.get()` with defaults for every new key — old JSON files load as `mode="custom"` with all field defaults.

### Task 2: Stack Templates Module (TDD)

Created `thermal_sim/models/stack_templates.py` with two pure functions:

**`dled_template(panel_width, panel_height, optical_layers=2)`** returns:
- 8-layer stack (optical_layers=2): Back Cover (Al 0.8mm), Metal Frame (Steel 1mm), LED Board (FR4 1mm), Diffuser (PC 2mm), BEF (PC 0.3mm), OCA (0.15mm), Display Cell (Glass 1.1mm), Cover Glass (Glass 1.8mm)
- LEDArray with mode="grid", 8x6 LEDs, 10% panel-edge offsets
- side convection_h=25.0 W/m²K (metal frame enhancement)

**`eled_template(panel_width, panel_height, edge_config="bottom", optical_layers=2)`** returns:
- Same 8-layer stack but LGP (PMMA 4mm) replaces LED Board (FR4)
- LEDArray with mode="edge" on LGP layer, 20 horizontal / 15 vertical LEDs
- side convection_h=25.0 W/m²K

Both templates filter the builtin material library to only materials referenced by their layers. No PySide6 dependencies.

## Test Coverage

**tests/test_led_array.py**: 15 tests (was 2 originally, added 13 new)
- custom mode backward compat
- grid mode offset placement and last-LED bounds check
- grid mode zone power assignment (4-zone 4x4 grid)
- grid mode empty zone_powers fallback
- edge mode bottom/left_right/all placement
- edge mode position clamping
- to_dict/from_dict round-trip for all new fields
- old JSON format defaults to mode="custom"
- total_power_w for grid zones and edge all-edges

**tests/test_stack_templates.py**: 19 tests (new file)
- Both templates return all required keys
- DLED 8-layer order and ELED LGP substitution
- Materials completeness (all layer references in materials dict)
- LED array mode/layer/panel dims for both templates
- optical_layers=3 produces 9-layer stack
- side boundary convection_h=25.0
- No PySide6 imports in stack_templates

**Full suite: 154 passed** (was 135 before this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Duplicate `_edge_led_count` method**
- **Found during:** Task 1 implementation review
- **Issue:** Initial draft had flawed first version and a corrected redefinition. Python uses the last definition silently but is misleading.
- **Fix:** Removed the incorrect first implementation, keeping only the correct one.
- **Files modified:** thermal_sim/models/heat_source.py

**2. [Rule 1 - Bug] Test corner ambiguity for edge mode tests**
- **Found during:** Task 1 test execution (1 test failed on GREEN run)
- **Issue:** `test_led_array_edge_all_produces_leds_on_all_four_edges` and `test_led_array_edge_left_right_produces_correct_count` filtered LEDs by y/x coordinate alone, causing corner LEDs to be double-counted (y=edge_offset appears in both horizontal bottom strip and the first vertical-strip LED).
- **Fix:** Changed test filters to use LED name substrings ("bot", "top", "left", "right") which are set by the `_expand_edge()` tagging scheme.
- **Files modified:** tests/test_led_array.py

**3. [Rule 1 - Bug] PySide6 string in docstring triggered test failure**
- **Found during:** Task 2 test execution (1 test failed on first GREEN run)
- **Issue:** `test_stack_templates_no_pyside6_dependency` used `inspect.getsource()` to check for "PySide6" in source, but the module docstring said "no PySide6 dependencies" — containing the string it was checking against.
- **Fix:** Changed test to check only import-statement lines rather than full source text.
- **Files modified:** tests/test_stack_templates.py

## Self-Check

Created files:
- `thermal_sim/models/stack_templates.py` — FOUND
- `tests/test_stack_templates.py` — FOUND

Modified files:
- `thermal_sim/models/heat_source.py` — FOUND
- `tests/test_led_array.py` — FOUND

Commits:
- `b79cc10` test(06-01): add failing tests for extended LEDArray modes
- `c56e8a4` feat(06-01): extend LEDArray with mode, zone, and edge fields
- `d1ec5fe` test(06-01): add failing tests for dled_template and eled_template
- `634da39` feat(06-01): create stack_templates module with dled_template and eled_template

## Self-Check: PASSED
