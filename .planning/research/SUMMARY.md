# Project Research Summary

**Project:** blu-thermal-simulation v2.0 — 3D RC-network thermal solver
**Domain:** Engineering desktop thermal simulation tool (Python / NumPy / SciPy sparse)
**Researched:** 2026-03-16
**Confidence:** HIGH

## Executive Summary

This milestone upgrades an existing, working 2.5D RC-network thermal simulation tool (one material per layer, one z-node per layer) to a 3D solver that supports per-cell material zones within a layer and multiple z-nodes through each layer's thickness. The upgrade is motivated by ELED display module cross-sections, where a single z-layer contains four materially distinct regions side by side (metal frame, FR4/LED board, air gap, LGP) that the current homogenized-material model cannot represent without errors of 10–100x in local conductivity. Research confirms that commercial tools (Icepak, FloTHERM) solve the same problem the same way: rectangular zone descriptors overlay a Cartesian grid background material and are rasterized to per-cell material arrays at solve time. This is the right architecture for this tool.

No new dependencies are required. Every capability needed for the 3D solver, per-cell material assignment, z-refinement, and z-slice visualization is already present in the installed stack (NumPy 1.26+, SciPy 1.12+, Matplotlib 3.8+, PySide6 6.7+). The implementation is a restructuring of the existing network builder, model dataclasses, and result array conventions. The largest changes are in `network_builder.py` (node indexing scheme, per-cell conductance arrays, z-sublevel loop structure), and these cascade through the postprocessor, solvers' reshape calls, and probe extraction. The solver core (`spsolve`, `splu`) is unchanged.

The dominant risks are correctness risks, not dependency risks. Three pitfalls are critical: (1) existing projects must produce identical temperatures after the migration — a regression test written before any builder changes is the non-negotiable guard; (2) node indexing must be centralized in a single `NodeLayout` abstraction before z-refinement is added, because the old `layer_idx * n_per_layer` formula is silently wrong for variable nz per layer; and (3) per-cell conductance must be computed via NumPy vectorized array slicing (harmonic mean), not a Python loop per cell, or network build time degrades by two orders of magnitude. None of these are novel problems — they have clear, documented solutions detailed in the research.

---

## Key Findings

### Recommended Stack

No new packages are required. All 3D solver capabilities are covered by the existing `requirements.txt`. The decisions are about usage patterns within the existing stack, not additions to it.

**Core technologies:**

- **NumPy 1.26+** — per-cell material maps as `uint8` index arrays into parallel `float64` property lookup arrays; vectorized harmonic-mean conductance via array slicing; all hot-path operations must stay in NumPy, not Python loops; `uint8` supports up to 256 materials (displays use 10–20), costs 1 byte/cell vs 8 for float64
- **SciPy 1.12+ sparse** — COO accumulation then single `tocsr()` conversion remains correct at 3D scale; `csr_matrix` (legacy API) kept — no migration to `csr_array` until deprecation is announced; `spsolve` and `splu` are unchanged; int32 overflow bug fixed in 1.8.0, already satisfied by this version requirement
- **Matplotlib 3.8+** — z-slice navigation uses `imshow` + `set_data` + `draw_idle` (existing pattern, no figure recreation); `Axes3D.plot_surface` is explicitly excluded for temperature results (software renderer bottleneck at 100x100+ arrays; 3D shading distorts thermal gradient perception); `Axes3D` retained only for the existing structure preview schematic
- **PySide6 6.7+** — `QSlider` for z-node selection; `QTableWidget` for zone definition; existing `FigureCanvasQTAgg` embedding unchanged; all needed widgets are in the installed version
- **pytest 8.0+** — new analytical 3D validation tests required; backward compat regression test (reference temperatures saved from v1.0 solver) is mandatory before any builder changes

**Memory envelope (100x100x40 node 3D system):** ~45 MB matrix + vectors; factorization fill-in expected 110–330 MB for banded 3D systems; well within 8 GB+ desktop RAM. Threshold for concern: >300k nodes for direct solver stall risk, >1M nodes for COO assembly memory pressure.

See `STACK.md` for detailed storage pattern rationale, per-scenario guidance, and alternatives considered.

### Expected Features

**Must have — v2.0 core (launch-blocking):**
- Per-cell material lookup in the network builder — replaces the single scalar `material_for_layer(l_idx)` path; every conductance computation uses cell-local material properties
- Rectangular material zone definition on `Layer` — `MaterialZone` dataclass (layer name, material key, x0, y0, x1, y1); background fill = `layer.material`; last-defined zone wins on overlap
- Harmonic-mean conductance at zone boundaries — `k_eff = 2*k1*k2/(k1+k2)`; inseparable from per-cell material and must ship together; arithmetic mean is physically wrong at high k-contrast interfaces (aluminum vs air is 4,000x contrast)
- Z-refinement: `Layer.nz: int = 1` — multiple z-nodes through a layer's thickness; `dz_sub = layer.thickness / layer.nz`; internal z-z links use `G = k_through * A / dz_sub` with no interface resistance term
- New node indexing scheme — `node = (z_offsets[l] + k) * (nx*ny) + iy*nx + ix`; centralized in a `NodeLayout` abstraction established before any other builder changes
- Backward compatibility — existing project JSON files load without modification, solve to identical temperatures; `nz` defaults to 1, `material_zones` defaults to `[]`
- Analytical 3D validation tests — minimum: two-zone lateral boundary test, single-material z-refined slab temperature profile vs 1D analytical solution, harmonic-mean interface conductance correctness test

**Should have — v2.0 polish (GUI layer, add after solver is validated):**
- GUI: `nz` spinbox per layer in the Layers tab (default 1, max 10 soft guard)
- GUI: material zones table (x_min, x_max, y_min, y_max, material columns) populated when a layer row is selected
- GUI: z-plane slice selector in the temperature map panel (`QComboBox` or `QSlider`)
- GUI: probe `z_fraction` control (shown only when target layer has nz > 1)
- GUI: live total node count in the status bar (updates on nz or mesh parameter change, within 100ms)
- ELED cross-section zone preset — extend Phase 6 ELED stack template to auto-generate `MaterialZone` objects for metal strip, LED board, air gap, LGP bulk

**Defer to v2.x:**
- XZ cross-section plot (1D temperature profile along z at selected x,y)
- Zone import from CSV
- Per-zone heat generation (heat source relative to zone position)
- Polygon or arbitrary-shape material zones — rectangles are sufficient for all display module geometries; polygon rasterization adds a mesh-preprocessor complexity category
- Temperature-dependent material properties — requires nonlinear solver loop, not justified for 25–80°C operating range
- Auto z-refinement based on thermal gradient — adaptive meshing pipeline contradicts the tool's sub-second to low-second solve target
- Full 3D isosurface / volume rendering — PyVista/VTK dependency, out of scope

See `FEATURES.md` for the full feature dependency graph, effort estimates (days per feature), and competitor feature comparison (Icepak, FloTHERM, EnergyPlus).

### Architecture Approach

The existing solver pipeline architecture is preserved. `DisplayProject` gains two new fields (`material_zones: list[MaterialZone]` on the project and `nz: int = 1` on `Layer`). A new `build_material_map()` helper resolves zone rectangles to per-cell property arrays once before network assembly. The network builder is rewritten to use cumulative z-offsets, per-cell conductance arrays (harmonic mean for lateral links), and separate within-layer vs between-layer through-thickness conductance formulas. The `ThermalNetwork` dataclass gains `n_z_nodes`, `z_layer_map`, and `z_sublevel_map` fields. Solvers change only their reshape call. Postprocessor probe extraction and the GUI require targeted updates to consume `z_layer_map`.

**Major components:**

1. **`MaterialZone` model** (`thermal_sim/models/material_zone.py`, new) — rectangular override descriptor with `to_dict`/`from_dict`; pure dataclass, no dependencies; coordinates in metres (SI), GUI displays in mm
2. **`build_material_map()` helper** (`thermal_sim/solvers/material_map.py`, new) — resolves zone list + layer defaults to per-cell `[n_layers, ny, nx]` float64 property arrays; called once at network build time; AABB overlap logic reused from existing `_source_mask()`; cleanly separates zone geometry from conductance physics
3. **`NodeLayout` / z-offset scheme** (embedded in `network_builder.py`) — cumulative offset array `z_offsets[l] = sum(nz[:l])`; single source of truth for `(layer_idx, k, iy, ix) -> flat_node_idx`; must be established before any z-refinement code; eliminates all inline `layer_idx * n_per_layer` expressions
4. **`network_builder.py` (modified)** — z-sublevel loops for within-layer through-thickness links; per-cell harmonic-mean conductance arrays for lateral links; `_add_link_vectorized()` extended to accept `conductance: np.ndarray | float`; heat sources deposited on top z-node of target layer by default (surface-mounted assumption)
5. **`ThermalNetwork` (modified)** — adds `n_z_nodes`, `z_layer_map`; `n_nodes` property becomes `n_z_nodes * nx * ny`; backward compat preserved when all nz=1 (formula reduces to current scheme exactly)
6. **Solvers (reshape only)** — `n_layers` in reshape calls replaced by `n_z_nodes`; no other changes to steady-state or transient solver logic
7. **Postprocessor + GUI (z-aware updates)** — probe extraction uses `z_offsets[layer_idx] + (nz-1)` for top-face node; GUI layer profile plot uses `z_layer_map` to group z-nodes by physical layer; temperature map panel gains z-index selector

**Build order (strict dependency chain):**

1. `MaterialZone` model (no deps)
2. `Layer.nz` field extension (no deps)
3. `DisplayProject.material_zones` + validation
4. `build_material_map()` helper (independently testable)
5. `ThermalNetwork` schema extension
6. `network_builder.py` rewrite (highest risk; test backward compat with nz=1 / no zones first)
7. Solver reshape changes
8. Postprocessor probe index fix
9. New 3D validation tests (analytical benchmarks)
10. GUI z-slice controls and zone editor

See `ARCHITECTURE.md` for full data flow diagram, serialization change patterns, anti-pattern catalogue, and integration point callsite table.

### Critical Pitfalls

1. **Per-cell conductance lookup destroys vectorization** — naive Python `for` loop over cells to look up per-cell material causes ~100x slowdown (milliseconds becomes seconds at a 30x20 mesh). Prevention: build per-link conductance arrays using NumPy array slicing and harmonic mean before calling `_add_link_vectorized()`; extend that function to accept `float | np.ndarray`. Warning sign: any `for ix in range(grid.nx)` loop inside the network builder inner path.

2. **Node index formula silently breaks for variable nz** — `layer_idx * n_per_layer` is wrong as soon as any layer has `nz > 1`; wrong nodes are indexed, probes return plausible but incorrect temperatures with no error. Prevention: centralize all node indexing in a `NodeLayout` abstraction before writing any z-refinement code; write a unit test for heterogeneous `nz=[1,3,2]` configuration immediately after creating `NodeLayout`.

3. **Backward compatibility drift** — old projects load without error but produce different temperatures because the new builder uses a subtly different conductance formula in the fallback path (e.g., different half-thickness handling or accidentally omitting the interface resistance term). Prevention: write the regression test (compare new builder output to v1.0 reference `.npy` temperature file) before touching any builder code; this test is the Phase 1 entry gate.

4. **Interface resistance applied to within-layer z-z links** — `interface_resistance_to_next` belongs only at the physical layer boundary, not between z-sublevel nodes within the same layer; applying it internally makes through-plane gradient 5–10x too steep. Prevention: maintain two distinct code paths — internal z-z links use `G = k_through * A / dz_sub` only; inter-layer links use half-thickness + interface + half-thickness. Analytical 1D slab test for nz=5 catches this immediately.

5. **SuperLU factorization stalls GUI at large 3D meshes** — at nz=5 across 8 layers on a 100x80 mesh (3.2M nodes), factorization can take minutes on a laptop; progress bar appears frozen (indistinguishable from a crash). Prevention: add pre-solve warning at >300k nodes; keep nz spinbox default at 1, max at 10; confirm `splu()` runs inside the existing `SimulationController` worker thread with an indeterminate progress indicator.

See `PITFALLS.md` for performance trap table, integration gotcha table, UX pitfalls, and the complete "Looks Done But Isn't" verification checklist.

---

## Implications for Roadmap

Based on the combined research, the v2.0 milestone splits into three phases driven by the dependency structure and risk profile documented in the architecture and pitfalls research.

### Phase 1: 3D Solver Core — Per-Cell Materials and Node Indexing

**Rationale:** Per-cell material lookup is the architectural load-bearing change. Every other v2.0 feature depends on the solver being correct first. The backward compatibility regression test must be written before any code changes, making it the explicit entry gate. `NodeLayout` must be introduced in this phase even with nz=1 everywhere, because z-refinement code written on top of the old index scheme is high-cost to fix after the fact.

**Delivers:**
- Backward compat regression test passing before any builder changes (old project produces identical temperatures to v1.0)
- New `MaterialZone` model (`thermal_sim/models/material_zone.py`) with JSON round-trip and validation
- `DisplayProject.material_zones` field with `__post_init__` validation (layer and material name checks)
- `build_material_map()` helper with per-cell float64 property arrays and AABB zone rasterization
- `network_builder.py` rewritten with cumulative z-offset node indexing and per-cell harmonic-mean conductance
- `ThermalNetwork` extended with `n_z_nodes`, `z_layer_map`
- `Layer.nz` field (model only, nz=1 still the only operative value at end of this phase)
- Validation tests: two-zone lateral boundary test, harmonic-mean interface conductance correctness test
- All `examples/*.json` files load and solve identically

**Addresses (FEATURES.md):** Per-cell material lookup, rectangular material zone definition, harmonic-mean conductance at boundaries, backward compatibility, partial analytical validation suite

**Avoids (PITFALLS.md):** Vectorization destruction (array pattern enforced from the start), node index formula breakage (`NodeLayout` centralized before any downstream code), backward compat drift (regression test written first)

**Research flag:** Standard patterns — direct solver, COO assembly, AABB zone rasterization are all established. No additional research phase needed.

---

### Phase 2: Z-Refinement — Multiple Z-Nodes Per Layer

**Rationale:** Z-refinement extends the node indexing scheme established in Phase 1 to variable `nz` per layer. It is sequenced after Phase 1 because it requires the per-cell material map infrastructure (within-layer z-z links use per-cell k_through values from the material map). GUI z-slice controls, z-fraction probes, and live node count are all sequenced after the solver validates.

**Delivers:**
- Within-layer z-sublevel node generation in the network builder (nz > 1 operative)
- Correct within-layer vs inter-layer z-z conductance formulas with no interface resistance on internal links
- Solver reshape changes (`n_layers` → `n_z_nodes` in `steady_state.py` and `transient.py`)
- Postprocessor probe extraction updated to use `z_offsets[layer_idx] + (nz-1)` for top-face default
- Analytical z-refinement validation: 1D slab temperature profile for nz=5 vs analytical solution (catches interface resistance misapplication)
- GUI: nz spinbox per layer (default 1, max 10, existing `TableDataParser` pattern)
- GUI: z-plane slice selector in temperature map panel (`QComboBox` or `QSlider` connected to `im.set_data` + `draw_idle`)
- GUI: probe z_fraction control (shown only when target layer has nz > 1)
- GUI: live total node count in the status bar

**Addresses (FEATURES.md):** Z-refinement (Layer.nz), probe z_fraction addressing, nz spinbox in Layers GUI, z-plane slicing in visualization, node count estimate in status bar

**Avoids (PITFALLS.md):** Interface resistance on internal z-z links (two distinct code paths), SuperLU stall (node count warning at >300k, nz spinbox max=10 soft guard), result array shape breakage everywhere z_layer_map is consumed

**Research flag:** Standard patterns — cumulative offset node indexing and within-layer z-z conductance fully specified in ARCHITECTURE.md from first principles. No additional research phase needed.

---

### Phase 3: ELED Zone Preset and Zone Editor GUI

**Rationale:** This phase delivers the primary user-facing value of v2.0 — the ability to define ELED cross-section material zones through the GUI without editing JSON, and the auto-generated zone preset for the ELED stack template (from Phase 6). It is sequenced last because it is purely additive on top of the working 3D solver from Phases 1 and 2.

**Delivers:**
- GUI: material zones table per layer (x_min, x_max, y_min, y_max, material columns; second `QTableWidget` below layers table, same `+/-` row add/delete pattern as heat sources)
- GUI: zone assignment 2D color map preview in zone editor (live update on zone change; calls `build_material_map()` with current settings)
- Documented zone overlap rule (last-wins) displayed in tooltip
- Zone coordinates displayed in mm in GUI, stored in metres (matching `feedback_units_mm.md` preference)
- ELED cross-section zone preset extending the Phase 6 ELED stack template (auto-generates `MaterialZone` objects for metal strip, LED board strip, air gap, LGP bulk; widths parameterized from ELED geometry config)

**Addresses (FEATURES.md):** Material zone table per layer in GUI, ELED cross-section zone preset

**Avoids (PITFALLS.md):** Zone overlap ambiguity (explicit last-wins rule with zone preview map confirmation), UX coordinate confusion (mm display consistent with existing UI convention), GUI rebuild-on-every-keystroke (debounce or block-signals pattern in zone table editor)

**Research flag:** Standard patterns for the zone table (QTableWidget, existing pattern). One targeted check needed at start of Phase 3: verify that the Phase 6 ELED template config exposes frame width, LED board width, and air gap width as named fields accessible to the preset generator. If those fields do not exist on `LEDArray` or the ELED stack template, they will need to be added before the preset can be built.

---

### Phase Ordering Rationale

- Phases 1 and 2 are strictly ordered by dependency: per-cell material lookup must exist before within-layer z-refinement links can use per-cell `k_through` values. `NodeLayout` must be established in Phase 1 (with nz=1 everywhere) so Phase 2 only needs to populate the nz > 1 code paths.
- Phase 3 is independent of Phase 2's GUI work but depends on Phase 1's model (`MaterialZone`). It is last because the GUI zone editor is the highest user-facing polish and lowest solver risk — wrong code in Phase 3 cannot corrupt solver output.
- All three phases are additive under the backward-compatibility constraint: a project with no zones and all nz=1 must produce identical results at the end of all three phases as it did before Phase 1 began.
- GUI features within each phase should be sequenced after solver validation tests pass. This prevents the GUI layer from obscuring solver correctness bugs.

### Research Flags

Phases needing additional research during planning:
- **Phase 3 (ELED preset):** Verify that the Phase 6 ELED template config exposes the geometry parameters (frame width, LED board width, air gap width) needed to auto-generate zones. This is a one-file inspection at the start of Phase 3 planning, not a full research pass.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Direct sparse solver extension with AABB zone rasterization and vectorized NumPy conductance assembly — well-documented in ARCHITECTURE.md and STACK.md with concrete code patterns.
- **Phase 2:** Cumulative offset node indexing and within-layer conductance formulas — fully specified in ARCHITECTURE.md from first principles; within-layer vs inter-layer distinction is physics-clear.
- **Phase 3:** `QTableWidget` zone editor — follows the existing heat source table pattern already present in the codebase.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; all patterns verified against SciPy/NumPy/Matplotlib official documentation and first-principles arithmetic; memory estimates are calculable from node count × bytes |
| Features | HIGH | Grounded in direct codebase inspection of `network_builder.py`, `layer.py`, `project.py`; harmonic-mean conductance confirmed by Patankar (1980) and INL FDM comparative study; zone-as-object pattern confirmed in FloTHERM and Icepak documentation |
| Architecture | HIGH | All findings from direct source inspection of the existing codebase; no external library unknowns; build order confirmed by dependency analysis; backward compat formula traced line-by-line in the current builder |
| Pitfalls | HIGH | All pitfalls derived from direct source inspection of the existing code (not speculation); vectorization degradation and NodeLayout fragility confirmed by examining the actual `_add_link_vectorized()` signature and node index formula in `network_builder.py` |

**Overall confidence: HIGH**

### Gaps to Address

- **Heat source distribution on z-refined layers:** The architecture research recommends depositing surface heat sources on the top-most z-node only (not distributed across all nz sub-nodes). This decision is documented but has not been validated against a physical reference case. A validation test in Phase 2 should cover this: LED on a nz=3 layer — verify that the junction temperature is higher than with nz=1 (no artificial spreading), and that the gradient through the layer matches the 1D analytical solution.

- **ELED zone geometry parameterization:** The Phase 3 ELED cross-section preset requires frame width, LED board width, and air gap width from the Phase 6 ELED stack template. If `LEDArray` or the ELED template config does not expose these as named fields, the preset requires adding new fields to the template. Assess this at the start of Phase 3 planning before committing to an implementation approach.

- **CSV export format versioning:** Adding a z-slice index to the CSV export format (needed for nz > 1 results) will break existing CSV readers if the format changes without a version marker. A format version bump should be planned before Phase 2 is declared complete. PITFALLS.md flags this as an integration gotcha.

- **SuperLU iterative fallback threshold:** STATE.md notes CG did not converge well at 1M nodes in previous testing. The current recommendation is to add a user warning at >300k nodes and not add a second solver unless direct measurement shows it is needed. If engineers push nz values that produce meshes beyond this threshold in practice, this gap may require revisiting. The 300k warning threshold should be documented prominently in the Phase 2 GUI work.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase: `thermal_sim/solvers/network_builder.py` — existing node indexing, COO assembly, `_add_link_vectorized()`, through-thickness conductance formula (half-thickness model)
- Direct codebase: `thermal_sim/models/project.py`, `layer.py`, `material.py` — existing dataclass patterns, `from_dict()` / `to_dict()`, `material_for_layer()`
- Direct codebase: `thermal_sim/solvers/steady_state.py`, `transient.py` — reshape calls, `splu()` location, `state_shape` assumption
- Direct codebase: `thermal_sim/core/postprocess.py` — `_probe_indices()`, `_top_n_from_map()` layer index usage
- Direct codebase: `.planning/STATE.md` — measured solver performance (90×60 <1s, 150×100 ~5s); CG convergence failure at 1M nodes
- Direct codebase: `.planning/PROJECT.md` — v2.0 feature scope, backward compat requirement, out-of-scope items (polygon zones, unstructured mesh, temperature-dependent k)
- NumPy structured arrays documentation — cache locality of parallel vs structured arrays; uint8 fancy indexing
- SciPy sparse documentation (v1.17.0) — COO+CSR assembly recommendation; `csr_array` vs `csr_matrix` deprecation status; `spsolve` format preference
- GitHub scipy/scipy issue #14984 — int32 overflow in SuperLU; confirmed fixed in SciPy 1.8.0
- INL: "Comparative Study of Harmonic and Arithmetic Averaging of Diffusion Coefficients for Non-Linear Heat Conduction Problems" — harmonic mean as standard for FDM discontinuous conductivity fields
- Patankar, "Numerical Heat Transfer and Fluid Flow" (1980) — harmonic mean conductance at material interfaces (foundational FDM reference)
- Matplotlib mplot3d gallery (v3.10.8) — `imshow3d` confirmed as gallery copy-paste, not a built-in function; intersection plane rendering limitation documented
- EnergyPlus/THERM documentation — rectangular zone definition sufficient for building envelope structured-grid models

### Secondary (MEDIUM confidence)

- Electronics Cooling (2010): "Creating PCB Thermal Conductivity Maps Using Image Processing" — tile-based per-cell conductivity approach; validation at 3.3% average error vs detailed simulation
- FloTHERM product specification (Siemens/Innofour) — structured Cartesian grid; localized overlapping grid; object-based zone geometry rasterized at solve time
- FloTHERM V11 feature article — overlapping localized grid details
- DataCamp: Matplotlib 3D Volumetric Data tutorial — `set_data` + `draw_idle` slice navigation pattern

### Tertiary (LOW confidence)

- None — all findings are grounded in HIGH or MEDIUM confidence sources.

---

*Research completed: 2026-03-16*
*Ready for roadmap: yes*
