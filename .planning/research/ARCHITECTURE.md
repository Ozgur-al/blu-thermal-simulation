# Architecture Research

**Domain:** 3D RC-network thermal solver — per-cell material assignment and z-refinement extension
**Researched:** 2026-03-16
**Confidence:** HIGH — all findings from direct codebase inspection of the existing Phase 3 implementation; no external library dependencies required

---

## Context: What Changes and What Stays

This milestone extends the existing 2.5D solver (one z-node per layer, uniform material per layer) to a 3D solver (multiple z-nodes per layer, per-cell material zones). The physics math is identical — G = kA/L for every link — but the node indexing scheme, the material lookup, and the `DisplayProject` model must change.

The following components remain completely unchanged:
- Sparse matrix assembly mechanism (COO → CSR in one shot)
- Solver core (`spsolve`, `splu + time-stepping`)
- `SteadyStateResult` and `TransientResult` shape convention `[n_layers_or_znodes, ny, nx]`
- Postprocessing functions (operate on result arrays)
- JSON I/O pattern (`to_dict` / `from_dict` with `.get(key, default)`)
- GUI layer (reads from `DisplayProject`, displays result arrays)

The following components require targeted changes:
- `Layer` model: add `nz: int = 1` field
- `DisplayProject` model: add `material_zones: list[MaterialZone]` field
- `MeshConfig`: add no new fields (nz lives on `Layer`)
- `network_builder.py`: rewrite node indexing, lateral conduction, through-thickness conduction
- `ThermalNetwork`: update `n_nodes`, `n_layers`, `layer_names` computation
- `SteadyStateSolver` / `TransientSolver`: reshape logic for result arrays
- New file: `thermal_sim/models/material_zone.py`
- New helper: `thermal_sim/solvers/material_map.py`

---

## Standard Architecture

### System Overview

```
DisplayProject (model layer)
  ├── layers: list[Layer]          each Layer now has nz: int >= 1
  ├── materials: dict[str, Material]
  ├── material_zones: list[MaterialZone]   NEW — rectangular regions with material override
  └── (heat_sources, boundaries, probes — unchanged)
        │
        ▼
material_map.py (new helper)
  build_material_map(project, nx, ny)
    → material_key_map: ndarray[n_layers, ny, nx]  (string indices into materials dict)
    → k_in_plane_map: ndarray[n_layers, ny, nx]
    → k_through_map: ndarray[n_layers, ny, nx]
    → density_map: ndarray[n_layers, ny, nx]
    → specific_heat_map: ndarray[n_layers, ny, nx]
        │
        ▼
network_builder.py (modified)
  build_thermal_network(project) -> ThermalNetwork
    Node indexing: z_node_idx * (nx*ny) + iy * nx + ix
    where z_node_idx enumerates ALL z-nodes across ALL layers in order
        │
        ▼
ThermalNetwork (modified)
  a_matrix: csr_matrix   (n_total_znodes * ny * nx) square
  b_boundary, b_sources, c_vector: 1D arrays of same length
  n_z_nodes: int          total z-nodes (sum of layer nz values)
  z_layer_map: list[int]  z_node_idx -> layer_idx  (for result interpretation)
  layer_names_by_znode: list[str]  z_node_idx -> layer name
        │
        ▼
Solvers (minor reshape change only)
  SteadyStateResult.temperatures_c: [n_z_nodes, ny, nx]
  TransientResult.temperatures_time_c: [nt, n_z_nodes, ny, nx]
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `MaterialZone` (new model) | Rectangular (layer, x0, y0, x1, y1, material) region override | `DisplayProject`, `build_material_map` |
| `build_material_map` (new helper) | Converts layer + zone list into per-cell material property arrays | `network_builder`, tests |
| `Layer.nz` (extended model) | Number of z-nodes for this layer's thickness (default 1 = backward compat) | `network_builder`, `DisplayProject` validation |
| `network_builder` (modified) | Builds sparse system using per-cell material arrays and variable z-node counts | `ThermalNetwork`, both solvers |
| `ThermalNetwork` (modified) | Carries `z_layer_map` and `n_z_nodes` in addition to existing fields | Both solvers, postprocessor |
| Solvers (reshape only) | Reshape flat solution into `[n_z_nodes, ny, nx]` instead of `[n_layers, ny, nx]` | Postprocessor, GUI, CLI |
| `DisplayProject` (extended) | Validates `material_zones` reference known layers and materials | Everything |

---

## Node Indexing Scheme: Variable nz Per Layer

### The Core Problem

The existing scheme is: `node = layer_idx * (nx*ny) + iy * nx + ix`

With z-refinement, layer `l` has `nz_l` z-nodes. The global z-node index is not simply `layer_idx` — it is the cumulative sum of all z-nodes in layers below.

### Recommended Scheme: Flat Z-Node Index (Cumulative Offset)

```
z_offsets[l] = sum(layer.nz for layer in project.layers[:l])
z_node_for_layer_l_sublevel_k = z_offsets[l] + k    (k in 0..nz_l-1)

Global node index:
  node = (z_offsets[l] + k) * (nx*ny) + iy * nx + ix
```

This produces a contiguous linear ordering: all x-y nodes of z-node 0, then all x-y nodes of z-node 1, etc., across all layers in sequence. Total nodes = `sum(layer.nz for layer in layers) * nx * ny`.

**Example:** Three layers with nz = [1, 3, 1], nx=10, ny=8
- Layer 0: z-nodes 0 (1 z-level), global node range [0, 80)
- Layer 1: z-nodes 1, 2, 3 (3 z-levels), global node range [80, 320)
- Layer 2: z-node 4 (1 z-level), global node range [320, 400)
- Total nodes = 5 * 10 * 8 = 400

**Why this scheme:**
- Simple arithmetic offset — no lookup table needed during assembly
- Natural extension of the existing `layer_idx * n_per_layer` pattern
- z_offsets precomputed once, reused for all link types
- Backward compatible: if all `layer.nz == 1`, the formula reduces exactly to the existing scheme

**Implementation:**

```python
# In build_thermal_network():
z_offsets = np.zeros(n_layers + 1, dtype=int)
for l, layer in enumerate(project.layers):
    z_offsets[l + 1] = z_offsets[l] + layer.nz
n_total_z = z_offsets[-1]          # total z-nodes
n_nodes = n_total_z * n_per_layer  # total nodes in system

def node_index(z_global: int, ix: int, iy: int) -> int:
    return z_global * n_per_layer + iy * nx + ix
```

### Z-Layer Map (for result interpretation)

Postprocessors and GUI code need to know which physical layer a given z-node belongs to. Precompute once during network build:

```python
z_layer_map = []   # z_layer_map[z_global] = layer_idx
z_sublevel_map = []  # z_sublevel_map[z_global] = k within that layer
for l, layer in enumerate(project.layers):
    for k in range(layer.nz):
        z_layer_map.append(l)
        z_sublevel_map.append(k)
```

Store both on `ThermalNetwork`. This lets postprocessors reconstruct per-layer views, and the GUI can slice by layer for display.

---

## MaterialZone Data Model

### Design Decision: Rectangular Regions (Not Per-Cell Arrays)

Per-cell arrays (shape [n_layers, ny, nx] of material keys) would be:
- Large to serialize (nx*ny strings per layer)
- Brittle under mesh resolution changes
- Hard to edit in a GUI

Rectangular region descriptors are:
- Compact (4 floats + a material name)
- Resolution-independent (zones expand to cell masks at build time)
- Easy to define in a GUI (click-drag region)
- Naturally stackable (later zones override earlier ones)

**Recommendation:** Use rectangular region descriptors exclusively.

### MaterialZone Model

```python
# thermal_sim/models/material_zone.py (new file)

@dataclass
class MaterialZone:
    """Rectangular material override region within a layer.

    Coordinates are in metres, same coordinate system as HeatSource.
    Zones are applied in list order; later zones take priority over earlier ones.
    """
    layer: str        # name of the layer this zone applies to
    material: str     # key into DisplayProject.materials
    x0: float         # left bound (metres)
    y0: float         # bottom bound (metres)
    x1: float         # right bound (metres)
    y1: float         # top bound (metres)

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "material": self.material,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialZone":
        return cls(
            layer=data["layer"],
            material=data["material"],
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
        )
```

### Zone Resolution: AABB Overlap at Build Time

Zones are resolved to per-cell material assignments in `build_material_map()`, using the same AABB overlap logic already present in `_source_mask()` for heat sources. This reuses proven code and ensures consistency.

```python
# thermal_sim/solvers/material_map.py (new helper)

def build_material_map(
    project: DisplayProject,
    grid: Grid2D,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns per-cell property arrays shaped [n_layers, ny, nx]:
      k_in_plane_map, k_through_map, density_map, specific_heat_map, emissivity_map

    Algorithm:
    1. Fill each layer with its default material properties.
    2. For each MaterialZone (in list order), apply AABB overlap and overwrite cells.
    """
```

This separation keeps `network_builder.py` clean — it calls `build_material_map()` once and uses the resulting numpy arrays for all conductance calculations.

---

## Through-Thickness Conduction: Within-Layer Z-Refinement

### Current (2.5D) Formula

Between layer `l` and layer `l+1`, for each (ix, iy) cell:

```
R_total = dz_lower / (2 * k_lower * A) + R_interface / A + dz_upper / (2 * k_upper * A)
G = 1 / R_total
```

Where `k_lower` and `k_upper` are uniform per layer.

### New (3D) Within-Layer Formula

Within layer `l`, between adjacent z-nodes `k` and `k+1` (sub-level nodes):

```
dz_sub = layer.thickness / layer.nz        # uniform z-node spacing within a layer
R = dz_sub / (2 * k_through[l, iy, ix] * A) + dz_sub / (2 * k_through[l, iy, ix] * A)
  = dz_sub / (k_through[l, iy, ix] * A)
G[ix, iy] = k_through_map[l, iy, ix] * A / dz_sub
```

Between the top of layer `l` (z-node `z_offsets[l] + nz_l - 1`) and the bottom of layer `l+1` (z-node `z_offsets[l+1]`):

```
# Half-thickness of top-most sub-node in layer l:
dz_lower_half = (layer_l.thickness / layer_l.nz) / 2

# Half-thickness of bottom-most sub-node in layer l+1:
dz_upper_half = (layer_l1.thickness / layer_l1.nz) / 2

# Per-cell conductance (vectorized over ix, iy):
R_lower = dz_lower_half / (k_through_map[l, iy, ix] * A)
R_iface = layer_l.interface_resistance_to_next / A
R_upper = dz_upper_half / (k_through_map[l+1, iy, ix] * A)
G[iy, ix] = 1.0 / (R_lower + R_iface + R_upper)
```

Note: with `nz=1`, `dz_lower_half = thickness/2` exactly, recovering the original formula.

### Vectorization Strategy

All within-layer z-links and between-layer z-links are fully vectorizable over (ix, iy). The `_add_link_vectorized()` function already accepts node arrays and per-node conductance arrays. Extend the signature to accept `conductance: np.ndarray | float`:

```python
def _add_link_vectorized(
    n1: np.ndarray,
    n2: np.ndarray,
    conductance: np.ndarray | float,
) -> None:
```

When `conductance` is a 1D array of length `n_per_layer`, each pair gets its own conductance value. This is the key vectorization for per-cell material variation.

---

## Lateral Conduction: Per-Cell Material

### Current Formula

Uniform per layer:
```python
g_x = material.k_in_plane * layer.thickness * grid.dy / grid.dx
g_y = material.k_in_plane * layer.thickness * grid.dx / grid.dy
```

All `n_per_layer` horizontal links in a layer get the same conductance.

### New Formula (Per-Cell, Per-Z-Sublevel)

For z-sublevel `k` in layer `l`:
```
dz_sub = layer.thickness / layer.nz

g_x[iy, ix] = harmonic_mean(k_in_plane[l, iy, ix], k_in_plane[l, iy, ix+1]) * dz_sub * dy / dx
g_y[iy, ix] = harmonic_mean(k_in_plane[l, iy, ix], k_in_plane[l, iy+1, ix]) * dz_sub * dx / dy
```

The **harmonic mean** of conductivities is the physically correct average for the effective conductance between two cells with different materials:

```
k_eff = 2 * k1 * k2 / (k1 + k2)
```

This is the standard formula for two resistors in series sharing equal length — the same math used for through-thickness coupling between layers.

**Implementation:**

```python
# For horizontal links in layer l, z-sublevel k:
z_global = z_offsets[l] + k
dz_sub = project.layers[l].thickness / project.layers[l].nz

k_left = k_in_plane_map[l, iy_all[mask_x], ix_all[mask_x]]
k_right = k_in_plane_map[l, iy_all[mask_x], ix_all[mask_x] + 1]
k_eff = 2.0 * k_left * k_right / (k_left + k_right)
g_x_arr = k_eff * dz_sub * grid.dy / grid.dx

n1 = z_global * n_per_layer + flat_left
n2 = z_global * n_per_layer + flat_right
_add_link_vectorized(n1, n2, g_x_arr)  # conductance is now an array
```

**Backward compatibility:** When all cells in a layer have the same material, `k_left == k_right`, so `k_eff = k_left = k_right`. The formula reduces exactly to the existing scalar formula.

---

## Thermal Capacity: Per-Cell, Per-Z-Sublevel

```
c_node[l, k, iy, ix] = density_map[l, iy, ix] * specific_heat_map[l, iy, ix]
                       * (layer.thickness / layer.nz) * A
```

This is fully vectorizable. Reshape the flat c_vec in layer-then-sublevel order:

```python
for l, layer in enumerate(project.layers):
    dz_sub = layer.thickness / layer.nz
    c_node_layer = density_map[l] * specific_heat_map[l] * dz_sub * area  # [ny, nx]
    for k in range(layer.nz):
        z_global = z_offsets[l] + k
        start = z_global * n_per_layer
        c_vec[start : start + n_per_layer] = c_node_layer.ravel()
```

---

## Boundary Conditions: Top/Bottom Surface Adaptation

The top and bottom surface boundary conditions attach to the outermost z-node of the top and bottom layers respectively. The conduction distance from the node center to the surface is now `dz_sub / 2`:

```python
# Top boundary:
top_layer = project.layers[-1]
dz_sub_top = top_layer.thickness / top_layer.nz
top_z_global = z_offsets[-1] - 1  # = n_total_z - 1
g_top = _surface_sink_conductance(
    boundary=project.boundaries.top,
    emissivity=emissivity_map[-1].ravel(),   # per-cell, may vary
    conduction_distance=dz_sub_top / 2.0,
    conductivity=k_through_map[-1].ravel(),   # per-cell array
    area=area,
)
```

Note: `_surface_sink_conductance()` currently computes a scalar from scalar inputs. It must be extended to accept array inputs for `emissivity`, `conductivity` when per-cell values differ. Alternatively, call it cell-by-cell (simpler, slightly slower). Given that boundary cells are a small fraction of total cells, per-cell scalar calls are acceptable for Phase 1.

---

## ThermalNetwork Extension

```python
@dataclass(frozen=True)
class ThermalNetwork:
    a_matrix: csr_matrix
    b_boundary: np.ndarray
    b_sources: np.ndarray
    c_vector: np.ndarray
    grid: Grid2D
    n_z_nodes: int            # total z-node count (was n_layers)
    n_layers: int             # physical layer count (for backward compat)
    layer_names: list[str]    # physical layer names (length n_layers)
    z_layer_map: list[int]    # z_node -> layer_idx  (length n_z_nodes)

    @property
    def b_vector(self) -> np.ndarray:
        return self.b_boundary + self.b_sources

    @property
    def n_nodes(self) -> int:
        return self.n_z_nodes * self.grid.nx * self.grid.ny
```

`z_layer_map` is the key backward compatibility bridge: for any code that currently iterates over `range(network.n_layers)`, it can be refactored to iterate over `range(network.n_z_nodes)` and use `z_layer_map[z]` to get the physical layer index.

---

## Architectural Patterns

### Pattern 1: Material Map as a Build-Time Precomputation

**What:** `build_material_map()` resolves zones to per-cell property arrays once before network assembly. Network builder uses these arrays throughout — it never queries `DisplayProject.material_zones` directly during link construction.

**When to use:** Always. This cleanly separates the zone geometry problem (which cells get which material?) from the physics problem (what conductances does that produce?).

**Trade-offs:** Allocates `5 * n_layers * ny * nx` floats upfront (~20 MB for a 100x80 grid with 10 layers). Acceptable for the target mesh sizes. Makes the network builder simpler and testable independently.

### Pattern 2: Cumulative Z-Offset Precomputation

**What:** Compute `z_offsets: list[int]` (length `n_layers + 1`) once at the top of `build_thermal_network()`. Use `z_offsets[l] + k` everywhere instead of re-summing each time.

**When to use:** All node index calculations in the network builder.

**Trade-offs:** None. Simple, correct, and eliminates the possibility of off-by-one errors in per-sublevel loops.

**Example:**
```python
z_offsets = [0]
for layer in project.layers:
    z_offsets.append(z_offsets[-1] + layer.nz)
# z_offsets is now a list of n_layers+1 ints
```

### Pattern 3: Vectorized Per-Cell Conductance Arrays

**What:** Instead of a single scalar conductance per layer for all lateral links, compute a 1D array of conductances (one per cell pair) using numpy operations on the material property maps.

**When to use:** All lateral and through-thickness link assembly.

**Trade-offs:** Requires extending `_add_link_vectorized()` to accept `conductance: np.ndarray | float`. The COO assembly naturally handles per-pair conductances — this is what COO format is designed for.

**Example:**
```python
# Horizontal links for z-sublevel k of layer l
k_left = k_in_plane_map[l].ravel()[mask_x]         # shape (n_horizontal_links,)
k_right = k_in_plane_map[l, :, 1:].ravel()[mask_x]  # right-neighbor k values
k_eff = 2.0 * k_left * k_right / (k_left + k_right)
g_x_arr = k_eff * dz_sub * grid.dy / grid.dx
_add_link_vectorized(n1, n2, g_x_arr)               # g is now 1D array
```

### Pattern 4: Backward Compatibility via Default Values

**What:** All new model fields use Python default values that reproduce the 2.5D behavior exactly.

**When to use:** Every new field on `Layer`, `DisplayProject`.

**Trade-offs:** None. This is the established pattern throughout the codebase (see `LEDArray` new fields in Phase 6).

**Defaults:**
- `Layer.nz: int = 1` → existing projects get 1 z-node per layer (unchanged behavior)
- `DisplayProject.material_zones: list[MaterialZone] = []` → no zones = uniform material per layer (unchanged behavior)
- `from_dict()` uses `.get("nz", 1)` and `.get("material_zones", [])` (same pattern as all other optional fields)

### Pattern 5: Result Shape Convention Unchanged at API Level

**What:** `SteadyStateResult.temperatures_c` shape is `[n_z_nodes, ny, nx]` where `n_z_nodes = n_layers` in the 2.5D case (all `nz=1`). The shape semantics are unchanged from the user's perspective as long as `layer_names` is extended to `layer_names_by_znode` (or the result carries `z_layer_map` for layer attribution).

**When to use:** Shape conventions are already used by GUI, postprocessor, CLI, and tests. Changing the shape semantics would break all downstream consumers.

**Trade-offs:** The `n_layers` dimension in the result shape now means `n_z_nodes`. For `nz=1` projects, these are identical. For `nz>1` projects, the caller uses `z_layer_map` to aggregate z-nodes back to physical layers if needed (e.g., for the layer profile plot).

---

## Data Flow

### Network Build Flow (Extended)

```
DisplayProject
    │
    ├── (1) build_material_map(project, grid)
    │         → k_in_plane_map: [n_layers, ny, nx]
    │         → k_through_map:  [n_layers, ny, nx]
    │         → density_map:    [n_layers, ny, nx]
    │         → specific_heat_map: [n_layers, ny, nx]
    │         → emissivity_map: [n_layers, ny, nx]
    │
    ├── (2) Compute z_offsets = cumulative_sum(layer.nz for layer in layers)
    │         → n_total_z = z_offsets[-1]
    │         → n_nodes = n_total_z * nx * ny
    │
    ├── (3) Assemble thermal capacity vector c_vec [n_nodes]:
    │         For each layer l, each z-sublevel k, each cell (iy, ix):
    │           c = density_map[l, iy, ix] * specific_heat_map[l, iy, ix] * dz_sub * area
    │
    ├── (4) Assemble lateral links (COO):
    │         For each layer l, each z-sublevel k:
    │           Harmonic-mean conductance per adjacent cell pair
    │           Vectorized over (iy, ix)
    │
    ├── (5) Assemble within-layer through-thickness links (COO):
    │         For each layer l with nz > 1, each sublevel pair (k, k+1):
    │           G[iy, ix] = k_through_map[l, iy, ix] * A / dz_sub
    │           Vectorized over (iy, ix)
    │
    ├── (6) Assemble between-layer through-thickness links (COO):
    │         For each adjacent layer pair (l, l+1):
    │           Half-dz from each side + interface resistance
    │           Per-cell conductance using k_through_map values at boundary
    │           Vectorized over (iy, ix)
    │
    ├── (7) Apply surface boundary conditions (top, bottom, sides)
    │         Same as before, but top/bottom attach to outermost z-nodes
    │
    ├── (8) Distribute heat sources → b_sources [n_nodes]
    │         Unchanged: heat sources reference layer names, not z-levels
    │         Distribute power to all z-nodes of that layer (split equally)
    │         OR: deposit only on top-most z-node of the layer (default for LEDs)
    │
    └── (9) COO → CSR, return ThermalNetwork
```

### Heat Source Distribution on Z-Refined Layers

**Decision required:** When a heat source targets a layer with `nz > 1`, how is power distributed over z-nodes?

**Recommended:** Deposit on the **single outermost z-node** of the layer (top z-node for surface heat sources like LEDs). Rationale: LED heat is generated at the LED junction, which is on the board surface, not volumetrically distributed. This is more physically accurate for surface-mounted sources.

For volumetric sources (e.g., bulk dissipation), distribute equally across all `nz` z-nodes of the layer. Add a `volumetric: bool = False` field to `HeatSource` to distinguish.

If this distinction is deferred, depositing only on the top-most z-node is the safer default — it matches how engineers think about surface heat sources and avoids artificial thermal spreading within the layer.

**Impact on network_builder:** Modify `_apply_heat_sources()` to identify the correct z-node(s) per source.

---

## DisplayProject Serialization Changes

### New Fields

```python
# In Layer:
nz: int = 1   # z-refinement node count for this layer

# In DisplayProject:
material_zones: list[MaterialZone] = field(default_factory=list)
```

### to_dict() Extension

```python
# Layer.to_dict():
return {
    "name": self.name,
    "material": self.material,
    "thickness": self.thickness,
    "interface_resistance_to_next": self.interface_resistance_to_next,
    "nz": self.nz,   # NEW
}

# DisplayProject.to_dict():
return {
    ...(existing)...,
    "material_zones": [z.to_dict() for z in self.material_zones],  # NEW
}
```

### from_dict() Extension (Backward Compatible)

```python
# Layer.from_dict():
return cls(
    ...(existing)...,
    nz=int(data.get("nz", 1)),   # defaults to 1 for existing files
)

# DisplayProject.from_dict():
return cls(
    ...(existing)...,
    material_zones=[MaterialZone.from_dict(z) for z in data.get("material_zones", [])],
)
```

### DisplayProject Validation Extension

```python
# In DisplayProject.__post_init__():
for zone in self.material_zones:
    if zone.layer not in layer_names:
        raise ValueError(f"MaterialZone references unknown layer '{zone.layer}'.")
    if zone.material not in self.materials:
        raise ValueError(f"MaterialZone references unknown material '{zone.material}'.")
    if zone.x0 >= zone.x1 or zone.y0 >= zone.y1:
        raise ValueError(f"MaterialZone has zero or negative area.")

for layer in self.layers:
    if layer.nz < 1:
        raise ValueError(f"Layer '{layer.name}' nz must be >= 1.")
```

---

## Recommended Project Structure (additions only)

```
thermal_sim/
├── models/
│   ├── material_zone.py        NEW: MaterialZone dataclass
│   ├── layer.py                EXTEND: add nz field
│   └── project.py              EXTEND: add material_zones field + validation
├── solvers/
│   ├── material_map.py         NEW: build_material_map() helper
│   └── network_builder.py      MODIFY: z-refinement + per-cell conductance
```

No other files require structural changes. Solvers (`steady_state.py`, `transient.py`) need only a one-line change to the reshape call (from `n_layers` to `n_z_nodes`), plus accepting the new `ThermalNetwork` fields.

---

## Integration Points

### Existing Code That References n_layers or layer_names

These are the callsites that must be reviewed after the `ThermalNetwork` shape change:

| Location | Current Usage | Required Change |
|----------|--------------|----------------|
| `steady_state.py` line 46 | `solution.reshape((network.n_layers, ...))` | Use `network.n_z_nodes` |
| `transient.py` line 80 | `state_shape = (network.n_layers, ...)` | Use `network.n_z_nodes` |
| `postprocess.py` `_probe_indices` | `project.layer_index(p.layer)` → result index | Must map layer name to first z_global of that layer |
| `postprocess.py` `_top_n_from_map` | `layer, rem = divmod(idx, nx*ny)` then `layer_names[layer]` | Replace `layer_names` with `z_layer_map` + `layer_names` |
| `ui/main_window.py` layer profile display | Iterates over `layer_names` in results | Use `z_layer_map` to group z-nodes by physical layer |
| `visualization/plotting.py` | `temperatures_c[layer_idx]` to pick a z-slice | Now accepts z-node index; GUI must provide correct z-node |

### Probe Temperature Extraction

Current: `layer_idx = project.layer_index(p.layer)` directly indexes into the result array.

New: `z_first = z_offsets[project.layer_index(p.layer)]` gives the first z-node for that layer. For the typical case of probes on a specific z-level, use the top z-node (`z_offsets[l+1] - 1`) since that is the node closest to the measurement surface.

---

## Backward Compatibility Strategy

### Guarantee

A project JSON file with no `nz` fields on layers and no `material_zones` key must:
1. Load without error
2. Solve and produce identical temperatures to the current solver
3. Round-trip serialize without corruption

### Verification

Add one test: load an existing example project, solve with the new builder, compare to a reference solution produced by the old builder. Temperature arrays must match to float32 precision.

### Migration Path for Existing Projects

No migration required. Existing files load as `nz=1`, `material_zones=[]`, which is mathematically identical to the current 2.5D solver.

---

## Build Order (Dependencies)

```
1. MaterialZone model (material_zone.py)
        no dependencies — pure dataclass

2. Layer.nz field extension
        no dependencies — add field, add from_dict key

3. DisplayProject.material_zones field extension
        depends on MaterialZone

4. build_material_map() helper (material_map.py)
        depends on MaterialZone, Layer, Material, Grid2D
        can be tested independently: given a project + grid → property arrays

5. ThermalNetwork schema extension (z_layer_map, n_z_nodes)
        no code dependency — just add fields to the dataclass

6. network_builder.py rewrite
        depends on build_material_map, Layer.nz, updated ThermalNetwork
        this is the core change; must be correct before solvers can produce results

7. Solver reshape changes (steady_state.py, transient.py)
        depends on updated ThermalNetwork.n_z_nodes

8. Postprocessor probe index fix
        depends on updated ThermalNetwork.z_layer_map

9. Validation tests
        depends on all of the above

10. GUI display (z-plane slicing, layer aggregation)
        depends on z_layer_map on result objects
```

**Recommended implementation sequence:**
- Step 1–5: Pure model work. No solver changes. Can be committed independently.
- Step 6: Network builder rewrite. The biggest risk. Test with nz=1, no zones first to confirm backward compat.
- Step 7–8: Minimal changes. Run existing test suite to verify no regressions.
- Step 9: New 3D validation tests (analytical benchmarks).
- Step 10: GUI work (lowest risk, purely presentational).

---

## Anti-Patterns

### Anti-Pattern 1: Storing Per-Cell Material Keys in the Project JSON

**What people do:** Add a `material_map: list[list[str]]` field to `Layer` that stores a full per-cell material assignment grid.

**Why it's wrong:** The grid changes when the user changes nx/ny. The stored map becomes stale and wrong. It also bloats the JSON file significantly.

**Do this instead:** Store zone descriptors (x0, y0, x1, y1, material) that are resolution-independent. Resolve to per-cell arrays at build time inside `build_material_map()`.

### Anti-Pattern 2: Adding nz to MeshConfig Instead of Layer

**What people do:** Add `nz: int = 1` to `MeshConfig`, applying one z-node count to all layers.

**Why it's wrong:** Different layers in a display stack have different thermal gradients. The LED board needs z-refinement; the thick aluminum back cover does not. Forcing uniform nz wastes nodes.

**Do this instead:** Put `nz` on `Layer`. Each layer independently controls its z-resolution. The `MeshConfig` remains in-plane only.

### Anti-Pattern 3: Per-Step Material Lookup in the Time Loop

**What people do:** Call `project.material_for_layer(l_idx)` or resolve zones inside the transient solver's time loop.

**Why it's wrong:** Material properties are constant throughout a simulation. Resolving them per time step is wasted O(n_cells) work repeated thousands of times.

**Do this instead:** `build_material_map()` runs once during `build_thermal_network()`. The resulting property arrays are embedded in the `ThermalNetwork` or used only during network construction. The time loop never touches materials.

### Anti-Pattern 4: Reindexing n1 and n2 with Mixed Layer/Z-Node Conventions

**What people do:** Mix `layer_idx * n_per_layer` (old scheme) with `z_global * n_per_layer` (new scheme) in different parts of the builder.

**Why it's wrong:** The two schemes agree only when `nz=1` for all layers. Mixing them silently produces wrong links for z-refined layers.

**Do this instead:** Delete the old `node_index(layer_idx, ix, iy)` local function from `build_thermal_network()` and replace it with `node_index(z_global, ix, iy)` everywhere. The mapping from `(layer_idx, k)` to `z_global` is always `z_offsets[layer_idx] + k`. Never use `layer_idx` directly as a z-node index after the refactor.

### Anti-Pattern 5: Distributing Heat Uniformly Across All Z-Nodes

**What people do:** When a `HeatSource` targets a layer with `nz=3`, split its power equally over 3 z-nodes.

**Why it's wrong:** Surface heat sources (LEDs, chip heating) are not volumetric. Spreading power through 3 mm of material changes the temperature gradient shape and produces incorrect junction temperatures.

**Do this instead:** For the default surface-mounted case, deposit all power on the topmost z-node of the layer. For future volumetric sources, add a `volumetric` flag to `HeatSource`. Start with surface-only behavior.

---

## Scaling Considerations

This is a single-user desktop tool. "Scaling" means model complexity growth.

| Concern | Current state (nz=1) | With z-refinement (nz=3 per layer) |
|---------|---------------------|-------------------------------------|
| Node count | n_layers * nx * ny | 3 * n_layers * nx * ny |
| Matrix size | ~50k nodes (10 layers, 50x100) | ~150k nodes |
| spsolve time | < 1 second | 2-5 seconds (sparse, acceptable) |
| Memory (matrix) | ~few MB | ~10-30 MB |
| Transient time | O(n_steps * n_nodes) | 3x longer per step |
| With material zones | Same as above | Material map adds ~5 * n_layers * ny * nx floats (~few MB) |

z-refinement is the larger computational cost factor. Material zones add negligible cost (build-time only). The target hardware (Windows laptop) can handle n_total_z up to ~10 per typical 10-layer stack without issue.

---

## Sources

- Direct inspection: `thermal_sim/solvers/network_builder.py` — existing node indexing, COO assembly, link vectorization pattern
- Direct inspection: `thermal_sim/models/project.py` — `DisplayProject`, `MeshConfig`, `material_for_layer()`
- Direct inspection: `thermal_sim/models/layer.py` — `Layer` dataclass, `to_dict`/`from_dict` pattern
- Direct inspection: `thermal_sim/models/material.py` — `Material` frozen dataclass
- Direct inspection: `thermal_sim/solvers/steady_state.py` — result reshape convention
- Direct inspection: `thermal_sim/solvers/transient.py` — `state_shape`, implicit Euler structure
- Direct inspection: `thermal_sim/core/postprocess.py` — `_probe_indices()`, `_top_n_from_map()`
- Direct inspection: `.planning/codebase/ARCHITECTURE.md` — node indexing canonical definition
- Direct inspection: `.planning/PROJECT.md` — milestone constraints, key decisions
- RC-network thermal modeling: Harmonic mean conductivity for material interfaces is standard finite-difference practice (Patankar, Numerical Heat Transfer and Fluid Flow, 1980 — well-established, HIGH confidence)

---

*Architecture research for: 3D RC-network thermal solver with per-cell materials and z-refinement*
*Researched: 2026-03-16*
