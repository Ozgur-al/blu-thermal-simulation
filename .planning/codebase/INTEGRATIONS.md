# External Integrations

**Analysis Date:** 2026-03-14

## APIs & External Services

**None detected** - This application has no external API dependencies or cloud service integrations. All computation is local.

## Data Storage

**Databases:**
- None - Application uses no database systems

**File Storage:**
- Local filesystem only
  - Input: JSON project files (e.g., `examples/*.json`)
  - Output: CSV files and PNG images to specified `--output-dir`
  - Example locations: `outputs/temperature_map.csv`, `outputs/probe_temperatures_vs_time.csv`

**Caching:**
- None - Application is stateless per run

## Authentication & Identity

**Auth Provider:**
- None - No authentication required
- Local user runs solver directly via CLI or GUI

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Console output only
  - CLI mode: prints to stdout (summary stats, min/avg/max temps, hottest cells)
  - GUI mode: dialog boxes for errors/messages

## CI/CD & Deployment

**Hosting:**
- Local execution only (no remote hosting)
- No cloud deployment or containerization configured

**CI Pipeline:**
- None detected (no GitHub Actions, GitLab CI, or equivalent config files)

## Environment Configuration

**Required env vars:**
- None - All configuration via:
  - JSON project files
  - CLI command-line arguments
  - GUI interactive forms

**Secrets location:**
- Not applicable - no secrets or credentials needed

## File I/O

**Input File Formats:**
- **JSON** (project definition)
  - Path pattern: User-specified via `--project` CLI arg or GUI file dialog
  - Default: `examples/steady_uniform_stack.json`
  - Serialization: `thermal_sim.io.project_io:load_project()` and `DisplayProject.from_dict()`

**Output File Formats:**
- **CSV** - Temperature maps and probe time-series
  - `temperature_map.csv` - 2D grid of temperatures (rows = y cells, columns = x cells)
  - `probe_temperatures.csv` - Probe point readings (steady-state)
  - `probe_temperatures_vs_time.csv` - Probe time-series (transient)
  - Location: `--output-dir` (default: `outputs/`)
  - Written by: `thermal_sim.io.csv_export.*` functions

- **PNG** - Visualization plots (optional)
  - `temperature_map.png` - Contour-style heatmap of selected layer
  - `probe_temperatures_vs_time.png` - Line plot of probe curves
  - Generated when `--plot` flag is used
  - Written by: `thermal_sim.visualization.plotting.*` functions

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Project Data Structure

**JSON Schema (subset):**
- Root object contains:
  - `name`: Project identifier
  - `width`, `height`: Domain dimensions (meters)
  - `materials`: Dictionary of material property definitions
  - `layers`: List of layer definitions with material references
  - `heat_sources`: List of heat source definitions
  - `led_arrays`: List of LED template definitions (expanded at runtime)
  - `boundaries`: Boundary conditions (top/bottom/side convection/radiation)
  - `mesh`: Grid resolution (nx, ny cells)
  - `transient_config`: Time step and integration parameters (for transient runs)
  - `probes`: Virtual thermistor locations for point measurements

**Serialization:**
- Bidirectional conversion: `DisplayProject.to_dict()` / `DisplayProject.from_dict()`
- JSON I/O: `thermal_sim.io.project_io.save_project()` / `load_project()`
- Hand-written serialization in each model class (no schema library)

## Standalone Operation

This application is fully self-contained:
- Solver computation: NumPy/SciPy only
- Visualization: Matplotlib (optional for plots)
- GUI: PySide6 (optional, CLI works without)
- No network access required
- No authentication or external services
- Suitable for offline/air-gapped environments

---

*Integration audit: 2026-03-14*
