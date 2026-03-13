# Architecture

**Analysis Date:** 2026-03-14

## Pattern Overview

**Overall:** Layered thermal network RC solver with domain-driven design

**Key Characteristics:**
- 2.5D physics model: in-plane conduction per layer + through-thickness coupling
- Linear algebraic solver pipeline: Project model → network builder → sparse solver → postprocessor
- Thermal capacitance-aware for transient simulation (implicit Euler)
- Material/layer/heat-source abstraction with JSON persistence
- Dual interfaces: CLI for batch runs, PySide6 GUI for interactive design

## Layers

**Domain Models (`thermal_sim/models/`):**
- Purpose: Define simulation input structure (materials, layers, heat sources, boundaries, probes)
- Location: `thermal_sim/models/`
- Contains: Dataclasses for `Material`, `Layer`, `HeatSource`, `LEDArray`, `Probe`, `BoundaryConditions`, `DisplayProject` with validation and `to_dict()`/`from_dict()` round-trip serialization
- Depends on: Python stdlib only
- Used by: Network builder, I/O, UI, tests

**Network Builder (`thermal_sim/solvers/network_builder.py`):**
- Purpose: Convert a `DisplayProject` into discrete linear system (sparse conductance matrix A, forcing vector b, thermal capacity vector C)
- Location: `thermal_sim/solvers/network_builder.py`
- Contains: `Grid2D` spatial discretization, node indexing scheme, conductance link builders (in-plane, through-thickness, boundaries), heat source distribution
- Depends on: Domain models, NumPy, SciPy sparse, geometry utilities
- Used by: Both steady-state and transient solvers

**Physics Core (`thermal_sim/core/`):**
- Purpose: Constants, material library presets, geometry helpers, postprocessing
- Location: `thermal_sim/core/`
- Contains:
  - `constants.py`: Stefan-Boltzmann constant, physical constants
  - `geometry.py`: `Grid2D` class for mesh cell size calculations
  - `material_library.py`: Default material presets (aluminum, copper, FR4, etc.)
  - `postprocess.py`: Statistics extraction, probe readout, hotspot ranking, layer averages
- Depends on: NumPy
- Used by: Network builder, solvers, visualization, CLI

**Solvers (`thermal_sim/solvers/`):**
- Purpose: Compute temperature fields from thermal network
- Location: `thermal_sim/solvers/`
- Contains:
  - `steady_state.py`: `SteadyStateSolver` class - solves `A*T = b` via `scipy.sparse.linalg.spsolve`
  - `transient.py`: `TransientSolver` class - implicit Euler time integration with LU prefactoring and re-use
- Depends on: Network builder, SciPy sparse solvers, NumPy
- Used by: CLI, GUI, tests
- Returns: `SteadyStateResult` or `TransientResult` dataclasses containing temperature arrays shaped `[n_layers, ny, nx]`

**I/O (`thermal_sim/io/`):**
- Purpose: Load/save project files, export results
- Location: `thermal_sim/io/`
- Contains:
  - `project_io.py`: JSON serialization via model `to_dict()`/`from_dict()` methods
  - `csv_export.py`: CSV export for temperature maps and probe histories
- Depends on: Domain models, JSON, CSV
- Used by: CLI, GUI, examples

**Visualization (`thermal_sim/visualization/`):**
- Purpose: Matplotlib-based temperature map and curve plotting
- Location: `thermal_sim/visualization/plotting.py`
- Contains: `plot_temperature_map()` for spatial heatmaps, `plot_probe_history()` for time curves
- Depends on: Matplotlib, NumPy
- Used by: CLI (with --plot flag), GUI dashboard

**UI (`thermal_sim/ui/`):**
- Purpose: Interactive PySide6 desktop application for project editing and result visualization
- Location: `thermal_sim/ui/`
- Contains:
  - `main_window.py`: QMainWindow with tabbed editor (materials, layers, heat sources, LED arrays, boundaries, probes) and results dashboard (embedded matplotlib canvases)
  - `structure_preview.py`: Layer stack visualization
- Depends on: PySide6, domain models, solvers, postprocessing, I/O, visualization
- Used by: GUI launcher

**Application Entry Points (`thermal_sim/app/`):**
- Purpose: Command-line and GUI interfaces
- Location: `thermal_sim/app/`
- Contains:
  - `cli.py`: Argument parsing, orchestration of solver → postprocessing → export → visualization pipeline
  - `gui.py`: PySide6 QApplication initialization
- Depends on: All layers above

## Data Flow

**Steady-State Workflow:**

1. Load JSON project via `load_project()` → `DisplayProject` dataclass
2. Expand LED array templates via `project.expanded_heat_sources()`
3. Build network via `build_thermal_network(project)` → `ThermalNetwork` (sparse matrix A, vector b, capacity C)
4. Solve via `spsolve(A, b)` → temperature solution vector
5. Reshape to `[n_layers, ny, nx]` → `SteadyStateResult`
6. Postprocess via `basic_stats()`, `probe_temperatures()`, `top_n_hottest_cells()`
7. Export CSV and PNG (optional)
8. Print summary to console

**Transient Workflow:**

1. Load project, expand heat sources, build network (same as steady-state)
2. Prefactor LHS = `C/dt + A` via `splu()` for repeated factorization
3. Implicit Euler time loop:
   - RHS = `b + (C/dt) * T_n`
   - Solve via `splu.solve(RHS)` → `T_{n+1}`
   - Sample every `output_interval_s`
4. Collect sampled temperatures into `[nt, n_layers, ny, nx]` array
5. Postprocess final state and histories
6. Export CSV and PNG

**State Management:**

- `DisplayProject` is the single source of truth (domain model)
- Solvers are stateless; each call to `solve()` rebuilds network from project
- Results are immutable dataclasses
- GUI maintains project in memory and allows in-place edits with re-solve

## Key Abstractions

**Grid2D (Spatial Discretization):**
- Purpose: Encapsulates 2D mesh layout (Cartesian, regular spacing)
- Examples: `thermal_sim/core/geometry.py`
- Pattern: Frozen dataclass with derived properties (dx, dy, cell_area)

**ThermalNetwork (Discrete System):**
- Purpose: Represents the linear system before solving
- Examples: `thermal_sim/solvers/network_builder.py:ThermalNetwork`
- Pattern: Frozen dataclass containing sparse CSR matrix A, vectors b (forcing), c (capacity), grid metadata

**Material (Anisotropic Thermal Properties):**
- Purpose: Separates in-plane (lateral) and through-thickness conductivity
- Examples: `thermal_sim/models/material.py`
- Pattern: Frozen immutable dataclass; supports emissivity override for radiation boundary conditions

**LEDArray (Template Expansion):**
- Purpose: Parametric heat source array that expands to individual `HeatSource` objects
- Examples: `thermal_sim/models/heat_source.py:LEDArray`
- Pattern: Dataclass with `.expand()` method returning list of `HeatSource` instances

**Shape Polymorphism (Heat Sources):**
- Purpose: Support different power distribution footprints (full, rectangle, circle)
- Examples: `thermal_sim/models/heat_source.py:HeatSource.shape`
- Pattern: String-based discriminator in `__post_init__()` validation; network builder interprets in `_distribute_heat()`

**SurfaceBoundary (Convection + Radiation):**
- Purpose: Combine convection (h) and linearized radiation (4*eps*sigma*T_amb^3) into single effective h
- Examples: `thermal_sim/models/boundary.py:SurfaceBoundary`
- Pattern: Dataclass with optional `emissivity_override` for per-surface radiation tuning

## Entry Points

**CLI Runner (`python -m thermal_sim.app.cli`):**
- Location: `thermal_sim/app/cli.py:main()`
- Triggers: Direct invocation with argparse
- Responsibilities:
  - Parse arguments (--project, --mode, --output-dir, --plot, --plot-layer)
  - Load project, validate, optionally save normalized copy
  - Route to `_run_steady()` or `_run_transient()`
  - Orchestrate solver → postprocessing → export → console output

**GUI Launcher (`python -m thermal_sim.app.gui`):**
- Location: `thermal_sim/app/gui.py:main()`
- Triggers: Direct invocation
- Responsibilities:
  - Initialize PySide6 QApplication
  - Launch `MainWindow` (tabbed editor + results dashboard)
  - Handle file open/save, solver runs, result visualization

**Test Entry Points:**
- Location: `tests/test_*.py`
- Pattern: Direct instantiation of domain models and solvers for validation

## Error Handling

**Strategy:** Exceptions propagate; validation happens in `__post_init__()` methods

**Patterns:**
- Domain model validation in dataclass `__post_init__()` raises `ValueError` for invalid inputs
- Solver RuntimeError if convergence fails or mesh too coarse
- CLI catches RuntimeError and exits with code 2
- GUI displays QMessageBox for runtime errors
- Project loading via JSON deserializer catches malformed files

## Cross-Cutting Concerns

**Logging:** Print to console only; no file logging in current phase

**Validation:**
- Domain models validate state via `__post_init__()` (non-empty strings, positive dimensions, reference integrity)
- Network builder asserts conductances non-negative before adding links
- Solvers validate result shapes before returning

**Material Property Lookup:**
- `DisplayProject.material_for_layer(layer_index)` centralizes material retrieval
- Network builder fetches via this method for each layer

**Mesh Indexing:**
- Canonical node index: `layer_idx * (nx*ny) + iy * nx + ix`
- Grid2D provides cell centers for probe interpolation
- Result reshaping from flat vector to `[n_layers, ny, nx]` preserves this scheme

**JSON Serialization:**
- All domain classes implement `to_dict()` and `from_dict()`
- No external schema library; hand-written conversions in each class
- Preserves default values during round-trip

---

*Architecture analysis: 2026-03-14*
