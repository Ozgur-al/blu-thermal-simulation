# Technology Stack

**Analysis Date:** 2026-03-14

## Languages

**Primary:**
- Python 3.11+ - All application, solver, and testing code

**Secondary:**
- JSON - Project configuration and example files (`.examples/` directory)

## Runtime

**Environment:**
- Python 3.11+ (documented in CLAUDE.md as 3.14+ requirement)

**Package Manager:**
- pip
- Lockfile: missing (uses `requirements.txt` for dependency pinning)

## Frameworks

**Core:**
- NumPy 1.26+ - Numerical arrays, matrix operations, linear algebra
- SciPy 1.12+ - Sparse matrix solvers (`scipy.sparse.linalg.spsolve`), sparse matrix construction

**GUI:**
- PySide6 6.7+ - Desktop GUI framework (Qt bindings for Python)
  - Used in `thermal_sim/ui/main_window.py` for project editor and results dashboard
  - Optional dependency: can run CLI without it

**Visualization:**
- Matplotlib 3.8+ - Temperature map plotting and probe curve visualization
  - Direct usage in `thermal_sim/visualization/plotting.py`
  - Embedded in PySide6 GUI via `FigureCanvasQTAgg` for live result display

**Testing:**
- pytest 8.0+ - Test runner and assertion framework
  - Config: No custom config file (uses defaults)
  - Tests located in `tests/` directory

## Key Dependencies

**Critical:**
- NumPy - Matrix/vector operations for thermal network representation
- SciPy - Sparse linear solver (`spsolve`) for steady-state system: `A*T = b`
- SciPy sparse - Sparse matrix construction (LIL, CSR formats) for conductance matrices

**Infrastructure:**
- Matplotlib - Rendering temperature maps and transient probe histories to PNG
- PySide6 - Desktop application framework for GUI mode (optional, not needed for CLI)

**Development/Testing:**
- pytest - Test execution and validation of analytical cases

## Configuration

**Environment:**
- No .env files required - all configuration via:
  - JSON project files (e.g., `examples/steady_uniform_stack.json`)
  - CLI arguments (e.g., `--project`, `--output-dir`, `--mode`, `--plot`)
  - GUI interactive input forms

**Build:**
- No build system configured (pure Python package)
- Virtual environment: `.venv/` (mentioned in README.md setup)
- Installation: `pip install -r requirements.txt`

## Package Structure

**Entry Points:**
- CLI: `python -m thermal_sim.app.cli --mode steady`
- GUI: `python -m thermal_sim.app.gui`

**Core Modules:**
- `thermal_sim.models.*` - Domain model classes (Material, Layer, HeatSource, etc.)
- `thermal_sim.solvers.*` - Steady-state and transient solvers
- `thermal_sim.core.*` - Physical constants and shared utilities
- `thermal_sim.io.*` - JSON/CSV serialization
- `thermal_sim.visualization.*` - Plotting utilities
- `thermal_sim.ui.*` - PySide6 GUI components

## Platform Requirements

**Development:**
- Windows 11 Pro (confirmed in environment)
- Python 3.11+ installation
- Virtual environment for isolation
- pip for package management

**Production:**
- Any platform supporting Python 3.11+
- GUI requires X11/Wayland (Linux) or Windows/macOS graphical subsystem
- CLI mode (headless) works on any platform

## SI Unit Convention

**All internal calculations use SI units:**
- Temperature: Kelvin (K) for calculations, converted to Celsius (°C) for display
- Power: Watts (W)
- Thermal conductivity: W/(m·K)
- Heat capacity: J/(kg·K)
- Density: kg/m³
- Distances/dimensions: meters (m)
- Time: seconds (s)

---

*Stack analysis: 2026-03-14*
