# Requirements: Thermal Simulator

**Defined:** 2026-03-14
**Core Value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access.

## v1 Requirements (Complete)

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

- [x] **DIST-01**: PyInstaller --onedir bundle that launches GUI with double-click on Windows
- [x] **DIST-02**: Bundle works without admin access on managed Windows machines
- [x] **DIST-03**: Resource path helper centralized for packaged and dev builds

### Architecture Support

- [x] **ARCH-01**: LEDArray supports grid (DLED), edge (ELED), and custom modes with expand() producing correct HeatSource lists
- [x] **ARCH-02**: DLED stack template provides complete layer/material/boundary/LED defaults for direct-lit architecture
- [x] **ARCH-03**: ELED stack template provides complete layer/material/boundary/LED defaults for edge-lit architecture
- [x] **ARCH-04**: DLED zone-based dimming with per-zone power assignment produces asymmetric thermal patterns
- [x] **ARCH-05**: GUI architecture dropdown (DLED/ELED/Custom) auto-populates project from template
- [x] **ARCH-06**: LED Arrays tab adapts UI based on architecture selection (DLED grid panel, ELED edge panel, Custom table)

## v2 Requirements

### 3D Solver Core

- [x] **SOLV-01**: Network builder supports per-cell material assignment via MaterialZone rectangular descriptors rasterized at build time
- [x] **SOLV-02**: Lateral conductance between cells of different materials uses harmonic-mean formula
- [x] **SOLV-03**: NodeLayout abstraction centralizes node indexing for variable z-nodes per layer
- [x] **SOLV-04**: Existing v1.0 projects load and solve with identical temperatures (backward-compat regression test)

### Z-Refinement

- [x] **ZREF-01**: Layer model supports `nz` field (default 1) for multiple z-nodes through thickness
- [x] **ZREF-02**: Internal z-z links within a layer use `dz/(k*A)` with no interface resistance
- [x] **ZREF-03**: Interface resistance applies only at true layer boundaries, not internal z-sublayers
- [x] **ZREF-04**: Steady-state and transient solvers handle 3D node count and reshape results correctly
- [x] **ZREF-05**: Analytical validation test: single-layer slab with nz=5 matches 1D through-thickness profile

### 3D GUI & Visualization

- [x] **GUI3D-01**: Z-plane slice selector in temperature map (slider to pick z-sublayer within a layer)
- [x] **GUI3D-02**: Live node count display in status bar, warning at >300k nodes before solve
- [x] **GUI3D-03**: Per-layer `nz` spinbox in Layers tab
- [x] **GUI3D-04**: Material zone editor per layer (add/remove rectangular zones with material assignment)
- [x] **GUI3D-05**: Zone preview overlay on temperature map showing material region boundaries

### ELED Architecture Fix

- [x] **ELED-01**: ELED template generates correct cross-section zones: metal frame, FR4+LED PCB, air gap, LGP as lateral material zones at the LGP z-level
- [x] **ELED-02**: ELED thermal model captures both heat paths: LED→FR4→metal (primary) and LED→air→LGP (secondary)

### Edge Layer Stacking

- [x] **EDGE-01**: Layer model supports `edge_layers` dict field with per-edge (bottom/top/left/right) ordered lists of lateral layers (material + thickness), serialized in project JSON
- [x] **EDGE-02**: Edge layers auto-generate MaterialZone rectangles at solve time; corners use outermost material (frame); edge zones + manual zones coexist with manual winning on overlap
- [x] **EDGE-03**: ELED architecture selection auto-populates LGP layer edge layers with correct perimeter structure (frame+air+PCB on LED edges, frame+air on non-LED edges)

### 3D Assembly Visualization

- [x] **VIS3D-01**: Interactive 3D view (PyVista/VTK) showing assembly as color-coded blocks with rotation, pan, zoom, and layer labels
- [x] **VIS3D-02**: Explode slider separates layers vertically for inspecting internal structure including edge layers
- [x] **VIS3D-03**: 3D results view shows temperature data overlaid on assembly geometry after solving

### Voxel-Based 3D Solver

- [x] **VOX-01**: Assembly block model (named 3D rectangular solids with position, size, material) with frozen dataclass and to_dict/from_dict serialization
- [x] **VOX-02**: Conformal mesh generation snapping to all block boundaries in x, y, and z, producing non-uniform Cartesian grid
- [x] **VOX-03**: Per-voxel material assignment via cell-center containment test; empty voxels filled with air (k=0.026 W/mK); last-defined-wins on overlap
- [x] **VOX-04**: Voxel network builder assembling COO sparse conductance matrix with harmonic-mean conductance at material boundaries and non-uniform cell geometry
- [x] **VOX-05**: Steady-state solver using bicgstab+ILU preconditioner for >5k nodes, spsolve for smaller problems
- [x] **VOX-06**: Transient solver using splu LU prefactoring for implicit Euler time-stepping
- [x] **VOX-07**: Surface source placement on named block faces (LEDs as separate heat source objects, not assembly blocks)
- [x] **VOX-08**: Auto-detect exposed boundary faces (voxel faces not touching another block) and apply convection/radiation BCs from named boundary groups
- [x] **VOX-09**: Analytical validation tests (1D resistance chain, 2-node network, RC transient decay) rewritten using assembly blocks
- [ ] **VOX-10**: CLI and project IO for new VoxelProject JSON format (clean break from old DisplayProject format)
- [ ] **VOX-11**: GUI block editor replacing layer editor — table-based entry for blocks, sources, boundaries, probes, mesh config
- [ ] **VOX-12**: 3D PyVista view with interactive slice planes, block transparency/hide, temperature threshold filter, and probe markers
- [ ] **VOX-13**: DLED and ELED ready-to-run example JSON files using new assembly block format
- [ ] **VOX-14**: Old Layer/Zone/EdgeLayer model files, old network builder, and old solver code removed (clean break; git history preserves)

## Future Enhancements

- **TMPL-01**: New From Template dialog with thumbnail previews of example projects
- **KEYS-01**: Comprehensive keyboard shortcut map covering all operations
- **VAL-01**: GUI "Validation Report" mode that runs all analytical tests and displays agreement plots
- **SNAP-01**: Persist result snapshots to disk alongside project JSON

## Out of Scope

| Feature | Reason |
|---------|--------|
| Temperature-dependent material properties | Requires nonlinear solver loop; 10x complexity for marginal accuracy in 25-120°C operating range |
| CFD / fluid flow modeling | Intentionally an RC-network approximation tool, not a CFD solver |
| Unstructured/tetrahedral meshing | Structured Cartesian grid with material zones sufficient for display modules |
| Polygon material zones | Rectangular zones cover all display module geometries (strips, patches, edge regions) |
| Web-based UI or report viewer | Desktop PySide6 is the target; PDF is the sharing artifact |
| Auto-mesh refinement | Tool's value is fast solves; expose grid resolution as user parameter instead |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GUI-01 | Phase 1 — Foundation | Complete |
| GUI-02 | Phase 1 — Foundation | Complete |
| GUI-03 | Phase 1 — Foundation | Complete |
| GUI-04 | Phase 1 — Foundation | Complete |
| GUI-05 | Phase 1 — Foundation | Complete |
| GUI-06 | Phase 1 — Foundation | Complete |
| GUI-07 | Phase 1 — Foundation | Complete |
| RSLT-01 | Phase 2 — Results | Complete |
| RSLT-02 | Phase 2 — Results | Complete |
| RSLT-03 | Phase 2 — Results | Complete |
| RSLT-04 | Phase 2 — Results | Complete |
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
| DIST-01 | Phase 5 — Distribution | Complete |
| DIST-02 | Phase 5 — Distribution | Complete |
| DIST-03 | Phase 5 — Distribution | Complete |
| ARCH-01 | Phase 6 — Architecture Support | Complete |
| ARCH-02 | Phase 6 — Architecture Support | Complete |
| ARCH-03 | Phase 6 — Architecture Support | Complete |
| ARCH-04 | Phase 6 — Architecture Support | Complete |
| ARCH-05 | Phase 6 — Architecture Support | Complete |
| ARCH-06 | Phase 6 — Architecture Support | Complete |
| SOLV-01 | Phase 7 — 3D Solver Core | Complete |
| SOLV-02 | Phase 7 — 3D Solver Core | Complete |
| SOLV-03 | Phase 7 — 3D Solver Core | Complete |
| SOLV-04 | Phase 7 — 3D Solver Core | Complete |
| ZREF-01 | Phase 8 — Z-Refinement | Complete |
| ZREF-02 | Phase 8 — Z-Refinement | Complete |
| ZREF-03 | Phase 8 — Z-Refinement | Complete |
| ZREF-04 | Phase 8 — Z-Refinement | Complete |
| ZREF-05 | Phase 8 — Z-Refinement | Complete |
| GUI3D-01 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| GUI3D-02 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| GUI3D-03 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| GUI3D-04 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| GUI3D-05 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| ELED-01 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |
| ELED-02 | Phase 9 — 3D GUI and ELED Zone Preset | Complete |

| EDGE-01 | Phase 10 — Edge Layers and 3D Preview | Complete |
| EDGE-02 | Phase 10 — Edge Layers and 3D Preview | Complete |
| EDGE-03 | Phase 10 — Edge Layers and 3D Preview | Complete |
| VIS3D-01 | Phase 10 — Edge Layers and 3D Preview | Complete |
| VIS3D-02 | Phase 10 — Edge Layers and 3D Preview | Complete |
| VIS3D-03 | Phase 10 — Edge Layers and 3D Preview | Complete |

| VOX-01 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-02 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-03 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-04 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-05 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-06 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-07 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-08 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-09 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-10 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-11 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-12 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-13 | Phase 11 — Voxel-Based 3D Solver | Planned |
| VOX-14 | Phase 11 — Voxel-Based 3D Solver | Planned |

**Coverage:**
- v1 requirements: 30 total (all complete)
- v2 requirements: 22 total (22 complete, 0 planned)
- v3 requirements: 14 total (0 complete, 14 planned)
- Mapped to phases: 30 (v1) + 22 (v2) + 14 (v3)
- Unmapped: 0

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-16 — Phase 11 requirements added: VOX-01 through VOX-14 for voxel-based 3D solver*
