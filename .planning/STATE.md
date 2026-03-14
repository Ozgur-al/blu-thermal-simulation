---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-14T23:33:57.898Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 21
  completed_plans: 20
---

---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-14T23:27:53.811Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 21
  completed_plans: 19
---

---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-03-14T14:12:17Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 14
  completed_plans: 14
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access — one-click launch, intuitive workflow.
**Current focus:** Phase 5 — Distribution

## Current Position

Phase: 5 of 5 (Distribution) — in progress
Plan: 2 of 3 in current phase (completed 05-02)
Status: Phase 5 in progress
Last activity: 2026-03-15 - Completed 05-02-PLAN.md — ThermalSim.spec + build.py 5-step pipeline; verified 110 MB onedir bundle launches on build machine (DIST-01, DIST-02 satisfied)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 6 min
- Total execution time: 0.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 23 min | 8 min |
| 02-results | 3 | 10 min | 3 min |

**Recent Trend:**
- Last 5 plans: 13m, 6m, 4m, 3m, 5m
- Trend: fast

*Updated after each plan completion*
| Phase 03-simulation-capabilities P02 | 5 | 2 tasks | 4 files |
| Phase 04-polish P01 | 2 | 2 tasks | 5 files |
| Phase 04-polish P02 | 5 | 1 task | 1 file |
| Phase 04-polish P03 | 2 | 2 tasks | 2 files |
| Phase 05-distribution P01 | 3 | 2 tasks | 5 files |
| Phase 05-distribution P02 | 3 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: MainWindow refactor must precede all new GUI features — 939-line god object is the top structural risk
- [Init]: Backend engines (sweep, power profile, PDF) built CLI-first before GUI wiring
- [Init]: PyInstaller --onedir only (never --onefile) — AV quarantine risk on managed Windows machines
- [Init]: reportlab + qt-material + pyinstaller + pyinstaller-hooks-contrib are the only four new dependencies
- [01-01]: TableDataParser uses all-static methods — no instance needed, maximally testable without MainWindow
- [01-01]: PlotManager takes explicit dimension arguments rather than reading MainWindow widgets — clean interface boundary
- [01-01]: MplCanvas moved to plot_manager.py (canvas is a plotting concern, not a window concern)
- [01-01]: populate_tables_from_project added to TableDataParser to cover model-to-table direction
- [01-02]: SimulationController is a separate QObject from MainWindow so simulation lifecycle is independently testable
- [01-02]: Progress capped at ~100 cross-thread signal emissions via progress_every = n_steps // 100
- [01-02]: TransientSolver returns valid partial TransientResult on cancel rather than raising
- [01-02]: Three-zone status bar uses addPermanentWidget (not showMessage) to preserve persistent solver state
- [01-03]: _CellEditCommand captures pre-edit value via currentCellChanged (before edit) rather than cellPressed — more reliable
- [01-03]: Run/Cancel are QActions in both menu and toolbar — single enabled-state source, no QPushButton duplication
- [01-03]: _save_project() (Ctrl+S) saves silently to current path; _save_project_as_dialog() always shows dialog — VS Code behavior
- [01-03]: _maybe_save_changes() is the single guard called from closeEvent, _new_project(), and _load_project_dialog()
- [02-01]: ResultSnapshot is mutable (not frozen) — frozen=True raises TypeError for numpy arrays which are not hashable
- [02-01]: plot_temperature_map_annotated() accepts an existing ax rather than creating/saving a figure — enables GUI and PDF to share the same renderer
- [02-01]: PDF page builders each return a fig for the caller to savefig/close — prevents matplotlib memory accumulation
- [02-02]: result_tabs stored as self.result_tabs (not local) so _on_hotspot_navigate can switch tabs
- [02-02]: Old Summary tab retained for backward compatibility; Results tab is additive, not a replacement
- [02-02]: _plot_map() always does ax.clear() + fresh colorbar — simpler than in-place update when annotations change
- [02-03]: ComparisonWidget imports MplCanvas from plot_manager with defensive fallback for forward compatibility
- [02-03]: probe_values for transient snapshots stores full time-series arrays (not just final scalar)
- [02-03]: Steady-state probes in comparison rendered as horizontal axhline rather than skipped
- [02-04]: All RSLT requirements verified by human tester in the live GUI — Phase 2 is complete
- [Phase 03-simulation-capabilities]: SweepEngine discards full solver result after stats extraction — memory-safe design prevents large transient array accumulation
- [Phase 03-simulation-capabilities]: Material mutation via dataclasses.replace() since Material is frozen=True — setattr raises FrozenInstanceError
- [Phase 03-simulation-capabilities]: SweepResult imports SweepConfig lazily inside from_dict() to avoid circular import
- [03-03]: import_materials returns a new merged dict — does not mutate either input dict
- [03-03]: Built-in table rows use Qt.ItemFlag.ItemIsEditable cleared (not clone-on-edit) — avoids undo system entanglement
- [03-03]: load_builtin_library uses importlib.resources.files for PyInstaller bundle compatibility (superseded by 05-01 migration to paths.py)
- [03-03]: Type column placed last (col 6) so parse_materials_table cols 0-5 need no change
- [03-01]: power_at_time falls back to power_w when profile_end <= 0 (single-breakpoint edge case)
- [03-01]: First breakpoint enforced at time_s=0 in __post_init__ to prevent looping discontinuities
- [03-01]: TransientSolver detects _has_profiles once before loop — no overhead for constant-power runs
- [03-01]: ThermalNetwork b_vector is now a @property returning b_boundary + b_sources for backward compatibility
- [03-05]: Near-square-wave profile uses 4 breakpoints [(0,Q),(T_on-dt,Q),(T_on,0),(T_period-dt,0)] to stay within 1% of analytical solution
- [03-05]: generate_all_validation_plots placed in test_validation_cases.py — shares setup boilerplate and callable via python -c
- [03-05]: Tolerance for lateral spreading test uses rel_tol=1e-6 (tighter) since steady-state is an exact sparse solve
- [03-04]: Power profile state stored in dict[int, list[PowerBreakpoint]] keyed by sources_table row index — avoids extra dataclass or TableDataParser changes
- [03-04]: _source_profiles initialized in __init__ (not _build_sources_tab) so it persists across tab construction
- [03-04]: _build_project_from_ui patches power_profile onto heat_sources after TableDataParser builds base project
- [04-01]: qt-material import placed inside PySide6 try block — both fail together if PySide6 missing
- [04-01]: mpl.rcParams.update() called before MainWindow() so MplCanvas Figure picks up dark colors at creation time
- [04-01]: PDF isolation uses plt.style.context('default') not manual rcParams save/restore — context manager is exception-safe
- [04-01]: PROBE_COLORS defined once in plotting.py and imported by plot_manager.py — single source of truth
- [03-06]: All 7 Phase 3 requirements verified by human tester in live GUI and CLI — Phase 3 is complete
- [04-02]: QDockWidget.setObjectName required for saveState/restoreState to correctly identify docks across sessions
- [04-02]: _build_result_tabs() split into _build_plot_tabs() and _build_summary_tabs() — clean separation matches dock structure
- [04-02]: self.result_tabs replaced by _plot_tabs and _summary_tabs — _results_widget and _sweep_results_widget live in summary dock
- [04-02]: _restore_layout() called after _load_startup_project() so default dock positions are established first, then overridden by saved state
- [04-03]: validate_cell() uses exact lowercased header matching — avoids false positives and is consistent with actual headers in _build_*_tab() methods
- [04-03]: _remove_table_row() wrapper added rather than patching TableDataParser.remove_selected_row() — keeps static helper stateless and pure
- [04-03]: _on_run_ended() delegates to _update_validation_status() — single source of truth for run button enabled state
- [05-01]: paths.py uses Path(__file__).resolve().parent.parent.parent (3 levels up) as dev root — exact package depth from thermal_sim/core/paths.py
- [05-01]: SystemExit re-raised in gui.py crash handler — normal app.exec() exit must not be treated as a crash
- [05-01]: Splash QPainter-drawn at runtime — no external asset file; matches theme colors (#212121 bg, #FFB300 amber)
- [05-01]: gui.py top-level imports limited to sys, traceback, paths — crash handler can show dialog even if PySide6 import partially fails
- [Phase 05-02]: build.py imports APP_VERSION from thermal_sim.core.paths — single version source of truth across app and build pipeline
- [Phase 05-02]: MpCmdRun search uses sorted glob on Platform/* path first (Windows 11), falls back to Program Files — handles version churn without hardcoding
- [Phase 05-02]: Signing skipped non-fatally when signtool or cert missing — build succeeds unsigned with warning; enables CI builds without Windows SDK

### Pending Todos

None.

### Blockers/Concerns

- [Phase 3]: Sweep memory — estimate ~350 MB for 10-run transient sweep; validate with tracemalloc early in Phase 3 before it becomes an emergency
- [Phase 5]: Corporate AV behavior beyond Defender (CrowdStrike, Cylance) not verified — needs real test on a target machine

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | the app stutters a lot | 2026-03-14 | fec724d | [1-the-app-stutters-a-lot](./quick/1-the-app-stutters-a-lot/) |

## Session Continuity

Last session: 2026-03-15
Stopped at: Completed 05-02-PLAN.md — ThermalSim.spec + build.py; verified 110 MB onedir bundle launches on build machine (DIST-01, DIST-02 satisfied)
Resume file: None
