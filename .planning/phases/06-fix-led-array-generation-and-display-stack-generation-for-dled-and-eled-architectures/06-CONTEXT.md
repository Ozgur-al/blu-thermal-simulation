# Phase 6: Fix LED Array Generation and Display Stack Generation for DLED and ELED Architectures - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable the simulator to correctly model both direct-lit (DLED) and edge-lit (ELED) display backlight architectures. This means: architecture-aware LED array generation (2D grid for DLED with zones and edge offsets, 1D edge strips for ELED), predefined layer stack templates for each architecture, and a GUI workflow that lets users pick an architecture and get a pre-populated project. The existing manual/custom workflow remains available.

</domain>

<decisions>
## Implementation Decisions

### ELED LED Placement
- Support all four edge configurations: bottom-only, top-only, left/right (dual-edge), and all-four-sides
- LEDs are positioned with a configurable offset from the panel edge (not at the edge itself, not outside the panel)
- Discrete LEDs with pitch along the edge — expands to individual HeatSource objects like current LEDArray
- Edge LEDs live on a separate LED board layer (thin PCB/FPC) adjacent to the LGP, not on the LGP layer itself

### Stack Templates — DLED
- Layer order (bottom to top): Back Cover (Al) → Metal Frame (Steel/Al) → LED Board (FR4) → Optical Sheets (variable count, customizable) → OCA → Display Cell (Glass) → Cover Glass
- Optical sheet stack (diffuser, BEF, DBEF, etc.) must be customizable — user can add/remove optical layers
- Templates provide full defaults: material assignments and typical thicknesses pre-filled
- Metal bezel/frame modeled as enhanced side boundary conditions (higher effective h) — the frame bottom is captured by the Metal Frame layer in the stack

### Stack Templates — ELED
- Layer order (bottom to top): Back Cover (Al) → Metal Frame (Steel/Al) → LGP (PMMA/acrylic) → Optical Sheets (variable) → OCA → Display Cell (Glass) → Cover Glass
- Edge LED board is a separate thin layer adjacent to the LGP (not stacked in the Z-direction — this is an edge-mounted component)
- Same metal frame treatment as DLED: frame layer in stack + enhanced side boundary

### DLED Array Configuration
- Auto-center LED array on the panel dimensions (derive from width/2, height/2)
- Independent edge offsets per side: offset_top, offset_bottom, offset_left, offset_right — LEDs don't extend to panel border when offset > 0
- Zone-based dimming: user specifies zone grid (zone_count_x, zone_count_y), system divides LED grid evenly across zones, user sets power per zone
- Uniform power within each zone

### GUI Workflow
- Architecture dropdown at the top of the editor: DLED / ELED / Custom
- Selecting DLED or ELED auto-populates layers table, materials, and LED array config with template defaults
- Switching architecture replaces the project silently (no confirmation dialog)
- LED Arrays tab adapts based on architecture: DLED shows grid config + edge offsets + zone power table; ELED shows edge selection + strip parameters (offset, count, pitch, LED footprint)
- "Custom" keeps the current fully manual workflow unchanged

### Claude's Discretion
- Default thickness values for each template layer
- Default material assignments from the existing material library
- Zone power table UI layout within the LED Arrays tab
- How edge LED board layer is represented in the 2.5D model (since it's alongside the LGP, not stacked)
- Loading skeleton / transition when switching architectures

</decisions>

<specifics>
## Specific Ideas

- Display assemblies go into a metal "bucket" frame that covers 5 sides — this is universal to both DLED and ELED architectures
- The optical sheet stack (diffuser plates, brightness enhancement films) varies between designs — must not be hardcoded to a single diffuser layer
- DLED LED boards cover the full back area (minus edge offsets); ELED LED boards are thin FPC strips on the LGP edges
- Zone dimming is important for DLED thermal analysis — different zones at different power levels create asymmetric thermal patterns

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LEDArray` class (`models/heat_source.py`): Currently handles 2D grid expansion — can be extended for edge strip mode and zone power
- `HeatSource` class: Individual LED heat sources after expansion — no changes needed
- `BoundaryConditions` / `SurfaceBoundary` (`models/boundary.py`): Side boundary already supports convection h — can be enhanced for metal frame
- `default_materials()` in `material_library.py`: Already includes Glass, OCA, PMMA, Aluminum, FR4, Steel — covers most template materials
- `structure_preview.py`: Stack visualization widget — will need to render architecture-aware stacks

### Established Patterns
- All domain models use `to_dict()` / `from_dict()` for JSON serialization — new fields must follow this pattern
- `LEDArray.expand()` returns `list[HeatSource]` — zone power and edge strip modes should produce the same output type
- `DisplayProject.expanded_heat_sources()` aggregates all sources — existing pipeline will work if expand() returns correct sources
- GUI tables with undo/redo via `QUndoStack` — new UI elements must integrate with the existing undo system

### Integration Points
- `MainWindow._build_led_arrays_tab()`: Will need architecture-aware mode switching
- `TableDataParser.parse_led_arrays_table()` / `populate_tables()`: Must handle new LED array fields
- `network_builder.py:build_thermal_network()`: Already distributes heat sources from expanded list — no changes needed if expand() is correct
- Template system needs to write to layers table, materials table, and LED arrays table simultaneously

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-fix-led-array-generation-and-display-stack-generation-for-dled-and-eled-architectures*
*Context gathered: 2026-03-15*
