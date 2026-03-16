# Phase 11: Voxel-Based 3D Solver - Research

**Researched:** 2026-03-16
**Domain:** 3D conformal voxel mesh, RC-network thermal solver, assembly block data model, PyVista 3D visualization
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Voxel grid model:** Assembly blocks (named 3D rectangular solids with position, size, material). Users define geometry LEGO-style; solver auto-generates conformal mesh. No manual voxel painting.
- **Heat sources:** NOT assembly blocks. Separate objects that attach to a named block's surface face. Placement model: "on top face of block X."
- **Boundary conditions:** Auto-detect exposed faces (any voxel face not touching another block). User assigns h/emissivity to named boundary groups (e.g., "top_exposed").
- **Mesh:** XYZ conformal (non-uniform). Grid lines snap to ALL block boundaries in x, y, AND z.
- **Empty voxels:** Air-filled (k ≈ 0.026 W/mK). Gaps between components are air.
- **Mesh size:** Warn at threshold (e.g., 500k nodes) but never block solving. User decides.
- **Backward compatibility:** Clean break. Remove old Layer/Zone/EdgeLayer models, network builder, old solvers entirely. Git history preserves old code. New project JSON format.
- **Tests:** Rewrite existing analytical validation tests (1D chain, 2-node, RC transient) using assembly blocks. Same physics, new input model.
- **Example files:** DLED and ELED ready-to-run JSON examples using new format.
- **3D visualization:** PyVista/VTK embedded in PySide6 GUI as new "3D View" tab via `pyvistaqt.QtInteractor`. Required features: slice planes, block transparency/hide, temperature threshold filter, probe points in 3D.

### Claude's Discretion

- Sparse matrix format and solver choice (spsolve vs iterative for large meshes)
- Internal data structures for the conformal mesh generator
- Exact PyVista widget layout and toolbar controls
- Warning threshold for node count
- Air gap thermal modeling details (pure conduction vs effective conductivity)
- JSON schema design for the new project format

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

## Summary

Phase 11 replaces the current 2.5D layer-stack model with a true 3D voxel solver built on an assembly block input model. Users define named 3D rectangular blocks (position, size, material), and the solver auto-generates a conformal non-uniform Cartesian grid whose lines snap to every block boundary in x, y, and z. Each voxel receives a per-cell material assignment by testing which block it falls inside. The RC-network conductance formula is unchanged — only the mesh generation, material assignment, and node indexing change.

The most critical design decisions for Phase 11 are: (1) **solver choice** — `scipy.sparse.linalg.spsolve` (UMFPACK direct) degrades catastrophically beyond ~60×40×8 nodes (16k+); iterative `bicgstab` with ILU preconditioner is 100–130× faster at 120×80×12 = 115k nodes and scales gracefully; (2) **conformal mesh generation** — collect all unique x/y/z coordinates from block boundaries, sort them, and produce non-uniform grid spacings; (3) **the 3D visualization** tab must use `pyvista.ImageData` with `cell_data` scalars (not point data) to correctly represent per-cell temperatures.

The old code base is extensively reusable: `Material` dataclass, `material_library.py`, boundary condition formulas, the COO-triplet sparse assembly pattern, implicit Euler transient solver structure, and `pyvistaqt.QtInteractor` integration. The new code replaces: project model, conformal mesh class, network builder, heat source placement model, and boundary detection.

**Primary recommendation:** Replace `spsolve` with `bicgstab` + `spilu` preconditioner for steady-state (with `spsolve` as fallback for <5k nodes), and keep `splu` LU prefactoring for transient (amortizes cost over many timesteps). Warn at 500k nodes.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | ≥1.26 (2.4.3 installed) | Array operations, voxel masks, mesh coordinate arrays | Already required; vectorized block-to-voxel assignment |
| scipy.sparse | ≥1.12 (1.17.1 installed) | COO/CSR matrix assembly; `spsolve`, `splu`, `bicgstab`, `spilu` | Already required; all solvers present |
| pyvista | 0.47.1 (installed) | 3D mesh types (`ImageData`, `Box`, `PolyData`); slice, threshold, cell_data | Already installed; `ImageData.cell_data` is the correct container for per-voxel temperatures |
| pyvistaqt | 0.11.3 (installed) | `QtInteractor` embeds VTK render loop in PySide6 | Already installed and used in `assembly_3d.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.sparse.linalg.bicgstab | included in scipy | Iterative solver, fast for large structured problems | Steady-state >5k nodes |
| scipy.sparse.linalg.spilu | included in scipy | Incomplete LU preconditioner for iterative solver | Paired with bicgstab to cut iteration count |
| scipy.sparse.linalg.splu | included in scipy | Direct LU factorization for transient (repeated solves) | Transient: factorize once, back-solve every timestep |
| scipy.sparse.linalg.spsolve | included in scipy | UMFPACK direct solve | Steady-state <5k nodes (fast for tiny problems) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| bicgstab + spilu | GMRES + AMG (pyamg) | AMG is faster for very large problems (>1M nodes) but adds a dependency; not in requirements.txt |
| COO→CSR assembly | lil_matrix incremental | COO batch-concatenation is faster; matches existing pattern |
| pyvista ImageData | pyvista UnstructuredGrid | UnstructuredGrid is more flexible but non-uniform Cartesian grids map naturally to ImageData with non-uniform spacing |

**Installation:** No new dependencies required — all libraries already installed.

---

## Architecture Patterns

### Recommended Project Structure

```
thermal_sim/
├── models/
│   ├── assembly_block.py     # AssemblyBlock dataclass (new)
│   ├── surface_source.py     # SurfaceSource dataclass — LED on block face (new)
│   ├── voxel_project.py      # VoxelProject — top-level model replacing DisplayProject (new)
│   ├── material.py           # REUSE as-is
│   ├── boundary.py           # REUSE as-is (SurfaceBoundary)
│   └── probe.py              # REUSE; update to reference block name instead of layer name
├── core/
│   ├── conformal_mesh.py     # ConformalMesh3D — non-uniform grid from block boundaries (new)
│   ├── voxel_assignment.py   # Block-to-voxel rasterization (new)
│   ├── material_library.py   # REUSE as-is
│   └── constants.py          # REUSE as-is
├── solvers/
│   ├── voxel_network_builder.py  # Builds COO sparse A, b, C from VoxelProject (new)
│   ├── steady_state_voxel.py     # SteadyStateSolver using bicgstab/spsolve (new)
│   └── transient_voxel.py        # TransientSolver using splu implicit Euler (new)
├── ui/
│   ├── voxel_3d_view.py      # PyVista 3D view tab: slice, threshold, transparency (new)
│   ├── block_editor.py       # GUI block table replacing layer editor (new)
│   └── main_window.py        # UPDATE: add 3D View tab, replace layer editor
├── io/
│   ├── voxel_project_io.py   # JSON load/save for VoxelProject (new)
│   └── csv_export.py         # UPDATE for 3D voxel results
└── visualization/
    └── plotting.py           # RETAIN matplotlib 2D slices; supplement with PyVista
examples/
├── dled_example.json         # New format DLED example (new)
└── eled_example.json         # New format ELED example (new)
tests/
├── test_conformal_mesh.py    # Tests for mesh generation (new)
├── test_voxel_assignment.py  # Block-to-voxel rasterization tests (new)
├── test_voxel_solver.py      # Analytical validation tests ported to assembly blocks (new)
└── [existing tests]          # REMOVE tests that depend on old Layer model
```

### Pattern 1: Conformal Non-Uniform Grid Generation

**What:** Collect all unique x, y, z coordinates from block boundaries, sort and deduplicate, producing non-uniform grid line positions. Per-interval spacings are non-uniform; each interval has one mesh cell by default (the user can specify a per-interval subdivision count for denser meshing if needed).

**When to use:** At solver build time, before any conductance computation.

**Core algorithm:**
```python
# Source: derived from CONTEXT.md conformal mesh decision
def build_conformal_mesh(blocks: list[AssemblyBlock]) -> ConformalMesh3D:
    xs = sorted(set(b for block in blocks for b in [block.x, block.x + block.width]))
    ys = sorted(set(b for block in blocks for b in [block.y, block.y + block.depth]))
    zs = sorted(set(b for block in blocks for b in [block.z, block.z + block.height]))
    return ConformalMesh3D(x_edges=xs, y_edges=ys, z_edges=zs)
```

The `ConformalMesh3D` stores edge positions (not spacings), derives `dx[i]`, `dy[j]`, `dz[k]` on demand, and provides:
- `n_cells_x = len(x_edges) - 1`, similarly for y, z
- `cell_center_x(i)`, `cell_center_y(j)`, `cell_center_z(k)`
- `node_index(ix, iy, iz)` → flat index

### Pattern 2: Block-to-Voxel Material Assignment

**What:** For each voxel (ix, iy, iz), test which assembly block contains its center point. Assign that block's material. Voxels not inside any block get the Air material (k ≈ 0.026 W/mK).

**Key detail:** Use cell-center containment test: center must be strictly inside block bounds. When blocks overlap, last-defined-wins (iterate blocks in definition order; later blocks overwrite earlier assignments — user controls priority by ordering).

```python
# Vectorized assignment using NumPy broadcasting
def assign_voxel_materials(mesh: ConformalMesh3D, blocks: list[AssemblyBlock],
                           materials: dict[str, Material]) -> np.ndarray:
    # material_id_grid shape: (nz, ny, nx) — integer index into materials array
    cx = mesh.x_centers()  # shape (nx,)
    cy = mesh.y_centers()  # shape (ny,)
    cz = mesh.z_centers()  # shape (nz,)
    # Use np.meshgrid or broadcasting to get (nz, ny, nx) center arrays
    # Then iterate blocks, marking cells inside each block
    ...
```

### Pattern 3: COO Sparse Matrix Assembly (Unchanged Core Pattern)

**What:** The conductance matrix assembly is identical to the current `network_builder.py` pattern. For each pair of neighboring voxels, compute harmonic-mean conductance, accumulate COO triplets, convert to CSR once at the end.

**Key difference from current code:** In the current code, lateral conductance uses uniform `dx, dy`; in the 3D voxel solver, cell faces have non-uniform dimensions. For neighbor (i,j,k)–(i+1,j,k) in x-direction:
```python
# Area of shared face: dy[j] * dz[k]  (non-uniform)
# Conduction half-distances: dx[i]/2 and dx[i+1]/2
face_area = dy[j] * dz[k]
r_left  = (dx[i]/2)   / (k_x[i,j,k]   * face_area)
r_right = (dx[i+1]/2) / (k_x[i+1,j,k] * face_area)
g = 1.0 / (r_left + r_right)  # harmonic mean of conductances
```

This generalizes the existing harmonic-mean formula to 3D non-uniform grids.

### Pattern 4: Solver Strategy by Problem Size

**What:** Choose solver based on node count to balance speed and memory.

```python
# Steady-state solver selection (measured on this machine):
# <5k nodes:   spsolve (direct, <10ms)
# 5k-500k:    bicgstab + spilu (fast iterative, <1s for 115k nodes)
# >500k:      bicgstab + spilu + warn user

DIRECT_THRESHOLD = 5_000   # nodes below which spsolve is used
WARN_THRESHOLD = 500_000   # nodes above which user is warned

def solve_steady_state(A, b, n_nodes):
    if n_nodes <= DIRECT_THRESHOLD:
        return spsolve(A, b)
    ilu = spilu(A.tocsc(), fill_factor=10, drop_tol=1e-4)
    M = LinearOperator(A.shape, ilu.solve)
    x, info = bicgstab(A, b, M=M, rtol=1e-8, maxiter=500)
    if info != 0:
        # Fallback: retry without preconditioner
        x, info = bicgstab(A, b, rtol=1e-6, maxiter=1000)
    return x
```

For transient, keep `splu` LU prefactoring — cost is paid once, each back-solve is fast (measured: ~70ms for 90k nodes).

### Pattern 5: Temperature Result as 3D Array

**What:** Result array has shape `(nz, ny, nx)` where nz, ny, nx are the conformal mesh cell counts. This maps directly to `pyvista.ImageData` with non-uniform spacing via `pyvista.RectilinearGrid`.

```python
# Correct PyVista container for non-uniform spacing + cell data:
import pyvista as pv
grid = pv.RectilinearGrid(x_edges, y_edges, z_edges)
grid.cell_data['Temperature_C'] = temperatures.ravel(order='F')  # Fortran order for VTK
```

Note: `pv.ImageData` requires uniform spacing. For non-uniform conformal grids, use `pv.RectilinearGrid(x_edges, y_edges, z_edges)` instead.

### Pattern 6: Surface Heat Source Placement

**What:** LEDs attach to a named block's face. The face is identified by block name + face direction (`top`, `bottom`, `left`, `right`, `front`, `back`). At solve time, find the voxels on that face (the row of voxels at the block boundary) and inject power into them.

```python
@dataclass(frozen=True)
class SurfaceSource:
    name: str
    block: str             # name of the AssemblyBlock
    face: str              # "top" | "bottom" | "left" | "right" | "front" | "back"
    power_w: float
    shape: str             # "full" | "rectangle" | "circle"
    # shape parameters (x/y position within the face, width/height or radius)
    x: float = 0.0
    y: float = 0.0
    width: float | None = None
    height: float | None = None
    radius: float | None = None
```

The solver maps `block + face` to a specific z-slice (for top/bottom) or x/y column (for left/right/front/back) within the conformal mesh, then applies the source mask within that slice.

### Pattern 7: Auto-Detect Exposed Boundary Faces

**What:** A voxel face is "exposed" (has convection/radiation BC) if no neighboring voxel on that side is inside a block (i.e., the neighbor is Air). Walk the grid boundary faces and check material.

**Implementation:** After material assignment, the grid exterior faces (ix=0, ix=nx-1, iy=0, iy=ny-1, iz=0, iz=nz-1) and any face between a non-air voxel and an air voxel on the interior are all exposed. The user assigns `h_convection` and `emissivity` to named groups. The solver applies the standard `G_surface = 1 / (R_cond_half + R_conv)` formula to these faces.

### Anti-Patterns to Avoid

- **Using `pv.ImageData` for non-uniform grids:** `ImageData` requires uniform spacing (`spacing` parameter). Non-uniform conformal grids MUST use `pv.RectilinearGrid(x_edges, y_edges, z_edges)`.
- **Using `spsolve` at scale:** Measured 14.5s for 90k nodes, 16.3s for 115k nodes. `bicgstab` solves the same in 0.1–0.12s. Direct solve is NOT acceptable for the target problem size.
- **Python loops per voxel in conductance assembly:** Must use vectorized NumPy operations for face-area and conductance arrays. The existing vectorized COO pattern from `network_builder.py` is the correct template.
- **Flat indexing as `iz * ny * nx + iy * nx + ix` with reversed axis order:** VTK/PyVista uses Fortran (column-major) order for `RectilinearGrid`. Plan the flat index convention explicitly and be consistent between the solver and visualization.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Iterative linear solver | Custom CG/GMRES | `scipy.sparse.linalg.bicgstab` | Convergence, preconditioning, stopping criteria are subtle |
| Incomplete LU preconditioner | Custom ILU | `scipy.sparse.linalg.spilu` | Pivoting, fill factor, drop tolerance — many edge cases |
| 3D visualization | Custom OpenGL widget | `pyvista.RectilinearGrid` + `QtInteractor` | VTK handles all rendering, interaction, colormaps |
| Slice plane interaction | Custom cutting plane | `pyvista.Plotter.add_slider_widget` + `mesh.slice` | Already implemented in PyVista |
| Temperature colormap | Custom colormap | `pyvista` built-in `'plasma'`, `'hot'`, `'coolwarm'` | Perceptually uniform, tested |
| Block AABB test | Manual for-loops | `np.where` + broadcast masks (existing `_source_mask` pattern) | Vectorized, already validated |

**Key insight:** The hard parts (sparse linear algebra, VTK rendering, preconditioning) are already solved by scipy and PyVista. The novel work in this phase is the conformal mesh generator and the block-to-voxel material assignment — both are straightforward NumPy operations.

---

## Common Pitfalls

### Pitfall 1: spsolve at Large Node Counts
**What goes wrong:** Solve time explodes. Measured: 90k nodes → 14.5s, 115k nodes → 16.3s. A 500k-node problem would take minutes.
**Why it happens:** UMFPACK fill-in grows super-linearly for 3D structured problems.
**How to avoid:** Use `bicgstab + spilu` for n_nodes > 5000. Measured: 115k nodes → 0.12s (120× faster).
**Warning signs:** Solve hangs for >2s on the first small test problem.

### Pitfall 2: RectilinearGrid vs ImageData for Non-Uniform Grids
**What goes wrong:** PyVista `ImageData` only accepts uniform spacing. Passing a non-uniform conformal grid to `ImageData` silently distorts geometry — slices appear at wrong positions.
**Why it happens:** `pv.ImageData` ignores per-interval spacing variation; it uses a single `spacing=(dx, dy, dz)` parameter.
**How to avoid:** Use `pv.RectilinearGrid(x_edges, y_edges, z_edges)` — designed for exactly this case. Verified working in installed pyvista 0.47.1.
**Warning signs:** Slice planes don't align with block boundaries in the 3D view.

### Pitfall 3: Flat Index Convention Mismatch (Solver vs PyVista)
**What goes wrong:** Temperature array appears scrambled or transposed in 3D visualization.
**Why it happens:** NumPy uses C-order (row-major): `flat = iz * ny * nx + iy * nx + ix`. VTK/PyVista RectilinearGrid uses Fortran-order (column-major): `flat = ix * ny * nz + iy * nz + iz`.
**How to avoid:** Store solver result as `(nz, ny, nx)` NumPy array. When assigning to `RectilinearGrid.cell_data`, use `.ravel(order='F')` or reshape explicitly. Define a canonical convention at the start and enforce it in a single `node_index()` method.
**Warning signs:** Temperature pattern looks correct in shape but x and z appear swapped.

### Pitfall 4: Air Voxel Conductance Stability
**What goes wrong:** The thermal conductance matrix becomes numerically ill-conditioned if air voxels (k=0.026) are adjacent to high-conductivity metal (k=200). The ratio is ~7700:1.
**Why it happens:** The harmonic mean of a small and large conductance is dominated by the small one, creating near-zero off-diagonal entries. This is physically correct but can trigger poor convergence in iterative solvers.
**How to avoid:** Use `fill_factor=10` in `spilu` (not the default). Set a minimum conductance floor of 1e-12 W/K (already done via the `g > 0` filter in `_add_link_vectorized`). ILU preconditioner handles this well in practice.
**Warning signs:** `bicgstab` fails to converge (info != 0) on models with large air gaps.

### Pitfall 5: Block Overlap in Voxel Assignment
**What goes wrong:** When two blocks overlap (e.g., FR4 strip defined inside the metal frame volume), only one gets assigned — the result depends on iteration order, which may not match user intent.
**Why it happens:** Last-defined-wins policy without explicit documentation leads to confusion.
**How to avoid:** Document the last-defined-wins rule clearly in the JSON schema. Consider emitting a warning when block boundaries overlap (detectable at mesh build time by checking AABB intersections). The existing `_rasterize_zones` pattern (last-defined-wins) is the right model.
**Warning signs:** ELED air gap voxels get assigned as FR4 when the FR4 block is listed before the air gap block.

### Pitfall 6: Very Large Transient Problems and splu Memory
**What goes wrong:** `splu` LU factorization for a 500k-node system can use 2–4 GB RAM and take 10–20 minutes.
**Why it happens:** LU fill-in for 3D structured matrices. The existing codebase already hit this: DLED.json at 450×300 = 1.08M nodes caused UMFPACK OOM segfault (documented in STATE.md).
**How to avoid:** Warn at 500k nodes before transient solve. For transient on large meshes, ILU-preconditioned GMRES or bicgstab per timestep may be necessary (at the cost of convergence iterations per step).
**Warning signs:** Transient solve never returns; RAM usage grows without bound.

---

## Code Examples

Verified patterns from existing codebase and confirmed against installed library versions:

### Conformal Mesh from Block Boundaries
```python
# Collect unique coordinates from all block corners
def build_x_edges(blocks: list[AssemblyBlock]) -> list[float]:
    coords = set()
    for b in blocks:
        coords.add(b.x)
        coords.add(b.x + b.width)
    return sorted(coords)
```

### Voxel Material Assignment (Vectorized)
```python
import numpy as np

def assign_materials_vectorized(mesh, blocks, air_material):
    nz, ny, nx = mesh.nz, mesh.ny, mesh.nx
    # Cell center coordinates
    cx = mesh.x_centers()  # (nx,)
    cy = mesh.y_centers()  # (ny,)
    cz = mesh.z_centers()  # (nz,)

    # material_key_grid[iz, iy, ix] = material name string
    material_grid = np.full((nz, ny, nx), air_material, dtype=object)

    for block in blocks:
        # Boolean mask: which cells are inside this block
        mx = (cx >= block.x) & (cx < block.x + block.width)   # (nx,)
        my = (cy >= block.y) & (cy < block.y + block.depth)   # (ny,)
        mz = (cz >= block.z) & (cz < block.z + block.height) # (nz,)
        # Outer product: (nz, ny, nx)
        mask3d = mz[:, None, None] & my[None, :, None] & mx[None, None, :]
        material_grid[mask3d] = block.material

    return material_grid
```

### RectilinearGrid for 3D Temperature Visualization
```python
import pyvista as pv
import numpy as np

# x_edges, y_edges, z_edges: 1D arrays of edge positions (in metres or mm)
grid = pv.RectilinearGrid(x_edges * 1000, y_edges * 1000, z_edges * 1000)  # convert to mm
# Temperature array shape: (nz, ny, nx) from solver
# VTK RectilinearGrid expects Fortran order: ix varies fastest
grid.cell_data['Temperature_C'] = temperatures.ravel(order='F')
# Slice at z=mid
mid_z = (z_edges[0] + z_edges[-1]) / 2.0 * 1000
slice_mesh = grid.slice(normal='z', origin=(0, 0, mid_z))
```

### Slice Plane Slider in PyVista Qt Widget
```python
# Source: pyvista 0.47.1 — add_slider_widget
def _add_z_slice_control(plotter, grid, z_edges_mm):
    def update_slice(value):
        z_pos = z_edges_mm[0] + (z_edges_mm[-1] - z_edges_mm[0]) * value / 100.0
        plotter.remove_actor('z_slice')
        sliced = grid.slice(normal='z', origin=(0, 0, z_pos))
        plotter.add_mesh(sliced, scalars='Temperature_C', cmap='plasma',
                         name='z_slice')
    plotter.add_slider_widget(update_slice, rng=[0, 100], value=50,
                              title='Z-Slice', pointa=(0.1, 0.1), pointb=(0.9, 0.1))
```

### Threshold Filter for Temperature
```python
# Show only voxels above T_threshold
hot_cells = grid.threshold(T_threshold, scalars='Temperature_C')
plotter.add_mesh(hot_cells, scalars='Temperature_C', cmap='hot', opacity=0.8,
                 name='hot_cells')
```

### bicgstab + ILU Steady-State Solve
```python
from scipy.sparse.linalg import bicgstab, spilu, LinearOperator

def solve_bicgstab(A_csr, b):
    ilu = spilu(A_csr.tocsc(), fill_factor=10, drop_tol=1e-4)
    M = LinearOperator(A_csr.shape, ilu.solve)
    x, info = bicgstab(A_csr, b, M=M, rtol=1e-8, maxiter=500)
    if info != 0:
        x, _ = bicgstab(A_csr, b, rtol=1e-6, maxiter=2000)
    return x
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 2.5D layer stack (uniform z per layer) | 3D conformal voxel grid (non-uniform x/y/z) | Phase 11 | Edge structures at independent z-heights; ELED correctly modeled |
| Layer-based heat sources (referenced by layer name) | Surface sources on block faces | Phase 11 | LEDs attach to physically correct interface |
| Manual MaterialZone rectangles per layer | Automatic air-fill for empty voxels | Phase 11 | Gap air paths (LED→air→LGP) captured without user intervention |
| spsolve (UMFPACK direct) | bicgstab + spilu (iterative) | Phase 11 | 100× speedup at 100k nodes; enables larger models |
| `pyvista.ImageData` per layer for results | `pyvista.RectilinearGrid` for full volume | Phase 11 | Correct non-uniform spacing; unified 3D slice/threshold |

**Deprecated/outdated in this codebase after Phase 11:**
- `models/layer.py`, `models/material_zone.py`: replaced by `models/assembly_block.py`
- `models/project.py:DisplayProject`: replaced by `models/voxel_project.py:VoxelProject`
- `solvers/network_builder.py`: replaced by `solvers/voxel_network_builder.py`
- `models/stack_templates.py`: replaced by new example JSON files

---

## Open Questions

1. **Mesh density control within conformal intervals**
   - What we know: CONTEXT.md says the mesh snaps to ALL block boundaries. This gives one cell per interval by default.
   - What's unclear: Does the user need to sub-divide intervals (e.g., 5 cells across the 3mm FR4 strip) for accuracy? Or is one cell per interval always sufficient for the target use case?
   - Recommendation: Start with one cell per boundary interval. Add a global `cells_per_interval` multiplier (integer, default 1) as a single user-facing mesh density knob. This is simpler than per-block refinement.

2. **GUI block editor scope**
   - What we know: Replaces the Layers tab. Users define blocks with name, material, x/y/z position, width/depth/height.
   - What's unclear: How much geometric validation (e.g., block fits within a bounding box) is needed in the editor vs at solve time?
   - Recommendation: Validate at solve time only. Keep the block editor as a simple table (like the current layers table) with no interactive 3D drag-and-drop — that would be a separate deferred enhancement.

3. **Probe placement in 3D**
   - What we know: CONTEXT.md says probes are "labeled markers" in 3D view; user can click to read temperature.
   - What's unclear: Do probes reference a block name + face position, or absolute (x, y, z) coordinates?
   - Recommendation: Use absolute (x, y, z) coordinates for simplicity. Map to nearest voxel center at readout time. This matches the existing pattern (probes have `x`, `y` in the old model).

4. **Backward compatibility of CLI and examples**
   - What we know: CONTEXT.md says "clean break — no legacy module needed." Old project files require manual migration.
   - What's unclear: Does the CLI still accept `--project` JSON or does everything go through a new schema?
   - Recommendation: Rewrite CLI to load only the new `VoxelProject` JSON format. Document migration steps in the example files.

---

## Existing Code to Preserve vs Remove

### PRESERVE (copy/reuse as-is)
- `thermal_sim/models/material.py` — `Material` dataclass, `k_in_plane / k_through` anisotropy
- `thermal_sim/core/material_library.py` — preset materials (aluminum, FR4, steel, etc.)
- `thermal_sim/core/constants.py` — `STEFAN_BOLTZMANN`, physical constants
- `thermal_sim/models/boundary.py` — `SurfaceBoundary`, `BoundaryConditions` — same physics
- `thermal_sim/models/probe.py` — update `layer` field to reference block name or (x,y,z) position
- COO triplet accumulation + `_add_link_vectorized` pattern from `network_builder.py`
- Implicit Euler transient structure: `C/dt`, `splu` prefactoring, back-solve loop from `transient.py`
- `tests/conftest.py` — `pv.OFF_SCREEN = True` fixture
- `thermal_sim/ui/assembly_3d.py` — `_material_color_map`, `_FIXED_COLORS`, `QtInteractor` integration pattern

### REMOVE (replaced by new code)
- `thermal_sim/models/layer.py` — `Layer`, `EdgeLayer`
- `thermal_sim/models/material_zone.py` — `MaterialZone`
- `thermal_sim/models/project.py` — `DisplayProject`, `MeshConfig`, `EdgeFrame`
- `thermal_sim/models/stack_templates.py` — `dled_template`, `eled_template`, `generate_edge_zones`
- `thermal_sim/solvers/network_builder.py` — entire file
- `thermal_sim/solvers/steady_state.py` — `SteadyStateSolver`, `SteadyStateResult`
- `thermal_sim/solvers/transient.py` — `TransientSolver`, `TransientResult`
- `thermal_sim/core/geometry.py` — `Grid2D` (replaced by `ConformalMesh3D`)

### UPDATE (adapt for new model)
- `thermal_sim/app/cli.py` — rewrite for `VoxelProject` JSON
- `thermal_sim/ui/main_window.py` — add 3D View tab, replace Layers tab with Blocks tab
- `thermal_sim/core/postprocess.py` — update for 3D result array; per-block stats instead of per-layer
- `thermal_sim/io/csv_export.py` — update for 3D voxel result format
- `thermal_sim/io/project_io.py` — update to `load_voxel_project` / `save_voxel_project`
- `thermal_sim/visualization/plotting.py` — update layer references; add 3D slice matplotlib fallback

---

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection — `thermal_sim/solvers/network_builder.py`, `steady_state.py`, `transient.py`, `models/layer.py`, `models/project.py`, `ui/assembly_3d.py`
- Benchmarks run on installed scipy 1.17.1 + numpy 2.4.3 on this machine
- PyVista 0.47.1 feature verification: `RectilinearGrid`, `ImageData`, `slice()`, `threshold()`, `cell_data` — all confirmed functional
- `requirements.txt` — installed library versions confirmed

### Secondary (MEDIUM confidence)
- `scipy.sparse.linalg` module inspection — all solver functions (`spsolve`, `splu`, `spilu`, `bicgstab`, `gmres`, `LinearOperator`) present in installed version
- Solver performance benchmarks (synthetic 3D Laplacian): representative of thermal problems but not identical to the actual system (which has non-symmetric conductances from anisotropy and surface BCs)

### Tertiary (LOW confidence)
- Node count scaling estimates for memory — based on 8 bytes/float and 7 NNZ/node heuristic; actual fill depends on problem geometry and ILU fill factor

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries installed and verified in-process
- Architecture: HIGH — conformal mesh, voxel assignment, and COO assembly are well-established patterns; directly follows existing codebase conventions
- Pitfalls: HIGH — spsolve scaling measured directly; RectilinearGrid vs ImageData verified in PyVista 0.47.1; flat index convention is a known VTK/NumPy mismatch
- Solver choice: HIGH — bicgstab vs spsolve benchmarked directly on this hardware

**Research date:** 2026-03-16
**Valid until:** 2026-06-16 (scipy/numpy/pyvista APIs stable; no fast-moving dependencies)
