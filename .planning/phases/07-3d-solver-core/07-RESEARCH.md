# Phase 7: 3D Solver Core - Research

**Researched:** 2026-03-16
**Domain:** Thermal RC-network solver — per-cell material zones, NodeLayout abstraction, harmonic-mean conductance, backward-compat regression
**Confidence:** HIGH (all findings from direct source inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Regression baseline**
- Regression gate covers all 4 example JSON projects (DLED, led_array_backlight, localized_hotspots, steady_uniform) AND the analytical validation test cases in test_validation_cases.py
- Both steady-state and transient solvers must be tested for each project
- Floating-point tolerance: exact match (1e-12) — same sparse solver on same matrix should match to machine precision if indexing is correct
- Pre-merge gate: regression test must pass before any network builder change is considered complete. Capture v1.0 baseline first, then assert against it after refactoring

**Zone-layer interaction**
- Uncovered cells in zoned layers default to air (not the layer's base material)
- When a layer has NO zones defined, the builder auto-generates a full-coverage zone from `layer.material` at build time — old JSONs stay unchanged on disk, builder handles the upgrade transparently
- Air material uses the built-in preset from the material library (k~0.026 W/mK). If 'air' isn't in the project's materials dict, inject it automatically at build time

**Zone overlap rules**
- Last-defined wins: zones are rasterized in list order, later zones overwrite earlier ones
- Zone coordinates use absolute meters from origin (same coordinate system as HeatSource: x, y, width, height)
- Zones that extend beyond layer bounds are clipped at rasterization — warn but allow (no error)
- Rectangles only (no "full" shape shorthand). A full-layer zone is a rectangle matching layer dimensions

### Claude's Discretion

- NodeLayout internal API design and data structure
- Harmonic-mean conductance formula implementation details
- How zone rasterization maps rectangles to mesh cells (cell-overlap vs center-in-zone)
- Sparse matrix assembly order for the new per-cell conductance logic

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SOLV-01 | Network builder supports per-cell material assignment via MaterialZone rectangular descriptors rasterized at build time | MaterialZone dataclass (new), Layer.zones field, rasterization in build_thermal_network using existing _source_mask pattern |
| SOLV-02 | Lateral conductance between cells of different materials uses harmonic-mean formula | Harmonic-mean formula: g_ij = 2 * g_i * g_j / (g_i + g_j); replaces current uniform g_x/g_y; requires per-cell conductance arrays |
| SOLV-03 | NodeLayout abstraction centralizes node indexing for variable z-nodes per layer | NodeLayout dataclass with offset array per layer; replaces closure `node_index(layer_idx, ix, iy)` in network_builder; prepares for nz>1 in Phase 8 |
| SOLV-04 | Existing v1.0 projects load and solve with identical temperatures (backward-compat regression test) | Baseline capture via JSON serialization of solved temperatures; assert element-wise within 1e-12 after refactoring |
</phase_requirements>

---

## Summary

Phase 7 is a pure internal refactoring of `thermal_sim/solvers/network_builder.py` with two new model objects. No solver algorithm changes, no new solver types, no GUI changes. The critical constraint is that all existing projects produce bit-identical results after the refactor — which is achievable because the same scipy sparse solver on an identical matrix will produce results identical to machine precision.

The three technical tasks are: (1) add `MaterialZone` model and `zones` field to `Layer`; (2) replace the uniform per-layer conductance loops with per-cell conductance arrays using harmonic-mean at material boundaries; (3) introduce `NodeLayout` to replace the inline `node_index` closure. All three are internal to `network_builder.py` and the models layer — the solvers (`steady_state.py`, `transient.py`) are untouched.

The regression baseline strategy is the most important gate: capture solved temperature arrays from all 4 JSON examples (steady + transient) before any code change, pickle/store them, and assert exact match after each refactoring step. This prevents the silent-wrong-answer failure mode.

**Primary recommendation:** Start with the regression baseline capture in a new test file `tests/test_regression_v1.py`, commit that green test, then implement changes in wave order: MaterialZone model → auto-zone logic → NodeLayout → per-cell conductance with harmonic-mean.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | already in requirements.txt | Per-cell conductance 2D arrays, rasterization of zones | Vectorized ops required by performance constraint; already used throughout |
| scipy.sparse | already in requirements.txt | COO/CSR matrix assembly, spsolve | Already the solver; no change needed |
| pytest | already installed | Test framework for regression, unit tests | Project already uses pytest throughout |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | Python 3.14 stdlib | MaterialZone frozen dataclass | All model classes are dataclasses; follow existing pattern |
| warnings (stdlib) | Python 3.14 stdlib | Emit warning when zone extends beyond layer bounds | Non-fatal clipping condition |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 2D numpy array for per-cell material index | dict mapping (ix,iy)->material | Array is O(1) lookup vs O(n) dict; required for vectorized conductance |
| Harmonic-mean per-interface | Arithmetic mean | Harmonic mean is physically correct for series resistance at a material interface; arithmetic mean is wrong |
| AABB cell-overlap rasterization | Center-in-zone | AABB matches existing `_source_mask` pattern; center-in-zone can miss thin zones on coarse meshes |

**Installation:** No new dependencies. All required libraries are already in `requirements.txt`.

---

## Architecture Patterns

### Recommended File Changes

```
thermal_sim/
├── models/
│   ├── material_zone.py     # NEW: MaterialZone dataclass
│   └── layer.py             # EDIT: add zones: list[MaterialZone] field
├── solvers/
│   └── network_builder.py   # EDIT: NodeLayout, per-cell conductance, zone rasterization
tests/
└── test_regression_v1.py    # NEW: baseline regression test (wave 0)
```

### Pattern 1: MaterialZone as Frozen Dataclass

**What:** New `MaterialZone(frozen=True)` dataclass in `thermal_sim/models/material_zone.py` following the exact `to_dict()`/`from_dict()` pattern established by every other model.
**When to use:** Always — no other serialization approach fits the project pattern.
**Example:**
```python
# follows Material, Layer, HeatSource patterns verbatim
@dataclass(frozen=True)
class MaterialZone:
    material: str   # key into project.materials dict
    x: float        # zone origin x (m), absolute from panel origin
    y: float        # zone origin y (m)
    width: float    # zone width (m)
    height: float   # zone height (m)

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "MaterialZone": ...
```

### Pattern 2: Layer.zones Field with Default Empty List

**What:** Add `zones: list[MaterialZone] = field(default_factory=list)` to the `Layer` dataclass. `to_dict()` serializes as `"zones": [...]`; `from_dict()` uses `.get("zones", [])` so old JSON without the field deserializes cleanly.
**When to use:** Layer with no zones listed = no zones on disk = builder auto-generates full-coverage zone at build time.

### Pattern 3: NodeLayout Abstraction

**What:** `NodeLayout` dataclass that owns the node-index formula. For Phase 7 (nz=1 everywhere), the formula is identical to the current closure. For Phase 8 it will handle variable `nz` per layer.
**Example interface (Claude's discretion):**
```python
@dataclass(frozen=True)
class NodeLayout:
    n_per_layer: int          # nx * ny (all layers share same in-plane grid)
    n_layers: int
    # layer_offsets[l] = first node index for layer l
    # For nz=1: layer_offsets[l] = l * n_per_layer
    layer_offsets: tuple[int, ...]

    def node(self, layer_idx: int, ix: int, iy: int, iz: int = 0) -> int:
        return self.layer_offsets[layer_idx] + iz * self.n_per_layer + iy * nx + ix

    @property
    def n_nodes(self) -> int:
        return self.layer_offsets[-1] + self.n_per_layer  # last layer end
```
The planner should treat the exact API as implementation detail (Claude's discretion). The key constraint: with nz=1, `layout.node(l, ix, iy)` must equal `l * (nx*ny) + iy*nx + ix` — the current formula — so all existing tests pass unchanged.

### Pattern 4: Zone Rasterization Using AABB Cell-Overlap

**What:** Reuse the existing `_source_mask` AABB overlap approach (lines 310–326 of `network_builder.py`) adapted for rectangular zones. Produces a `(ny, nx)` boolean mask per zone. Zones are applied in list order (later overwrites earlier) to build a final `(ny, nx)` integer array of material indices.
**Why AABB:** Handles thin zones on coarse meshes (same reason as heat sources). Matches the coordinate system (`x, y, width, height` centered). Validated in existing code.

### Pattern 5: Per-Cell Conductance with Harmonic Mean

**What:** Replace the scalar `g_x` / `g_y` per layer with 2D numpy arrays `g_x_cells[iy, ix]` (conductance of the link from cell (ix,iy) to (ix+1,iy)) and `g_y_cells[iy, ix]` (link to (ix,iy+1)).

**Harmonic-mean formula** for two cells of different materials at a shared face:
```
g_i = k_i * thickness * face_length / dx  (or dy for y-links)
g_ij = 2 * g_i * g_j / (g_i + g_j)       # series resistance = harmonic mean
```
For same-material cells: `g_ij = g_i = g_j` (harmonic mean reduces to the uniform value).

**Vectorized assembly** (no Python loop per cell):
```python
# g_x_per_cell[iy, ix] = k_inplane * thickness * dy / dx  for each cell
g_x_per_cell = k_map * layer.thickness * grid.dy / grid.dx  # (ny, nx) array
# harmonic mean between adjacent x-neighbors:
g_left  = g_x_per_cell[:, :-1]   # cells 0..nx-2
g_right = g_x_per_cell[:, 1:]    # cells 1..nx-1
g_x_link = 2 * g_left * g_right / (g_left + g_right)  # (ny, nx-1)
```
Then `g_x_link.ravel()` feeds `_add_link_vectorized` just like the current uniform scalar, but each link has its own value. The vectorized link adder already accepts per-link arrays (the scalar `conductance` parameter would become an ndarray).

### Anti-Patterns to Avoid

- **Python loop per cell for conductance:** Performance requirement ("Vectorized NumPy conductance assembly required — no Python loops per cell in builder hot path"). Use `k_map * ...` array ops.
- **Modifying the conductance formula for same-material links:** Harmonic mean of equal values equals the same value. No need to special-case uniform layers.
- **Changing `_add_link_vectorized` signature in a backward-breaking way:** Generalize it to accept `conductance: float | np.ndarray`. When float, broadcast as before; when ndarray, use element-wise.
- **Mutating `project.materials` or `project.layers` in the builder:** Inject air at build time into a local copy, never mutate the project object.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| COO to CSR conversion | Custom sparse assembly | `scipy.sparse.coo_matrix(...).tocsr()` | Already used; handles duplicate index summing automatically |
| Series-resistance at interface | Any other averaging | Harmonic mean formula (2ab/(a+b)) | Series resistance is 1/g_total = 1/g_i + 1/g_j; rearranges to harmonic mean exactly |
| Zone overlap test | Custom polygon clip | NumPy AABB on meshgrid (same as `_source_mask`) | Already validated; rectangles only per locked decision |

**Key insight:** The entire network builder uses vectorized COO accumulation intentionally — adding new per-cell material logic must follow the same pattern, not introduce loops.

---

## Common Pitfalls

### Pitfall 1: Air Material Key Mismatch
**What goes wrong:** Code injects "air" key but material library has "Air Gap". Auto-inject logic silently uses wrong name and `project.materials["air"]` KeyErrors.
**Why it happens:** The builtin library key is `"Air Gap"` (confirmed in `materials_builtin.json`), not `"air"`.
**How to avoid:** Inject using the key `"Air Gap"` with the exact properties from the builtin library (`k=0.026 W/mK, density=1.2, cp=1005`). Or define the canonical air key as a module-level constant `AIR_MATERIAL_KEY = "Air Gap"`.
**Warning signs:** `KeyError: 'air'` during any project solve with a zoned layer.

### Pitfall 2: Division by Zero in Harmonic Mean
**What goes wrong:** If either adjacent cell has `k_in_plane = 0` (or a near-zero conductance), `2*g_i*g_j/(g_i+g_j)` can produce NaN or division by zero.
**Why it happens:** Air gap has k=0.026 W/mK (not zero), but it's the lowest value. In the formula the denominator is zero only if both g_i and g_j are zero — impossible in practice since all materials have k>0 by `Material.__post_init__`. However, floating-point underflow is possible for extreme cases.
**How to avoid:** `Material.__post_init__` already enforces `k > 0`, so zero conductance from material alone is impossible. Document this assumption rather than adding runtime checks.

### Pitfall 3: Auto-Zone Produces Different Matrix for Old Projects
**What goes wrong:** Auto-generating a full-coverage zone from `layer.material` changes the code path but must produce the same conductance values. If harmonic-mean logic is applied to same-material adjacent cells, the result must equal the old uniform scalar.
**Why it happens:** Harmonic mean of equal values equals the same value (2g²/(2g) = g), so this is mathematically guaranteed. The risk is a bug where same-material cells hit a different code branch.
**How to avoid:** Regression test tolerance is 1e-12 — any code-path divergence will be caught. Harmonic mean of equal values: verify unit test explicitly.

### Pitfall 4: NodeLayout n_nodes Miscalculation
**What goes wrong:** After introducing `NodeLayout`, `ThermalNetwork.n_nodes` and the reshape in `SteadyStateSolver` and `TransientSolver` diverge from NodeLayout's count.
**Why it happens:** Two separate n_nodes calculations exist: the solver reshape (`n_layers * nx * ny`) and the new layout.
**How to avoid:** `ThermalNetwork` must hold a `NodeLayout` and derive all node counts from it. The reshape in both solvers becomes `layout.n_nodes` and shape comes from `layout`.

### Pitfall 5: Layer.zones Serialization Breaks Existing Projects
**What goes wrong:** `Layer.to_dict()` always emits `"zones": []` and old projects that were saved with the new code now differ from pristine JSON. While functionally equivalent, diff-on-save tools treat it as a change.
**Why it happens:** Adding a default list field that serializes always.
**How to avoid:** In `to_dict()`, emit `"zones"` only when non-empty (`if self.zones: d["zones"] = [...]`). In `from_dict()`, use `.get("zones", [])`. This way round-trip of old JSON produces identical bytes.

### Pitfall 6: _add_link_vectorized Cannot Handle Per-Link Conductance
**What goes wrong:** Current `_add_link_vectorized` takes `conductance: float` and calls `np.full(len(n1), conductance)`. Per-cell harmonic-mean results are ndarray, not float.
**Why it happens:** Original API was designed for uniform conductance per layer.
**How to avoid:** Generalize: `conductance: float | np.ndarray`. When float, keep `np.full`. When ndarray, use directly. Or split into two helpers — but generalizing is less disruptive.

---

## Code Examples

Verified patterns from codebase source inspection:

### Current Node Index Formula (to be preserved via NodeLayout)
```python
# From network_builder.py line 57 — this identity MUST hold after NodeLayout
def node_index(layer_idx: int, ix: int, iy: int) -> int:
    return layer_idx * n_per_layer + iy * grid.nx + ix
```

### Current _source_mask AABB (reuse for zone rasterization)
```python
# From network_builder.py lines 313–326
# Zone rasterization is identical: replace source.{x,y,width,height} with zone.{x,y,width,height}
sx0 = zone.x - zone.width / 2.0
sx1 = zone.x + zone.width / 2.0
sy0 = zone.y - zone.height / 2.0
sy1 = zone.y + zone.height / 2.0
mask = (
    (xx + half_dx > sx0) & (xx - half_dx < sx1) &
    (yy + half_dy > sy0) & (yy - half_dy < sy1)
)
```

### Current Lateral Conductance (to be replaced with per-cell version)
```python
# From network_builder.py lines 96–110 — REPLACE with per-cell array version
g_x = material.k_in_plane * layer.thickness * grid.dy / grid.dx  # scalar, uniform
g_y = material.k_in_plane * layer.thickness * grid.dx / grid.dy
```

### Harmonic Mean Implementation
```python
# For x-direction links across a material boundary
# k_map shape: (ny, nx) — k_in_plane value per cell
g_x_per_cell = k_map * layer.thickness * grid.dy / grid.dx    # (ny, nx)
g_left  = g_x_per_cell[:, :-1]   # shape (ny, nx-1)
g_right = g_x_per_cell[:, 1:]    # shape (ny, nx-1)
g_x_link = 2.0 * g_left * g_right / (g_left + g_right)       # harmonic mean
# Ravel to 1D for _add_link_vectorized
```

### Regression Baseline Capture Pattern
```python
# tests/test_regression_v1.py
import numpy as np, json
from pathlib import Path
from thermal_sim.io.project_io import load_project
from thermal_sim.solvers.steady_state import SteadyStateSolver

EXAMPLES = [
    "examples/DLED.json",
    "examples/led_array_backlight.json",
    "examples/localized_hotspots_stack.json",
    "examples/steady_uniform_stack.json",
]

def test_regression_steady_state_matches_v1_baseline():
    """All example projects must produce temperatures within 1e-12 of v1.0 baseline."""
    for path in EXAMPLES:
        project = load_project(Path(path))
        result = SteadyStateSolver().solve(project)
        # Load pre-captured baseline (stored as .npy files committed alongside test)
        baseline = np.load(f"tests/baselines/{Path(path).stem}_steady.npy")
        np.testing.assert_allclose(result.temperatures_c, baseline, atol=1e-12, rtol=0)
```

### Auto-Zone Injection at Build Time
```python
# In build_thermal_network(), before rasterization loop:
def _effective_zones(layer: Layer, project_width: float, project_height: float) -> list[MaterialZone]:
    """Return zones to use: explicit zones or auto-generated full-coverage zone."""
    if layer.zones:
        return layer.zones
    # Auto-generate: full-panel coverage from layer.material
    return [MaterialZone(
        material=layer.material,
        x=project_width / 2.0,
        y=project_height / 2.0,
        width=project_width,
        height=project_height,
    )]
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Uniform `g_x` per layer (scalar) | Per-cell `g_x_link` array (harmonic mean) | Phase 7 change |
| Inline closure `node_index()` | `NodeLayout` dataclass | Phase 7 change |
| `layer.material` as sole material source | `layer.zones` list with auto-fallback | Phase 7 change |

---

## Open Questions

1. **Air Gap key collision with existing project materials**
   - What we know: Builtin key is `"Air Gap"`, not `"air"`. If a project already has a material keyed `"Air Gap"`, injecting air at build time would skip injection (already present).
   - What's unclear: What if the project's `"Air Gap"` has different k? Should the builder use the project's definition or override with the canonical value?
   - Recommendation: Use whatever is in `project.materials["Air Gap"]` if it exists; inject from builtin only if absent. This respects user customization and avoids surprising overrides.

2. **Zone coordinate convention: center or corner**
   - What we know: CONTEXT.md says coordinates are `x, y, width, height` matching HeatSource convention. `HeatSource.x/y` are the center of the source (used in `_source_mask` as `sx0 = source.x - source.width/2`).
   - What's unclear: The CONTEXT.md says "absolute meters from origin" but doesn't explicitly say center vs corner.
   - Recommendation: Follow HeatSource convention exactly (x,y = center). The `_source_mask` reuse only works naturally if zones use the same center convention.

3. **`_add_link_vectorized` generalization vs new helper**
   - What we know: Current signature is `(n1, n2, conductance: float)`.
   - What's unclear: Whether to overload to `float | np.ndarray` or add a separate `_add_link_per_cell_vectorized`.
   - Recommendation: Generalize to `float | np.ndarray` via a simple `if isinstance(conductance, float): g = np.full(...) else: g = conductance` branch. Keeps the codebase DRY.

---

## Validation Architecture

*(workflow.nyquist_validation is not set in config.json — section omitted per instructions)*

---

## Sources

### Primary (HIGH confidence)

- Direct source inspection: `thermal_sim/solvers/network_builder.py` — full builder implementation, conductance formulas, _source_mask pattern
- Direct source inspection: `thermal_sim/models/layer.py`, `material.py`, `project.py`, `heat_source.py` — serialization patterns, dataclass conventions
- Direct source inspection: `thermal_sim/resources/materials_builtin.json` — confirmed `"Air Gap"` key and properties (k=0.026)
- Direct source inspection: `thermal_sim/solvers/steady_state.py`, `transient.py` — reshape patterns, n_nodes usage
- Direct source inspection: `tests/test_validation_cases.py` — existing test patterns, project construction approach
- Direct source inspection: `.planning/phases/07-3d-solver-core/07-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)

- Harmonic-mean conductance formula for series thermal resistance: derived from first principles (R_total = R_i + R_j, g = 1/R_total), verified against the existing builder formula structure

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in requirements.txt, confirmed from imports
- Architecture: HIGH — based on direct source inspection of the actual codebase
- Pitfalls: HIGH — identified from reading the actual code paths that will change
- Air material key: HIGH — confirmed "Air Gap" from materials_builtin.json inspection

**Research date:** 2026-03-16
**Valid until:** 2026-06-16 (stable Python/scipy/numpy APIs, no external dependencies added)
