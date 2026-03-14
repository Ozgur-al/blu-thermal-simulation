# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access — one-click launch, intuitive workflow.
**Current focus:** Phase 1 — Foundation

## Current Position

Phase: 1 of 5 (Foundation)
Plan: 2 of 5 in current phase
Status: In progress
Last activity: 2026-03-14 — Completed 01-02: SimulationController + three-zone status bar

Progress: [██░░░░░░░░] 8%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 10 min
- Total execution time: 0.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 2 | 19 min | 10 min |

**Recent Trend:**
- Last 5 plans: 13m, 6m
- Trend: fast

*Updated after each plan completion*

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

### Pending Todos

None.

### Blockers/Concerns

- [Phase 3]: Sweep memory — estimate ~350 MB for 10-run transient sweep; validate with tracemalloc early in Phase 3 before it becomes an emergency
- [Phase 5]: Corporate AV behavior beyond Defender (CrowdStrike, Cylance) not verified — needs real test on a target machine

## Session Continuity

Last session: 2026-03-14
Stopped at: Completed 01-02-PLAN.md — SimulationController extracted; three-zone status bar built; 28 tests pass
Resume file: None
