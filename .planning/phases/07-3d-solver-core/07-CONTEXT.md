# Phase 7: 3D Solver Core - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade the network builder to support per-cell material assignment via rectangular MaterialZone descriptors, centralize node indexing in a NodeLayout abstraction, implement harmonic-mean conductance at zone material boundaries, and ensure all existing projects produce identical temperatures to v1.0.

</domain>

<decisions>
## Implementation Decisions

### Regression baseline
- Regression gate covers all 4 example JSON projects (DLED, led_array_backlight, localized_hotspots, steady_uniform) AND the analytical validation test cases in test_validation_cases.py
- Both steady-state and transient solvers must be tested for each project
- Floating-point tolerance: exact match (1e-12) — same sparse solver on same matrix should match to machine precision if indexing is correct
- Pre-merge gate: regression test must pass before any network builder change is considered complete. Capture v1.0 baseline first, then assert against it after refactoring

### Zone-layer interaction
- Uncovered cells in zoned layers default to air (not the layer's base material)
- When a layer has NO zones defined, the builder auto-generates a full-coverage zone from `layer.material` at build time — old JSONs stay unchanged on disk, builder handles the upgrade transparently
- Air material uses the built-in preset from the material library (k~0.026 W/mK). If 'air' isn't in the project's materials dict, inject it automatically at build time

### Zone overlap rules
- Last-defined wins: zones are rasterized in list order, later zones overwrite earlier ones
- Zone coordinates use absolute meters from origin (same coordinate system as HeatSource: x, y, width, height)
- Zones that extend beyond layer bounds are clipped at rasterization — warn but allow (no error)
- Rectangles only (no "full" shape shorthand). A full-layer zone is a rectangle matching layer dimensions

### Claude's Discretion
- NodeLayout internal API design and data structure
- Harmonic-mean conductance formula implementation details
- How zone rasterization maps rectangles to mesh cells (cell-overlap vs center-in-zone)
- Sparse matrix assembly order for the new per-cell conductance logic

</decisions>

<specifics>
## Specific Ideas

- User sees uncovered cells as physically "air" — the mental model is zones are the real materials placed on a layer, everything else is empty space
- Auto-zone from layer.material preserves backward compat without changing any JSON files on disk
- Zone coordinate system matches heat sources for consistency — GUI will display in mm

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `network_builder.py:_add_link_vectorized()`: Symmetric conductance link builder — can be extended for harmonic-mean conductance
- `network_builder.py:_source_mask()`: Cell-overlap rasterization for heat sources — similar approach can rasterize zones
- `Grid2D`: Spatial discretization with dx/dy/cell_area — directly usable by zone rasterization
- `material_library.py`: Already has material presets including air properties

### Established Patterns
- `to_dict()`/`from_dict()` serialization on all domain models — MaterialZone must follow this
- `@dataclass(frozen=True)` for immutable value objects — MaterialZone fits this pattern
- `DisplayProject.material_for_layer(layer_index)` returns one material per layer — must be extended or supplemented for per-cell lookup
- Closure-based `node_index(layer_idx, ix, iy)` in network_builder — NodeLayout replaces this

### Integration Points
- `build_thermal_network()` is the single entry point for both solvers — all changes go here
- `Layer` dataclass will need a `zones` field (list of MaterialZone, default empty)
- `ThermalNetwork` may need to carry zone/material metadata for result interpretation
- Existing tests construct `DisplayProject` directly — regression tests follow same pattern

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-3d-solver-core*
*Context gathered: 2026-03-16*
