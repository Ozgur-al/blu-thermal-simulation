# Phase 11: Voxel-Based 3D Solver - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 2.5D RC-network with a true per-cell 3D voxel solver. The user defines physical structure as named assembly blocks (position, size, material) placed in 3D space. LEDs attach as surface sources on block faces. The solver auto-generates a conformal mesh, assigns per-voxel materials, and computes heat distribution from actual thermal resistances. Full 3D visualization with PyVista. Clean break from the old Layer-based model.

</domain>

<decisions>
## Implementation Decisions

### Voxel grid generation — Assembly block model
- New explicit voxel model replacing the old Layer/Zone/EdgeLayer abstraction
- Users define named 3D assembly blocks with position, size, and material — like building with LEGO
- Each block is a rectangular solid placed at (x, y, z) with dimensions (width, height, depth) and a material reference
- The solver reads block definitions and auto-generates the 3D voxel grid
- No manual voxel painting — the block abstraction is the input model

### LED / heat source placement — Surface sources
- LEDs are NOT assembly blocks — they remain separate heat source objects
- LEDs attach to a named block's surface (e.g., "place LED array on top face of FR4_strip")
- Thermal contact happens through the interface between the LED source and the block face it's placed on
- This keeps the block model clean (geometry + material) and heat sources as a separate concern

### Boundary conditions — Auto-detect exposed faces
- Any voxel face not touching another block is automatically an exposed surface
- User assigns convection/radiation coefficients to named boundary groups (e.g., "top_exposed" = natural convection, "bottom_exposed" = forced cooling)
- System identifies which faces belong to which group automatically
- No more explicit top/bottom/side surface model

### Non-uniform z-thickness — Full XYZ conformal mesh
- Mesh snaps to ALL block boundaries in x, y, AND z
- Every block face aligns exactly with a mesh line — no staircase approximation
- Z-layers inserted wherever any block has a face (e.g., 4mm LGP + 1.6mm FR4 produces z-slices at 0, 1.6, 4mm)
- Non-uniform grid spacing in all three dimensions

### Empty voxels — Air-filled
- Voxels not occupied by any block default to air (k ≈ 0.026 W/mK)
- Physically correct: gaps between components really are air
- Preserves thermal coupling through air gaps (important for ELED: LED→air→LGP path)

### Mesh size control — Warn but allow
- No hard limits on node count or minimum cell size
- Warn the user if node count exceeds a threshold (e.g., 500k nodes) but don't block solving
- User decides whether to coarsen block definitions or accept longer solve times

### Backward compatibility — Clean break
- Remove old Layer/Zone/EdgeLayer models, old network builder, and old solver code entirely
- Git history preserves everything — no legacy module needed
- New project JSON format based on assembly blocks
- Existing project files require manual migration (documented)

### Test strategy — Rewrite existing tests
- Port existing analytical validation tests (1D resistance chain, 2-node network, RC transient decay) to use assembly blocks
- Same physics validation, new input model
- Proves the new voxel solver matches known analytical answers

### Example files — DLED + ELED
- Ship ready-to-run example JSON files for both architectures:
  - DLED backlight: simple slab stack (diffuser, LGP, reflector, metal frame) with LED array on bottom
  - ELED module: full edge assembly (metal frame, air gaps, FR4 PCB strips, LGP, LEDs on PCB faces)
- Users learn the new format by example

### Result visualization — Full 3D with PyVista/VTK
- PyVista (VTK wrapper) for 3D scientific visualization
- Embedded in existing PySide6 GUI as a new "3D View" tab via PyVista's QtInteractor widget
- Essential features:
  - **Slice planes**: interactive cutting planes sliding through x, y, z to reveal internal temperatures
  - **Block transparency/hide**: toggle visibility or transparency per assembly block
  - **Temperature threshold filter**: show only voxels above/below a temperature value
  - **Probe points in 3D**: click to read temperature, or place named probes as labeled markers

### Claude's Discretion
- Sparse matrix format and solver choice (spsolve vs iterative for large meshes)
- Internal data structures for the conformal mesh generator
- Exact PyVista widget layout and toolbar controls
- Warning threshold for node count
- Air gap thermal modeling details (pure conduction vs effective conductivity)
- JSON schema design for the new project format

</decisions>

<specifics>
## Specific Ideas

- "I'm expecting a full, easy-to-use ELED and DLED thermal simulator — put LEDs anywhere and they interact with environment as expected"
- Assembly blocks like LEGO — define physical components, place them in space, and the physics just works
- The ELED use case is the driving motivation: metal frame surrounding LGP, FR4 PCB strips with LEDs adhered to the frame, air gaps between components — all at different z-heights that the old 2.5D model couldn't represent

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Material` dataclass: anisotropic k_in_plane / k_through — reusable as-is for voxel materials
- `material_library.py`: preset materials (aluminum, copper, FR4, etc.) — directly applicable
- `HeatSource` / `LEDArray`: expand() pattern could be adapted for surface source placement on block faces
- `Grid2D`: mesh utilities — will need replacement with 3D conformal mesh class
- `constants.py`: Stefan-Boltzmann and physical constants — reusable
- `postprocess.py`: statistics, probe readout — needs adaptation for 3D results
- Implicit Euler transient solver pattern (LU prefactoring) — algorithm reusable even with new mesh

### Established Patterns
- Frozen dataclasses for immutable model objects (`@dataclass(frozen=True)`)
- `to_dict()` / `from_dict()` round-trip JSON serialization on all model classes
- `ThermalNetwork` as intermediate between model and solver (sparse matrix A, vectors b, c)
- Solvers are stateless — each call rebuilds network from project
- Result dataclasses (`SteadyStateResult`, `TransientResult`) with shaped temperature arrays

### Integration Points
- `cli.py`: argument parsing, solver orchestration, export pipeline — needs rewrite for new model
- `gui.py` / `main_window.py`: tabbed editor — needs new block editor replacing layer editor, plus 3D view tab
- `project_io.py`: JSON load/save — needs new format for assembly blocks
- `csv_export.py`: export functions — needs adaptation for 3D voxel results
- `plotting.py`: matplotlib 2D heatmaps — supplemented by PyVista 3D viewer

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-voxel-3d-solver*
*Context gathered: 2026-03-16*
