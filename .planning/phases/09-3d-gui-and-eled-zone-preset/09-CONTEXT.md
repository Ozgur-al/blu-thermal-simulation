# Phase 9: 3D GUI and ELED Zone Preset - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose 3D solver features (per-cell material zones, z-refinement from Phases 7-8) through the GUI, and auto-generate ELED cross-section material zones from the architecture dropdown. Users can control z-refinement, edit material zones, view any z-plane of the 3D result, and get a correctly zoned ELED model without manual zone entry.

</domain>

<decisions>
## Implementation Decisions

### Z-plane slice navigation
- Integrated combo: single QComboBox replacing the current layer combo, listing all z-sublayers across all layers (e.g., "LGP (z=1/5)", "LGP (z=2/5)", ..., "FR4", "Metal Cover")
- Layers with nz=1 show plain name only (no "(z=1/1)" suffix)
- Ordering is bottom-to-top, matching the existing layer stacking convention
- The combo replaces `map_layer_combo` — no separate slider or secondary dropdown

### Material zone editor UX
- Table rows per layer: each layer gets an expandable zone sub-table below its row in the Layers tab
- Expand/collapse via toggle (arrow or "Zones" button) — collapsed by default
- Zone table columns: Material (QComboBox from project materials), X start, X end, Y start, Y end
- Zone coordinates entered in mm, auto-converted to SI (meters) internally — consistent with heat source and mesh input convention
- Add/remove zone rows via [+] [-] buttons

### Zone preview overlay
- Dashed boundary lines drawn over the temperature heatmap showing zone edges, with material name labels at zone corners
- Always-on: overlay appears automatically whenever the displayed layer has material zones (no toggle checkbox)
- Editor preview: inline matplotlib canvas below the zone sub-table when expanded, showing zone rectangles on the layer footprint — updates immediately as zone coordinates change
- Same dashed style on both the editor preview and the results temperature map

### ELED auto-zone configuration
- ELED panel gets spinboxes for each zone width: frame width, PCB+LED width, air gap width, LGP width (remaining)
- Per-edge control: separate width spinboxes for left and right edges — supports asymmetric ELED configurations
- Explicit "Generate Zones" button to populate zone table from spinbox values (not auto-updating)
- Zones applied to LGP layer only — other layers (diffuser, backplate) remain uniform material

### Claude's Discretion
- nz spinbox placement and styling in the Layers tab
- Node count display format in status bar and warning threshold presentation (>300k)
- Combo selection behavior when nz changes (auto-select middle vs stay on current)
- Exact dashed line styling (color, dash pattern, label font size)
- Editor preview canvas sizing and aspect ratio
- Default ELED zone widths for the spinbox presets

</decisions>

<specifics>
## Specific Ideas

- The integrated z-plane combo should look like: `[LGP (z=1/5) v]` with multi-z layers expanded and nz=1 layers showing just the name
- Zone sub-table should feel consistent with existing Heat Sources table pattern
- ELED cross-section zones follow the physical arrangement: [frame | PCB+LED | air | LGP bulk | air | PCB+LED | frame] — but left and right edges can have different widths

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `map_layer_combo` (QComboBox): Current layer selector in temperature map panel — will be replaced/extended with z-sublayer entries
- `arch_combo` + `QStackedWidget`: Existing Custom/DLED/ELED panel switching — ELED panel needs zone width spinboxes added
- `plot_temperature_map_annotated()`: Current matplotlib heatmap function — needs zone overlay rectangle drawing added
- `MplCanvas` (FigureCanvasQTAgg): Existing embedded matplotlib widget pattern — reuse for inline zone preview canvas
- `QTableWidget`: Used throughout for materials, layers, heat sources, probes — zone sub-table follows same pattern
- `_on_architecture_changed()`: Existing template population logic for DLED/ELED — extend for zone generation

### Established Patterns
- mm-to-SI conversion in UI: All dimension inputs use mm in the GUI, convert to meters for the model (heat sources, mesh config)
- `to_dict()`/`from_dict()` serialization: Zone data will need this pattern for JSON round-trip
- `_populate_ui_from_project()`: Central method that refreshes all UI from the project model — will need zone table population
- Expand/collapse pattern: Not currently used in the app — this will be a new UI pattern

### Integration Points
- `Layer` model: Needs `nz` field (from Phase 8) and `material_zones` list (from Phase 7) — Phase 9 builds UI on top of these
- `DisplayProject.layers`: Zone data serialized/deserialized as part of the project JSON
- `SteadyStateResult` / `TransientResult`: Result arrays will have 3D shape with z-dimension — combo must map selection to correct array index
- Status bar: Already shows file path, modified indicator, last run time — add node count display

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-3d-gui-and-eled-zone-preset*
*Context gathered: 2026-03-16*
