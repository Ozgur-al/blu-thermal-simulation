# Thermal Simulator (Display/Automotive) - Phase 3

Engineering-focused thermal simulation tool for display module concept studies.
This is a practical approximation model for tradeoff decisions, not a CFD replacement.

## Current Scope

Implemented so far:
- Project/model structure
- Material/layer/heat source/boundary models
- Steady-state solver (layered 2.5D RC network)
- Transient solver (implicit Euler)
- CLI runner
- CSV export (steady + transient probes vs time)
- Plot export (temperature map + probe curves)
- Desktop GUI for project editing, run control, and visualization
- LED array template definition (auto-expanded to localized heat sources)
- Unit tests with analytical validation cases

## Internal Architecture

The codebase is organized under `thermal_sim/`:

- `app/`
  - `cli.py`: command-line entry point for steady and transient runs
  - `gui.py`: desktop GUI launcher
- `core/`
  - `constants.py`: physical constants
  - `geometry.py`: mesh/grid helpers
  - `material_library.py`: practical material presets
  - `postprocess.py`: statistics/probe/hotspot summaries
- `models/`
  - `material.py`: material properties (supports anisotropic k in-plane vs through-plane)
  - `layer.py`: stack layer definition
  - `heat_source.py`: localized/full heat source definitions
    - includes `LEDArray` template support
  - `boundary.py`: convection/radiation boundary conditions
  - `probe.py`: virtual thermistors/probe points
  - `project.py`: full project model + JSON-ready serialization
- `solvers/`
  - `network_builder.py`: shared matrix/capacity builder
  - `steady_state.py`: sparse linear steady-state solver
  - `transient.py`: implicit Euler transient solver
- `io/`
  - `project_io.py`: JSON save/load
  - `csv_export.py`: CSV export of map and probes
- `visualization/`
  - `plotting.py`: matplotlib-based exports for map and curves
- `ui/`
  - `main_window.py`: project editor and results dashboard
- `tests/`
  - solver/model validation tests
- `examples/`
  - ready-to-run project JSON files

## Governing Equations and Assumptions

All internal units are SI.

### Governing Model

The solver uses a layered in-plane grid:
- One thermal node per `(layer, x-cell, y-cell)` at layer mid-plane
- Conductive links:
  - In-plane neighbors (x/y) in each layer
  - Through-thickness links between adjacent layers
- Boundary sink links to ambient (top, bottom, and side)
- Heat sources inject power at selected nodes

Steady-state nodal equation:

`sum_j G_ij (T_i - T_j) + sum_k G_i,amb,k (T_i - T_amb,k) = Q_i`

where:
- `G_ij` is conductance between nodes `i` and `j`
- `G_i,amb,k` is conductance from node `i` to ambient boundary `k`
- `Q_i` is injected heat power (W)

This produces linear system:

`A * T = b`

solved with `scipy.sparse.linalg.spsolve`.

Transient model:

`C * dT/dt + A * T = b`

with implicit Euler integration:

`(C/dt + A) * T_(n+1) = b + (C/dt) * T_n`

### Conductance Definitions

- In-plane x-link:
  - `Gx = k_in_plane * thickness * dy / dx`
- In-plane y-link:
  - `Gy = k_in_plane * thickness * dx / dy`
- Through-thickness link between layer `l` and `l+1`:
  - `Rz = t_l/(2*kz_l*A) + R_interface/A + t_u/(2*kz_u*A)`
  - `Gz = 1/Rz`
- Convection boundary:
  - `q = hA(T_surface - T_amb)`
- Radiation boundary (linearized around ambient):
  - `h_rad = 4 * eps * sigma * T_amb,K^3`
  - `h_total = h_conv + h_rad`

### Key Assumptions

- Lumped node at each cell/layer mid-plane
- Material properties are constant (temperature-independent in this version)
- Radiation uses linearized effective `h_rad`
- Side boundaries modeled as exposed perimeter sinks
- No fluid/air channel internal flow model
- No contact pressure-dependent interface behavior

These are intentional to prioritize design consistency and speed.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run a Simulation (CLI)

Default steady-state example:

```bash
python -m thermal_sim.app.cli --mode steady
```

Run a transient case:

```bash
python -m thermal_sim.app.cli --mode transient --project examples/localized_hotspots_stack.json --output-dir outputs --plot
```

Run the desktop GUI:

```bash
python -m thermal_sim.app.gui
```

CLI outputs:
- console summary (min/avg/max, probe values, top hot cells)
- `outputs/temperature_map.csv`
- `outputs/probe_temperatures.csv` (steady, if probes exist)
- `outputs/probe_temperatures_vs_time.csv` (transient, if probes exist)
- `outputs/temperature_map.png` and `outputs/probe_temperatures_vs_time.png` (with `--plot`)

## Tests

```bash
py -m pytest -q tests
```

Included validation tests:
- 1D equivalent thermal resistance analytical comparison
- 2-layer nodal analytical comparison
- localized hotspot sanity behavior
- interface resistance trend check
- first-order RC transient analytical comparison
- transient convergence to steady-state reference

## Example Projects

- `examples/steady_uniform_stack.json`
- `examples/localized_hotspots_stack.json`
- `examples/led_array_backlight.json`

## Phase Roadmap

- Phase 4: polish, documentation expansion, report generation, more validation datasets
