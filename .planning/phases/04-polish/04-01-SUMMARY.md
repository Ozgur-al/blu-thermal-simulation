---
phase: 04-polish
plan: 01
subsystem: ui
tags: [qt-material, matplotlib, theming, dark-theme, pdf-export]

# Dependency graph
requires:
  - phase: 03-simulation-capabilities
    provides: GUI structure (MainWindow, PlotManager, pdf_export) to apply theming to
provides:
  - qt-material dark_amber theme applied to all Qt widgets
  - DARK_MPL_STYLE dict (11 keys) for dark matplotlib backgrounds
  - PROBE_COLORS amber accent palette for probe history charts
  - Monospace QSS overrides for table cells and status bar
  - PDF export isolated from dark rcParams via plt.style.context('default')
affects: [04-polish]

# Tech tracking
tech-stack:
  added: [qt-material>=2.14, Jinja2 (transitive)]
  patterns: [rcParams set before MainWindow construction, plt.style.context wrapper for light-print isolation]

key-files:
  created: []
  modified:
    - thermal_sim/app/gui.py
    - thermal_sim/visualization/plotting.py
    - thermal_sim/ui/plot_manager.py
    - thermal_sim/io/pdf_export.py
    - requirements.txt

key-decisions:
  - "qt-material import placed inside the PySide6 try block — both fail together if PySide6 missing"
  - "mpl.rcParams.update() called before MainWindow() so MplCanvas Figure picks up dark colors at creation time"
  - "PDF isolation uses plt.style.context('default') not rcParams restore — context manager is exception-safe"
  - "PROBE_COLORS defined once in plotting.py and imported by plot_manager.py — single source of truth"

patterns-established:
  - "Theming pattern: apply_stylesheet first, then append extra QSS via app.setStyleSheet(app.styleSheet() + extra)"
  - "PDF isolation pattern: all figure creation inside plt.style.context('default') block"

requirements-completed: [PLSH-01]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 4 Plan 01: Dark Theme, Probe Colors, and PDF Isolation Summary

**qt-material dark_amber theme, DARK_MPL_STYLE dict (11 keys), PROBE_COLORS amber palette, and plt.style.context('default') PDF isolation replacing Fusion + custom _STYLESHEET**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T14:59:03Z
- **Completed:** 2026-03-14T15:01:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced Fusion + `_STYLESHEET` constant with `apply_stylesheet(app, theme='dark_amber.xml')` from qt-material
- Defined `DARK_MPL_STYLE` (11 keys: figure/axes backgrounds, edge/text/tick/grid colors, legend colors) and applied via `mpl.rcParams.update()` before MainWindow construction
- Added monospace QSS overrides for `QTableWidget` and `QStatusBar QLabel` appended after qt-material styles
- Defined `PROBE_COLORS` amber accent palette in plotting.py, used by both `plot_probe_history()` and `PlotManager.plot_probe_history()` via import
- Wrapped entire `generate_pdf_report()` body in `plt.style.context('default')` so printed PDFs have light backgrounds regardless of global dark rcParams

## Task Commits

Each task was committed atomically:

1. **Task 1: Apply qt-material theme and matplotlib dark style in gui.py** - `d27ad3e` (feat)
2. **Task 2: Add probe color palette to plotting.py and isolate PDF export from dark theme** - `d41263f` (feat)

**Plan metadata:** (final docs commit follows)

## Files Created/Modified
- `thermal_sim/app/gui.py` - Replaced Fusion/_STYLESHEET with qt-material apply_stylesheet, added DARK_MPL_STYLE and rcParams setup, monospace QSS overrides
- `thermal_sim/visualization/plotting.py` - Added PROBE_COLORS constant, updated plot_probe_history() to use it
- `thermal_sim/ui/plot_manager.py` - Imported PROBE_COLORS, applied to probe history canvas loop
- `thermal_sim/io/pdf_export.py` - Wrapped generate_pdf_report() body in plt.style.context('default')
- `requirements.txt` - Added qt-material>=2.14

## Decisions Made
- qt-material import placed inside the PySide6 try block so both fail together if PySide6 is missing
- `mpl.rcParams.update()` called before `MainWindow()` construction so `MplCanvas` Figure objects pick up dark colors at creation time
- PDF isolation uses `plt.style.context('default')` (context manager) not manual rcParams save/restore — exception-safe
- `PROBE_COLORS` defined once in `plotting.py` and imported by `plot_manager.py` — single source of truth for the palette

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — qt-material 2.17 installed cleanly, all 111 existing tests pass without regression.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Theming foundation is complete; 04-02 (dock layout) and subsequent plans build on a fully styled GUI
- Temperature maps use inferno colormap (pre-existing, no change needed)
- PDF export is print-safe with light backgrounds even when GUI runs in dark mode

---
*Phase: 04-polish*
*Completed: 2026-03-14*

## Self-Check: PASSED

- thermal_sim/app/gui.py — FOUND
- thermal_sim/visualization/plotting.py — FOUND
- thermal_sim/ui/plot_manager.py — FOUND
- thermal_sim/io/pdf_export.py — FOUND
- requirements.txt — FOUND
- .planning/phases/04-polish/04-01-SUMMARY.md — FOUND
- Commit d27ad3e — FOUND
- Commit d41263f — FOUND
