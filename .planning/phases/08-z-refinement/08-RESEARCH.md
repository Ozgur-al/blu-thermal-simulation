# Phase 8: Z-Refinement - Research

**Researched:** 2026-03-16
**Domain:** RC-network thermal solver — per-layer z-sublayer node expansion and through-plane validation
**Confidence:** HIGH — all findings from direct codebase inspection and established numerical heat transfer theory; no external library dependencies required beyond existing stack

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Boundary condition z-treatment:**
- Per-sublayer side faces: each z-sublayer gets its own side BC with area = sublayer_thickness * cell_edge_length
- Top/bottom surface BCs attach to outermost z-sublayer only (top BC -> topmost sublayer of top layer, bottom BC -> bottommost sublayer of bottom layer)
- Surface BC conduction distance = dz/2 (half sublayer thickness), not t/2 (half total layer thickness)
- Inter-layer z-z links: r_total = dz_lower/(2*k_lower*A) + R_interface/A + dz_upper/(2*k_upper*A), using half-sublayer-thickness from each side

**Heat source z-placement:**
- Add `z_position` field to HeatSource: options "top" (default), "bottom", "distributed"
- Default "top" — heat injects into topmost z-sublayer of the source's layer (matches LED/surface heat generation)
- "distributed" splits power equally across all nz sublayers (power_per_sublayer = power_w / nz)
- LEDArray template gets z_position field; all expanded HeatSource objects inherit it
- Backward compatible: missing z_position in JSON defaults to "top"

**Probe z-behavior:**
- Add `z_position` field to Probe: options "top" (default), "bottom", "center", or integer sublayer index
- Default "top" — matches typical surface thermocouple placement
- Missing z_position in old JSON defaults to "top"
- Per-layer stats (T_max, T_avg, T_min) aggregate across ALL z-sublayers in the layer
- Hotspot ranking considers all z-sublayers — hotspot could be at any depth
- Default temperature map visualization shows top sublayer per layer (Phase 9 adds z-slice slider)

**Result data structure:**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ZREF-01 | Layer model supports `nz` field (default 1) for multiple z-nodes through thickness | Layer.nz field pattern, backward-compat deserialization |
| ZREF-02 | Internal z-z links within a layer use `dz/(k*A)` with no interface resistance | Within-layer conductance formula (two identical half-nodes = full dz) |
| ZREF-03 | Interface resistance applies only at true layer boundaries, not internal z-sublayers | Inter-layer formula vs intra-layer formula distinction |
| ZREF-04 | Steady-state and transient solvers handle 3D node count and reshape results correctly | Solver reshape pattern, result metadata fields |
| ZREF-05 | Analytical validation test: single-layer slab with nz=5 matches 1D through-thickness profile | 1D slab analytical solution derivation, test design |
</phase_requirements>

---

## Summary

Phase 8 extends the Phase 7 network builder to support multiple z-nodes per layer. Phase 7 establishes the `NodeLayout` abstraction and cumulative z-offset scheme; Phase 8 activates it for `nz > 1` by wiring within-layer z-z links, adapting boundary condition z-attachment, and propagating z-position semantics to heat sources and probes.

The physics is straightforward: within a uniform layer each z-sublayer of thickness `dz = t/nz` is connected to its neighbor above and below by conductance `G = k*A/dz` (the two half-resistances of adjacent sublayers cancel to one full-dz resistance with no interface term). At the true boundary between two distinct layers the existing half-dz formulation from each side plus the interface resistance term is preserved. This precise distinction between ZREF-02 and ZREF-03 is the single most important physical correctness requirement.

The result data structure decision (flat `[total_z, ny, nx]` with `nz_per_layer` and `z_offsets` metadata on the result objects) means both solvers change only in their reshape call and in what metadata they carry. All postprocessors that currently slice `temperatures_c[layer_idx]` must switch to `temperatures_c[z_offsets[layer_idx]:z_offsets[layer_idx+1]]` for per-layer aggregation. The backward-compat guarantee holds because when all `nz=1`, `total_z = n_layers` and the shape is byte-identical to Phase 7 output.

**Primary recommendation:** Implement in this order — (1) add `nz` to `Layer`, `z_position` to `HeatSource`/`LEDArray`/`Probe`; (2) extend `network_builder` with within-layer z-z links using z_offsets from Phase 7; (3) update result objects with `nz_per_layer`/`z_offsets` metadata; (4) update postprocessors for z-aggregation; (5) write ZREF-05 analytical test first to drive the implementation.

---

## Standard Stack

### Core (no new dependencies — all existing)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| numpy | existing | z-offset arithmetic, conductance arrays, result reshape | Already in requirements.txt |
| scipy.sparse | existing | spsolve and splu unchanged — node count changes, solver does not | Already in requirements.txt |
| pytest | existing | ZREF-05 analytical validation test | Already in requirements.txt |

No new package installations required.

---

## Architecture Patterns

### Recommended Project Structure (additions only)
```
thermal_sim/
├── models/
│   ├── layer.py          MODIFY: add nz: int = 1 field
│   ├── heat_source.py    MODIFY: add z_position: str = "top" to HeatSource and LEDArray
│   └── probe.py          MODIFY: add z_position field (str or int, default "top")
├── solvers/
│   └── network_builder.py  MODIFY: within-layer z-z links, side BC per sublayer
├── solvers/
│   ├── steady_state.py   MODIFY: reshape + nz_per_layer/z_offsets metadata
│   └── transient.py      MODIFY: reshape + nz_per_layer/z_offsets metadata
├── core/
│   └── postprocess.py    MODIFY: per-layer aggregation uses z_offsets
tests/
└── test_validation_cases.py  ADD: ZREF-05 test function
```

### Pattern 1: Within-Layer Z-Z Link Assembly

**What:** For layer `l` with `nz_l > 1`, connect adjacent sublayers k and k+1 for each (ix, iy) cell. No interface resistance term because these are nodes within the same physical material.

**Physics derivation:** Two adjacent z-sublayers each have half-thickness `dz/2`. The conductance between their centers:
```
R = (dz/2) / (k*A) + (dz/2) / (k*A) = dz / (k*A)
G = k*A / dz      where dz = layer.thickness / layer.nz
```
This is `dz/(k*A)` per the ZREF-02 requirement — no interface resistance term.

**When to use:** Only for sublayer pairs within the same physical layer (k to k+1 where k < nz_l - 1).

**Example:**
```python
# Source: direct derivation from ARCHITECTURE.md and CONTEXT.md decisions
for l_idx, layer in enumerate(project.layers):
    if layer.nz <= 1:
        continue  # skip — no within-layer z links for nz=1
    dz_sub = layer.thickness / layer.nz
    # Per-cell conductance using k_through_map (Phase 7 provides this)
    g_z_arr = k_through_map[l_idx].ravel() * area / dz_sub  # shape (n_per_layer,)
    for k in range(layer.nz - 1):
        z_lower = z_offsets[l_idx] + k
        z_upper = z_offsets[l_idx] + k + 1
        n1 = z_lower * n_per_layer + flat_all_layer
        n2 = z_upper * n_per_layer + flat_all_layer
        _add_link_vectorized(n1, n2, g_z_arr)
```

Note: `k_through_map` comes from Phase 7's `build_material_map()`. For uniform-material layers, `g_z_arr` reduces to a scalar — but the vectorized call handles both cases.

### Pattern 2: Inter-Layer Z-Z Link (Boundary Between Different Layers)

**What:** The link between the topmost sublayer of layer `l` and the bottommost sublayer of layer `l+1`. This is where interface resistance lives.

**Physics derivation (from CONTEXT.md locked decision):**
```
R_total = dz_lower/(2*k_lower*A) + R_interface/A + dz_upper/(2*k_upper*A)
```
where `dz_lower = layers[l].thickness / layers[l].nz` and `dz_upper = layers[l+1].thickness / layers[l+1].nz`.

With `nz=1` on both layers, `dz_lower = layers[l].thickness` and `dz_lower/2 = layers[l].thickness/2`, which exactly reproduces the pre-Phase 8 formula. Backward compat is exact.

**Example:**
```python
# Source: CONTEXT.md locked decision + ARCHITECTURE.md formula
for l_idx in range(n_layers - 1):
    lower = project.layers[l_idx]
    upper = project.layers[l_idx + 1]
    dz_lower = lower.thickness / lower.nz
    dz_upper = upper.thickness / upper.nz

    # z_offsets[l_idx + 1] - 1 is the topmost sublayer of lower layer
    z_top_lower = z_offsets[l_idx + 1] - 1
    # z_offsets[l_idx + 1] is the bottommost sublayer of upper layer
    z_bot_upper = z_offsets[l_idx + 1]

    r_lower_half = dz_lower / (2.0 * k_through_map[l_idx].ravel() * area)
    r_iface = lower.interface_resistance_to_next / area
    r_upper_half = dz_upper / (2.0 * k_through_map[l_idx + 1].ravel() * area)
    g_z_arr = 1.0 / (r_lower_half + r_iface + r_upper_half)

    n1 = z_top_lower * n_per_layer + flat_all_layer
    n2 = z_bot_upper * n_per_layer + flat_all_layer
    _add_link_vectorized(n1, n2, g_z_arr)
```

### Pattern 3: Heat Source Z-Position Dispatch

**What:** When applying heat sources to `b_sources`, dispatch based on `source.z_position` ("top", "bottom", "distributed") to determine which z-node(s) receive power.

**Example:**
```python
# Source: CONTEXT.md locked decisions
def _z_nodes_for_source(source, layer_idx, z_offsets, layers):
    nz = layers[layer_idx].nz
    z_base = z_offsets[layer_idx]
    z_pos = getattr(source, 'z_position', 'top')
    if z_pos == 'top':
        return [z_base + nz - 1]           # topmost sublayer
    elif z_pos == 'bottom':
        return [z_base]                    # bottommost sublayer
    elif z_pos == 'distributed':
        return list(range(z_base, z_base + nz))  # all sublayers
    elif isinstance(z_pos, int):
        return [z_base + z_pos]            # explicit sublayer index
    return [z_base + nz - 1]              # default to top
```

For "distributed", `power_per_sublayer = source.power_w / nz`. For all others, full `source.power_w` goes to the single z-node.

### Pattern 4: Result Metadata on SteadyStateResult and TransientResult

**What:** Both result dataclasses gain `nz_per_layer: list[int]` and `z_offsets: list[int]` so downstream consumers can reconstruct per-layer views without needing the original `DisplayProject`.

**Example (SteadyStateResult extension):**
```python
# Source: CONTEXT.md locked decisions + existing steady_state.py pattern
@dataclass
class SteadyStateResult:
    temperatures_c: np.ndarray  # shape: [total_z, ny, nx]
    layer_names: list[str]
    dx: float
    dy: float
    nz_per_layer: list[int]     # NEW: [nz for each physical layer]
    z_offsets: list[int]        # NEW: cumulative z-offsets, length n_layers+1

    def layer_temperatures(self, layer_name: str) -> np.ndarray:
        """Return temperatures for all z-sublayers of a named layer: [nz, ny, nx]."""
        l_idx = self.layer_names.index(layer_name)
        z0 = self.z_offsets[l_idx]
        z1 = self.z_offsets[l_idx + 1]
        return self.temperatures_c[z0:z1]
```

The solver reshape call becomes:
```python
# In SteadyStateSolver.solve():
n_total_z = network.n_z_nodes
temperatures = solution.reshape((n_total_z, network.grid.ny, network.grid.nx))
return SteadyStateResult(
    temperatures_c=temperatures,
    layer_names=network.layer_names,
    dx=network.grid.dx,
    dy=network.grid.dy,
    nz_per_layer=[layer.nz for layer in project.layers],
    z_offsets=list(network.z_offsets),
)
```

### Pattern 5: Postprocessor Per-Layer Aggregation

**What:** Existing postprocess functions that index `temperatures_c[layer_idx]` must use `z_offsets` to aggregate across sublayers.

**Example (layer_stats update):**
```python
# Source: existing postprocess.py + CONTEXT.md (per-layer stats aggregate ALL z-sublayers)
def layer_stats(temperatures_c, layer_names, z_offsets):
    result = []
    for idx, name in enumerate(layer_names):
        z0 = z_offsets[idx]
        z1 = z_offsets[idx + 1]
        layer_slice = temperatures_c[z0:z1]  # [nz, ny, nx]
        t_max = float(layer_slice.max())
        t_avg = float(layer_slice.mean())
        t_min = float(layer_slice.min())
        result.append({"layer": name, "t_max_c": t_max, "t_avg_c": t_avg,
                       "t_min_c": t_min, "delta_t_c": t_max - t_min})
    return result
```

**Example (probe temperature extraction update):**
```python
# Source: existing postprocess.py _probe_indices + CONTEXT.md probe z_position
def _z_node_for_probe(probe, project, z_offsets):
    l_idx = project.layer_index(probe.layer)
    nz = project.layers[l_idx].nz
    z_base = z_offsets[l_idx]
    z_pos = getattr(probe, 'z_position', 'top')
    if z_pos == 'top':
        return z_base + nz - 1
    elif z_pos == 'bottom':
        return z_base
    elif z_pos == 'center':
        return z_base + nz // 2
    elif isinstance(z_pos, int):
        return z_base + z_pos
    return z_base + nz - 1
```

### Pattern 6: Side BC Per-Sublayer

**What:** Side boundary conditions now iterate over ALL z-sublayers (not just one per layer). Each sublayer face area = `dz_sub * cell_edge_length`.

**Key difference from Phase 7 (nz=1 case):** Previously side BC for layer `l` uses area = `layer.thickness * cell_edge_length`. With nz > 1, the loop runs `nz` times, each with area = `dz_sub * cell_edge_length`. The total area is identical (nz * dz_sub * cell_edge = thickness * cell_edge), so backward compatibility is preserved in aggregate, and each sublayer gets its own balanced contribution.

**Example:**
```python
# Source: existing network_builder.py side BC loop + CONTEXT.md decision
for l_idx, layer in enumerate(project.layers):
    material = project.material_for_layer(l_idx)
    dz_sub = layer.thickness / layer.nz
    for k in range(layer.nz):
        z_global = z_offsets[l_idx] + k
        base = z_global * n_per_layer
        g_x_edge = _surface_sink_conductance(
            boundary=project.boundaries.side,
            emissivity=material.emissivity,
            conduction_distance=grid.dx / 2.0,
            conductivity=material.k_in_plane,
            area=dz_sub * grid.dy,   # sublayer area, not full layer area
        )
        # ... apply to left/right edge nodes at base + ...
```

### Anti-Patterns to Avoid

- **Using `layer_idx * n_per_layer` as node base:** After Phase 7, the correct base is `z_offsets[layer_idx] * n_per_layer`. Any remnant of the old scheme will produce silently wrong results for nz > 1. Search the entire builder for `l_idx * n_per_layer` after the refactor.
- **Confusing intra-layer and inter-layer z-links:** ZREF-02 (no interface resistance within a layer) and ZREF-03 (interface resistance at layer boundary) are distinct formulas. The intra-layer loop uses `G = k*A/dz`; the inter-layer loop uses the half-dz + R_interface formula.
- **Applying interface resistance for the first pair of sublayers:** When nz_l=3, there are 2 intra-layer links (k=0->1, k=1->2) and they all use `G = k*A/dz`. Only the link from the topmost k=nz_l-1 sublayer of layer l to the bottommost k=0 sublayer of layer l+1 uses the interface resistance formula.
- **Aggregating probe temperatures before z-position is resolved:** Probes have a `z_position` that selects a specific sublayer. Do not average across z-sublayers for a probe — that is only for per-layer stats.
- **Result reshape with old `n_layers`:** After Phase 8, the reshape uses `n_total_z` (sum of all nz), not `n_layers`. Using `n_layers` when any layer has `nz > 1` will produce a shape error immediately.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| z-offset arithmetic | Custom lookup table | Cumulative sum from Phase 7 z_offsets | Phase 7 already defines this; duplicate code drifts out of sync |
| Per-cell conductance arrays | Loop per (ix,iy) | Vectorized numpy on k_through_map[l].ravel() | Phase 7 established this pattern; per-cell Python loops are 100-1000x slower |
| COO matrix assembly | Custom dict-based accumulator | Existing `_add_link_vectorized()` + `coo_matrix()` | Already handles per-pair conductance arrays when conductance is 1D ndarray |
| 1D slab analytical solution | Numerical integration | Closed-form tridiagonal solution | 5-node system is analytically solvable in 10 lines; no numerical approximation needed |
| Backward compat regression test | New project JSON | Existing example JSONs + analytical test cases in test_validation_cases.py | Phase 7 already mandates these; Phase 8 inherits the same gate |

**Key insight:** Phase 7 does the heavy architectural lifting. Phase 8 is surgical additions to a working 3D builder: wire the within-layer z-links, update BC z-attachment, add z_position fields, update result shapes and metadata. Do not re-architect; extend.

---

## Common Pitfalls

### Pitfall 1: Interface Resistance Leaking Into Intra-Layer Links

**What goes wrong:** The `inter-layer` z-z link formula (with interface resistance) is accidentally also used for `intra-layer` sublayer-to-sublayer links. This inflates thermal resistance within a layer by `R_interface` per sublayer pair, producing temperatures that are too high and fail the ZREF-05 analytical test.

**Why it happens:** Both intra and inter link loops iterate over layer pairs; it is easy to copy-paste the inter-layer formula incorrectly.

**How to avoid:** Keep the two loops completely separate. Intra-layer loop: `G = k_through * area / dz_sub`. Inter-layer loop: `G = 1 / (dz_lower/(2*k_lower*A) + R_iface/A + dz_upper/(2*k_upper*A))`. The ZREF-05 validation test will catch this immediately if the layer has `interface_resistance_to_next = 0` (which it should for the single-layer test).

**Warning signs:** ZREF-05 test fails with temperatures higher than analytical. Temperature gradient across a uniform slab is not linear (it should be exactly linear for uniform heat generation).

### Pitfall 2: Side BC Area Using Full Layer Thickness Instead of dz_sub

**What goes wrong:** Side BCs for z-refined layers use `layer.thickness * grid.dy` as area for each sublayer, instead of `dz_sub * grid.dy`. This overcounts the side BC conductance by a factor of `nz`.

**Why it happens:** The existing single-layer side BC loop uses `layer.thickness` directly. When the loop is expanded to iterate over sublayers, forgetting to replace `layer.thickness` with `dz_sub` is easy.

**How to avoid:** Compute `dz_sub = layer.thickness / layer.nz` at the top of the per-sublayer loop. The ZREF-04 backward compat test (nz=1 produces identical temperatures) will catch this because with nz=1, dz_sub = layer.thickness and the result is the same.

**Warning signs:** Side temperatures diverge from expected values when nz > 1. The symptom is overcooled peripheral cells.

### Pitfall 3: Top/Bottom BC Attaching to Wrong Z-Node

**What goes wrong:** Top BC attaches to z-node `z_offsets[-2]` (the topmost node of the second-to-last z-group) instead of `z_offsets[-1] - 1` (the topmost node of the last layer's last sublayer). This is an off-by-one that only manifests when the top layer has `nz > 1`.

**Why it happens:** The current code uses `top_indices = (n_layers - 1) * n_per_layer + flat_all_layer`. After Phase 8, this must be `(n_total_z - 1) * n_per_layer + flat_all_layer`.

**How to avoid:** Express all top/bottom BC node indices in terms of `n_total_z`:
- Top BC node base: `(n_total_z - 1) * n_per_layer`
- Bottom BC node base: `0 * n_per_layer` (unchanged)

**Warning signs:** Top layer temperature profile is wrong when top layer has nz > 1. Backward compat test (nz=1) passes because then `n_total_z - 1 = n_layers - 1`.

### Pitfall 4: Probe Index Using Old Layer-Based Indexing

**What goes wrong:** `probe_temperatures()` computes `result.temperatures_c[layer_idx, iy, ix]` where `layer_idx` is the physical layer number. After Phase 8, the first dimension is z-node index, not layer index. For nz=1 this coincidentally works; for nz > 1 it silently reads the wrong z-node.

**Why it happens:** The result shape looks the same to Python (it's always 3D). The bug is invisible until `nz > 1`.

**How to avoid:** Always resolve probes through `z_offsets` and `probe.z_position`. Use the `_z_node_for_probe()` helper pattern described above. Write a regression test with nz=2 and probe z_position="bottom" to verify the correct sublayer is read.

**Warning signs:** Probe temperatures do not change when nz increases (reading z-node 0 instead of z-node nz-1).

### Pitfall 5: Transient LHS Not Rebuilt After Node Count Increases

**What goes wrong:** The transient solver precomputes `lhs = A + C/dt` and factors it via `splu`. If `n_total_z` is computed incorrectly (e.g., still using `n_layers`), the LHS has the wrong shape and `lu.solve(rhs)` raises a dimension mismatch.

**Why it happens:** `state_shape` in `transient.py` line 80 uses `network.n_layers`; if this is not updated to `network.n_z_nodes`, the pre-allocation will have the wrong first dimension.

**How to avoid:** Replace all occurrences of `network.n_layers` in `transient.py` with `network.n_z_nodes`. The ZREF-04 test (mixed nz project) will catch this with a shape error on the first time step.

**Warning signs:** `lu.solve(rhs)` raises `ValueError: dimension mismatch` when any layer has `nz > 1`.

---

## Code Examples

### ZREF-01: Layer.nz Field Addition
```python
# Source: existing layer.py + CONTEXT.md backward-compat pattern
@dataclass
class Layer:
    name: str
    material: str
    thickness: float
    interface_resistance_to_next: float = 0.0
    nz: int = 1  # NEW: number of z-sublayers (default 1 = no z-refinement)

    def __post_init__(self) -> None:
        # ... existing validation ...
        if self.nz < 1:
            raise ValueError(f"Layer '{self.name}' nz must be >= 1.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "material": self.material,
            "thickness": self.thickness,
            "interface_resistance_to_next": self.interface_resistance_to_next,
            "nz": self.nz,  # NEW
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Layer":
        return cls(
            name=data["name"],
            material=data["material"],
            thickness=float(data["thickness"]),
            interface_resistance_to_next=float(data.get("interface_resistance_to_next", 0.0)),
            nz=int(data.get("nz", 1)),  # NEW: defaults to 1 for existing JSONs
        )
```

### ZREF-02 / ZREF-03: Intra-Layer vs Inter-Layer Z Links
```python
# Source: CONTEXT.md locked decisions + ARCHITECTURE.md formula derivation

# INTRA-LAYER (ZREF-02): within layer l, sublayers k and k+1
# G = k_through * A / dz_sub  [no interface resistance]
for l_idx, layer in enumerate(project.layers):
    if layer.nz <= 1:
        continue
    dz_sub = layer.thickness / layer.nz
    g_z_arr = k_through_map[l_idx].ravel() * area / dz_sub  # [n_per_layer]
    for k in range(layer.nz - 1):
        z_lower = z_offsets[l_idx] + k
        z_upper = z_offsets[l_idx] + k + 1
        n1 = z_lower * n_per_layer + flat_all_layer
        n2 = z_upper * n_per_layer + flat_all_layer
        _add_link_vectorized(n1, n2, g_z_arr)

# INTER-LAYER (ZREF-03): boundary between layer l and layer l+1
# G = 1 / (dz_lower/(2*k_lower*A) + R_iface/A + dz_upper/(2*k_upper*A))
for l_idx in range(n_layers - 1):
    lower = project.layers[l_idx]
    upper = project.layers[l_idx + 1]
    dz_lower = lower.thickness / lower.nz
    dz_upper = upper.thickness / upper.nz
    r_lower_half = dz_lower / (2.0 * k_through_map[l_idx].ravel() * area)
    r_iface = lower.interface_resistance_to_next / area
    r_upper_half = dz_upper / (2.0 * k_through_map[l_idx + 1].ravel() * area)
    g_arr = 1.0 / (r_lower_half + r_iface + r_upper_half)
    z_top_lower = z_offsets[l_idx + 1] - 1
    z_bot_upper = z_offsets[l_idx + 1]
    n1 = z_top_lower * n_per_layer + flat_all_layer
    n2 = z_bot_upper * n_per_layer + flat_all_layer
    _add_link_vectorized(n1, n2, g_arr)
```

### ZREF-04: Solver Reshape Update
```python
# Source: existing steady_state.py reshape pattern
# Before Phase 8:
#   temperatures = solution.reshape((network.n_layers, network.grid.ny, network.grid.nx))
# After Phase 8:
n_total_z = network.n_z_nodes  # sum of all layer.nz values
temperatures = solution.reshape((n_total_z, network.grid.ny, network.grid.nx))
return SteadyStateResult(
    temperatures_c=temperatures,
    layer_names=network.layer_names,
    dx=network.grid.dx,
    dy=network.grid.dy,
    nz_per_layer=[layer.nz for layer in project.layers],
    z_offsets=list(network.z_offsets),
)
```

### ZREF-05: Analytical Validation Test (1D Slab, nz=5)

**Physics setup for the test:**
- Single layer, 1×1 mesh (nx=1, ny=1), nz=5
- Uniform material: k_through = k (W/mK), thickness = t
- Heat source: "distributed" z_position, total power Q_w → `power_per_sublayer = Q_w / 5`
- Boundary: top convection h_top, bottom convection h_bot, no side convection, no radiation
- This creates a 5+2 node system: 5 z-sublayers with BCs on both ends

**Analytical solution for the discrete 5-node system:**

With `nz=5`, sublayer thickness `dz = t/5`. Let nodes be indexed 0 (bottom) to 4 (top).

Conductances:
- `G_intra = k * A / dz`   (within-layer, between any two adjacent nodes)
- `G_bot = 1 / (dz/2/(k*A) + 1/(h_bot*A))`   (bottom surface BC conductance)
- `G_top = 1 / (dz/2/(k*A) + 1/(h_top*A))`   (top surface BC conductance)
- Power at each node: `q_node = Q_w / 5 / A`  (W/m^2 — actually W per node since 1×1)
  In actual implementation: `q_per_node = Q_w / 5` (W per sublayer, 1 cell, so it is Q_w/5 W per node)

Nodal equations (Laplacian matrix):
- Node 0: `(G_bot + G_intra)*T0 - G_intra*T1 = q_per_node + G_bot*T_amb`
- Node i (1..3): `-G_intra*T_{i-1} + 2*G_intra*T_i - G_intra*T_{i+1} = q_per_node`
- Node 4: `-G_intra*T3 + (G_intra + G_top)*T4 = q_per_node + G_top*T_amb`

This is a 5×5 tridiagonal system solved with `np.linalg.solve()`. The solver result `result.temperatures_c[:, 0, 0]` (or after reshape, `result.temperatures_c[z0:z1, 0, 0]` for the one layer) must match the analytical solution to `rel_tol=1e-9`.

**Test tolerance:** `rel_tol=1e-9` — same as the existing analytical tests. The 5-node system solves both analytically and numerically using the same sparse solver; they should match to machine precision.

```python
# Source: derived from CONTEXT.md requirements + existing test_validation_cases.py pattern
def test_zref05_single_layer_nz5_matches_1d_analytical() -> None:
    """ZREF-05: Single layer with nz=5, distributed heat, matches 1D analytical profile.

    Verifies:
    - Within-layer z-z links use G = k*A/dz (no interface resistance, ZREF-02)
    - Top/bottom BCs attach to outermost sublayers with conduction distance dz/2 (ZREF-03)
    - Result shape is [5, 1, 1] with nz_per_layer=[5], z_offsets=[0, 5] (ZREF-04)
    - Temperature profile matches 5-node tridiagonal hand calculation (ZREF-05)
    """
    import math
    import numpy as np
    from thermal_sim.models.material import Material
    from thermal_sim.models.layer import Layer
    from thermal_sim.models.project import DisplayProject, MeshConfig
    from thermal_sim.models.heat_source import HeatSource
    from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
    from thermal_sim.solvers.steady_state import SteadyStateSolver

    width = 0.10
    height = 0.10
    area = width * height
    thickness = 0.005   # 5 mm layer
    k = 2.0             # W/(m·K)
    Q_w = 3.0           # W total power
    h_top = 10.0        # W/(m²·K)
    h_bot = 5.0         # W/(m²·K)
    T_amb = 25.0        # °C
    nz = 5

    mat = Material("Slab", k, k, 1000.0, 900.0, 0.9)
    project = DisplayProject(
        name="ZREF-05 1D slab",
        width=width,
        height=height,
        materials={"Slab": mat},
        layers=[Layer(name="L", material="Slab", thickness=thickness, nz=nz)],
        heat_sources=[HeatSource(
            name="Q", layer="L", power_w=Q_w, shape="full", z_position="distributed"
        )],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=T_amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=T_amb, convection_h=h_bot, include_radiation=False),
            side=SurfaceBoundary(ambient_c=T_amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )
    result = SteadyStateSolver().solve(project)

    # Verify result shape and metadata
    assert result.temperatures_c.shape == (nz, 1, 1)
    assert result.nz_per_layer == [nz]
    assert result.z_offsets == [0, nz]

    # Build 5-node analytical solution
    dz = thickness / nz
    G_intra = k * area / dz
    G_bot = 1.0 / (dz / (2.0 * k * area) + 1.0 / (h_bot * area))
    G_top = 1.0 / (dz / (2.0 * k * area) + 1.0 / (h_top * area))
    q_node = Q_w / nz  # W per sublayer node (1 cell)

    A_mat = np.zeros((nz, nz))
    rhs = np.full(nz, q_node)
    # Interior nodes
    for i in range(1, nz - 1):
        A_mat[i, i-1] = -G_intra
        A_mat[i, i] = 2.0 * G_intra
        A_mat[i, i+1] = -G_intra
    # Bottom node (index 0)
    A_mat[0, 0] = G_bot + G_intra
    A_mat[0, 1] = -G_intra
    rhs[0] += G_bot * T_amb
    # Top node (index nz-1)
    A_mat[nz-1, nz-2] = -G_intra
    A_mat[nz-1, nz-1] = G_intra + G_top
    rhs[nz-1] += G_top * T_amb

    T_expected = np.linalg.solve(A_mat, rhs)

    # Compare: result.temperatures_c[z_idx, 0, 0] vs T_expected[z_idx]
    for z_idx in range(nz):
        T_num = float(result.temperatures_c[z_idx, 0, 0])
        T_anal = T_expected[z_idx]
        assert math.isclose(T_num, T_anal, rel_tol=1e-9, abs_tol=1e-9), (
            f"z-node {z_idx}: numerical {T_num:.6f} C, expected {T_anal:.6f} C"
        )
```

**Additional test for ZREF-03 (interface resistance at layer boundary):**
- Two-layer project, each with nz=3. Bottom layer has interface_resistance_to_next > 0.
- Verify that the link between the topmost sublayer of layer 0 and bottommost sublayer of layer 1 includes the interface resistance (temperatures across the interface jump by Q * R_interface / area).
- This can be checked by solving a 6-node (3+3) system analytically.

**Backward compat test for ZREF-04:**
- Load an existing project (e.g., `examples/steady_uniform_stack.json`)
- Solve with Phase 8 builder (all layers implicitly have nz=1)
- Assert temperatures match the Phase 7 reference to 1e-12 relative tolerance
- Assert `result.nz_per_layer` is all 1s and `result.z_offsets` matches `[0, 1, 2, ..., n_layers]`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single z-node per layer (2.5D) | Multiple z-nodes per layer (3D) | Phase 8 | Resolves through-plane temperature gradient within thick layers |
| `temperatures_c[layer_idx]` direct indexing | `temperatures_c[z_offsets[l]:z_offsets[l+1]]` z-slice | Phase 8 | All downstream consumers must use z_offsets for per-layer views |
| `node = layer_idx * n_per_layer + ...` | `node = (z_offsets[l] + k) * n_per_layer + ...` | Phase 7 (foundation) + Phase 8 (activated) | Off-by-one is catastrophic; z_offsets precomputed once at build time |
| Heat source deposits to one node per layer | Heat source dispatches to z-node(s) via z_position | Phase 8 | "top" (default) preserves LED junction accuracy; "distributed" handles volumetric sources |

**Deprecated/outdated after Phase 8:**
- `network.n_layers` used in reshape calls: replace with `network.n_z_nodes` in steady_state.py and transient.py
- `probe_temperatures()` using `project.layer_index()` directly as z-index: now routes through `z_offsets`
- `layer_stats()` indexing `temperatures_c[idx]`: now slices `temperatures_c[z0:z1]`
- `_top_n_from_map()` divmod by `nx*ny` then using result as layer_idx: must use `z_layer_map` (Phase 7 field on ThermalNetwork) to map z-node to physical layer name

---

## Open Questions

1. **Does Phase 7 deliver NodeLayout / z_offsets / n_z_nodes on ThermalNetwork, or does Phase 8 add them?**
   - What we know: Phase 7 CONTEXT.md ("NodeLayout abstraction centralizes node indexing for variable z-nodes per layer") and ARCHITECTURE.md explicitly define `z_offsets`, `n_z_nodes`, and `z_layer_map` as Phase 7 ThermalNetwork fields.
   - What's unclear: Whether Phase 7 implementation is complete before Phase 8 planning begins, given Phase 7 is still "Pending" in STATE.md.
   - Recommendation: Phase 8 PLAN should declare "depends on Phase 7 delivering ThermalNetwork with n_z_nodes, z_offsets, z_layer_map." If Phase 7 delivers these, Phase 8 only needs to wire the within-layer z-links. If Phase 7 does not deliver them, Phase 8 task 1 must add them.

2. **Where does z_position validation live for HeatSource?**
   - What we know: `HeatSource.__post_init__` validates shape, power_w, etc. z_position = "top" | "bottom" | "distributed" are the three string values.
   - What's unclear: Whether an invalid string like "middle" should raise immediately in `__post_init__` or at solve time in `_apply_heat_sources`.
   - Recommendation: Validate in `__post_init__` to match the existing eager validation pattern. Accepted values: `{"top", "bottom", "distributed"}`. Integer values are valid only for Probe, not HeatSource.

3. **What does `_top_n_from_map` return for layer names in z-refined results?**
   - What we know: CONTEXT.md says "hotspot ranking considers all z-sublayers — hotspot could be at any depth." The current `_top_n_from_map` does `divmod(idx, nx*ny)` and uses result as layer_idx, then returns `layer_names[layer]`. With z-refinement, the first divmod result is a z-node index, not a layer index.
   - What's unclear: Should the hotspot report say "layer L, sublayer k=3" or just "layer L"?
   - Recommendation: Use `z_layer_map[z_node]` to get the physical layer index, and report `layer_names[z_layer_map[z_node]]`. For Phase 8, sublayer detail in hotspot reports can be omitted (Phase 9 GUI will add it). The planner should specify this as a conscious simplification.

---

## Sources

### Primary (HIGH confidence)
- Direct inspection: `thermal_sim/solvers/network_builder.py` — existing `_add_link_vectorized()`, side BC loop, inter-layer z-link formula
- Direct inspection: `thermal_sim/solvers/steady_state.py` — result reshape convention (`n_layers * ny * nx`)
- Direct inspection: `thermal_sim/solvers/transient.py` — `state_shape`, implicit Euler LHS prefactoring
- Direct inspection: `thermal_sim/core/postprocess.py` — `_probe_indices()`, `layer_stats()`, `_top_n_from_map()`
- Direct inspection: `thermal_sim/models/layer.py` — existing `to_dict()`/`from_dict()` pattern
- Direct inspection: `thermal_sim/models/heat_source.py` — `HeatSource.__post_init__` validation pattern, `expand()` in LEDArray
- Direct inspection: `thermal_sim/models/probe.py` — minimal Probe dataclass with layer/x/y
- Direct inspection: `.planning/phases/08-z-refinement/08-CONTEXT.md` — all locked user decisions
- Direct inspection: `.planning/phases/07-3d-solver-core/07-CONTEXT.md` — Phase 7 NodeLayout, z_offsets, ThermalNetwork schema
- Direct inspection: `.planning/research/ARCHITECTURE.md` — full z-refinement architecture research (2026-03-16)
- Direct inspection: `tests/test_validation_cases.py` — analytical test patterns (tridiagonal, isclose tolerance)

### Secondary (MEDIUM confidence)
- Standard finite-difference thermal resistance formula: `G = k*A/L` for each half-node, resulting in `G = k*A/dz` for adjacent nodes of equal thickness — textbook numerical heat transfer (Patankar 1980, established practice)
- Harmonic mean conductivity for dissimilar material interfaces: `k_eff = 2*k1*k2/(k1+k2)` — same reference, confirmed in ARCHITECTURE.md

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all existing scipy/numpy/pytest
- Architecture: HIGH — direct codebase inspection, Phase 7 context already designed the scheme
- Physics formulas (ZREF-02/03): HIGH — standard finite-difference, textbook derivation confirmed
- Analytical test design (ZREF-05): HIGH — 5-node tridiagonal is analytically closed-form
- Pitfalls: HIGH — derived from code inspection of specific existing patterns that will break

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable domain — pure numerical, no external library churn)
