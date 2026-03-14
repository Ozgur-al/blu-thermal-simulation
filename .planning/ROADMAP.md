# Roadmap: Thermal Simulator Phase 4

## Overview

This roadmap transforms an existing, working Phase 3 prototype into a professional engineering tool. The sequencing is driven by three hard constraints: the MainWindow god object must be decomposed before any new GUI feature can be added safely; backend engines must be testable via CLI before being wired into the GUI; and packaging must be last because it validates everything. Five phases deliver the upgrade in the only order that avoids structural collapse.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Refactor MainWindow into collaborators; wire undo/redo and run-with-progress
- [ ] **Phase 2: Results** - Structured results summary, hotspot annotation, PDF report, results comparison
- [ ] **Phase 3: Simulation Capabilities** - Parametric sweep engine, time-varying heat sources, expanded validation
- [ ] **Phase 4: Polish** - Qt Material theme, QDockWidget layout, inline validation feedback
- [ ] **Phase 5: Distribution** - PyInstaller one-folder bundle, resource path helper, launch verification

## Phase Details

### Phase 1: Foundation
**Goal**: Engineers can edit projects confidently knowing every change is undoable, simulations run off the main thread with visible progress, and the GUI shell is clean enough to accept new features safely
**Depends on**: Nothing (first phase)
**Requirements**: GUI-01, GUI-02, GUI-03, GUI-04, GUI-05, GUI-06, GUI-07
**Success Criteria** (what must be TRUE):
  1. User can press Ctrl+Z after any table edit and the change is fully reversed; Ctrl+Y re-applies it
  2. User can click Run and see a progress bar update during a transient simulation, then click Cancel to stop it without freezing the window
  3. Status bar always shows the current file path, a modified asterisk when unsaved changes exist, and the time of the last run
  4. All CLI capabilities (output directory, CSV export, solver mode selection) are reachable from the GUI without opening a terminal
  5. F5 triggers run, Escape cancels, Ctrl+S saves — all work from any focused widget
**Plans:** 4 plans
- [x] 01-01-PLAN.md -- Extract TableDataParser and PlotManager from MainWindow
- [x] 01-02-PLAN.md -- SimulationController, transient solver progress hooks, three-zone status bar
- [x] 01-03-PLAN.md -- Undo/redo, menus, keyboard shortcuts, dirty tracking, unsaved changes prompt
- [ ] 01-04-PLAN.md -- Human verification checkpoint for all Phase 1 requirements

### Phase 2: Results
**Goal**: Engineers can immediately see structured thermal metrics after a run, navigate hotspots on the map, export a PDF report for design review, and compare named result snapshots side-by-side
**Depends on**: Phase 1
**Requirements**: RSLT-01, RSLT-02, RSLT-03, RSLT-04
**Success Criteria** (what must be TRUE):
  1. After any simulation run, a results summary table shows T_max, T_avg, and T_min per layer plus a ranked hotspot list — no scrolling through raw data required
  2. Top-N hotspot locations appear as labeled markers directly on the temperature map plot
  3. User can click Export PDF and receive a file containing the stack summary, temperature maps, probe history, and key metrics — suitable for handing to a reviewer
  4. User can save a named result snapshot, run a modified simulation, and view an overlay probe plot and side-by-side metric table comparing the two runs
**Plans:** 4 plans
- [ ] 02-01-PLAN.md -- Backend foundations: layer_stats, per-layer hotspots, annotated map renderer, ResultSnapshot, PDF export
- [ ] 02-02-PLAN.md -- Results tab UI: structured tables, hotspot click-to-navigate, annotated temperature maps
- [ ] 02-03-PLAN.md -- Snapshot management, comparison tab, PDF export button wiring
- [ ] 02-04-PLAN.md -- Human verification checkpoint for all Phase 2 requirements

### Phase 3: Simulation Capabilities
**Goal**: Engineers can run parametric sweeps across design variants, define duty-cycle power profiles, and validate results against expanded analytical benchmarks — all exercisable from the CLI before GUI wiring
**Depends on**: Phase 2
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, MAT-01, MAT-02, MAT-03
**Success Criteria** (what must be TRUE):
  1. User can define a sweep (one parameter, a list of values) and execute it; progress shows "Run N of M" and the sweep completes without freezing the GUI
  2. Sweep results display as a comparison table (parameter value vs. T_max/T_avg per layer) and a parameter-vs-metric plot
  3. User can assign a piecewise-linear power profile (duty cycle) to a heat source and the transient solver uses it correctly at each timestep
  4. User can import a JSON material file and see those materials available in the material picker, distinguished from built-in presets; exporting produces a valid JSON file
  5. Running the validation suite produces at least three analytical comparison plots beyond the existing Phase 2 test cases
**Plans**: TBD

### Phase 4: Polish
**Goal**: The GUI looks and feels like a professional engineering tool — consistent Material Design theme, flexible dockable panels, and immediate visual feedback on invalid inputs
**Depends on**: Phase 3
**Requirements**: PLSH-01, PLSH-02, PLSH-03
**Success Criteria** (what must be TRUE):
  1. All GUI elements render with the qt-material dark theme; no widgets retain the default OS appearance
  2. User can undock, reposition, and resize the main panels (editor, results, plot) independently; layout persists across sessions
  3. Invalid inputs (e.g., negative thickness, non-numeric conductivity) show an inline visual indicator immediately without requiring the user to attempt a run
**Plans**: TBD

### Phase 5: Distribution
**Goal**: A non-programmer engineer can download a zip, extract it, and double-click to launch the full tool on a managed Windows machine with no admin access and no Python installed
**Depends on**: Phase 4
**Requirements**: DIST-01, DIST-02, DIST-03
**Success Criteria** (what must be TRUE):
  1. Double-clicking the launcher opens the GUI within 10 seconds on a clean Windows machine with no Python installed
  2. The bundle runs successfully on a managed Windows machine with Defender enabled and no admin access — no AV quarantine, no UAC prompt
  3. All resource paths (example JSON files, icons, fonts) resolve correctly both from the packaged bundle and from a direct in-repo dev launch
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/4 | In progress | - |
| 2. Results | 0/4 | Planning complete | - |
| 3. Simulation Capabilities | 0/TBD | Not started | - |
| 4. Polish | 0/TBD | Not started | - |
| 5. Distribution | 0/TBD | Not started | - |
