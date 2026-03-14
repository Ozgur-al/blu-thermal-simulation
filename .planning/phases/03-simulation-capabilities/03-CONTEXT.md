# Phase 3: Simulation Capabilities - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can run parametric sweeps across design variants, define duty-cycle power profiles, and validate results against expanded analytical benchmarks. All capabilities must be fully accessible from both CLI and GUI — no CLI-only or JSON-only features.

</domain>

<decisions>
## Implementation Decisions

### Sweep definition
- Sweeps defined in a separate JSON file (`sweep.json`) with target parameter path and list of values
- CLI: `--sweep sweep.json` flag on existing CLI
- GUI: dedicated sweep dialog with parameter dropdown, value entry (comma-separated or min/max/step range), and mode selector (steady/transient)
- Single parameter per sweep only (no multi-parameter grid for v1)
- Sweepable parameters: layer thickness, material k_in_plane/k_through, boundary convection_h (top/bottom), heat source power_w
- Sweeps work with both steady-state and transient modes
- Progress shows "Run N of M"

### Power profiles (duty cycles)
- Optional `power_profile` field on each HeatSource: list of `{time_s, power_w}` breakpoints (piecewise-linear)
- If `power_profile` is absent, constant `power_w` is used (backward compatible)
- Profile shorter than simulation time: **loops from the beginning** (good for periodic duty cycles)
- GUI: inline breakpoint table in Heat Sources tab with add/remove row buttons and a checkbox "[x] Time-varying"
- Live-updating profile preview plot below the breakpoint table — refreshes automatically as user edits values
- Transient solver interpolates between breakpoints at each timestep

### Material library
- Built-in presets shipped as a bundled JSON file (`materials_builtin.json`) with common display/automotive materials (copper, aluminum, FR4, glass, adhesives, etc.)
- GUI: Materials tab shows a "Type" column distinguishing "Built-in" vs "User" materials
- Import/Export via toolbar buttons in the Materials tab — Import opens file picker for JSON, Export saves selected materials to JSON
- On import name conflict: auto-rename with suffix (e.g., "Copper" → "Copper_imported") and notify user
- Built-in materials are read-only; attempting to edit creates a user clone (e.g., "Copper" → "Copper (custom)")

### Sweep results display
- Dedicated sweep results panel/tab appears after sweep completes
- Comparison table: parameter value vs T_max and T_avg per layer (final-timestep values for transient)
- Parameter-vs-metric plot: default Y-axis is T_max of topmost layer; user can switch layer/metric via dropdowns
- Export buttons in sweep results panel: CSV for table, PNG for plot

### Validation test expansion
- Claude's Discretion: selection of 3+ new analytical benchmark cases beyond existing 1D two-layer resistance chain test

### Claude's Discretion
- Sweep JSON schema details and validation
- Specific built-in material property values (from engineering references)
- Power profile interpolation implementation in the transient solver
- Validation test case selection (which analytical benchmarks to implement)
- Sweep progress reporting mechanism (signals for GUI, stdout for CLI)
- Exact sweep dialog layout and widget choices

</decisions>

<specifics>
## Specific Ideas

- Sweep dialog mockup: parameter dropdown, values field with "or" separator for min/max/step range mode, radio buttons for steady/transient mode
- Power profile table: checkbox enables time-varying mode, revealing breakpoint table and preview plot below
- Material table: Type column with "Built-in"/"User" labels, toolbar buttons for Import/Export/New
- Sweep results: table + plot stacked vertically in one panel with export buttons in toolbar

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HeatSource` dataclass (`models/heat_source.py`): add optional `power_profile` field with `to_dict()`/`from_dict()` round-trip
- `Material` dataclass (`models/material.py`): frozen dataclass with existing `to_dict()`/`from_dict()` — extend for library concept
- `TransientSolver` (`solvers/transient.py`): currently uses constant `b_vector` — needs per-timestep power scaling from profiles
- `build_thermal_network` (`solvers/network_builder.py`): `_apply_heat_sources` distributes power to `b_vec` — need to separate power contribution from boundary contributions for time-varying support
- `SteadyStateSolver` / `TransientSolver`: both take `DisplayProject` — sweep engine creates modified copies and calls these
- CLI argparse (`app/cli.py`): add `--sweep` flag to existing parser

### Established Patterns
- All model dataclasses use `to_dict()`/`from_dict()` for JSON serialization — new models (sweep config, power profile) should follow same pattern
- GUI uses PySide6 with tabbed editor and matplotlib `FigureCanvasQTAgg` — sweep dialog and results panel should use same toolkit
- Validation tests construct `DisplayProject` objects directly in code — new analytical tests should follow same pattern

### Integration Points
- Sweep engine: sits between CLI/GUI and existing solvers — creates modified `DisplayProject` copies per sweep point
- Power profiles: transient solver time-step loop needs to rebuild/scale power portion of `b_vector` per step
- Material library: `DisplayProject.materials` dict is the integration point — picker populates from built-in + user sources
- Sweep results panel: new tab/panel in MainWindow alongside existing results dashboard

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-simulation-capabilities*
*Context gathered: 2026-03-14*
