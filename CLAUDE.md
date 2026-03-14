# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Engineering-focused thermal simulation tool for display/automotive module concept studies. This is a 2.5D RC-network approximation model (not CFD) for rapid design tradeoff decisions. All internal units are SI. Python 3.14+.

## Commands

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run simulations
python -m thermal_sim.app.cli --mode steady
python -m thermal_sim.app.cli --mode transient --project examples/localized_hotspots_stack.json --output-dir outputs --plot

# Launch GUI
python -m thermal_sim.app.gui

# Tests
py -m pytest -q tests
py -m pytest -q tests/test_validation_cases.py::test_1d_two_layer_resistance_chain_matches_hand_calculation  # single test
```

## Architecture

The main package is `thermal_sim/`. There are also empty top-level stub packages (`app/`, `core/`, `models/`, etc.) — all real code lives under `thermal_sim/`.

### Solver pipeline

1. **Project model** (`models/project.py:DisplayProject`) — central dataclass holding the full simulation input: layers, materials, heat sources, LED arrays, boundary conditions, mesh config, transient config, probes. JSON-serializable via `to_dict()`/`from_dict()`.

2. **Network builder** (`solvers/network_builder.py:build_thermal_network`) — converts a `DisplayProject` into a sparse linear system. Shared by both solvers. Builds the conductance matrix `A`, forcing vector `b`, and thermal capacity vector `C`. Node indexing: `layer_idx * (nx*ny) + iy * nx + ix`.

3. **Solvers**:
   - `solvers/steady_state.py` — solves `A*T = b` via `scipy.sparse.linalg.spsolve`
   - `solvers/transient.py` — implicit Euler: prefactors LHS with `splu`, then time-steps `(C/dt + A) * T_{n+1} = b + (C/dt) * T_n`

4. **Postprocessing** (`core/postprocess.py`) — stats, probe readout, hotspot ranking
5. **I/O** (`io/project_io.py`, `io/csv_export.py`) — JSON project load/save, CSV export
6. **Visualization** (`visualization/plotting.py`) — matplotlib temperature maps and probe curves

### GUI

PySide6 desktop app (`ui/main_window.py`) with tabbed editor (materials, layers, heat sources, LED arrays, boundaries, probes) and result dashboard (temperature map, layer profile, probe history, summary). Matplotlib canvases embedded via `FigureCanvasQTAgg`.

### Key domain concepts

- **Materials** support anisotropic thermal conductivity: `k_in_plane` (lateral) vs `k_through` (through-thickness)
- **Layers** are stacked bottom-to-top with optional `interface_resistance_to_next` between adjacent layers
- **Heat sources** can be `full`, `rectangle`, or `circle` shaped; power is distributed uniformly across overlapping mesh cells
- **LED arrays** (`models/heat_source.py:LEDArray`) are templates that expand into individual `HeatSource` objects via `expand()`
- **Boundaries** (top/bottom/side): convection + optional linearized radiation (`h_rad = 4 * eps * sigma * T_amb^3`)
- **Probes**: virtual thermistors at specific (layer, x, y) positions

### Serialization pattern

All model dataclasses follow the same `to_dict()`/`from_dict()` round-trip pattern for JSON serialization. No external schema library — hand-written conversion in each class.

## Dependencies

numpy, scipy (sparse solvers), matplotlib (plotting), PySide6 (GUI), pytest (testing)

## Test approach

Validation tests in `tests/test_validation_cases.py` compare solver output against hand-calculated analytical solutions (1D resistance chains, 2-node networks, RC transient decay). Tests construct `DisplayProject` objects directly in code rather than loading JSON files.
