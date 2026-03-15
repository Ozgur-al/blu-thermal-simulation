# Stack Research

**Domain:** Python desktop engineering simulation tool — v2.0 3D solver additions
**Researched:** 2026-03-16
**Confidence:** HIGH (numpy/scipy patterns), HIGH (memory math), MEDIUM (matplotlib 3D visualization)

---

## Context: What Already Exists

This is a subsequent-milestone research document. The full existing stack is:

- Python 3.11+, NumPy 1.26+, SciPy 1.12+, PySide6 6.7+, Matplotlib 3.8+, pytest 8.0+, qt-material 2.14+

**No new packages are required for the 3D solver.** Every capability needed is already present in the stack. This document covers usage patterns, data structure choices, and integration points for the new features only.

---

## Recommended Stack — New Additions

### No new dependencies

The 3D solver milestone requires zero additional pip installs. The decisions below are about how to use existing libraries correctly, not what to add.

---

## Per-Cell Material Assignment: Storage Pattern

### Decision: uint8 index array + parallel float64 property arrays

**Use this pattern, not a dict-per-cell or structured array.**

```python
# Layer material zone map: shape (ny, nx), dtype uint8
# Value = index into material lookup arrays
material_map: np.ndarray  # shape (n_layers, ny, nx), uint8

# Flat lookup arrays indexed by material ID — one entry per registered material
k_in_plane: np.ndarray    # shape (n_materials,), float64
k_through: np.ndarray     # shape (n_materials,), float64
density: np.ndarray       # shape (n_materials,), float64
specific_heat: np.ndarray # shape (n_materials,), float64
emissivity: np.ndarray    # shape (n_materials,), float64

# Lookup for a layer: vectorized, no Python loop
k_xy_grid = k_in_plane[material_map[layer_idx]]  # shape (ny, nx), float64
```

**Why uint8 index + parallel float64 arrays:**

- Memory: `uint8` costs 1 byte per cell vs 8 bytes for a float64 property copy per cell. For a 100x100x40 mesh, the entire material map is 400 KB vs 3.2 MB if properties were stored inline. More importantly, the conductivity arrays used in network assembly come out as contiguous float64 slices, which feeds directly into vectorized arithmetic.

- Access pattern: The network builder loops over pairs of adjacent cells computing conductances via `G = k * A / L`. With uint8 maps, that becomes `k_grid = k_in_plane[material_map[z]]` — a single vectorized index operation that produces the full (ny, nx) conductivity plane, then arithmetic proceeds as before. No Python-level cell loops required.

- Why not structured arrays: NumPy structured arrays (C-struct layout) cause poor cache behavior when accessing a single field (e.g., `k_through`) across all cells — the processor must skip over the other fields between each load. Parallel float64 arrays are fully contiguous per property and cache-optimal for the field-at-a-time access pattern in network assembly. Numba's documentation documents structured arrays as ~10x slower than plain arrays for this reason; the same principle applies to plain NumPy vectorized code.

- Why not dict-per-cell: Python dict lookup in a hot loop over 400,000 cells is 100–1000x slower than numpy fancy indexing. This would make network assembly prohibitively slow.

- uint8 supports up to 256 distinct materials per project. Display module stacks have at most 10–20 materials. uint8 is sufficient and wastes no memory.

**Data model change:** `Layer` gains an optional `material_zones: list[MaterialZone]` field, where each `MaterialZone` specifies a rectangular region and a material key. When absent, the entire layer uses `layer.material` (backward-compatible). The network builder resolves the map once at assembly time by rasterizing zones onto the (ny, nx) grid.

---

## Sparse Matrix Assembly for 3D Networks

### Decision: Keep COO accumulation, convert to CSR once — no format change needed

The existing COO-to-CSR assembly pattern in `network_builder.py` is already correct for 3D. The only change is scale.

**What changes at 3D scale:**

The current 2.5D builder uses a uniform conductance per layer for lateral links (`g_x = k * t * dy/dx`, scalar). In 3D, this becomes a per-cell conductance since `k` varies cell to cell. The link generation loop must produce per-link conductance arrays instead of broadcasting a scalar. The vectorized structure of `_add_link_vectorized` already accepts `np.ndarray` conductances — it accepts either a scalar or an array via `np.full(len(n1), conductance)`. For 3D, pass the per-link conductance array directly.

**3D node indexing:**

```python
# 3D flat index: z_idx * (ny * nx) + iy * nx + ix
# where z_idx counts across ALL z-nodes (sum of nz[i] for layers 0..layer-1)
def node_3d(z_idx: int, iy: int, ix: int) -> int:
    return z_idx * (ny * nx) + iy * nx + ix
```

Z-refinement means a layer with `nz=4` contributes 4 z-slices of (ny, nx) nodes. Total nodes = sum(layer.nz for all layers) * ny * nx.

**Memory estimates — 100x100x40 node system (10 layers, nz=4 each):**

| Quantity | Value | Memory |
|----------|-------|--------|
| Total nodes (n) | 100 × 100 × 40 = 400,000 | — |
| Non-zeros in A (6-connectivity, banded) | ~7 per node × 400,000 = 2,800,000 | — |
| CSR data array (float64) | 2,800,000 × 8 bytes | 22 MB |
| CSR indices (int32) | 2,800,000 × 4 bytes | 11 MB |
| CSR indptr (int32) | 400,001 × 4 bytes | 1.6 MB |
| b, c, T vectors (float64) | 3 × 400,000 × 8 bytes | 9.6 MB |
| Material map (uint8) | 40 × 100 × 100 | 400 KB |
| **Total estimate** | | **~45 MB** |

This is well within typical desktop RAM (8 GB+). SuperLU fill-in during factorization can be 5–50x the non-zero count for banded systems — the worst case (50x fill) would be ~1.1 GB, which is still manageable. For a 3D structured grid with local connectivity, actual fill is typically 5–15x — expected factorization footprint is 110–330 MB.

**int32 index overflow risk:**

The 32-bit SuperLU overflow bug (GitHub issue #14984) triggers around n=46,679 with multiple RHS columns. With n=400,000 and a single RHS, the risk is lower but non-zero. SciPy 1.8.0 fixed the signed integer overflow; the project already requires SciPy 1.12+, so the fix is present. No action needed, but worth testing with the largest realistic mesh.

**Do not migrate to the new `csr_array` / `coo_array` API yet.** SciPy 1.12 supports both the legacy `csr_matrix` / `coo_matrix` classes and the new `_array` classes. `spsolve` works with both. Migrating to `_array` classes now introduces risk for zero benefit — the existing `csr_matrix` code is correct and tested. The new API becomes mandatory only when `spmatrix` classes are eventually deprecated (not scheduled as of SciPy 1.15).

---

## Z-Refinement: No New Libraries

Z-refinement is a model-level change, not a solver-level change. The math is identical to inter-layer conduction — `G = k * A / dz`, where `dz = layer.thickness / layer.nz`. Each z-node within a layer connects to the next z-node above it with the same formula. The top z-node of one layer connects to the bottom z-node of the next layer (with interface resistance). No new scipy capabilities required.

**`Layer` model addition:**

```python
@dataclass
class Layer:
    name: str
    material: str
    thickness: float
    interface_resistance_to_next: float = 0.0
    nz: int = 1                           # NEW: number of z-nodes through this layer
    material_zones: list[MaterialZone] = field(default_factory=list)  # NEW
```

When `nz=1` and `material_zones=[]`, behavior is identical to the current 2.5D model — backward compatible.

---

## 3D Visualization: Matplotlib Slice Views

### Decision: Multi-panel 2D imshow slices, not Axes3D

**Use 2D imshow panels for z-slice navigation. Do not use Axes3D for primary visualization.**

**Why not Axes3D:**

- `Axes3D.plot_surface` is a 3D wire-mesh renderer. It provides perspective projection of a colored surface, but does not produce true 2D heatmap quality — colors are shaded by the 3D illumination model, which distorts thermal gradient perception.
- The gallery-provided `imshow3d` helper (which uses `plot_surface` internally) is not a built-in function. It has documented limitations: no aspect ratio control, integer-position pixel edges, and — critically — incorrect rendering when multiple planes intersect. This makes multi-slice simultaneous display unreliable.
- `Axes3D` performance degrades on large arrays. A 100x100 surface has 10,000 polygons; matplotlib's software renderer (used in PySide6 embedded canvases) becomes sluggish above ~50,000 polygons.

**What to use instead:**

```python
# Pattern: two-panel layout for z-slice navigation
fig, (ax_map, ax_profile) = plt.subplots(1, 2)

# Left panel: 2D imshow of selected z-slice (existing pattern, unchanged)
im = ax_map.imshow(T[z_idx].reshape(ny, nx), origin='lower',
                   extent=[0, width, 0, height], cmap='hot', aspect='auto')

# Right panel: 1D profile through selected x or y cut (new)
ax_profile.plot(z_positions, T_column)  # temperature vs z at (ix, iy)
```

For layer-aware slicing, the GUI exposes a slider or combo box to select the z-index. The existing `FigureCanvasQTAgg` embedding supports this without new widgets — connect a `QSlider.valueChanged` signal to a function that calls `im.set_data(new_slice)` and `fig.canvas.draw_idle()`. This is the standard matplotlib interactive slice pattern; `set_data` + `draw_idle` avoids re-creating the figure on every frame.

**Optional: Axes3D for structural preview only**

`Axes3D` is appropriate for the existing Structure Preview dialog where a coarse schematic of layer boundaries (colored rectangles) is shown. This is not temperature data — it is a static annotation. Keep using Axes3D there. Do not use it for the temperature results dashboard.

---

## Supporting Libraries Summary

| Library | Version | Role | Change for 3D |
|---------|---------|------|---------------|
| numpy | 1.26+ (existing) | Per-cell material maps, vectorized conductance arrays | Use uint8 material_map + float64 lookup arrays |
| scipy.sparse | 1.12+ (existing) | COO assembly, CSR for spsolve | No format change; per-link conductance arrays replace scalars |
| scipy.sparse.linalg | 1.12+ (existing) | spsolve, splu for transient | No change; system is larger but API is identical |
| matplotlib | 3.8+ (existing) | Z-slice visualization | Use imshow + set_data pattern, not Axes3D for results |
| PySide6 | 6.7+ (existing) | GUI z-slice slider, zone editor | QSlider for z-index; QGraphicsScene for zone rectangle editor |

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| uint8 material index + float64 lookup arrays | Structured numpy array (dtype with fields) | Field access in structured arrays is non-contiguous; poor cache locality for property-at-a-time network assembly; ~10x slower in tight vectorized loops |
| uint8 material index + float64 lookup arrays | dict mapping (ix, iy) -> Material | Python dict lookup per cell in hot loop; 100-1000x slower than numpy fancy indexing over 400,000 cells |
| 2D imshow + QSlider for z-navigation | Axes3D plot_surface | Software renderer bottleneck at 100x100+ arrays; 3D shading distorts thermal color perception; imshow3d is a gallery copy-paste, not a maintained API |
| COO accumulate then tocsr() once | Building CSR directly with lil_matrix | lil_matrix row-insertion is fine for small systems but memory-inefficient for large ones; COO accumulate + tocsr() is the documented best practice for FEM-style assembly with duplicate entries |
| Keep csr_matrix (legacy API) | Migrate to csr_array (new API) | Zero benefit at this version range; migration introduces test risk; `spsolve` works with both; defer until spmatrix deprecation is announced |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| dict-per-cell material storage | Python dict overhead in vectorized assembly loop; ~100x slower than numpy index arrays for 400,000 cells | uint8 material_map + float64 lookup arrays |
| numpy structured arrays for material properties | Field access is non-contiguous in memory; cache thrash when extracting a single property (k_through) across all cells | Separate parallel float64 arrays per property |
| Axes3D for temperature results visualization | Software renderer slow on large grids; 3D shading distorts heatmap color; imshow3d intersecting plane limitation | 2D imshow panels with z-slice slider |
| `scipy.sparse.csr_array` (new API) right now | No benefit over existing csr_matrix at SciPy 1.12+; adds migration risk to tested code | Keep csr_matrix; migrate when spmatrix is deprecated |
| Any external thermal solver (FEM/FVM library) | Out-of-scope; project is an RC-network approximation tool; adding FEM would require compiled extensions incompatible with no-admin Windows constraint | Extend existing scipy spsolve pipeline |

---

## Stack Patterns by Scenario

**If nz=1 for all layers (2.5D project loaded):**
- Material map collapses to a single z-node per layer: `material_map[layer_idx, :, :] = material_id`
- Network builder produces identical output to the current 2.5D builder — backward compatibility confirmed

**If a layer has lateral material zones:**
- Rasterize `MaterialZone` rectangles onto the (ny, nx) grid at network build time — do not rasterize on every solve
- Store the rasterized map as `np.ndarray(uint8)` on the `ThermalNetwork` or as a scratch array in the builder

**If total node count exceeds 1,000,000 (e.g., 200x200x25):**
- Factorization fill-in may push RAM above 4 GB
- Switch from `spsolve` (direct) to `scipy.sparse.linalg.gmres` or `bicgstab` (iterative, Krylov) with an ILU preconditioner
- This is not expected for the target 100x100x40 case but document the threshold

**If z-slice navigation feels slow in GUI:**
- Use `im.set_data(new_slice)` + `canvas.draw_idle()` instead of `plt.imshow()` re-call — avoids axis recreation
- Pre-compute the full 3D temperature array into a `(n_z_total, ny, nx)` numpy array once after solve; slice from RAM on demand

---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| numpy | 1.26+ (existing) | uint8 fancy indexing, structured arrays — stable API |
| scipy | 1.12+ (existing) | spsolve int32 overflow fixed in 1.8.0 (already satisfied); COO+CSR assembly API stable |
| matplotlib | 3.8+ (existing) | imshow + set_data + draw_idle pattern stable since 2.x; Axes3D stable since 1.x |
| PySide6 | 6.7+ (existing) | QSlider, QGraphicsScene, FigureCanvasQTAgg — all stable |

---

## Installation

```bash
# No new packages required.
# All 3D solver capabilities are covered by the existing requirements.txt:
#   numpy>=1.26
#   scipy>=1.12
#   matplotlib>=3.8
#   PySide6>=6.7
#   pytest>=8.0
#   qt-material>=2.14
```

---

## Sources

- [NumPy Structured Arrays docs (v2.4)](https://numpy.org/doc/stable/user/basics.rec.html) — structured array cache locality limitations confirmed [HIGH confidence]
- [SciPy sparse docs (v1.17.0)](https://docs.scipy.org/doc/scipy/reference/sparse.html) — COO+CSR assembly recommendation, new array API status, csr_array [HIGH confidence]
- [SciPy spsolve docs (v1.17.0)](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.spsolve.html) — format conversion behavior, CSC preference for SuperLU [HIGH confidence]
- [GitHub scipy issue #14984](https://github.com/scipy/scipy/issues/14984) — int32 overflow in SuperLU; fixed in SciPy 1.8.0 [HIGH confidence]
- [GitHub scipy issue #18603](https://github.com/scipy/scipy/issues/18603) — int64 index downcast handling in spsolve [MEDIUM confidence]
- [Matplotlib mplot3d gallery (v3.10.8)](https://matplotlib.org/stable/gallery/mplot3d/index.html) — available 3D plot types, imshow3d limitations [HIGH confidence]
- [Matplotlib imshow3d example (v3.10.8)](https://matplotlib.org/stable/gallery/mplot3d/imshow3d.html) — confirmed imshow3d is a gallery copy-paste, not a built-in function; intersection rendering limitation documented [HIGH confidence]
- [DataCamp: Matplotlib 3D Volumetric Data](https://www.datacamp.com/tutorial/matplotlib-3d-volumetric-data) — slice navigation with set_data + draw_idle pattern [MEDIUM confidence]
- Memory estimates computed from first principles: n=400,000 nodes, ~7 non-zeros/node in 3D 6-connectivity structured grid, float64=8 bytes, int32=4 bytes [HIGH confidence — arithmetic]

---

*Stack research for: Python thermal simulation desktop app — v2.0 3D solver additions*
*Researched: 2026-03-16*
