# Phase 4: Polish - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the GUI look and feel like a professional engineering tool. Apply a consistent Material Design dark theme, convert the fixed splitter layout to flexible dockable panels, and add immediate inline validation feedback on invalid inputs. No new simulation features or data capabilities — purely visual and interaction polish.

</domain>

<decisions>
## Implementation Decisions

### Theme & color scheme
- Use qt-material library with `dark_amber` preset — dark gray backgrounds (#212121/#303030) with amber/gold accent (#ffc107)
- Replace the existing custom stylesheet in gui.py entirely — let qt-material handle all widget styling consistently
- Dark-only theme — no light/dark toggle needed
- Typography: sans-serif (Segoe UI / system default) for labels and menus; monospace (Consolas / Courier) for numeric table cells and status bar values

### Dockable panel layout
- Convert three panels to QDockWidgets: Editor Tabs, Result Plots, Results Summary Table
- Comparison tab stays inside the Results area (not its own dock)
- Default arrangement: Editor left, Result Plots top-right, Results Summary bottom-right
- Persist dock layout across sessions using QSettings saveState()/restoreState()
- Add a View menu with checkable entries for each dock panel (QDockWidget.toggleViewAction())

### Inline validation feedback
- Red border + tooltip on invalid cells — hovering shows the error message (e.g., "Thickness must be > 0")
- Validation triggers on cell exit (focus-out), not on every keystroke
- Scope: all numeric table fields across Materials, Layers, Heat Sources, Boundaries, Probes tabs
- Run button disabled when any validation errors exist; status bar shows error count (e.g., "2 validation errors")

### Matplotlib in dark theme
- Match GUI background: figure facecolor #212121, axes facecolor #303030, text/ticks #e0e0e0, grid #444444
- Temperature map colormap: `inferno` (perceptually uniform, colorblind-friendly, great on dark backgrounds)
- Probe history line colors: amber accent palette — #ffc107 (amber), #ff7043 (deep orange), #66bb6a (green), #42a5f5 (blue), #ab47bc (purple)
- PDF export keeps print-friendly light style (white background, dark text) — separate from GUI dark theme

### Claude's Discretion
- Exact qt-material configuration parameters and any necessary overrides
- How to structure the matplotlib style dict (rcParams vs per-plot configuration)
- QDockWidget sizing ratios and minimum sizes
- How to integrate validation with the existing undo/redo system
- Whether to add a "Reset Layout" action in View menu

</decisions>

<specifics>
## Specific Ideas

- Dark amber theme gives a distinctive warm engineering tool feel — not the typical cold blue of ANSYS/COMSOL
- Inferno colormap chosen specifically because it reads as "thermal" intuitively (dark = cool, bright = hot) and is colorblind-safe
- Probe plot colors start with amber to reinforce the app's brand color
- Engineers should be able to fullscreen the plot panel by undocking it while keeping the editor visible

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gui.py`: Already has `_STYLESHEET` and `app.setStyle("Fusion")` — replace with qt-material setup
- `QSettings`: Already used in main_window.py for some state — extend for dock layout persistence
- `TableDataParser.validate_tables()`: Existing validation logic to build inline validation on top of
- `QDoubleValidator`: Already used for emissivity field — pattern to extend to all numeric fields
- `PlotManager` (ui/plot_manager.py): Centralized plot management — good place to apply dark theme style
- `plotting.py`: Temperature map and probe history functions — need dark theme color parameters

### Established Patterns
- PySide6 widget construction in `_build_ui()` method of MainWindow
- Tab-based organization with QTabWidget
- Matplotlib canvases embedded via FigureCanvasQTAgg
- Three-zone status bar (path, solver state, run info)

### Integration Points
- `gui.py:main()` — qt-material theme application replaces current Fusion + stylesheet setup
- `MainWindow._build_ui()` — QSplitter replaced with QDockWidget construction
- `TableDataParser.validate_tables()` — validation rules extracted for per-cell inline use
- `PlotManager` + `plotting.py` — matplotlib style configuration for dark theme
- `generate_pdf_report()` — must NOT inherit dark theme; needs its own light style context

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-polish*
*Context gathered: 2026-03-14*
