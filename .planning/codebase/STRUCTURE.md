# Codebase Structure

**Analysis Date:** 2026-03-14

## Directory Layout

```
blu-thermal-simulation/
├── thermal_sim/                    # Main package (all source code)
│   ├── __init__.py
│   ├── app/                        # Entry points (CLI, GUI)
│   │   ├── __init__.py
│   │   ├── cli.py                  # Command-line runner
│   │   └── gui.py                  # GUI launcher
│   ├── core/                       # Physics constants, geometry, material library, postprocessing
│   │   ├── __init__.py
│   │   ├── constants.py            # Physical constants (Stefan-Boltzmann, etc.)
│   │   ├── geometry.py             # Grid2D mesh utilities
│   │   ├── material_library.py     # Default material presets
│   │   └── postprocess.py          # Statistics, probe readout, hotspot ranking
│   ├── models/                     # Domain dataclasses (no logic)
│   │   ├── __init__.py
│   │   ├── project.py              # DisplayProject, MeshConfig, TransientConfig
│   │   ├── material.py             # Material (anisotropic k)
│   │   ├── layer.py                # Layer (thickness, interface resistance)
│   │   ├── heat_source.py          # HeatSource, LEDArray
│   │   ├── boundary.py             # BoundaryConditions, SurfaceBoundary
│   │   └── probe.py                # Probe (virtual thermistor)
│   ├── solvers/                    # Linear system construction and solving
│   │   ├── __init__.py
│   │   ├── network_builder.py      # Grid discretization, matrix/vector assembly
│   │   ├── steady_state.py         # SteadyStateSolver (sparse direct solve)
│   │   └── transient.py            # TransientSolver (implicit Euler with LU)
│   ├── io/                         # Project I/O and result export
│   │   ├── __init__.py
│   │   ├── project_io.py           # JSON load/save via to_dict/from_dict
│   │   └── csv_export.py           # CSV export for maps and probe histories
│   ├── visualization/              # Result plotting
│   │   ├── __init__.py
│   │   └── plotting.py             # Matplotlib temperature maps and curves
│   └── ui/                         # Desktop GUI (PySide6)
│       ├── __init__.py
│       ├── main_window.py          # Tabbed editor + results dashboard
│       └── structure_preview.py    # Layer stack visualization
├── tests/                          # Test suite (pytest)
│   ├── test_validation_cases.py    # Analytical comparison tests
│   ├── test_steady_state_solver.py # Steady-state solver unit tests
│   ├── test_transient_solver.py    # Transient solver unit tests
│   ├── test_models.py              # Domain model validation tests
│   └── test_led_array.py           # LED array expansion tests
├── examples/                       # Ready-to-run project JSON files
│   ├── steady_uniform_stack.json
│   ├── localized_hotspots_stack.json
│   └── led_array_backlight.json
├── outputs*/                       # Artifact directories (generated, not committed)
│   └── temperature_map.csv, *.png, etc.
├── .planning/codebase/             # GSD documentation (this directory)
├── README.md                       # Project overview
├── CLAUDE.md                       # Claude Code guidance
├── requirements.txt                # pip dependencies
└── .gitignore                      # Git ignore rules
```

## Directory Purposes

**thermal_sim/:**
- Purpose: Main package containing all source code
- Contains: Python modules organized by concern (app, core, models, solvers, io, visualization, ui)
- Key files: `__init__.py` (empty; package marker)

**thermal_sim/app/:**
- Purpose: Entry points for CLI and GUI modes
- Contains: Main runners and application initialization
- Key files:
  - `cli.py`: Parses arguments, loads project, runs solver, orchestrates export
  - `gui.py`: Initializes PySide6 QApplication and MainWindow

**thermal_sim/core/:**
- Purpose: Shared physics utilities, material presets, and result analysis
- Contains: Constants, spatial discretization helpers, material library, postprocessing functions
- Key files:
  - `constants.py`: Physical constants (Stefan-Boltzmann 5.67e-8 W/(m²K⁴))
  - `geometry.py`: `Grid2D` class for mesh cell size calculations (dx, dy, cell_area)
  - `material_library.py`: Predefined materials (aluminum, copper, FR4, etc.) with anisotropic k values
  - `postprocess.py`: Min/max/avg temperature statistics, probe interpolation, hotspot ranking

**thermal_sim/models/:**
- Purpose: Domain data model (dataclasses with validation, no business logic)
- Contains: Input structure definitions, all with `to_dict()`/`from_dict()` for JSON round-trip
- Key files:
  - `project.py`: `DisplayProject` (central model), `MeshConfig`, `TransientConfig` - all validation in `__post_init__()`
  - `material.py`: `Material` with anisotropic `k_in_plane` and `k_through`, emissivity
  - `layer.py`: `Layer` with thickness, interface resistance
  - `heat_source.py`: `HeatSource` (full/rectangle/circle shapes), `LEDArray` (template with `.expand()` method)
  - `boundary.py`: `BoundaryConditions`, `SurfaceBoundary` (convection + radiation)
  - `probe.py`: `Probe` (virtual thermistor at layer/x/y)

**thermal_sim/solvers/:**
- Purpose: Discretization and solving of the thermal network
- Contains: Network assembly (matrix/vector construction) and two solver implementations
- Key files:
  - `network_builder.py`: `build_thermal_network()` function produces `ThermalNetwork` with sparse CSR matrix A, vector b (forcing), vector c (thermal capacity); node indexing: `layer_idx * (nx*ny) + iy * nx + ix`
  - `steady_state.py`: `SteadyStateSolver.solve()` → `spsolve(A, b)` → reshape to `[n_layers, ny, nx]` → `SteadyStateResult`
  - `transient.py`: `TransientSolver.solve()` → implicit Euler loop with LU prefactoring → sample over time → `TransientResult` with shape `[nt, n_layers, ny, nx]`

**thermal_sim/io/:**
- Purpose: Project persistence and result export
- Contains: JSON serialization and CSV export functions
- Key files:
  - `project_io.py`: `load_project(path)` → JSON → `DisplayProject.from_dict()` → `DisplayProject`; `save_project()` reverses
  - `csv_export.py`: `export_temperature_map()` (CSV of [layer, x, y, T_C]), `export_probe_temperatures()`, `export_probe_temperatures_vs_time()`

**thermal_sim/visualization/:**
- Purpose: Matplotlib-based result visualization
- Contains: Plotting functions
- Key files:
  - `plotting.py`: `plot_temperature_map()` (heatmap for single layer), `plot_probe_history()` (time-series curves)

**thermal_sim/ui/:**
- Purpose: Interactive desktop GUI (PySide6)
- Contains: Main window with tabbed editor and embedded matplotlib canvases
- Key files:
  - `main_window.py`: `MainWindow` class - tabbed interface (Materials, Layers, Heat Sources, LED Arrays, Boundaries, Probes) + Results dashboard (temperature map, layer profile, probe history, summary stats)
  - `structure_preview.py`: Layer stack visualization widget

**tests/:**
- Purpose: Test suite validating domain models and solvers
- Contains: Pytest-based tests with analytical comparison cases
- Key files:
  - `test_validation_cases.py`: Compare solver output to hand-calculated 1D resistance chains, 2-node networks, RC transient decay
  - `test_steady_state_solver.py`: Unit tests for steady-state solver (one-cell, multi-cell, anisotropic materials)
  - `test_transient_solver.py`: Transient solver tests (convergence to steady-state, time-stepping accuracy)
  - `test_models.py`: Domain model validation (layer references, material properties, bounds checks)
  - `test_led_array.py`: LED array expansion correctness

**examples/:**
- Purpose: Ready-to-run project JSON files
- Contains: Pre-configured scenarios (steady uniform stack, localized hotspots, LED array backlight)
- Key files:
  - `steady_uniform_stack.json`: Simple multi-layer uniform structure
  - `localized_hotspots_stack.json`: With small heat sources
  - `led_array_backlight.json`: LED array template expansion example

**outputs*/ directories:**
- Purpose: Artifact storage (temperature maps, probe curves, PNG plots)
- Generated: By CLI solver runs
- Committed: No (.gitignore excludes)

## Key File Locations

**Entry Points:**
- `thermal_sim/app/cli.py`: CLI runner; import and call `main()`
- `thermal_sim/app/gui.py`: GUI launcher; import and call `main()`

**Configuration:**
- `thermal_sim/models/project.py`: `DisplayProject` with `MeshConfig`, `TransientConfig`, `BoundaryConditions`
- `thermal_sim/core/material_library.py`: Material presets

**Core Logic:**
- `thermal_sim/solvers/network_builder.py`: Physics discretization (matrix assembly)
- `thermal_sim/solvers/steady_state.py`: Steady-state solver
- `thermal_sim/solvers/transient.py`: Transient solver with implicit Euler

**Testing:**
- `tests/test_validation_cases.py`: Analytical validation (1D, 2-node, RC circuits)
- `tests/test_steady_state_solver.py`: Steady-state unit tests

## Naming Conventions

**Files:**
- Module files: lowercase_with_underscores.py (e.g., `material.py`, `heat_source.py`)
- Test files: `test_*.py` (pytest discovery pattern)
- Config files: JSON (e.g., `steady_uniform_stack.json`)

**Directories:**
- Package directories: lowercase (e.g., `thermal_sim`, `solvers`, `models`)
- Test directory: `tests`
- Examples: `examples`
- Output: `outputs` or `outputs_*` (phase-specific)

**Classes/Types:**
- Domain models: PascalCase (e.g., `DisplayProject`, `Material`, `HeatSource`, `SteadyStateSolver`)
- Private/internal: Prefixed with `_` (e.g., `_base_material()` in tests)

**Functions:**
- Public: lowercase_with_underscores (e.g., `build_thermal_network()`, `load_project()`)
- Private: Prefixed with `_` (e.g., `_run_steady()`, `_layer_index()`)

**Variables:**
- Loop indices: Lowercase (e.g., `ix`, `iy`, `l_idx`)
- Array shapes: Descriptive (e.g., `temperatures_c`, `times_s`, `probe_history`)
- Conductance/resistance: g*, r* (e.g., `g_x`, `r_int`)

**Constants:**
- UPPERCASE_WITH_UNDERSCORES (e.g., `STEFAN_BOLTZMANN`)

## Where to Add New Code

**New Feature (e.g., new solver or boundary condition type):**
- Domain model: Add class to `thermal_sim/models/` (e.g., `new_feature.py`)
- Logic: Add computation to appropriate layer (solvers, core, or io)
- Tests: Create `tests/test_new_feature.py`
- Integration: Update CLI or GUI to expose new option

**New Component/Module:**
- Within `thermal_sim/`: Create subdirectory if it spans multiple files
- Add `__init__.py` (can be empty for package marker)
- Place public classes/functions at module level
- Examples: `thermal_sim/models/`, `thermal_sim/solvers/`

**Utilities:**
- Shared helpers: `thermal_sim/core/` (if physics/geometry-related) or new `thermal_sim/utils/` (if generic)
- Material presets: `thermal_sim/core/material_library.py`
- Math/geometry: `thermal_sim/core/geometry.py`

**UI Enhancements:**
- New widget: Add to `thermal_sim/ui/main_window.py` or separate `thermal_sim/ui/widget_name.py`
- New tab: Add `QWidget` subclass and integrate into tabbed interface in `MainWindow.setup_tabs()`

## Special Directories

**thermal_sim/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (.gitignore excludes)

**.pytest_cache/:**
- Purpose: Pytest cache
- Generated: Yes (by pytest)
- Committed: No (.gitignore excludes)

**outputs*/ (outputs, outputs_led_array, outputs_localized, etc.):**
- Purpose: Result artifact directories
- Generated: Yes (by CLI runs)
- Committed: No (.gitignore excludes)

**examples/:**
- Purpose: Sample projects for users and tests
- Generated: No (hand-authored)
- Committed: Yes

**.planning/codebase/:**
- Purpose: GSD analysis documents
- Generated: Yes (by GSD commands)
- Committed: Yes (alongside regular commits)

---

*Structure analysis: 2026-03-14*
