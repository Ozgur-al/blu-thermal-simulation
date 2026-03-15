# Phase 8: Z-Refinement - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can assign multiple z-nodes to any layer (via `nz` field), the solver handles the full 3D node count correctly with proper within-layer and inter-layer conductance formulas, and a 1D analytical benchmark confirms the through-plane temperature profile is physically correct. GUI controls for nz are Phase 9.

</domain>

<decisions>
## Implementation Decisions

### Boundary condition z-treatment
- Per-sublayer side faces: each z-sublayer gets its own side BC with area = sublayer_thickness * cell_edge_length
- Top/bottom surface BCs attach to outermost z-sublayer only (top BC -> topmost sublayer of top layer, bottom BC -> bottommost sublayer of bottom layer)
- Surface BC conduction distance = dz/2 (half sublayer thickness), not t/2 (half total layer thickness)
- Inter-layer z-z links: r_total = dz_lower/(2*k_lower*A) + R_interface/A + dz_upper/(2*k_upper*A), using half-sublayer-thickness from each side

### Heat source z-placement
- Add `z_position` field to HeatSource: options "top" (default), "bottom", "distributed"
- Default "top" — heat injects into topmost z-sublayer of the source's layer (matches LED/surface heat generation)
- "distributed" splits power equally across all nz sublayers (power_per_sublayer = power_w / nz)
- LEDArray template gets z_position field; all expanded HeatSource objects inherit it
- Backward compatible: missing z_position in JSON defaults to "top"

### Probe z-behavior
- Add `z_position` field to Probe: options "top" (default), "bottom", "center", or integer sublayer index
- Default "top" — matches typical surface thermocouple placement
- Missing z_position in old JSON defaults to "top"
- Per-layer stats (T_max, T_avg, T_min) aggregate across ALL z-sublayers in the layer
- Hotspot ranking considers all z-sublayers — hotspot could be at any depth
- Default temperature map visualization shows top sublayer per layer (Phase 9 adds z-slice slider)

### Result data structure
- Flat z-axis: result shape [total_z, ny, nx] where total_z = sum(nz_i for all layers)
- Transient shape: [nt, total_z, ny, nx]
- Result objects carry `nz_per_layer: list[int]` and `z_offsets: list[int]` metadata
- When all nz=1: total_z = n_layers, shape is [n_layers, ny, nx] — identical to v1, no wrapper needed
- Same metadata pattern for both SteadyStateResult and TransientResult

### Claude's Discretion
- Internal z-z link conductance implementation details
- NodeLayout abstraction extensions for z-indexing (building on Phase 7)
- Analytical validation test design (1D slab with nz=5)
- Capacity vector construction for sublayers
- Lateral conductance formulas for sublayers (using sublayer thickness)

</decisions>

<specifics>
## Specific Ideas

- z_position field on HeatSource uses string values: "top", "bottom", "distributed" — not numeric indices
- Probe z_position supports both named positions ("top", "bottom", "center") and integer sublayer index for precise control
- Phase 9 z-slice slider will index into the flat z-axis using z_offsets

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `network_builder.py:_add_link_vectorized()`: symmetric conductance link insertion — reuse for z-z links
- `network_builder.py:_surface_sink_conductance()`: surface BC formula — adapt conduction_distance to dz/2
- `ThermalNetwork` dataclass: extend with z-metadata fields
- `Layer.to_dict()`/`from_dict()`: established serialization pattern — add nz field same way

### Established Patterns
- COO triplet accumulation -> single CSR assembly (network_builder.py)
- Vectorized node operations per layer (lateral links, side BCs)
- `from_dict()` with `.get(field, default)` for backward-compatible deserialization
- `expanded_heat_sources()` for LED array expansion

### Integration Points
- `Layer` model: add `nz: int = 1` field
- `HeatSource` model: add `z_position: str = "top"` field
- `LEDArray` model: add `z_position: str = "top"` field, propagate to expand()
- `Probe` model: add `z_position` field (str or int, default "top")
- `SteadyStateResult` / `TransientResult`: add nz_per_layer, z_offsets; change shape
- `build_thermal_network()`: new z-loop for sublayer links, modified inter-layer links
- `_apply_heat_sources()`: z-position-aware node selection
- `postprocess.py`: per-layer stats aggregate across z-sublayers
- `plotting.py`: default to top sublayer per layer for temperature map

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-z-refinement*
*Context gathered: 2026-03-16*
