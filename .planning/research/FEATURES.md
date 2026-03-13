# Feature Research

**Domain:** Desktop thermal simulation engineering tool (RC-network solver, display/automotive)
**Researched:** 2026-03-14
**Confidence:** MEDIUM — professional simulation tool UX patterns are well-documented from COMSOL, Ansys Icepak, and Zemax; Phase 4-specific implementation details drawn from training data and verified against current documentation where possible.

---

## Context: What Already Exists (Phase 1-3)

The following are DONE and are NOT features to build in Phase 4:

- 2.5D RC thermal network solver (steady-state + transient, implicit Euler)
- Material model with anisotropic conductivity, emissivity, interface resistance
- Layer stack, heat sources (full-area, rectangle, circle), LED array templates
- Convection + linearized radiation boundary conditions
- Virtual probe points with time histories
- CLI runner: steady/transient, CSV export, PNG plots
- JSON project save/load with full round-trip serialization
- PySide6 GUI: tabbed editor (materials, layers, heat sources, boundaries, probes), results dashboard, structure preview
- Embedded matplotlib: temperature maps, probe histories, layer profiles
- Material library presets (aluminum, copper, FR4, etc.)
- Analytical validation test suite

Phase 4 elevates this from a working prototype to a professional internal tool. The features below are evaluated in that framing — "would a thermal engineer who uses Zemax or Icepak notice if this is missing?"

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in a professional simulation tool. Missing = tool feels like a script, not a product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Undo/Redo for project edits** | Every desktop engineering tool (Zemax, COMSOL, all CAD) has undo/redo. Absent = users fear editing. | MEDIUM | Qt provides `QUndoStack` / `QUndoCommand` natively; requires wrapping each edit operation as a Command. This is non-trivial but well-understood. |
| **Inline validation feedback in editors** | Professional tools show red borders or warning icons on invalid inputs immediately (e.g. negative thickness, missing material reference). | LOW | Extend `__post_init__` validation to surface in GUI via field-level visual feedback. QValidator or post-edit signal checks. |
| **Run/Cancel simulation with progress indicator** | Engineers expect to be able to cancel a long run. No progress bar on a 30-second transient feels broken. | MEDIUM | Requires running solver in a QThread + progress callback. Transient loop already has time steps — natural progress unit. |
| **Status bar with simulation state** | Icepak, COMSOL, and Zemax all show solver status, last run time, and current file state in a bottom bar. | LOW | QStatusBar with: file path (modified indicator), last run time, solver state. |
| **Auto-save / unsaved changes indicator** | Window title asterisk on unsaved changes is expected in every desktop engineering tool. | LOW | Track dirty state on project changes; update title bar with `*` prefix. |
| **All CLI capabilities accessible from GUI** | Engineers using the GUI should not need to drop to terminal for any workflow step. Currently CSV export, CLI-only flags, and batch-mode are not fully exposed in GUI. | MEDIUM | Expose: output directory picker, CSV export button, mode selection, all solver options. |
| **PDF engineering report export** | Professional tools generate reports for design reviews, handoffs, and documentation. Icepak auto-generates reports with screenshots, probe tables, and material summaries. | HIGH | ReportLab + matplotlib figures embedded as images. Sections: project summary, stack table, boundary conditions, temperature maps per layer, probe history plots, key metrics table (T_max, T_avg, hotspots). |
| **Layer/material/source inline editing** | COMSOL and Zemax let users double-click items in a tree to edit them in place, not just through a side-panel form. Editing feels direct. | MEDIUM | Replace current tab-per-entity-type with a tree view + inline edit dialogs. Or improve the current form editors to feel more direct. |
| **Consistent keyboard shortcuts** | Ctrl+S (save), Ctrl+Z/Y (undo/redo), F5 (run), Escape (cancel) — professional tools honor these without exception. | LOW | Map standard keyboard shortcuts throughout. |
| **Structured results summary table** | After every run, a summary table showing T_max, T_avg, T_min per layer, plus hotspot rank — this is the first thing a thermal engineer looks at. | LOW | Already partially in postprocess.py; expose as a formatted table in a dedicated Results Summary panel. |

### Differentiators (Competitive Advantage)

Features that elevate the tool beyond a script wrapper — what makes it the tool engineers reach for over opening Python themselves.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Parametric sweep engine** | Engineers need to answer "how does T_max change with 10% vs 20% copper thickness?" without manually re-running. This is the most requested feature class in thermal tools (COMSOL parametric study, Icepak sensitivity). | HIGH | Define sweep: parameter name + value list + run label. Execute N sequential solves. Results table: one row per run, columns = key metrics. Export to CSV. Plot overlay: selected metric vs parameter value. |
| **Time-varying heat sources (power cycling)** | Real-world display panels have duty cycles — LEDs pulse, SoCs have burst workloads. Steady-state doesn't capture peak temperature under cycling. | HIGH | Model: heat source gets optional `power_profile` = list of (time, power) tuples. Network builder interpolates power at each transient timestep. UI: profile editor (table + mini-plot). |
| **Results comparison view (multi-run overlay)** | After parametric sweep or comparing design variants, overlaying probe histories on one plot and comparing T_max tables side-by-side is the core workflow. MATLAB Simulation Data Inspector, AnyLogic Compare Runs, and COMSOL all have this. | MEDIUM | Store named result snapshots. Comparison tab: select 2+ snapshots, render overlay probe plot and side-by-side metric table. |
| **Material library import/export (JSON/CSV)** | Ansys supports XML import of custom material libraries; teams share material databases across projects. Engineers want to add a new TIM or substrate and share it with colleagues. | MEDIUM | "User materials" library separate from built-in presets. Export as JSON. Import from JSON with merge-or-replace semantics. GUI material picker shows library source tag. |
| **One-click packaged launcher (.exe or batch)** | Non-programmer engineers won't run `python -m thermal_sim.app.gui`. A double-click executable is the difference between "a tool I use" and "a thing IT manages". | MEDIUM | PyInstaller one-folder bundle (faster startup than one-file for large scipy/matplotlib bundles). `run_gui.bat` as fallback for in-repo use. Icon branding. |
| **Hotspot annotation on temperature maps** | Professional tools like Icepak label the top-N hotspot locations directly on the temperature map. Engineers immediately see where problems are without reading a table. | LOW | Extend `plot_temperature_map()` to accept `annotate_hotspots=N` parameter. Plot text markers at top-N hotspot cell centers with temperature values. |
| **Project templates / example library** | Zemax ships with example files showing optical system types. COMSOL has an Application Library. New users start with a working example, not a blank canvas. | LOW | Already have 3 example JSON files (Phase 2). Expose these in a "New From Template" dialog in the GUI, with thumbnail previews showing the geometry. |
| **Expanded validation datasets with comparison plots** | Internal tools gain trust when their results visibly agree with analytical solutions or published benchmarks. A "Validation" tab showing solver vs analytical curves builds engineer confidence. | MEDIUM | Extend existing validation tests. Add a GUI "Validation Report" mode that runs all analytical test cases and displays agreement plots. |

### Anti-Features (Commonly Requested, Often Problematic)

Features to deliberately NOT build in Phase 4. These seem like good ideas but create disproportionate complexity or scope creep.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Temperature-dependent material properties** | "More accurate" — conductivity of metals does vary with temperature. Engineers know this. | Requires nonlinear solve loop, breaks current sparse linear solver pipeline entirely. 10x complexity increase for marginal accuracy at the operating temperature ranges this tool targets (25-120°C). | Add a documentation note: "Properties assumed constant; valid for typical electronics operating range. Contact TIM vendor for high-T extrapolations." |
| **Undo/redo on simulation results** | Seems natural — "undo last solve". | Results are immutable derived data; the project model is the source of truth. Undoing a solve means re-running the previous project state, which is expensive and confusing. | Undo applies to project edits only (not solver runs). Named result snapshots provide the "go back to previous run" workflow instead. |
| **Web-based report viewer** | "So I can share results in a browser" | Adds a web server, HTML templating, and a different rendering pipeline. Breaks the self-contained desktop tool model. | PDF report is the right artifact for sharing — opens without any special software, printable, archivable. |
| **Cloud sync / multi-user project sharing** | "Collaborate with remote colleagues" | Requires authentication, conflict resolution, server infrastructure. Completely out of scope for an internal desktop tool distributed via file share. | Share project JSON files + PDF reports over existing file share / email. |
| **3D visualization / CAD import** | "I want to see the real geometry" | This is a 2.5D RC model — the physics abstraction is layered; 3D geometry is not the model. Importing CAD would require a mesher, geometry engine, and would invalidate the entire RC-network approach. | Structure preview dialog (already built) shows the layer stack. For 3D, use Icepak. This tool's value is speed and simplicity. |
| **Auto-meshing refinement / convergence loops** | "The mesh should refine automatically until converged" | Adaptive meshing requires repeated network rebuilds, a convergence criterion loop, and significantly more memory. The tool's value proposition is sub-second to seconds solves. | Expose grid resolution as a user-visible parameter. Document that the validation tests confirm convergence at recommended resolution. |
| **Real-time (live-updating) simulation** | "Update results as I type" | Transient solves can take 10-60 seconds. Live updates would require background threading for every edit and complex result invalidation logic. | Run button with clear simulation state indicator (stale / current). Progress bar for long solves. |
| **Built-in Python scripting console** | Power users sometimes want to script from within the tool | Adds a significant GUI component (QCodeEditor), sandboxing concerns, and doubles the surface area for bugs. | CLI is already the scripting interface. Engineers can run CLI from terminal or batch files. |

---

## Feature Dependencies

```
[Parametric Sweep Engine]
    └──requires──> [Results Comparison View]
                       └──enhances──> [PDF Report Export]

[Time-Varying Heat Sources]
    └──requires──> [Run/Cancel with Progress Indicator]
                       (transient runs get much longer with cycling profiles)

[PDF Report Export]
    └──requires──> [Structured Results Summary Table]
    └──enhances──> [Hotspot Annotation on Temperature Maps]

[Material Library Import/Export]
    └──requires──> [Expanded Material Library (built-in presets)]

[One-Click Packaged Launcher]
    └──requires──> [All CLI Capabilities in GUI]
                       (packaging only makes sense when GUI is complete)

[Undo/Redo]
    └──enables──> [Inline Validation Feedback]
                       (validation can surface errors that undo can fix)

[Results Comparison View]
    └──enhances──> [Parametric Sweep Engine]
    └──enhances──> [Project Templates / Example Library]

[Keyboard Shortcuts]
    └──enhances──> [Undo/Redo]
```

### Dependency Notes

- **Parametric Sweep requires Results Comparison View:** Sweep output is meaningless without a way to compare and inspect the N result sets side by side. Build both in the same phase or the sweep feels incomplete.
- **Time-Varying Heat Sources requires Run/Cancel Progress:** Power cycling transient runs will be 5-20x longer than standard transients. Without cancellation, engineers will force-quit the app.
- **PDF Report requires Structured Results Summary:** The report pulls from the same metrics table. Build summary table first; report assembles from it.
- **Packaging requires GUI feature parity:** Bundling an incomplete GUI into an .exe just ships an incomplete tool permanently. Packaging should be the final step after all GUI capabilities are exposed.
- **Undo/Redo is foundational:** Implement early in Phase 4 because every subsequent GUI feature should be wrapped in QUndoCommand objects. Retrofitting undo is painful.

---

## MVP Definition (Phase 4 Framing)

This is an existing product, not a greenfield MVP. Phase 4 "MVP" means: what is the minimum set of features that makes this feel like a professional internal tool rather than a prototype?

### Must Ship in Phase 4 (Core Polish)

- [ ] **Undo/Redo** — engineers who fear editing don't use the tool
- [ ] **Run/Cancel with progress indicator** — transient runs need a cancel button
- [ ] **Status bar** — file state, last run time, solver status
- [ ] **All CLI capabilities in GUI** — CSV export, output directory, mode selection
- [ ] **Structured results summary table** — T_max/T_avg/T_min per layer, hotspot rank
- [ ] **PDF engineering report export** — enables design review handoffs
- [ ] **Parametric sweep engine + results comparison** — core differentiator engineers need
- [ ] **One-click packaged launcher** — adoption depends on this for non-programmer colleagues

### Add After Core Is Working

- [ ] **Time-varying heat sources (power cycling)** — high value, high complexity; add once sweep engine is stable
- [ ] **Material library import/export** — medium value; add when material customization requests come in
- [ ] **Hotspot annotation on maps** — low complexity, high visual impact; quick win late in phase
- [ ] **Expanded validation with GUI report** — trust-building; add as polish at end of phase

### Defer to Future Phase

- [ ] **Project templates / New From Template dialog** — already have example files; GUI discovery deferred
- [ ] **Comprehensive keyboard shortcut map** — partial shortcuts first, full map later

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Undo/Redo | HIGH | MEDIUM | P1 |
| Run/Cancel + progress | HIGH | MEDIUM | P1 |
| Structured results summary table | HIGH | LOW | P1 |
| Status bar + dirty state | MEDIUM | LOW | P1 |
| All CLI capabilities in GUI | HIGH | MEDIUM | P1 |
| PDF report export | HIGH | HIGH | P1 |
| Parametric sweep engine | HIGH | HIGH | P1 |
| Results comparison view | HIGH | MEDIUM | P1 |
| One-click packaged launcher | HIGH | MEDIUM | P1 |
| Hotspot annotation on maps | MEDIUM | LOW | P2 |
| Time-varying heat sources | HIGH | HIGH | P2 |
| Material library import/export | MEDIUM | MEDIUM | P2 |
| Expanded validation / GUI report | MEDIUM | MEDIUM | P2 |
| Project templates / New dialog | LOW | LOW | P3 |
| Keyboard shortcut map | LOW | LOW | P3 |

**Priority key:**
- P1: Phase 4 core — ships before packaging
- P2: Phase 4 bonus — adds polish but not blockers
- P3: Future phase

---

## Competitor Feature Analysis

Reference tools: Ansys Icepak (electronics thermal), COMSOL Multiphysics (general FEA), Ansys Zemax OpticStudio (optical design, same user persona as target audience).

| Feature | Icepak | COMSOL | Zemax | Our Phase 4 Approach |
|---------|--------|--------|-------|----------------------|
| Report generation | Auto report with screenshots, probe tables, fan operating points | Template-based PDF/HTML report with result figures | PDF report via Report Designer | ReportLab PDF with matplotlib figures embedded; fixed structure, not templated |
| Parametric sweep | Built-in parametric solver; tabular results display | Full parametric sweep with probe table accumulation, all-combinations mode | Optimization + tolerance analysis (more advanced) | Sequential solve loop over user-defined parameter × value table; CSV + comparison plot |
| Results comparison | Solution Overview Reporter (live metrics); result archive in AEDT project | Compare datasets in Simulation Data Inspector-style view | Compare surfaces between system variants | Named result snapshots; comparison tab with overlay plots and side-by-side metric table |
| Progress/cancellation | Real-time convergence monitor; cancel button | Progress bar; stop solver button | Progress dialog for ray tracing | QThread solver + progress signal + cancel event |
| Material management | Granta materials database; XML import/export | Built-in material database + CSV import | Built-in + user-defined materials | Built-in presets + user JSON library with import/export |
| Undo/redo | Full undo history across all model edits | Full undo/redo in GUI | Full undo/redo | Qt QUndoStack wrapping all project edit operations |
| Packaging/deployment | License-server or node-locked EXE; enterprise IT managed | EXE installer; license required | EXE installer; license required | PyInstaller one-folder bundle; no admin required; runs from user-space |
| Time-varying sources | Tabular boundary conditions for transient; power profiles | Time-dependent expressions for heat sources | N/A (optical, not thermal) | `power_profile` list on HeatSource; interpolated in transient loop |

---

## Complexity Notes by Feature

### PDF Report Export — HIGH complexity
- ReportLab Platypus layout engine (MEDIUM learning curve)
- Must render matplotlib figures to BytesIO and embed as images — non-trivial
- Report template: 8-10 sections, each requiring conditional content based on sim type (steady vs transient)
- Page layout and typography require explicit attention; professional look requires iteration
- Source: pythonguis.com tutorial (updated Dec 2025) confirms PySide6 + ReportLab + worker threads is a proven pattern

### Parametric Sweep Engine — HIGH complexity
- N sequential solver calls: straightforward if solvers are stateless (they are)
- Progress reporting across N runs (not just within one run) requires two-level progress bar
- Results storage: in-memory dict of {run_label: SimResult} — size can grow; need to decide if persisted to disk
- UI: parameter table editor + run button + results table + comparison plot panel — 4 interconnected components
- CSV export of sweep results table is low complexity

### Time-Varying Heat Sources — HIGH complexity
- Model layer: `power_profile` is a list of `(time_s: float, power_W: float)` tuples on `HeatSource`
- Network builder: must interpolate power at each timestep from profile — numpy interp, straightforward
- JSON serialization: profiles serialize as list-of-lists
- Backward compat: existing projects without profiles must default to constant power (current behavior) — no breakage
- UI: tabular profile editor + small preview plot of the power vs time curve
- Risk: very large profiles (1000+ points) at fine timesteps can make network rebuild per step expensive — profile-aware rebuild caching may be needed

### One-Click Packaging — MEDIUM complexity
- PyInstaller 6.x with PySide6 hook is well-supported and tested (pythonguis.com tutorial verified)
- scipy + numpy are bundled correctly out of the box per PyInstaller docs
- matplotlib requires explicit collection of `matplotlib.libs` on some builds
- One-folder bundle recommended over one-file (faster startup for large scientific Python bundles; one-file must unpack to temp on every launch — 2-3s overhead)
- Bundle size estimate: ~250-400 MB for the one-folder distribution (numpy + scipy + matplotlib + PySide6)
- SmartScreen warnings on unsigned EXE are a real friction point for Windows internal distribution; document in packaging README

### Undo/Redo — MEDIUM complexity
- Qt's `QUndoStack` + `QUndoCommand` pattern is the correct approach (confirmed in PySide6 docs)
- Each project edit must be wrapped: `AddLayerCommand`, `EditMaterialCommand`, `DeleteHeatSourceCommand`, etc.
- Connecting QUndoStack to menu Edit > Undo/Redo with auto-updated text is provided by Qt
- Risk: LED array template operations and bulk operations (e.g., "reset all boundary conditions") need careful command grouping
- Results should NOT be in the undo stack — only project model mutations

---

## Sources

- Ansys Icepak 2025 R2 release notes: https://www.ansys.com/blog/whats-new-ansys-icepak-2025-r2
- COMSOL parametric sweep documentation (v6.3): https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_solver.36.048.html
- Thermal Analysis Methodology Best Practices (Electronics Cooling, 2024): https://www.electronics-cooling.com/2024/09/thermal-analysis-methodology-best-practices/
- PySide6 QUndoStack documentation: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QUndoStack.html
- Packaging PySide6 with PyInstaller & InstallForge (pythonguis.com, updated 2025): https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/
- PyInstaller official docs: https://pyinstaller.org/en/stable/operating-mode.html
- ReportLab for engineering PDF reports (pythonguis.com, Dec 2025): https://www.pythonguis.com/examples/python-pdf-report-generator/
- ReportLab + matplotlib chart integration: https://woteq.com/how-to-generate-charts-with-reportlab-and-matplotlib/
- MATLAB Simulation Data Inspector (results comparison pattern): https://www.mathworks.com/help/simulink/slref/simulationdatainspector.html
- Ansys Materials data for simulation (material library patterns): https://www.ansys.com/content/dam/product/materials/materials-data-simulation.pdf
- Power cycling / duty-cycle transient thermal analysis: https://pmc.ncbi.nlm.nih.gov/articles/PMC8467052/

---
*Feature research for: Desktop thermal simulation tool (blu-thermal-simulation Phase 4)*
*Researched: 2026-03-14*
