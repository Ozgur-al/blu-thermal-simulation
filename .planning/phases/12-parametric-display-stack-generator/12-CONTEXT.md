# Phase 12: Parametric Display Stack Generator - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Toolbar wizard that generates all AssemblyBlocks and boundary conditions from high-level parameters. User picks DLED/ELED architecture, configures LED placement, layer thicknesses, and BCs — the generator creates the full block stack. Also adds max_cell_size UI control for adaptive mesh refinement (already implemented in backend, needs UI exposure).

</domain>

<decisions>
## Implementation Decisions

### Wizard structure
- Sequential QWizard with step-by-step pages: Architecture → Panel dims → LED config → Layer thicknesses → BCs → Mesh → Generate
- Back/Next/Finish navigation
- Live 3D preview panel on the right side of the wizard — updates as parameters change
- Accessible via toolbar button + File menu entry ("Generate Display Stack")
- On Finish: replaces all existing blocks in the block editor (clean slate)

### ELED cross-section (front to back)
1. Panel (LCD)
2. Optical Films (N per-film table: material + thickness)
3. LGP (PMMA)
4. Reflector
5. Metal Frame — tray/border shape with side walls wrapping around the stack perimeter
6. Back Cover
- Air fills gaps between frame side walls and inner components
- LEDs on FR4 PCB adhered to metal frame at selected edges (at LGP z-level)

### DLED cross-section (front to back)
1. Panel (LCD)
2. Optical Films (N per-film table: material + thickness)
3. Diffuser Plate
4. Air gap (LED cavity)
5. LED array on PCB (LEDs face forward toward diffuser)
6. PCB
7. Reflector
8. Metal Frame — same tray/border shape as ELED
9. Back Cover

### Layer thickness configuration
- All layers configurable with sensible defaults pre-filled
- Optical films: count spinner + per-film mini-table (each film has its own material and thickness)
- Example defaults: Panel=1.5mm, LGP=4mm, Metal Frame=3mm, PCB=1.6mm, Reflector=0.3mm, Back Cover=1mm

### LED placement — ELED
- 4 checkboxes for top/bottom/left/right edges
- Per-edge configuration table: each selected edge gets its own row with count, LED width, LED height, LED depth, power per LED
- Uniform pitch auto-calculated: pitch = usable_length / count
- Symmetric offset/margin from both ends of the edge (user-configurable, LEDs distribute within remaining span)

### LED placement — DLED
- Grid layout: Rows × Columns
- X pitch and Y pitch (mm)
- Symmetric offset from panel edges
- LED dimensions (width, depth, height) and power per LED

### Boundary conditions
- Preset-based: Natural convection (h=8), Forced air (h=25), Enclosed still air (h=3), Custom
- Per-face assignment in the wizard (top, bottom, front, back, left, right — each face gets its own preset/override)
- Ambient temperature field
- Include radiation checkbox
- h override field per face

### Mesh configuration
- max_cell_size default: 2mm (hardcoded default in wizard)
- cells_per_interval: 1 (default)
- Show in wizard as a configuration step, user can adjust
- max_cell_size UI control also needs to be added to the block editor's Mesh tab (currently missing)

### Claude's Discretion
- LED naming convention (e.g. LED-L-0, LED-R-0, LED-Grid-R2C3)
- PCB block sizing relative to LEDs (how much wider/deeper than the LED row)
- Frame wall thickness default
- Air gap sizing between frame walls and inner components
- Wizard page layout and spacing details
- Material defaults for each layer type (which builtin material to pre-select)
- Estimated cell count display (nice-to-have)

</decisions>

<specifics>
## Specific Ideas

- Metal frame is a tray/border — has a back plate AND side walls that wrap around the perimeter. Inner components sit inside the tray.
- For ELED, the LED PCBs (FR4) are adhered to the metal frame side walls, at the same z-level as the LGP
- The air between frame side walls and inner components must be represented as explicit air blocks
- Optical films should support different materials per film (BEF, DBEF, diffuser sheet, etc.) via the per-film table

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SweepDialog` (QDialog pattern): form-based dialog with dropdown → dynamic fields, OK/Cancel — template for wizard pages
- `BlockEditorWidget.build_project()` / `load_project()`: project assembly from UI — wizard output feeds into `load_project()`
- `_mm()` / `_m()` unit conversion helpers: all UI in mm, storage in SI metres
- `_make_material_combo()`: material dropdown builder with library integration
- `_float_item()`: right-aligned numeric table cell helper
- `validate_blocks()`: post-generation validation for overlap/contact warnings

### Established Patterns
- QDialog with `_build_ui()` method + QDialogButtonBox
- Table-driven data entry (QTableWidget) with add/remove row buttons
- `project_changed` Signal for reactive 3D view updates
- `to_dict()` / `from_dict()` serialization on all model classes

### Integration Points
- **Toolbar**: `VoxelMainWindow._build_toolbar()` — add generator button here
- **Menu**: `VoxelMainWindow._build_menus()` — add under File menu
- **Block editor**: `BlockEditorWidget.load_project(project)` — wizard generates VoxelProject, passes to this
- **3D view**: `Voxel3DView.update_structure()` — auto-updates via `project_changed` signal chain
- **Mesh config**: `VoxelMeshConfig.max_cell_size` exists in model + backend, needs UI spinbox in block editor Mesh tab
- **BoundaryGroup.faces**: per-face BC assignment (implemented in Plan 11-06) — wizard uses this for per-face presets

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-parametric-display-stack-generator*
*Context gathered: 2026-03-16*
