# Pitfalls Research

**Domain:** Adding per-cell material heterogeneity and z-refinement to an existing structured-grid 2.5D RC-network thermal solver (Python / NumPy / SciPy sparse)
**Researched:** 2026-03-16
**Confidence:** HIGH — all findings from direct source inspection of the existing codebase; no external library dependencies introduced by this milestone; performance thresholds derived from measured node-count analysis of the existing solver

---

## Critical Pitfalls

### Pitfall 1: Per-Cell Conductance Lookup Destroys Vectorization in the Hot Path

**What goes wrong:**
The current network builder computes in-plane conductances as a single scalar per layer and then calls `_add_link_vectorized()` with a constant `conductance: float`. When you switch to per-cell materials, the naive replacement is a Python `for` loop over cells, looking up each cell's material and computing its conductance individually. This turns an O(n_per_layer) vectorized NumPy operation into an O(n_per_layer) Python loop — roughly 100x slower per layer. At a 150×100 mesh the current builder runs in milliseconds; a naive per-cell loop at the same mesh takes seconds.

**Why it happens:**
The `_add_link_vectorized()` function takes a scalar conductance and broadcasts it via `np.full(len(n1), conductance)`. The scalar-to-array step is a NumPy no-op. When per-cell material lookup is needed, developers naturally reach for a Python loop because the conductance is now cell-dependent. The loop seems like the obvious fix and it works correctly — it is just an order of magnitude too slow.

**How to avoid:**
Build a per-cell conductance array once before calling `_add_link_vectorized()`. For in-plane links, precompute a 2D array `g_x_map[iy, ix]` using NumPy vectorized indexing into the material property arrays. The link conductances for horizontal pairs `(ix, iy) -- (ix+1, iy)` involve two adjacent cells; use the harmonic mean of the two cell conductances (the correct physical formula for two resistors in series sharing an interface). This harmonic mean can be computed entirely with NumPy array slicing: `g_x = 2 / (1/g_left + 1/g_right)` where both are 2D arrays. Modify `_add_link_vectorized()` to accept either a scalar or a 1-D per-link array.

**Warning signs:**
- Any `for ix in range(grid.nx): for iy in range(grid.ny):` loop inside network builder
- A `conductance: float` type annotation on the vectorized helper that is not updated to `float | np.ndarray`
- Network build time growing linearly with cell count (profile with `time.perf_counter()` around `build_thermal_network()`)
- Profiler showing the network builder's inner loop as the top hotspot at >50% of build time

**Phase to address:** Per-cell material network builder phase (v2.0 Phase 1 — the core architectural change)

---

### Pitfall 2: Node Index Formula Breaks for Variable nz per Layer

**What goes wrong:**
The current canonical node index is `layer_idx * (nx * ny) + iy * nx + ix`. This assumes one z-node per layer. When z-refinement adds `nz[l]` nodes through a layer's thickness, this formula is wrong for every layer after the first that has `nz > 1`. All downstream code that uses this formula — the network builder, postprocessor, probe extraction, result reshaping — silently produces incorrect results if the formula is not updated everywhere simultaneously.

**Why it happens:**
The index formula appears in three places in the current codebase: `network_builder.py` (the `node_index()` local function and directly in `b_sources` / `b_boundary` index arithmetic), `transient.py` (the reshape call `t_vec.reshape(state_shape)` where `state_shape = (n_layers, grid.ny, grid.nx)`), and `postprocess.py` (probe extraction uses `layer_idx * n_per_layer + ...`). Developers often update the builder but forget the reshape or the postprocessor. The bug is silent because wrong probes still return a temperature value — just from the wrong node.

**How to avoid:**
Introduce a `NodeLayout` object (or a function) that is the single source of truth for node indexing. It takes a per-layer `nz` list and computes the cumulative offset for each layer. Every other module imports and uses `NodeLayout.node_index(layer_idx, iz, iy, ix)` — no module computes raw offsets inline. The `n_nodes` property, the reshape shape, and the probe extraction all derive from `NodeLayout`. Make the current `n_per_layer` a property on this object. Write a unit test that verifies `NodeLayout.node_index()` for a heterogeneous nz configuration before any downstream code is wired to it.

**Warning signs:**
- The expression `layer_idx * n_per_layer` appears anywhere outside `NodeLayout` (or the equivalent centralized indexing object)
- `state_shape = (n_layers, grid.ny, grid.nx)` hardcoded in `transient.py` — this must become `(total_z_nodes, grid.ny, grid.nx)` or a per-layer structure
- Probe temperatures that are numerically plausible but wrong (a subtle bug: probe reads from a neighbor node in the wrong layer)
- Unit tests that only test nz=1 per layer — they will pass even with the broken formula

**Phase to address:** Per-cell material network builder phase (v2.0 Phase 1) — establish NodeLayout before any z-refinement work; z-refinement phase (v2.0 Phase 2) — all consumers must be updated before declaring z-refinement complete

---

### Pitfall 3: Backward Compatibility Silently Breaks — Old Projects Solve Differently

**What goes wrong:**
An existing project JSON has no `material_zones` key and no `nz` key. The new `from_dict()` adds these optional fields. If the default for `material_zones` is an empty list, the new network builder interprets an empty zone list as "no zones defined" and falls back to the uniform-material behavior — this is correct. But if the fallback path in the network builder uses a slightly different conductance formula (e.g., different harmonic mean weighting, different interface resistance splitting) than the old code, old projects now produce different temperatures. The JSON loads without error and the solver runs without error — but the numbers are wrong relative to the old solver. Engineers who have calibrated expectations from v1.0 results will not trust the tool.

**Why it happens:**
The 2.5D builder uses a specific through-thickness conductance formula: `r_total = (lower.thickness / (2 * lower_mat.k_through * area)) + (interface_resistance / area) + (upper.thickness / (2 * upper_mat.k_through * area))`. This half-thickness resistance model is a particular discretization choice. When you generalize to per-cell and per-z-node conductances, it is easy to accidentally use a different formula (e.g., full-thickness instead of half-thickness, or forgetting the interface resistance term). This changes results for old projects even when no zones are defined.

**How to avoid:**
Write a regression test before writing any new code. Take an existing example project (e.g., `examples/steady_uniform.json`), run it through the current solver, save the temperature array to a `.npy` reference file. After the new builder is implemented, run the same project through the new builder with `material_zones=[]` and `nz=1` per layer, and assert that temperatures match to within 0.001°C. This test must be part of CI and must pass before the new builder is considered complete. The test will catch any formula drift immediately.

**Warning signs:**
- No regression test that compares new builder output to saved old-solver reference temperatures
- The fallback path in the new builder is new code rather than a verified copy of the old path
- `from_dict()` changes that modify how existing fields (e.g., `interface_resistance_to_next`) are read
- Phase plans that say "implement new builder, then verify backward compat" rather than "write backward compat test first, then implement"

**Phase to address:** v2.0 Phase 1 (first task before any builder changes) — write the regression test; then the test is the acceptance criterion for the entire phase

---

### Pitfall 4: Sparse Matrix Assembly Memory Explosion for Large 3D Meshes

**What goes wrong:**
The current COO accumulator pattern works well for 2.5D meshes. For a 100×80 mesh with 8 layers, `n_nodes = 64,000` and the matrix has at most 6 links per interior node ≈ 384,000 non-zero entries — small. For a 3D mesh with z-refinement: 100×80 mesh, 8 layers each with nz=5 means `n_nodes = 3,200,000`. The COO accumulator before `tocsr()` conversion holds 4 arrays (rows, cols, data for `_add_link_vectorized`) that each grow to ~20M entries. At 8 bytes per float64, this is ~640 MB of intermediate COO data just for the off-diagonal links — before the CSR conversion, which allocates another copy. On a 16 GB Windows laptop with competing processes, this can fail with MemoryError or cause OS-level swapping that makes the system unresponsive.

**Why it happens:**
The `coo_rows`, `coo_cols`, `coo_data` lists accumulate all links before a single `np.concatenate()` + `coo_matrix()` + `tocsr()` at the end. The peak memory is the sum of all intermediate arrays before the COO object is built. This is fine for 2.5D sizes but the 3D case can have 50x more nodes with z-refinement.

**How to avoid:**
For 3D meshes, switch from a list-of-arrays accumulator to building the CSR matrix in blocks: assemble in-plane links for each layer slice into a sub-matrix, assemble through-thickness links separately, then use `scipy.sparse.block_diag` and `scipy.sparse.bmat` to combine. Alternatively, preallocate fixed-size COO arrays using the exact non-zero count formula for a structured grid: `nnz = 2 * n_nodes + 2 * (nx-1)*ny*nz_total + 2 * nx*(ny-1)*nz_total + 2 * n_nodes_minus_top_z_slice` (interior links only). This avoids the `np.concatenate()` peak. For moderate 3D meshes (under 500k nodes), the current pattern is fine. For large meshes, add a `n_nodes` check before assembly and warn the user if memory estimate exceeds a threshold (e.g., 500k nodes → estimated peak 2 GB intermediate arrays).

**Warning signs:**
- No node-count sanity check before network assembly begins
- GUI allows setting nz=10 per layer without any warning about memory
- `np.concatenate(coo_rows)` is the largest memory allocation in a profile run
- Windows task manager shows physical memory >80% during network build for large meshes

**Phase to address:** v2.0 Phase 1 (per-cell builder) — add node count check and memory estimate warning; v2.0 Phase 2 (z-refinement) — assess whether the current assembly pattern is sufficient or needs restructuring based on actual mesh sizes engineers will use

---

### Pitfall 5: splu Factorization at 1M+ Nodes Takes Minutes and Stalls the GUI

**What goes wrong:**
`scipy.sparse.linalg.splu` (SuperLU) is a direct sparse solver. It works well up to ~200k nodes (sub-second on typical hardware). The current STATE.md notes that at 150×100 mesh the solver runs in ~5 seconds. With z-refinement at nz=5 per layer, the same panel becomes a 750k-node system. SuperLU's fill-in for a 3D structured grid is substantially worse than for a 2.5D slab — 3D structured grids have a less favorable sparsity pattern for LU decomposition. Factorization of a 1M-node 3D problem can take 5-15 minutes on a typical engineering laptop, and the transient solver's `splu()` prefactoring call happens synchronously before the time loop starts. If this is called on the main thread (even with the existing `SimulationController` worker), users see a frozen progress bar at 0% for minutes — indistinguishable from a crash.

**Why it happens:**
SuperLU's complexity scales superlinearly with node count for 3D problems. The 2.5D solver never encountered this because the z-direction had only one node per layer. Engineers, excited to try z-refinement, may set nz=10 on all layers to "get good resolution" — this immediately creates a prohibitively large system.

**How to avoid:**
Add a pre-solve node count check that emits a warning (both in the GUI and in the CLI) when `n_nodes > 300,000`: "Mesh contains {n} nodes — solve may take several minutes. Consider reducing nz or nx/ny." Do not refuse to solve, but make the scale explicit. In the GUI, show the node count in the status bar as a live indicator that updates when mesh parameters change. For the transient solver, ensure the `splu()` call is inside the `SimulationController`'s worker thread and reports progress ("Factorizing matrix..." with an indeterminate progress bar) so the GUI remains responsive. Do not add a second solver (iterative CG/GMRES) unless SuperLU is measured as insufficient at the actual mesh sizes engineers use — STATE.md notes CG did not converge well at 1M nodes.

**Warning signs:**
- No node count display or warning in the GUI
- The `splu()` call is outside the `QThread` worker (anywhere the main thread can block)
- No test that measures solver time at 3D mesh sizes before declaring the feature complete
- nz spinbox in the GUI with a maximum of 50 or no maximum

**Phase to address:** v2.0 Phase 1 (network builder) — add node count check and warning; v2.0 Phase 2 (z-refinement GUI) — live node count in status bar, nz spinbox max = 10 as a soft guard

---

### Pitfall 6: Interface Resistance Between z-Sub-Layers Must Not Use Layer-Level Value

**What goes wrong:**
The current `Layer` model has `interface_resistance_to_next: float` which represents the contact resistance between this layer and the layer above it in the stack. With z-refinement (multiple z-nodes through a single layer), there are now *internal* z-z conductances within one layer and *external* interface conductances between layers. If the builder incorrectly applies `interface_resistance_to_next` to both the layer boundary and the internal z-z links, the internal resistance is 5-10x too large (for nz=5, the internal links are `layer.thickness / nz` apart, not `layer.thickness / 2`). This produces temperatures with correct qualitative spatial distribution but systematically wrong magnitudes — the through-thickness gradient is too steep.

**Why it happens:**
The current through-thickness conductance formula: `r_total = lower.thickness / (2 * lower_mat.k_through * area) + interface_resistance / area + upper.thickness / (2 * upper_mat.k_through * area)` explicitly models half-thickness of each layer plus the interface gap. With sub-layers from z-refinement, each internal z-z link has a resistance of `(layer.thickness / nz) / (k_through * area)` with no interface term. The interface term belongs only at the true layer boundary. Mixing these up is easy because both look like "z-direction resistance" in the code.

**How to avoid:**
Make the distinction explicit in the builder. When iterating z-z links within a layer (internal to z-refinement), use only `dz / (k_through * area)` where `dz = layer.thickness / nz`. When iterating z-z links at the layer boundary (between layers), use the existing half-thickness + interface + half-thickness formula. Write an analytical test: a single-layer slab with nz=5, no interface resistance, thermal gradient should match the 1D analytical solution `T(z) = T_base + q * z / k`. This test will fail immediately if internal z-z links include the interface resistance term.

**Warning signs:**
- `interface_resistance_to_next` appears in any code path that generates z-z links for nodes within the same layer
- No nz>1 analytical validation test (through-thickness temperature gradient against 1D slab formula)
- The same conductance function is used for both internal-z and layer-boundary-z links

**Phase to address:** v2.0 Phase 2 (z-refinement network builder) — this is the single most physics-critical correctness pitfall for z-refinement

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copy-paste the old layer loop and add a material-zone branch inside it | Fast to write, old path unchanged | Duplicate logic diverges; future material model changes must be applied twice | Never — extract a shared `_cell_conductance_array()` function |
| Use Python `dict` lookup `material_map[zone_id]` inside the per-cell loop | Simple to read | O(n_cells) Python-level dict lookups; kills vectorization | Acceptable at design time; must be replaced with NumPy integer-indexed array lookup before shipping |
| Skip NodeLayout abstraction, update the index formula inline everywhere | Saves one class | Every consumer must be updated manually for z-refinement; missed consumers cause silent wrong results | Never — the abstraction has direct payoff at z-refinement time |
| Use `nz=1` everywhere internally but add nz>1 "later" | Avoids restructuring now | Deferred restructuring always costs more; by the time z-refinement is added, per-cell material code is established and hard to change | Never — if z-refinement is in scope for v2.0, NodeLayout must accommodate it from the start |
| Represent material zones as a list of `(rect, material_name)` tuples interpreted at build time | Avoids a 2D NumPy array | Requires O(n_cells * n_zones) overlap testing per build; slow for many zones | Acceptable for ≤5 zones; need NumPy `material_id_map[ny, nx]` for >5 zones or frequent rebuilds |
| Store `material_id_map` as a `list[list[str]]` (Python lists of material name strings) | Easy to serialize | 100x slower lookup than a NumPy `int32` array indexed into a material list | Fine in the model (for JSON round-trip); must be converted to `np.int32` array before the network builder uses it |

---

## Integration Gotchas

Common mistakes when connecting the new per-cell and z-refinement features to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `postprocess.py` probe extraction | `layer_idx * n_per_layer + iy * nx + ix` hardcoded — breaks for nz>1 | Use `NodeLayout.probe_node(layer_idx, probe_x, probe_y)` that accounts for variable nz; probe reads from the top z-node of the layer by default |
| `transient.py` result reshape | `t_vec.reshape((n_layers, grid.ny, grid.nx))` — fails for nz>1 | Reshape to `(total_z_nodes, grid.ny, grid.nx)` or use NodeLayout to extract per-layer-top slices for the output array |
| `SteadyStateResult` / `TransientResult` shape | `temperatures_c: np.ndarray  # shape: [n_layers, ny, nx]` — 3D arrays now have extra z axis | Either add a `temperatures_3d_c: np.ndarray  # [nz_total, ny, nx]` field alongside the existing one (backward compat), or change the shape and update all consumers simultaneously |
| GUI temperature map display | Expects `temperatures_c[layer_idx, :, :]` — direct 2D slice | For nz>1, expose a "z-slice selector" and compute the correct node index from NodeLayout; default to top z-node for backward visual compatibility |
| CSV export | `temperature_map_c[layer_idx]` indexing — breaks for nz>1 | Export format must be updated to include z-slice index; old CSV readers will break if format changes without version bump |
| JSON backward compat | Adding required `material_zones` key or `nz` key to Layer without defaults | All new fields must use `.get(key, default)` in `from_dict()`; `material_zones` default = `[]` means "uniform material from `layer.material`"; `nz` default = `1` means "one z-node, 2.5D behavior" |
| `DisplayProject.__post_init__` validation | Adding zone validation that rejects a zone material name not in `project.materials` — correct, but timing matters | Zone validation must run after all materials are loaded; the existing validation order is materials first, then layers — zones must be validated after both |
| `material_for_layer()` method | Code that calls `project.material_for_layer(l_idx)` in the new per-cell builder — this returns a single material, incorrect for per-cell | Replace calls to `material_for_layer()` in the builder with calls to `project.material_map_for_layer(l_idx)` that returns the `np.int32` zone map and the material list |

---

## Performance Traps

Patterns that work at small scale but fail as mesh size grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Python loop over cells for per-cell conductance | Network build time grows 100x vs current; 30×20 mesh takes 10s instead of 0.1s | Pre-build NumPy conductance arrays; harmonic-mean via array slicing | Immediately visible at 30×20 mesh with Python loops |
| `np.add.at()` for per-cell heat source distribution with zones | Slow for many small zones (each `add.at()` call is O(n_touched_cells)) | Pre-compute which cells belong to which zone; use boolean mask array | Noticeable at >20 zones; severe at >100 zones |
| Re-running `build_thermal_network()` for every GUI parameter change | Interactive parameter edits cause 5-30s lag per keystroke for large meshes | Debounce: only rebuild on explicit "Run" click, not on every spinbox change | Immediate for any mesh >50×50 |
| SuperLU factorization at >300k nodes | Factorization takes minutes; progress bar appears frozen | Node count check + user warning before solve; keep nz defaults low (1 or 2) | 3D mesh with 100×80×(8 layers * nz=5) = 3.2M nodes |
| Storing full transient history for 3D results | `[nt, nz_total, ny, nx]` at 1000 timesteps × 500k nodes × 8 bytes = 4 GB | Cap stored samples; stream to disk for large meshes; or reduce output_interval | >10 timesteps stored for a 300k node 3D mesh |
| `coo_matrix` intermediate arrays growing proportional to nnz | Peak memory 3-5x the final CSR matrix size during assembly | Pre-allocate fixed-size COO arrays using exact nnz formula for structured grid | Meshes with >200k nodes hit >2 GB intermediate allocation |

---

## UX Pitfalls

Common user experience mistakes in the material zone editor and z-refinement controls.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Material zone editor with no visual preview | Engineers cannot tell if zones cover the right cells; they run the solver to check | Show a 2D color map of the zone assignment in the zone editor (or in the structure preview); update it live as zone rectangles are defined |
| Zone overlap ambiguity (last-wins vs first-wins vs error) | Engineers define overlapping zones and get unexpected material assignment | Define and document a clear rule (last-defined zone wins, matching ELED cross-section use case); show the effective zone assignment map so the result is visible |
| z-refinement spinbox with no node count feedback | Engineer sets nz=10 on a 100×80 mesh without realizing this creates a 640k-node problem | Show live "Total nodes: {n}" in the status bar or next to the nz control; update on every spinbox change |
| Zone definition requires exact coordinates in SI units (metres) | Engineers think in mm; entering 0.004 instead of 4mm causes errors | Display zone coordinates in mm (matching the existing GUI mm preference from feedback); store internally in metres (existing SI convention) |
| Copying zone definitions from one layer to another is not supported | ELED cross-sections repeat on every row of the LED grid; engineers re-enter zones manually | Provide a "Copy zones from layer" dropdown in the zone editor; reduces ELED setup from 20 minutes to 20 seconds |
| No distinction between "no zones defined" and "one zone covering all cells" | Engineers add one zone that covers everything, then delete material fields, leaving an empty zone list; solver may behave unexpectedly | If `material_zones` is empty, always fall back to `layer.material` for the whole layer; never treat empty zones as an error; document this in tooltips |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces for v2.0.

- [ ] **Per-cell material network builder:** Produces correct COO triplets — verify that the resulting conductance matrix passes the backward-compat regression test (old project, identical temperatures to v1.0 solver output)
- [ ] **Per-cell material network builder:** Handles zone overlap correctly — verify the priority rule (last-wins) with a two-zone overlap unit test
- [ ] **NodeLayout abstraction:** Compute correct node indices — verify with a 3-layer, heterogeneous nz=[1,3,2] test that `NodeLayout.node_index()` produces unique, contiguous indices for all nodes
- [ ] **z-refinement network builder:** Internal z-z links have correct resistance — verify against 1D analytical temperature profile for a single-material slab with nz=5 and known boundary conditions
- [ ] **Backward compatibility:** Old project JSON loads and solves identically — automated test using saved reference temperatures from v1.0 solver
- [ ] **JSON serialization round-trip:** New fields survive save/load — verify that a project with 3 material zones and nz=[2,1,3] serializes to JSON and deserializes to an identical Python object
- [ ] **Probe extraction:** Returns temperature from correct node for nz>1 — verify probe at a specific z-position in a layer with nz=3 reads from the correct z-sub-node, not the default z=0 sub-node
- [ ] **GUI material zone editor:** Zone editor signals do not cascade — verify that setting a zone's material does not trigger a network rebuild on every keystroke (debounce or block-signals pattern)
- [ ] **Performance:** Network builder within acceptable time bounds — benchmark at 100×80 mesh, 8 layers, 5 zones per layer; assert build time <5 seconds
- [ ] **Memory:** Assembly peak memory acceptable — at 100×80, nz=3 per layer, 8 layers (192k nodes), measure peak RSS during `build_thermal_network()`; assert <1 GB

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Per-cell loop destroys performance | MEDIUM | Profile to identify which loop is slow; convert conductance computation to NumPy array arithmetic; `_add_link_vectorized()` signature accepts both scalar and array with one-line change |
| NodeLayout abstraction missing, index formula everywhere | HIGH | Introduce NodeLayout with the corrected formula; use grep to find all `layer_idx * n_per_layer` expressions; update them one-by-one; re-run tests after each file |
| Backward compat broken (different temperatures for old projects) | HIGH | Diff the old and new builder code path to find the formula change; restore the exact old formula in the nz=1 / no-zones path; write the regression test that would have caught this |
| Sparse matrix memory exhaustion at large meshes | MEDIUM | Switch from list-accumulator to block-wise assembly; `scipy.sparse.bmat()` accepts a list of sub-matrices without requiring all COO entries in memory simultaneously |
| SuperLU timeout for large 3D meshes | LOW | Add user warning before solve; do not attempt to add a second solver; document the practical mesh size limit (300k nodes) in the GUI tooltip and in the user guide |
| Interface resistance applied inside layer (wrong z-z formula) | MEDIUM | Write the 1D slab analytical test; find the location in the builder where `interface_resistance_to_next` is being accessed for an internal z-z link; remove it; verify test passes |
| JSON backward compat broken by new required keys | MEDIUM | Add `.get(key, default)` for all new fields in `from_dict()`; deploy updated version; communicate to users that the new version can load old files |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Per-cell conductance lookup destroys vectorization | v2.0 Phase 1 — per-cell network builder | Benchmark network build time at 100×80 mesh with 5 zones; assert <5 seconds |
| Node index formula breaks for variable nz | v2.0 Phase 1 — establish NodeLayout before any builder changes | Unit test: NodeLayout produces unique indices for heterogeneous nz=[1,3,2] configuration |
| Backward compat: old projects solve differently | v2.0 Phase 1 — write regression test FIRST, before any builder changes | Regression test passes: old project produces temperatures within 0.001°C of v1.0 reference |
| Sparse matrix assembly memory explosion | v2.0 Phase 1 — add node count warning; v2.0 Phase 2 — assess restructuring need | Memory profile at 192k-node 3D mesh; peak RSS <1 GB |
| splu factorization too slow for 3D meshes | v2.0 Phase 1 — add pre-solve warning; v2.0 Phase 2 (z-refine GUI) — live node count display | Node count warning appears in GUI before solve for any mesh >300k nodes |
| Interface resistance applied to internal z-z links | v2.0 Phase 2 — z-refinement network builder | 1D slab analytical test passes for nz=5 single material layer |
| JSON backward compat broken by new fields | v2.0 Phase 1 — `from_dict()` uses `.get()` for all new fields | Load all `examples/*.json` files with new code; no exceptions; load/solve produces identical temperatures |
| UX: no node count feedback in GUI | v2.0 Phase 2 — z-refinement controls | Live node count appears in status bar; updates within 100ms of nz spinbox change |
| UX: zone overlap ambiguity | v2.0 Phase 1 — zone editor design | Documented priority rule; zone preview map shows effective material assignment |
| Result array shape change breaks postprocessor | v2.0 Phase 1 — NodeLayout and result shape | All postprocessor functions pass existing tests; probe extraction test with nz>1 passes |

---

## Sources

- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/solvers/network_builder.py` — current COO accumulator pattern, `_add_link_vectorized()`, node index formula, through-thickness conductance formula
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/solvers/transient.py` — `splu()` call location, result reshape, state_shape assumption
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/solvers/steady_state.py` — `spsolve()` call, result reshape
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/models/project.py` — `DisplayProject`, `MeshConfig`, `material_for_layer()`, `from_dict()` patterns
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/models/layer.py` — `interface_resistance_to_next` field, `from_dict()` `.get()` pattern
- Direct source inspection: `G:/blu-thermal-simulation/.planning/codebase/CONCERNS.md` — identified scaling concerns, memory concerns, node index documentation
- Direct source inspection: `G:/blu-thermal-simulation/.planning/STATE.md` — measured performance: 90×60 <1s, 150×100 ~5s; CG convergence failure at 1M nodes
- Direct source inspection: `G:/blu-thermal-simulation/.planning/PROJECT.md` — v2.0 feature scope, backward compat requirement, structured Cartesian grid constraint
- SciPy documentation on SuperLU fill-in behavior for 3D structured grids (HIGH confidence — superlinear scaling of direct solvers on 3D problems is well-established numerical analysis)
- NumPy array operation performance (HIGH confidence — Python loop vs vectorized array operation 100x speedup is a well-known NumPy characteristic)

---

*Pitfalls research for: Adding per-cell material heterogeneity and z-refinement to existing 2.5D RC-network thermal solver*
*Researched: 2026-03-16*
