# Requirements: Thermal Simulator Phase 4

**Defined:** 2026-03-14
**Core Value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access.

## v1 Requirements

### GUI Foundation

- [x] **GUI-01**: MainWindow refactored into SimulationController, TableDataParser, and PlotManager
- [x] **GUI-02**: User can undo/redo any project edit via Ctrl+Z/Ctrl+Y
- [x] **GUI-03**: User can run simulation with visible progress bar and cancel button
- [x] **GUI-04**: Status bar shows file path, modified indicator, last run time, and solver state
- [x] **GUI-05**: Window title shows asterisk when project has unsaved changes
- [x] **GUI-06**: All CLI capabilities accessible from GUI (output dir, CSV export, mode selection)
- [x] **GUI-07**: Keyboard shortcuts: Ctrl+S save, Ctrl+Z/Y undo/redo, F5 run, Escape cancel

### Results & Reporting

- [x] **RSLT-01**: Structured results summary table showing T_max/T_avg/T_min per layer and hotspot rank
- [x] **RSLT-02**: Top-N hotspot locations annotated directly on temperature map plots
- [x] **RSLT-03**: User can export PDF engineering report with stack summary, temperature maps, probe data, and key metrics
- [x] **RSLT-04**: User can save named result snapshots and compare 2+ runs with overlay probe plots and side-by-side metric tables

### Simulation Capabilities

- [x] **SIM-01**: User can define parametric sweep (parameter + value list) and execute multiple solver runs
- [x] **SIM-02**: Sweep results displayed as comparison table and parameter-vs-metric plots
- [x] **SIM-03**: User can define time-varying power profiles (duty cycles) on heat sources
- [x] **SIM-04**: Transient solver interpolates power profile at each timestep

### Materials & Data

- [x] **MAT-01**: User can import/export custom material libraries as JSON
- [x] **MAT-02**: Material picker distinguishes built-in presets from user-defined materials
- [x] **MAT-03**: Additional analytical validation test cases with comparison plots

### Visual Polish

- [x] **PLSH-01**: Professional qt-material theme applied across all GUI elements
- [x] **PLSH-02**: QDockWidget-based layout replacing fixed splitter panels
- [x] **PLSH-03**: Inline validation feedback (visual indicators on invalid inputs)

### Distribution

- [ ] **DIST-01**: PyInstaller --onedir bundle that launches GUI with double-click on Windows
- [ ] **DIST-02**: Bundle works without admin access on managed Windows machines
- [x] **DIST-03**: Resource path helper centralized for packaged and dev builds

## v2 Requirements

### Future Enhancements

- **TMPL-01**: New From Template dialog with thumbnail previews of example projects
- **KEYS-01**: Comprehensive keyboard shortcut map covering all operations
- **VAL-01**: GUI "Validation Report" mode that runs all analytical tests and displays agreement plots
- **SNAP-01**: Persist result snapshots to disk alongside project JSON

## Out of Scope

| Feature | Reason |
|---------|--------|
| Temperature-dependent material properties | Requires nonlinear solver loop; 10x complexity for marginal accuracy in 25-120°C operating range |
| CFD / fluid flow modeling | Intentionally an RC-network approximation tool, not a CFD solver |
| Web-based UI or report viewer | Desktop PySide6 is the target; PDF is the sharing artifact |
| Cloud sync / multi-user collaboration | Out of scope for internal desktop tool distributed via file share |
| 3D visualization / CAD import | Physics model is 2.5D layered; 3D geometry would invalidate the RC-network approach |
| Auto-mesh refinement / convergence loops | Tool's value is sub-second solves; expose grid resolution as user parameter instead |
| Built-in Python scripting console | CLI is already the scripting interface |
| Real-time live-updating simulation | Transient solves take 10-60s; use explicit Run button with progress instead |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GUI-01 | Phase 1 — Foundation | Complete (01-01, 01-02) |
| GUI-02 | Phase 1 — Foundation | Complete (01-03) |
| GUI-03 | Phase 1 — Foundation | Complete (01-02) |
| GUI-04 | Phase 1 — Foundation | Complete (01-02) |
| GUI-05 | Phase 1 — Foundation | Complete (01-03) |
| GUI-06 | Phase 1 — Foundation | Complete (01-03) |
| GUI-07 | Phase 1 — Foundation | Complete (01-03) |
| RSLT-01 | Phase 2 — Results | Complete (02-01) |
| RSLT-02 | Phase 2 — Results | Complete (02-01) |
| RSLT-03 | Phase 2 — Results | Complete (02-01) |
| RSLT-04 | Phase 2 — Results | Complete (02-03) |
| SIM-01 | Phase 3 — Simulation Capabilities | Complete |
| SIM-02 | Phase 3 — Simulation Capabilities | Complete |
| SIM-03 | Phase 3 — Simulation Capabilities | Complete |
| SIM-04 | Phase 3 — Simulation Capabilities | Complete |
| MAT-01 | Phase 3 — Simulation Capabilities | Complete |
| MAT-02 | Phase 3 — Simulation Capabilities | Complete |
| MAT-03 | Phase 3 — Simulation Capabilities | Complete |
| PLSH-01 | Phase 4 — Polish | Complete |
| PLSH-02 | Phase 4 — Polish | Complete |
| PLSH-03 | Phase 4 — Polish | Complete |
| DIST-01 | Phase 5 — Distribution | Pending |
| DIST-02 | Phase 5 — Distribution | Pending |
| DIST-03 | Phase 5 — Distribution | Complete |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 after Phase 2 Plan 04 human verification — all RSLT requirements confirmed by tester*
