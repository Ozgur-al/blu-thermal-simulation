---
phase: 06-fix-led-array-generation-and-display-stack-generation-for-dled-and-eled-architectures
plan: 02
subsystem: ui
tags: [gui, pyside6, qstackedwidget, dled, eled, architecture-dropdown, template-application]

requires:
  - phase: 06-01
    provides: "LEDArray extended with mode/zone/edge fields; dled_template and eled_template factory functions in stack_templates.py"

provides:
  - "thermal_sim/ui/main_window.py: Architecture dropdown (Custom/DLED/ELED) in top controls"
  - "thermal_sim/ui/main_window.py: QStackedWidget LED Arrays tab with three pages"
  - "thermal_sim/ui/main_window.py: DLED panel with grid config, edge offsets, zone dimming, LED footprint spinboxes"
  - "thermal_sim/ui/main_window.py: ELED panel with edge config, strip params, LED footprint spinboxes"
  - "thermal_sim/ui/main_window.py: _on_architecture_changed wires template application"
  - "thermal_sim/ui/main_window.py: _apply_template seeds full UI from template data"
  - "thermal_sim/ui/main_window.py: _build_led_arrays_from_arch_panel constructs LEDArray from spinbox values"
  - "thermal_sim/ui/main_window.py: _build_project_from_ui branches on arch selection"

affects:
  - GUI LED Arrays tab

tech-stack:
  added: []
  patterns:
    - QStackedWidget page-switching indexed by architecture string lookup
    - blockSignals(True/False) wrapping all spinbox assignments in _apply_template to prevent signal cascade
    - _populate_ui_from_project resets arch to Custom with signals blocked (prevents _on_architecture_changed re-firing)
    - _build_project_from_ui branches on combo text to select data source (spinboxes vs table)
    - Spinbox values always stored in mm (user units); divided by 1000 when building LEDArray SI model

key-files:
  created: []
  modified:
    - thermal_sim/ui/main_window.py

key-decisions:
  - "QStackedWidget index 0=Custom, 1=DLED, 2=ELED — maps cleanly from arch_combo text via dict lookup"
  - "_apply_template calls _populate_ui_from_project first (handles layers/materials/boundaries/tables) then re-seeds arch-specific spinboxes — avoids duplicating populate logic"
  - "_apply_template restores arch_combo text and _led_arrays_stack index after _populate_ui_from_project resets them to Custom/0"
  - "_build_led_arrays_from_arch_panel constructs LEDArray with layer='LED Board' for DLED and layer='LGP' for ELED — matching template layer names"
  - "Undo stack cleared in _apply_template (silent replacement, consistent with _populate_ui_from_project behavior on project load)"
  - "Signal blocking on all spinbox assignments in _apply_template prevents cascade re-renders and spurious undo commands"
  - "Loading a project from disk always resets architecture to Custom (per RESEARCH.md design decision)"

patterns-established:
  - "Architecture-specific panels: use QStackedWidget with per-panel builder methods, switch via dict lookup on combo text"
  - "Template application: populate shared UI first via existing populate method, then seed architecture-specific widgets"

requirements-completed: [ARCH-05, ARCH-06]

duration: 10min
completed: "2026-03-15"
---

# Phase 06 Plan 02: Architecture Dropdown and DLED/ELED GUI Panels Summary

Architecture dropdown (Custom/DLED/ELED) with QStackedWidget LED tab, auto-populating DLED grid/zone and ELED edge spinbox panels from stack templates, with _build_project_from_ui branching on active architecture.

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-15T18:15:00Z
- **Completed:** 2026-03-15T18:23:24Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added architecture dropdown (Custom/DLED/ELED) to top controls row0 above existing view controls
- Replaced the flat LED Arrays tab with a QStackedWidget: Custom page (existing table, index 0), DLED page (index 1), ELED page (index 2)
- DLED panel has full grid config (count_x/y, pitch_x/y, power), edge offsets (top/bottom/left/right in mm), zone dimming (zone_count_x/y + dynamic zone power table), and LED footprint controls
- ELED panel has edge config combo (bottom/top/left/right/all), strip params (count, pitch, edge_offset, power), and LED footprint controls
- _on_architecture_changed switches the stack page and calls dled_template/eled_template with current panel dimensions, then populates via _apply_template
- _apply_template uses _populate_ui_from_project for shared data (layers, materials, boundaries) then seeds architecture-specific spinboxes; clears undo stack for silent replacement
- _build_project_from_ui branches on arch_combo: DLED/ELED read from spinboxes via _build_led_arrays_from_arch_panel, Custom reads from existing table parser unchanged
- Loading any project from disk resets architecture to Custom with signals blocked

## Task Commits

Each task was committed atomically:

1. **Task 1: Add architecture dropdown and build DLED/ELED/Custom widget panels** - `182a4dc` (feat)
2. **Task 2: Wire architecture switching, template application, and project building** - `5bb5387` (feat)

**Plan metadata:** (docs commit after self-check)

## Files Created/Modified

- `thermal_sim/ui/main_window.py` - Architecture combo, QStackedWidget LED tab, DLED/ELED panel builders, behavioral wiring methods

## Decisions Made

- QStackedWidget index mapping via dict lookup on combo text (`{"Custom": 0, "DLED": 1, "ELED": 2}`) — clear and extensible
- `_apply_template` calls existing `_populate_ui_from_project` first to avoid duplicating layer/material/boundary populate logic, then re-applies arch combo and stack index that `_populate_ui_from_project` resets
- DLED `_build_led_arrays_from_arch_panel` uses layer name "LED Board", ELED uses "LGP" — matching the template layer stack names so the layer reference validation in DisplayProject passes
- All spinbox assignments in `_apply_template` wrapped in `blockSignals(True/False)` per RESEARCH.md Pitfall 3 to prevent signal cascade during bulk update

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Architecture dropdown and DLED/ELED panels are fully wired
- Users can select DLED/ELED to auto-populate a typical display stack and run simulations
- Custom mode retains full backward compatibility with existing table-based workflow
- No blockers for downstream work

## Self-Check: PASSED

- `thermal_sim/ui/main_window.py` — FOUND
- `06-02-SUMMARY.md` — FOUND
- Commit `182a4dc` — FOUND
- Commit `5bb5387` — FOUND

---
*Phase: 06-fix-led-array-generation-and-display-stack-generation-for-dled-and-eled-architectures*
*Completed: 2026-03-15*
