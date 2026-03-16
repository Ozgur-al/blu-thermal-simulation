# Phase 10: Edge Layers and 3D Preview - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can define the ELED perimeter structure (frame, air gaps, PCB) as lateral layer stacks per edge per z-layer, without coordinate math. The system translates edge layers into MaterialZone rectangles for the existing solver. An interactive 3D preview lets engineers verify the assembly structure before solving, and view temperature results on the 3D geometry after solving.

Phase 9 Plans 01-02 (z-slice combo, nz spinbox, zone editor, zone overlay) are complete and retained. This phase replaces Phase 9 Plan 03 (ELED zone preset) with a fundamentally better abstraction.

</domain>

<decisions>
## Implementation Decisions

### Edge definition model
- Per-edge layer list: each edge (bottom, top, left, right) gets its own ordered list of lateral layers with material + thickness
- Per z-layer scope: edge layers are a property of a specific Layer in the z-stack (e.g., only the LGP gets edge structure; the diffuser above might have none)
- Auto-computed bulk: the central region (e.g., LGP bulk) is whatever remains after subtracting edge layer thicknesses from the panel dimensions. Error if edges exceed panel size
- "Copy from" button per edge to duplicate another edge's layer list for symmetric configs
- Serialized as `edge_layers` dict field on Layer: `{"bottom": [{"material": "Steel", "thickness": 0.003}, ...], ...}` — round-trips through JSON. Zones are generated at solve time only

### GUI workflow
- Edge layer editor lives in the Layers tab, below the existing zone panel — appears when a layer row is selected
- Tab buttons for each edge (Bottom / Top / Left / Right), each showing a table of material + thickness rows with Add/Remove/Copy-from controls
- Edge layers and manual zones coexist: edge layers define the perimeter structure, manual zones overlay on top for partial features (PCB cards, copper traces). Manual zones win on overlap
- ELED architecture preset auto-populates the LGP layer's edge layers when ELED is selected from the dropdown (no separate Generate button)

### 3D structure preview
- Interactive 3D view using PyVista/VTK (new dependency)
- Rotation, pan, zoom with color-coded blocks per material and layer labels
- Explode slider that separates layers vertically for inspecting internal structure
- Two placements: (1) live dock panel that updates while editing layers/edges, (2) results tab showing the same 3D geometry with temperature data overlaid after solving
- Both views share the same 3D rendering logic

### Zone generation strategy
- Edge layers are converted to MaterialZone rectangles internally — user never sees the generated rectangles in the zone table (fully transparent)
- Corner handling: when two edges meet, the corner square always gets the outermost material (typically Steel frame — physically accurate since frame corners are continuous metal)
- Edge-generated zones are prepended to the layer's zone list; manual zones come after and win on overlap (last-defined-wins, consistent with existing rasterizer behavior)

### Claude's Discretion
- PyVista/VTK widget integration with PySide6 (QtInteractor or BackgroundPlotter)
- Explode slider range and animation smoothness
- Edge layer table styling and sizing
- Default edge layer thicknesses for the ELED preset
- 3D colormap choice and material color mapping
- How the dock panel and results tab share the 3D rendering code

</decisions>

<specifics>
## Specific Ideas

- Edge layer tables should feel like the existing layers table — material combo + thickness in mm
- The 3D view should show the assembly as solid blocks, not wireframe — engineers want to see the physical structure
- "If I could just simply add 4 vertical metal layers with 4 vertical air gaps and could check the structure in 3D would be easier" — the user's original vision
- ELED auto-populate should set sensible defaults: frame 3mm, air gap 1mm, PCB+LED 5mm on the LED edge(s), frame+air on non-LED edges

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MaterialZone` dataclass (`models/material_zone.py`): frozen, center-based (x,y,width,height), to_dict/from_dict — edge layer generator outputs these
- `_rasterize_zones()` (`solvers/network_builder.py:104`): converts zones to per-cell material maps — works with any zone geometry, no changes needed
- `Layer.zones` field: already supports arbitrary zone lists — edge-generated zones prepend here
- Zone editor panel (`ui/main_window.py`): _zone_panel, _populate_zone_table, _refresh_zone_preview — coexists with new edge layer panel
- `MplCanvas` embedded matplotlib pattern — reusable for 2D cross-section fallback
- `generate_eled_zones()` in stack_templates.py — can be replaced/adapted for edge layer generation
- `eled_template()` — already creates the ELED layer stack; extend to include default edge_layers

### Established Patterns
- `to_dict()`/`from_dict()` serialization with `.get(field, default)` for backward compat
- `_populate_ui_from_project()` / `_build_project_from_ui()` round-trip pattern
- QDockWidget for flexible panel placement (Phase 4)
- `_layer_zones` dict storage pattern for per-layer data
- Tab buttons pattern not yet established — new UI element for edge selection

### Integration Points
- `Layer` model: add `edge_layers: dict[str, list[EdgeLayer]]` field
- `build_thermal_network()`: merge edge-generated zones with manual zones before rasterization
- `eled_template()`: return default edge_layers on the LGP layer
- `_on_architecture_changed()`: populate edge layer data when ELED selected
- New 3D widget: QDockWidget in main window + new tab in results area
- `requirements.txt`: add pyvista dependency

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-edge-layers-and-3d-preview*
*Context gathered: 2026-03-16*
