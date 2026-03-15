# Roadmap: Thermal Simulator

## Milestones

- [x] **v1.0** - Phases 1-6 (complete)
- [ ] **v2.0 Full 3D Solver** - Phases 7-9 (in progress)

## Phases

<details>
<summary>v1.0 (Phases 1-6) - COMPLETE</summary>

- [x] **Phase 1: Foundation** - Refactor MainWindow into collaborators; wire undo/redo and run-with-progress
- [x] **Phase 2: Results** - Structured results summary, hotspot annotation, PDF report, results comparison
- [x] **Phase 3: Simulation Capabilities** - Parametric sweep engine, time-varying heat sources, expanded validation
- [x] **Phase 4: Polish** - Qt Material theme, QDockWidget layout, inline validation feedback
- [x] **Phase 5: Distribution** - PyInstaller one-folder bundle, resource path helper, launch verification
- [x] **Phase 6: Architecture Support** - DLED and ELED display stack templates, architecture-aware LED array generation, GUI workflow

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
**Plans:** 4/4 plans complete

### Phase 2: Results
**Goal**: Engineers can immediately see structured thermal metrics after a run, navigate hotspots on the map, export a PDF report for design review, and compare named result snapshots side-by-side
**Depends on**: Phase 1
**Requirements**: RSLT-01, RSLT-02, RSLT-03, RSLT-04
**Success Criteria** (what must be TRUE):
  1. After any simulation run, a results summary table shows T_max, T_avg, and T_min per layer plus a ranked hotspot list
  2. Top-N hotspot locations appear as labeled markers directly on the temperature map plot
  3. User can click Export PDF and receive a file containing the stack summary, temperature maps, probe history, and key metrics
  4. User can save a named result snapshot, run a modified simulation, and view an overlay probe plot and side-by-side metric table comparing the two runs
**Plans:** 4/4 plans complete

### Phase 3: Simulation Capabilities
**Goal**: Engineers can run parametric sweeps across design variants, define duty-cycle power profiles, and validate results against expanded analytical benchmarks
**Depends on**: Phase 2
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, MAT-01, MAT-02, MAT-03
**Success Criteria** (what must be TRUE):
  1. User can define a sweep (one parameter, a list of values) and execute it; progress shows "Run N of M"
  2. Sweep results display as a comparison table and a parameter-vs-metric plot
  3. User can assign a piecewise-linear power profile to a heat source and the transient solver uses it correctly at each timestep
  4. User can import a JSON material file and see those materials available in the material picker, distinguished from built-in presets
  5. Running the validation suite produces at least three analytical comparison plots beyond the Phase 2 test cases
**Plans:** 6/6 plans complete

### Phase 4: Polish
**Goal**: The GUI looks and feels like a professional engineering tool — consistent Material Design theme, flexible dockable panels, and immediate visual feedback on invalid inputs
**Depends on**: Phase 3
**Requirements**: PLSH-01, PLSH-02, PLSH-03
**Success Criteria** (what must be TRUE):
  1. All GUI elements render with the qt-material dark theme; no widgets retain the default OS appearance
  2. User can undock, reposition, and resize the main panels independently; layout persists across sessions
  3. Invalid inputs show an inline visual indicator immediately without requiring the user to attempt a run
**Plans:** 4/4 plans complete

### Phase 5: Distribution
**Goal**: A non-programmer engineer can download a zip, extract it, and double-click to launch the full tool on a managed Windows machine with no admin access and no Python installed
**Depends on**: Phase 4
**Requirements**: DIST-01, DIST-02, DIST-03
**Success Criteria** (what must be TRUE):
  1. Double-clicking the launcher opens the GUI within 10 seconds on a clean Windows machine with no Python installed
  2. The bundle runs successfully on a managed Windows machine with no admin access
  3. All resource paths resolve correctly both from the packaged bundle and from a direct in-repo dev launch
**Plans:** 3/3 plans complete

### Phase 6: Architecture Support
**Goal**: Engineers can select a display backlight architecture (direct-lit or edge-lit) and get a pre-populated project with correct layer stack, materials, LED configuration, and boundary conditions
**Depends on**: Phase 5
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06
**Success Criteria** (what must be TRUE):
  1. User can select DLED from the architecture dropdown and get a complete layer stack with LED grid and zone dimming
  2. User can select ELED and get a complete layer stack with LGP and edge LED strips
  3. Zone-based dimming in DLED produces asymmetric thermal patterns matching the zone power distribution
  4. Existing Custom workflow and old JSON project files remain fully compatible
  5. The LED Arrays tab adapts its UI based on architecture selection
**Plans:** 3/3 plans complete

</details>

### v2.0 Full 3D Solver (In Progress)

**Milestone Goal:** Upgrade from 2.5D (uniform material per layer, one z-node per layer) to a full 3D RC-network solver with per-cell material assignment and z-refinement — enabling accurate ELED edge-assembly thermal modeling.

- [ ] **Phase 7: 3D Solver Core** - NodeLayout abstraction, per-cell material zones, harmonic-mean conductance, backward-compat regression gate
- [ ] **Phase 8: Z-Refinement** - Multiple z-nodes per layer, correct within-layer vs inter-layer conductance formulas, solver reshape, analytical validation
- [ ] **Phase 9: 3D GUI and ELED Zone Preset** - Z-slice viewer, nz spinbox, material zone editor, ELED cross-section auto-zones

## Phase Details

### Phase 7: 3D Solver Core
**Goal**: The network builder correctly handles per-cell material zones using centralized node indexing, and every existing project produces identical temperatures to the v1.0 solver — making the 3D foundation safe to build on
**Depends on**: Phase 6
**Requirements**: SOLV-01, SOLV-02, SOLV-03, SOLV-04
**Success Criteria** (what must be TRUE):
  1. All existing example project JSON files (no zones, all nz=1) load and solve to temperatures identical to v1.0 within floating-point tolerance — confirmed by a regression test that runs before any builder changes are merged
  2. A project with two lateral material zones (e.g., aluminum strip and FR4 background) produces a temperature map where the aluminum strip shows measurably lower temperatures than the FR4 background, reflecting the conductivity contrast
  3. The conductance at the boundary between two zone materials equals the harmonic mean of their individual conductances — verified by a unit test against a hand-calculated value
  4. Node indexing for a project with nz=1 everywhere uses the new NodeLayout abstraction and produces the same flat index as the old formula
**Plans:** 2 plans
- [ ] 07-01-PLAN.md — Regression baseline + MaterialZone model + Layer.zones field
- [ ] 07-02-PLAN.md — NodeLayout + per-cell harmonic-mean conductance + zone rasterization in builder

### Phase 8: Z-Refinement
**Goal**: Engineers can assign multiple z-nodes to any layer, the solver handles the full 3D node count correctly, and a 1D analytical benchmark confirms the through-plane temperature profile is physically correct
**Depends on**: Phase 7
**Requirements**: ZREF-01, ZREF-02, ZREF-03, ZREF-04, ZREF-05
**Success Criteria** (what must be TRUE):
  1. A layer with nz=5 produces a through-thickness temperature profile that matches the 1D analytical solution for a slab with uniform heat generation — confirmed by a pytest validation test
  2. Within-layer z-z links carry no interface resistance term; the inter-layer boundary between two different layers carries the full interface resistance — both verified by the analytical test
  3. The steady-state and transient solvers produce correct result arrays for a mixed-nz project (e.g., nz=[1, 3, 2] across three layers) without shape errors or index mismatches
  4. A project with all nz=1 (no z-refinement) produces identical temperatures after Phase 8 as it did after Phase 7 — backward compat holds through z-refinement addition
**Plans:** 3 plans
Plans:
- [ ] 08-01-PLAN.md — Model z-fields (nz, z_position) + result z-metadata + ZREF-05 analytical test
- [ ] 08-02-PLAN.md — Network builder z-refinement + solver reshape
- [ ] 08-03-PLAN.md — Postprocessing z-adaptation + backward compat regression

### Phase 9: 3D GUI and ELED Zone Preset
**Goal**: Engineers can control z-refinement and material zones through the GUI without editing JSON, view any z-plane of the 3D result, and get a correctly zoned ELED cross-section model from the architecture dropdown with no manual zone entry
**Depends on**: Phase 8
**Requirements**: GUI3D-01, GUI3D-02, GUI3D-03, GUI3D-04, GUI3D-05, ELED-01, ELED-02
**Success Criteria** (what must be TRUE):
  1. User can move a z-plane slider in the temperature map panel and the displayed map updates to show the correct z-sublayer within the selected layer — without recreating the figure
  2. User can add, edit, and delete rectangular material zone rows in the Layers tab; the zone preview overlay updates immediately to show material region boundaries on the layer footprint
  3. The status bar shows the total node count and displays a warning before solve if the count exceeds 300k
  4. User can select ELED from the architecture dropdown and get a layer whose cross-section is automatically divided into the correct lateral zones: metal frame, FR4+LED board, air gap, and LGP bulk — with widths drawn from the ELED geometry configuration
  5. A simulation of the ELED zoned project shows two heat paths active: higher temperature on the FR4+LED board zone (primary path to metal) and a secondary gradient toward the LGP
**Plans:** 3 plans
Plans:
- [ ] 09-01-PLAN.md — Z-slice combo, nz spinbox in Layers tab, node count in status bar
- [ ] 09-02-PLAN.md — Material zone editor with preview canvas, zone overlay on temperature map
- [ ] 09-03-PLAN.md — ELED cross-section zone preset with generate function and human verification

## Progress

**Execution Order:**
Phases execute in numeric order: 7 -> 8 -> 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 4/4 | Complete | 2026-03-14 |
| 2. Results | v1.0 | 4/4 | Complete | 2026-03-14 |
| 3. Simulation Capabilities | v1.0 | 6/6 | Complete | 2026-03-14 |
| 4. Polish | v1.0 | 4/4 | Complete | 2026-03-14 |
| 5. Distribution | v1.0 | 3/3 | Complete | 2026-03-14 |
| 6. Architecture Support | v1.0 | 3/3 | Complete | 2026-03-14 |
| 7. 3D Solver Core | v2.0 | 0/2 | Planning complete | - |
| 8. Z-Refinement | v2.0 | 0/3 | Planning complete | - |
| 9. 3D GUI and ELED Zone Preset | v2.0 | 0/3 | Planning complete | - |
