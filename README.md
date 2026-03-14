# BLU Thermal Simulation

Engineering-focused thermal simulation tool for display and automotive module concept studies. Uses a 2.5D RC-network approximation model for rapid design tradeoff decisions — not a CFD replacement, but fast enough to iterate on stack-up and layout ideas in seconds.

![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue)
![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20NC%201.0-green)

## Features

- **Steady-state and transient solvers** — sparse linear system (spsolve) and implicit Euler time-stepping
- **Anisotropic materials** — separate in-plane and through-thickness thermal conductivity
- **Layer stack modeling** — arbitrary layer count with optional interface resistance between layers
- **Localized heat sources** — full-layer, rectangular, or circular shapes with uniform power distribution
- **LED array templates** — define grid patterns that auto-expand into individual heat sources
- **Boundary conditions** — convection + linearized radiation on top, bottom, and sides
- **Virtual probes** — place thermistors at any (layer, x, y) to track temperature over time
- **Desktop GUI** — PySide6 app for project editing, run control, and interactive visualization
- **CLI** — batch runs with CSV and plot export
- **Validation suite** — tests against analytical solutions (1D resistance chains, RC transient decay)

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### Run the GUI

```bash
python -m thermal_sim.app.gui
```

### Run from CLI

```bash
# Steady-state with default example
python -m thermal_sim.app.cli --mode steady

# Transient with a specific project
python -m thermal_sim.app.cli --mode transient \
    --project examples/localized_hotspots_stack.json \
    --output-dir outputs --plot
```

### Run Tests

```bash
py -m pytest -q tests
```

## How It Works

The solver discretizes a layered structure into a grid of thermal nodes — one per (layer, x-cell, y-cell). Conductive links connect in-plane neighbors and through-thickness adjacent layers. Boundary sinks model convection and radiation to ambient.

**Steady-state** solves `A * T = b` directly. **Transient** uses implicit Euler: `(C/dt + A) * T_{n+1} = b + (C/dt) * T_n`.

All internal units are SI. The GUI displays dimensions in mm for convenience.

## Example Projects

Ready-to-run JSON files in `examples/`:

- `steady_uniform_stack.json` — uniform heating across a basic layer stack
- `localized_hotspots_stack.json` — localized heat sources on specific regions
- `led_array_backlight.json` — LED array template with grid pattern

## Dependencies

numpy, scipy, matplotlib, PySide6, pytest

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — free for personal, research, and educational use. Commercial use is not permitted.
