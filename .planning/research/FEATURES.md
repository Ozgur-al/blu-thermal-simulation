# Feature Research

**Domain:** 3D RC-network thermal solver — per-cell material zones and z-refinement for structured Cartesian grid
**Researched:** 2026-03-16
**Confidence:** HIGH — findings grounded in direct codebase inspection (network_builder.py, layer.py, project.py), confirmed by electronics-cooling.com PCB thermal conductivity mapping literature, and harmonic-mean conductance theory from peer-reviewed FDM literature.

---

## Context: Scope Boundary

This file covers only the **new v2.0 capabilities** being added to the existing working 2.5D simulator. The following are already shipped and are NOT features to build here:

- 2.5D layered RC thermal network (one material per layer, one z-node per layer)
- Steady-state (`spsolve`) and transient (implicit Euler) solvers
- LED array expansion — grid/edge/custom modes, zone-based power (Phase 6)
- Stack templates — DLED/ELED with architecture dropdown (Phase 6)
- GUI: tabbed editor, temperature maps, probe history, parametric sweep, PDF report, comparison
- JSON round-trip serialization (`to_dict` / `from_dict` pattern)
- Material library presets and user-library import/export

The v2.0 milestone is specifically about making the solver **3D**: per-cell materials within a layer (lateral zones), multiple z-nodes per layer (z-refinement), and the consequences for the network builder, GUI, and visualization.

---

## Why 3D Matters for This Tool

The existing 2.5D model assumes each layer has one material for all x,y positions. This cannot represent:

- **ELED cross-section**: at the same z-level (one layer), you have metal frame | FR4+LED board | air gap | LGP. Four different materials side-by-side. The 2.5D model forces a single homogenized material for the whole layer, which is wrong by 10-100x in local conductivity.
- **Metal bezel inserts**: aluminum strip along panel edges within an otherwise FR4 layer.
- **Copper pour on PCB layers**: copper-rich zones at arbitrary x,y positions within a layer.
- **Thermal interface pads**: localized TIM patches applied to specific regions, not the whole layer.

Z-refinement is needed when:

- A thick layer (e.g. 4mm LGP or 1mm glass) needs temperature gradient through its own thickness.
- Through-plane accuracy matters — not just the average temperature of the layer but the temperature at top vs bottom face.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that must work for the 3D solver to be a credible upgrade. Missing any of these means the feature is incomplete or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-cell material lookup in network builder** | The entire v2.0 value proposition — lateral material zones are meaningless if the solver ignores them | HIGH | Replace `material_for_layer(l_idx)` scalar lookup with `material_at(l_idx, ix, iy)` that queries a per-cell material map. Every conductance G = kA/L computation must use cell-local k. This is the architectural load-bearing change. |
| **Rectangular material zone definition on a layer** | Structured Cartesian grids use rectangular zones as the primitive. Icepak, FloTHERM, ANSYS Fluent cell zones, and EnergyPlus all define material regions as axis-aligned boxes in their structured-grid models. Polygon zones are found only in unstructured-mesh tools. | MEDIUM | A `MaterialZone` dataclass: `(layer_name, material_key, x_min, x_max, y_min, y_max)`. Multiple zones per layer, applied in priority order. Background fill = layer's existing `material` field. This preserves backward compatibility — if no zones exist, the layer's single material fills everything. |
| **Harmonic-mean conductance at material boundaries** | When two adjacent cells have different conductivities, the conductance of the link must use `G = 2*k1*k2 / (k1+k2) * A/L_half` (harmonic mean). Using arithmetic mean at material boundaries is known to overestimate conductance when there is a large k contrast. Published FDM literature confirms harmonic mean as the standard for discontinuous conductivity fields. | MEDIUM | This is a math change in `_add_link_vectorized`: instead of one G value per layer, each link pair gets its own G computed from local cell properties. Vectorization becomes per-link rather than per-layer. |
| **Z-refinement: multiple z-nodes per layer** | The current `n_per_layer` is 1 node through a layer's thickness. For thick layers (LGP 4mm, glass 1.1mm) or high-conductivity materials with strong through-plane gradients, one node per layer loses accuracy. The node-per-layer model is a known limitation of 2.5D formulations. | HIGH | `Layer` gets an optional `nz: int = 1` field. Total node count becomes sum over layers of `nx * ny * nz_i`. The node indexing scheme changes: `node_idx(l_idx, iz, iy, ix)`. Each sub-layer gets thickness `layer.thickness / nz`. Through-plane links connect sub-layers of the same physical layer (using `k_through * A / dz`), distinct from inter-layer links. |
| **Backward compatibility: 2.5D projects load identically** | Existing project JSON files must load and produce the same numerical results as before. Any field addition that breaks `from_dict()` or changes the default behavior is unacceptable. | MEDIUM | Achieved by: `MaterialZone` list defaults to empty (no zones = homogeneous layer, same as before). `nz` defaults to 1 (same node count as before). All new fields use `.get(key, default)` in `from_dict()`. Analytical validation tests must pass before and after the change. |
| **Probe addressing in 3D node space** | Existing probes specify `(layer, x, y)`. When a layer has `nz > 1`, a probe must map to a specific z sub-node. Engineers expect to be able to probe the top face, bottom face, or midplane of a thick layer. | MEDIUM | Probe gets an optional `z_fraction: float = 0.5` (0.0 = bottom face of layer, 1.0 = top face, 0.5 = midplane). When `nz=1`, ignored (single node). When `nz>1`, selects the sub-node nearest to `z_fraction * layer.thickness`. GUI shows this only when the target layer has `nz > 1`. |
| **Analytical validation tests for 3D conduction** | The existing validation suite tests 1D two-layer resistance chains and 2-node RC transients against hand-calculated analytical solutions. Adding 3D material zones without new validation tests leaves correctness unverified. | MEDIUM | Minimum required: (1) Two-zone horizontal layer test: left half = material A, right half = material B, uniform heat on left, verify temperature drop matches series R chain. (2) Z-refinement test: three-node-thick layer, compare midplane temperature against 5-node version — within 1%. (3) Lateral zone interface test: 2×1 cell grid with different k per cell, verify interface conductance uses harmonic mean. |

### Differentiators (Competitive Advantage)

Features that make the 3D upgrade noticeably more capable than what engineers could build themselves in a spreadsheet or 1D tool.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **ELED cross-section zone preset** | Engineers setting up ELED panels today must manually figure out how to represent "metal | FR4 | air | LGP" in the model. A built-in zone preset that auto-fills the correct material zones for ELED cross-section geometry removes trial and error. | MEDIUM | Extend the ELED stack template (from Phase 6) to also generate `MaterialZone` objects for the LGP layer: zone 1 = metal frame strip at left edge, zone 2 = LED board strip, zone 3 = air (or low-k filler), zone 4 = LGP bulk. Widths parameterized from ELED geometry config. |
| **Per-layer nz spinbox in GUI** | Current GUI has no z-refinement control. Commercial tools like Icepak expose mesh resolution per-region. Adding a simple integer spinbox per layer in the Layers tab gives engineers direct control with immediate understanding. | LOW | Add `nz` column to the Layers table (integer, default 1, range 1-20). Existing `TableDataParser` pattern handles it. Total node count updates in the status bar when nz changes so engineers can see the cost. |
| **Material zone table per layer in GUI** | Engineers need a way to define rectangular material zones without editing JSON by hand. A table with columns `[zone_name, material, x_min, x_max, y_min, y_max]` per layer (shown when a layer row is selected) covers the common case. | MEDIUM | Two-panel layout in the Layers tab: top = existing layers table, bottom = zones table that populates when a layer row is selected. Same `QTableWidget` + `TableDataParser` pattern already used for heat sources and LED arrays. |
| **Node count estimate in status bar** | The 3D solver can grow to many more nodes (nx * ny * sum_nz). A live node count display ("3D nodes: 15,000 — est. solve time: <1s") in the status bar lets engineers manage the complexity budget before they run. | LOW | Compute `sum(nx * ny * layer.nz for layer in project.layers)` whenever project changes. The existing status bar already shows last run time; add node count next to it. |
| **Z-plane slicing in temperature visualization** | The current visualization shows per-layer x-y temperature maps. With z-refinement, engineers need to select which z sub-node they are viewing. A simple slider or dropdown "Sub-layer (1 of 3)" added to the existing temperature map panel satisfies this without a full 3D renderer. | MEDIUM | Add a `z_index` control (QComboBox or QSlider) above the temperature map. Default = top sub-node of each layer (surface temperatures). Rebuilds the imshow from `T_3d[layer_idx, z_idx, :, :]`. No new rendering library needed. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like natural extensions of the 3D upgrade but should be deliberately excluded from v2.0.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Polygon or arbitrary-shape material zones** | "Some PCB copper pours are not rectangular" | Polygon zone rasterization onto a Cartesian grid requires a spatial query for every cell during network build. This is the complexity that turns a simple structured-grid tool into a mesh preprocessor. The ELED display use case (metal strips along edges, LED boards at edges) is accurately modeled with rectangles. | Rectangular zones only. Engineers who need polygon accuracy should use Icepak. Document the approximation explicitly. |
| **Temperature-dependent material properties** | "Conductivity changes with temperature — more accurate" | Requires a nonlinear solver loop (Picard or Newton iteration). The current sparse LU factorization approach breaks because the matrix changes with temperature. For the operating range of displays (25-80°C), the error from constant-k assumption is small (<5% for most structural materials). | Keep constant-k. Document range of validity. |
| **Auto z-refinement based on thermal gradient** | "The tool should figure out how many nodes I need per layer" | Adaptive refinement requires multiple solves, convergence checking, and mesh modification — a full adaptive meshing pipeline. This contradicts the tool's value of sub-second to low-second solves. | Expose `nz` as a user parameter with a recommended default in the tooltip. For guidance: nz=1 for thin layers (<0.5mm), nz=2-3 for thick dielectrics (LGP, glass), nz=4+ for through-plane sensitivity studies. |
| **Full 3D visualization (isosurface, volume render)** | "I want to see temperature in 3D" | Requires a 3D rendering engine (PyVista, VTK, or matplotlib mplot3d). mplot3d is slow for large grids and non-interactive. PyVista/VTK would be a major new dependency and integration effort. For display module concept studies, per-layer 2D maps are the correct abstraction. | Z-plane slicing within the existing matplotlib imshow panel. Engineers can step through sub-layers. For cross-section views, a "show xz-slice" option (a 1D profile along z at a selected x,y) is a low-complexity addition if needed. |
| **Unstructured or tetrahedral meshing** | "For curved parts (the bezel fillet) you need triangles" | Display module layers are rectangular blocks. The structured Cartesian grid is the correct mesh for this geometry. Unstructured meshing requires a mesh library (gmsh, etc.), a completely different solver pipeline, and CAD input formats. Out of scope explicitly (per PROJECT.md). | Structured Cartesian grid with rectangular zones is sufficient. The bezel/frame thermal effect is captured via enhanced side boundary conditions. |
| **Per-cell interface resistance (contact conductance maps)** | "The TIM is thicker under certain components — model that" | Would require an interface resistance map (nx * ny floats) per layer interface, stored and looked up during network build. This is physically correct but adds significant model complexity and a new data structure. PROJECT.md explicitly excludes "contact pressure-dependent interface resistance". | Scalar `interface_resistance_to_next` per layer already exists. Engineers can split the layer into sub-layers with different bulk conductivities as an approximation. |

---

## Feature Dependencies

```
[Per-cell material lookup in network builder]
    └──requires──> [Rectangular material zone definition]
                       └──enables──> [ELED cross-section zone preset]

[Z-refinement: multiple z-nodes per layer]
    └──requires──> [New node indexing scheme in network builder]
    └──enables──> [Z-plane slicing visualization]
    └──enables──> [Probe z_fraction addressing]

[Harmonic-mean conductance at material boundaries]
    └──requires──> [Per-cell material lookup in network builder]

[Analytical validation tests — 3D]
    └──requires──> [Per-cell material lookup]
    └──requires──> [Z-refinement]
    (tests must be written after solver changes, not before)

[Material zone table per layer in GUI]
    └──requires──> [Rectangular material zone definition on Layer model]
    └──enhances──> [ELED cross-section zone preset]

[nz spinbox in Layers GUI]
    └──requires──> [Z-refinement model field (Layer.nz)]
    └──enhances──> [Z-plane slicing visualization]

[Node count estimate in status bar]
    └──requires──> [nz in Layer model]
    └──enhances──> [Z-refinement UX]

[Backward compatibility: existing projects load identically]
    └──requires ALL changes have defaults──> [MaterialZone list default empty]
    └──requires──> [Layer.nz default = 1]
```

### Dependency Notes

- **Per-cell material lookup is the architectural prerequisite.** Nothing else works correctly without it. The network builder currently uses `material_for_layer(l_idx)` which returns one material for an entire layer. Every conductance computation in the lateral loop and the through-plane loop must switch to `material_at(l_idx, ix, iy)`. This change is non-negotiable and must come first.

- **Harmonic-mean conductance is inseparable from per-cell material.** Once adjacent cells can have different materials, computing G with a single k per layer is incorrect. The two features must be implemented together. There is no intermediate state where per-cell materials work correctly with arithmetic-mean conductance.

- **Z-refinement changes the node indexing scheme** throughout the solver pipeline (network builder, postprocessor, probe readout, visualization). It should be designed and implemented as a unit with a clean interface (`node_idx(l_idx, iz, ix, iy)`), not incrementally.

- **GUI features depend only on model fields**, not on the solver implementation. The `nz` spinbox in the Layers tab and the `MaterialZone` table can be built as soon as the model dataclasses are updated — the solver does not need to be working yet.

- **Validation tests must come after the solver changes** but before GUI wiring. Tests give confidence that the 3D conductance math is correct before the GUI layer obscures the signal.

- **Backward compatibility must be verified throughout.** Every change to `Layer.from_dict()`, `DisplayProject.__post_init__()`, and `network_builder.py` must be tested against the three example JSON files in `examples/`. These act as regression anchors.

---

## MVP Definition (v2.0 Framing)

This is an existing tool. v2.0 MVP means: the minimum set of 3D features that makes ELED cross-section modeling physically meaningful.

### Launch With (v2.0 core)

- [ ] **Per-cell material lookup + rectangular zones** — ELED lateral heterogeneity is the primary use case; without this, the upgrade is cosmetic
- [ ] **Harmonic-mean conductance** — required for physical correctness when zones exist; must ship alongside zones
- [ ] **Z-refinement (Layer.nz field)** — needed for through-plane accuracy in thick layers; architectural change, build with zone support
- [ ] **New node indexing scheme** — restructures network builder to support arbitrary nz per layer; prerequisite for everything
- [ ] **Backward compatibility** — existing project JSON files and validation tests must be unbroken
- [ ] **Analytical validation tests for 3D** — correctness evidence for the new solver

### Add After Core Is Working (v2.0 polish)

- [ ] **GUI: nz spinbox in Layers tab** — expose z-refinement control; low complexity once model field exists
- [ ] **GUI: Material zones table per layer** — expose zone definition without JSON editing; medium complexity
- [ ] **GUI: Z-plane slicing visualization** — step through sub-layers in temperature map panel; medium complexity
- [ ] **GUI: Probe z_fraction control** — only shown when target layer has nz > 1; low complexity
- [ ] **GUI: Node count estimate in status bar** — helps engineers manage complexity budget; low complexity
- [ ] **ELED cross-section zone preset** — extend Phase 6 ELED template to auto-generate zones; medium complexity once zone model exists

### Future Consideration (v2.x)

- [ ] **XZ cross-section plot** — 1D temperature profile along z at a selected (x, y) position; useful for through-plane studies; not blocking v2.0
- [ ] **Zone import from CSV** — engineers who want to define many zones programmatically; deferred to v2.x if requested
- [ ] **Per-zone heat generation** — heat sources defined relative to a material zone rather than absolute x,y position; useful for LED board modeling; deferred

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Per-cell material lookup in network builder | HIGH | HIGH | P1 |
| Harmonic-mean conductance at boundaries | HIGH | MEDIUM | P1 |
| Z-refinement (Layer.nz + new indexing) | HIGH | HIGH | P1 |
| Backward compatibility + existing tests pass | HIGH | LOW | P1 |
| Analytical 3D validation tests | HIGH | MEDIUM | P1 |
| nz spinbox in Layers GUI | MEDIUM | LOW | P2 |
| Material zones table per layer in GUI | HIGH | MEDIUM | P2 |
| Z-plane slicing in visualization | MEDIUM | MEDIUM | P2 |
| Probe z_fraction addressing | LOW | LOW | P2 |
| Node count in status bar | LOW | LOW | P2 |
| ELED cross-section zone preset | HIGH | MEDIUM | P2 |
| XZ cross-section plot | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v2.0 launch — the solver must work correctly first
- P2: Should have — GUI and visualization make the solver usable interactively
- P3: Nice to have — deferred to v2.x

---

## How Commercial Tools Handle Material Zones in Structured Grids

### FloTHERM (Siemens)

Uses a structured Cartesian grid throughout. Engineers define geometric objects (board, component, fin, etc.) with material properties; the grid intersects these objects and assigns material to each control volume. Resolution is user-controlled via localized grid refinement around objects. FloTHERM does NOT ask the user to define a cell-by-cell material map — instead, it renders the geometry into the grid at solve time. This is effectively the same as the rectangular zone approach: zones overlay the background and override material per cell.

**Lesson for this tool:** The zone-as-object model (define a rectangle, assign material) is the correct UX pattern. A cell-by-cell material table editor would be impractical for engineers. (MEDIUM confidence — from FloTHERM product documentation and training material; see sources.)

### ANSYS Icepak

Also structured Cartesian. Engineers define "blocks" (solid regions) and "PCB" objects with optional layout-derived conductivity maps. PCB conductivity maps are derived from board layout tools as per-tile orthotropic properties — the harmonic mean is used for through-plane and series-parallel for in-plane. At the solver level, each control volume stores its own k values.

**Lesson for this tool:** Per-cell material lookup in the solver is the right architecture; the GUI abstracts this as rectangular zones. The engineering accuracy requires harmonic mean at zone boundaries. (MEDIUM confidence — from Electronics Cooling article on PCB thermal conductivity mapping, 2010, and Icepak user documentation.)

### EnergyPlus / THERM

For building components, uses rectangular zone definition for thermal zones with per-zone material properties. THERM specifically uses polygon zone drawing on cross-sections — but this is for building envelope cross-sections where the geometry is truly polygonal (wall studs, insulation cavities). Display module layers are rectangular stacks where rectangles are adequate.

**Lesson for this tool:** Rectangles are sufficient for display module use cases. Polygons add complexity with no benefit for this geometry class. (HIGH confidence — from EnergyPlus documentation and THERM program description, directly inspected.)

### PCB-specific tools (Sigrity, SIwave thermal, FloTHERM PCB)

PCB thermal analyzers extract per-cell (per-tile) orthotropic conductivity from board layout exports. Each tile has a copper fraction that determines effective k in three directions. The tile-based approach is exactly "rectangular zones" — just automated from the layout bitmap rather than manually entered.

**Lesson for this tool:** For PCB layers, a future extension could accept a copper-fraction map (nx*ny floats) rather than zone rectangles. For v2.0 (display module focus), rectangular zone definition is the correct starting point. (MEDIUM confidence — from Electronics Cooling PCB conductivity mapping article.)

---

## Complexity Notes by Feature

### Per-cell material lookup + harmonic mean conductance — HIGH complexity

The current `_add_link_vectorized` in `network_builder.py` takes a single `conductance: float` for all links in a layer at once. For 3D, lateral links between cells (ix, iy) and (ix+1, iy) must use `G_ij = harmonic_mean(k_i, k_j) * thickness * dy / dx` — one G per link, not one G per layer. The vectorized loop must change from:

```python
g_x = material.k_in_plane * layer.thickness * grid.dy / grid.dx
_add_link_vectorized(base + flat_left, base + flat_right, g_x)  # scalar G for all links
```

to:

```python
# Per-link conductance array using material map
k_left  = material_map[l_idx, iy_all[mask_x], ix_all[mask_x]]      # shape (n_x_links,)
k_right = material_map[l_idx, iy_all[mask_x], ix_all[mask_x] + 1]  # shape (n_x_links,)
k_harm  = 2 * k_left * k_right / (k_left + k_right)
g_x_arr = k_harm * layer.thickness * grid.dy / grid.dx
_add_link_per_pair(base + flat_left, base + flat_right, g_x_arr)    # vector G
```

This requires refactoring `_add_link_vectorized` to accept either a scalar or an array. COO assembly still works — `coo_data.append(g_x_arr)` instead of `np.full(n, g_x)`.

**Estimated effort:** 3-5 days for network builder refactor + correctness tests.

### Z-refinement + new node indexing — HIGH complexity

Current indexing: `node_idx(l_idx, iy, ix) = l_idx * n_per_layer + iy * nx + ix`

3D indexing with nz: `node_idx(l_idx, iz, iy, ix) = offset[l_idx] + iz * ny * nx + iy * nx + ix`

Where `offset[l_idx] = sum(ny * nx * nz_k for k in range(l_idx))`.

This changes:
- `n_nodes` computation
- All node index lookups in boundary condition application (top/bottom nodes are now the topmost iz sub-node of the top layer, and bottommost iz of the bottom layer)
- All probe readout (probe must resolve to a specific iz)
- Postprocessor result array shape: changes from `(n_layers, ny, nx)` to `(total_sub_layers, ny, nx)` or a ragged structure
- Visualization: layer selection must include sub-layer index when nz > 1

**Estimated effort:** 4-7 days including all downstream changes.

### Rectangular material zone model + GUI — MEDIUM complexity

Model change: add `zones: list[MaterialZone] = field(default_factory=list)` to `Layer`. `MaterialZone` is a new dataclass: `layer_name (str implied), material (str), x_min, x_max, y_min, y_max (float)`. The `material_map[l_idx, :, :]` array is built once per solve from the zone definitions, using zone priority order (last zone wins at any cell). Background = `layer.material`.

GUI: a second `QTableWidget` below the layers table. Populates when a layer row is selected. Columns: `Material | x_min [mm] | x_max [mm] | y_min [mm] | y_max [mm]`. Same `+/-` row add/delete pattern as the existing heat sources table.

**Estimated effort:** 2-3 days model + 2-3 days GUI.

### Z-plane slicing visualization — MEDIUM complexity

The postprocessor currently returns temperature arrays shaped `(n_layers, ny, nx)` (one z-node per layer). With z-refinement it returns `(total_sub_layers, ny, nx)` or an indexed structure. The visualization tab needs a layer selector (existing) plus a sub-layer (iz) selector (new). `pcolormesh` / `imshow` call is unchanged — just the data slice changes.

**Estimated effort:** 1-2 days.

---

## Interface Stability Considerations

These interfaces are load-bearing and their changes must be managed carefully:

| Interface | Current Contract | v2.0 Change | Risk |
|-----------|-----------------|-------------|------|
| `material_for_layer(l_idx)` on `DisplayProject` | Returns one `Material` for entire layer | Must add `material_at(l_idx, ix, iy)` returning per-cell material | LOW — add new method, don't remove old one yet |
| `build_thermal_network(project)` signature | Takes `DisplayProject`, returns `ThermalNetwork` | Unchanged signature; internal structure changes | MEDIUM — return type `ThermalNetwork` needs updated `n_nodes` and `n_layers` semantics |
| `ThermalNetwork.n_nodes` property | `n_layers * nx * ny` | Must become `sum(nz_i) * nx * ny` | HIGH — any code computing result array shape from `n_layers * nx * ny` must be updated |
| Probe readout in `postprocess.py` | Takes `(layer_idx, ix, iy)`, returns scalar | Must take `(layer_idx, iz, ix, iy)` with iz from probe's z_fraction | MEDIUM |
| Postprocessor result shape | `T_array.shape = (n_layers, ny, nx)` | Becomes `(total_sub_layers, ny, nx)` or ragged by-layer structure | HIGH — visualization and GUI depend on this shape |

---

## Competitor Feature Analysis

| Feature | Icepak | FloTHERM | This Tool (v2.0) |
|---------|--------|----------|-----------------|
| Per-cell material assignment | Object-based geometry → grid intersection, any shape | Object-based (blocks, packages), Cartesian grid intersection | Rectangular zone overlay on background material; applied at network build time |
| Z-refinement | Automatic local mesh refinement per region | Overlapping localized grid; user controls local z-resolution | Per-layer nz integer; uniform sub-division within a layer |
| Material zone UI | 3D CAD-style object placement | Flotherm SmartParts wizard + drag-and-drop component placement | Table-based zone entry (x_min, x_max, y_min, y_max) in the Layers tab |
| 3D visualization | Full 3D temperature field rendering with cut planes | Full 3D post-processing, cut planes, streamlines | 2D z-plane slice of existing matplotlib imshow; concept-study level |
| Interface conductance | Automatic harmonic mean at material boundaries | User-specified contact resistance per interface | Harmonic mean at zone boundaries (automatic); scalar interface resistance remains at layer boundaries |

**Assessment:** Commercial tools use object-based zone geometry that is rasterized onto the Cartesian grid at solve time. This tool's rectangular zone approach is the same physics at a simpler input abstraction, appropriate for the concept-study use case.

---

## Sources

- Direct codebase inspection: `G:/blu-thermal-simulation/thermal_sim/solvers/network_builder.py` — existing `_add_link_vectorized`, `material_for_layer`, `build_thermal_network` (HIGH confidence)
- Direct codebase inspection: `G:/blu-thermal-simulation/thermal_sim/models/layer.py`, `project.py`, `models/heat_source.py` (HIGH confidence)
- Direct codebase inspection: `.planning/PROJECT.md` — Out-of-scope items confirm polygon zones, unstructured meshing, temperature-dependent properties all excluded (HIGH confidence)
- Electronics Cooling: "Creating PCB Thermal Conductivity Maps Using Image Processing" (2010) — tile-based per-cell conductivity approach, validation against detailed simulation at 3.3% average error: https://www.electronics-cooling.com/2010/09/creating-pcb-thermal-conductivity-maps-using-image-processing/ (MEDIUM confidence)
- Idaho National Laboratory: "A Comparative Study of the Harmonic and Arithmetic Averaging of Diffusion Coefficients for Non-Linear Heat Conduction Problems" — harmonic mean standard for discontinuous conductivity in FDM: https://inldigitallibrary.inl.gov/sites/sti/sti/3952796.pdf (HIGH confidence)
- ScienceDirect (Patankar 1978 pattern): harmonic mean conductance at material interfaces in finite volume / finite difference — established standard in numerical heat transfer textbooks (HIGH confidence; method appears in Patankar "Numerical Heat Transfer and Fluid Flow" 1980, a foundational reference)
- FloTHERM product specification (Siemens/Innofour): structured Cartesian grid, localized overlapping grid: https://www.innofour.com/solutions/cae-simulation-and-test/cad-embedded-cfd/technical-specifications/ (MEDIUM confidence)
- FloTHERM V11 overlapping localized grid article: https://blogs.sw.siemens.com/simulating-the-real-world/2015/11/30/top-7-flotherm-v11-features-5-overlapping-localized-grid/ (MEDIUM confidence)
- THERM 2.0 program description (polygon zone definition for building cross-sections): https://www.osti.gov/servlets/purl/901210 (HIGH confidence)
- EnergyPlus Input/Output Reference: thermal zone geometry (rectangular surface definition): https://bigladdersoftware.com/epx/docs/8-3/engineering-reference/conduction-finite-difference-solution.html (HIGH confidence)

---

*Feature research for: 3D RC-network thermal solver — per-cell material zones and z-refinement*
*Research scope: v2.0 milestone features only (not existing 2.5D capabilities)*
*Researched: 2026-03-16*
