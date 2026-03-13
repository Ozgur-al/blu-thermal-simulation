# Phase 2: Results - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can immediately see structured thermal metrics after a run, navigate hotspots on the map, export a PDF report for design review, and compare named result snapshots side-by-side. Parametric sweeps, time-varying sources, and material import/export are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Results summary table
- Per-layer table layout: one row per layer showing T_max, T_avg, T_min, and ΔT (all in °C)
- Separate ranked hotspot list below the layer table, showing top 10 hotspots with rank, layer name, location in mm, and temperature
- Separate probe readings section below hotspots: probe name, layer, location in mm, temperature
- Displayed in a dedicated Results tab that auto-activates after a simulation run completes

### Hotspot map annotations
- Crosshair + text label style: thin crosshair lines at hotspot location with rank number and temperature value
- Per-layer hotspots: each layer's temperature map shows its own top 3 hotspots
- Probes also shown on the temperature map with a distinct marker style (e.g., diamond or triangle) to differentiate from hotspot crosshairs
- Clicking a hotspot row in the summary table highlights/navigates to the corresponding marker on the temperature map

### PDF report
- Primary use case: personal archive (quick reference, not formal customer deliverable)
- Generated using matplotlib PdfPages backend (no new dependencies)
- Sections included: stack summary (layers/materials/thickness), temperature maps with hotspot annotations, metrics table (per-layer stats + hotspot ranking), and probe history plots (transient only)
- Minimal header on first page: project filename, simulation date, solver mode (steady/transient)

### Result snapshots & comparison
- In-memory named snapshots: user gives each result a name (e.g., "baseline", "thinner PCB"); snapshots lost when app closes
- Comparison view: side-by-side metric table with delta column (Δ), overlay probe history plot with different colors per snapshot, and side-by-side temperature maps for the same layer
- Up to 4 snapshots comparable simultaneously
- Metric table columns expand per snapshot (snapshot name as column header group)

### Claude's Discretion
- Exact crosshair line styling (color, width, alpha) and label font size
- Temperature map colormap choice for comparison views (shared vs per-map scale)
- Probe marker shape (diamond, triangle, or similar)
- Results tab internal layout and spacing
- Snapshot management UI (list widget, dropdown, or similar)
- PDF page sizing and margins

</decisions>

<specifics>
## Specific Ideas

- Hotspot crosshairs should be engineering-style: clean, thin lines that don't obscure the underlying heatmap data
- Comparison metric table should include a delta (Δ) column showing the difference between runs
- Probe overlay plot should use distinct colors per snapshot for easy visual differentiation

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `postprocess.py:basic_stats()` / `basic_stats_transient()`: Already computes T_max/T_avg/T_min — extend with ΔT calculation
- `postprocess.py:top_n_hottest_cells()` / `top_n_hottest_cells_transient()`: Returns ranked hotspot dicts with layer, x_m, y_m, temperature_c — directly usable for both table and map annotations
- `postprocess.py:probe_temperatures()` / `probe_temperatures_over_time()`: Probe readout already implemented
- `postprocess.py:layer_average_temperatures()`: Per-layer averages available
- `plotting.py:plot_temperature_map()`: Base heatmap using matplotlib imshow with inferno colormap — extend with hotspot annotation overlay
- `plotting.py:plot_probe_history()`: Time-series probe curves — extend for overlay comparison
- `csv_export.py`: CSV export patterns for reference

### Established Patterns
- Solver results are immutable dataclasses (`SteadyStateResult`, `TransientResult`) with temperature arrays shaped `[n_layers, ny, nx]`
- GUI uses embedded `FigureCanvasQTAgg` for matplotlib integration
- Tabbed interface pattern in `MainWindow` for organizing sections
- `to_dict()`/`from_dict()` pattern for serialization (relevant if snapshots ever persist)

### Integration Points
- Results tab integrates into existing `MainWindow` tab widget
- Hotspot annotations layer onto existing `plot_temperature_map()` function
- PDF export triggered from GUI menu or button (alongside existing CSV export)
- Snapshot save/compare accessible from Results tab after simulation completes

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-results*
*Context gathered: 2026-03-14*
