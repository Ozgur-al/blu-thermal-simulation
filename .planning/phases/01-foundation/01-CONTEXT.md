# Phase 1: Foundation - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor the 939-line MainWindow monolith into collaborators (SimulationController, TableDataParser, PlotManager), then add undo/redo, threaded simulation with progress/cancel, status bar, window title tracking, GUI exposure of all CLI capabilities, and keyboard shortcuts. The GUI shell must be clean enough to accept new features in subsequent phases.

</domain>

<decisions>
## Implementation Decisions

### Solver mode selection
- Toolbar dropdown (combo box) always visible in the main toolbar
- One click to switch between steady-state and transient
- Mode is prominent since it fundamentally changes solver behavior

### Output directory configuration
- "Set Output Directory..." option under a new Run menu
- Opens a native folder browser dialog
- Remembers the last-used path between sessions

### CSV export
- Manual action only — user clicks "Export CSV..." from menu or toolbar after reviewing results
- No auto-export after runs (avoids cluttering output directory)
- Engineers run many times, export selectively

### Menu bar structure
- Add a new top-level "Run" menu
- Contains: Run Simulation (F5), Cancel (Esc), Set Output Directory..., Export CSV...
- Clean separation from File menu (project I/O stays in File, simulation actions in Run)

### Modified state & undo interaction
- Undoing all changes back to last-saved state clears the modified asterisk
- Matches VS Code / Word behavior — project genuinely matches what's on disk
- Only accurate dirty tracking, not simplified "any edit = dirty forever"

### Status bar — run feedback
- Detailed solver metrics approach
- During run: progress bar + timestep count + peak temperature so far
- After run: T_max, solve time, mesh size
- Cancel shows "Cancelled" state

### Status bar — spatial layout
- Three-zone layout:
  - Left: file path + modified asterisk
  - Center: solver state / progress bar
  - Right: last run time + mesh size

### Unsaved changes prompt
- Standard Save/Discard/Cancel dialog on window close, open project, or new project
- Prevents accidental data loss

### Claude's Discretion
- Undo/redo granularity (what constitutes one undoable action, stack depth)
- Simulation progress & cancel behavior details (partial results handling, thread management)
- Exact refactoring boundaries between SimulationController, TableDataParser, and PlotManager
- Keyboard shortcut conflict resolution with focused widgets
- Progress bar widget choice and animation style

</decisions>

<specifics>
## Specific Ideas

- Run menu is a dedicated top-level menu — not buried in File or Edit
- Status bar should feel information-dense like an engineering tool (detailed metrics, not minimal)
- Modified tracking should be smart — undo back to saved state = not dirty

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `thermal_sim/ui/main_window.py` (939 lines): Current monolith to decompose — contains tabbed editor, result dashboard, solver invocation, file I/O, and matplotlib embedding all in one class
- `thermal_sim/ui/structure_preview.py`: Layer stack visualization widget — already separated, good pattern to follow
- `thermal_sim/visualization/plotting.py`: `plot_temperature_map()` and `plot_probe_history()` — candidates to wrap in PlotManager
- `thermal_sim/app/cli.py`: CLI orchestration logic (solver mode routing, output dir, CSV export) — reference for GUI parity

### Established Patterns
- PySide6 with `FigureCanvasQTAgg` for embedded matplotlib
- Tabbed QWidget interface for project editing
- Broad `except Exception` with `# noqa: BLE001` for UI error handling
- `DisplayProject` as single source of truth for simulation input
- Solvers are stateless — each `solve()` call rebuilds network from project

### Integration Points
- `MainWindow` currently calls `SteadyStateSolver.solve()` and `TransientSolver.solve()` synchronously — must move to QThread
- `DisplayProject` modifications happen through table widget callbacks — undo system must intercept these
- CLI's `_run_steady()` / `_run_transient()` orchestration logic should inform SimulationController design
- `csv_export.py` functions (`export_temperature_map`, `export_probe_temperatures`) ready to wire into Export CSV action

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-14*
