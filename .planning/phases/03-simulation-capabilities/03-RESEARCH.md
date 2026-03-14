# Phase 3: Simulation Capabilities - Research

**Researched:** 2026-03-14
**Domain:** Python parametric sweep engine, piecewise-linear power profiles, material library I/O, PySide6 GUI dialogs, analytical thermal benchmarks
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sweep definition**
- Sweeps defined in a separate JSON file (`sweep.json`) with target parameter path and list of values
- CLI: `--sweep sweep.json` flag on existing CLI
- GUI: dedicated sweep dialog with parameter dropdown, value entry (comma-separated or min/max/step range), and mode selector (steady/transient)
- Single parameter per sweep only (no multi-parameter grid for v1)
- Sweepable parameters: layer thickness, material k_in_plane/k_through, boundary convection_h (top/bottom), heat source power_w
- Sweeps work with both steady-state and transient modes
- Progress shows "Run N of M"

**Power profiles (duty cycles)**
- Optional `power_profile` field on each HeatSource: list of `{time_s, power_w}` breakpoints (piecewise-linear)
- If `power_profile` is absent, constant `power_w` is used (backward compatible)
- Profile shorter than simulation time: loops from the beginning (good for periodic duty cycles)
- GUI: inline breakpoint table in Heat Sources tab with add/remove row buttons and a checkbox "[x] Time-varying"
- Live-updating profile preview plot below the breakpoint table — refreshes automatically as user edits values
- Transient solver interpolates between breakpoints at each timestep

**Material library**
- Built-in presets shipped as a bundled JSON file (`materials_builtin.json`) with common display/automotive materials (copper, aluminum, FR4, glass, adhesives, etc.)
- GUI: Materials tab shows a "Type" column distinguishing "Built-in" vs "User" materials
- Import/Export via toolbar buttons in the Materials tab — Import opens file picker for JSON, Export saves selected materials to JSON
- On import name conflict: auto-rename with suffix (e.g., "Copper" → "Copper_imported") and notify user
- Built-in materials are read-only; attempting to edit creates a user clone (e.g., "Copper" → "Copper (custom)")

**Sweep results display**
- Dedicated sweep results panel/tab appears after sweep completes
- Comparison table: parameter value vs T_max and T_avg per layer (final-timestep values for transient)
- Parameter-vs-metric plot: default Y-axis is T_max of topmost layer; user can switch layer/metric via dropdowns
- Export buttons in sweep results panel: CSV for table, PNG for plot

**Validation test expansion**
- Claude's Discretion: selection of 3+ new analytical benchmark cases beyond existing 1D two-layer resistance chain test

### Claude's Discretion
- Sweep JSON schema details and validation
- Specific built-in material property values (from engineering references)
- Power profile interpolation implementation in the transient solver
- Validation test case selection (which analytical benchmarks to implement)
- Sweep progress reporting mechanism (signals for GUI, stdout for CLI)
- Exact sweep dialog layout and widget choices

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SIM-01 | User can define parametric sweep (parameter + value list) and execute multiple solver runs | SweepConfig dataclass + SweepEngine that deep-copies DisplayProject per run; parameter path addressing pattern |
| SIM-02 | Sweep results displayed as comparison table and parameter-vs-metric plots | SweepResultsWidget with QTableWidget + matplotlib canvas; CSV/PNG export via existing patterns |
| SIM-03 | User can define time-varying power profiles (duty cycles) on heat sources | PowerProfile dataclass added to HeatSource; piecewise-linear interpolation with looping |
| SIM-04 | Transient solver interpolates power profile at each timestep | Separate power b_vector from boundary b_vector in network_builder; per-step scaling in TransientSolver |
| MAT-01 | User can import/export custom material libraries as JSON | JSON load/save using existing Material.to_dict()/from_dict() pattern; file picker via QFileDialog |
| MAT-02 | Material picker distinguishes built-in presets from user-defined materials | MaterialSource enum ("builtin"/"user"); "Type" column in QTableWidget; built-in rows read-only |
| MAT-03 | Additional analytical validation test cases with comparison plots | Three new test cases in test_validation_cases.py; matplotlib comparison plots via existing plotting module |
</phase_requirements>

---

## Summary

Phase 3 builds three independent capability tracks: (1) parametric sweep engine that iterates the existing solvers over a parameter value list, (2) time-varying heat source power profiles with piecewise-linear interpolation in the transient solver, and (3) a formal material library system with built-in presets and user import/export. The entire stack depends on Python + NumPy + SciPy + PySide6 + matplotlib — all already present in `requirements.txt`. No new backend libraries are needed.

The sweep engine is the highest-risk item. The CONTEXT.md note about ~350 MB for a 10-run transient sweep is real: each run allocates `[n_samples, n_layers, ny, nx]` float64 arrays. The engine must stream results out (collect summary stats per run, discard the full temperature field after extracting T_max/T_avg per layer) rather than accumulating all TransientResult objects in memory. For power profiles, the key insight is that the network builder currently bakes the entire `b_vector` (boundary + heat sources) in one shot; to support per-timestep power, the heat-source contribution must be extracted as a separately-scalable vector.

The material library requires a careful distinction between "identity" (name string used as dict key in `DisplayProject.materials`) and "source" (builtin vs. user). The frozen `Material` dataclass needs no changes; only the management layer (library loader and GUI widget) needs to track provenance. Validation benchmarks should pick analytically tractable cases that exercise different physics paths: 1D transient RC decay (already exists as a solver test), multi-layer uniform power, finned/side-cooled geometry, and a 2-node with interface resistance are the cleanest choices.

**Primary recommendation:** Build bottom-up — SweepEngine + PowerProfile first (pure Python, fully testable without GUI), then wire GUI dialogs on top using the established `_SimWorker`/`Signal` pattern already in `SimulationController`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14+ | Runtime | Project requirement (CLAUDE.md) |
| numpy | already installed | Array math, `np.interp` for piecewise-linear interpolation | Already in requirements.txt; `np.interp` handles the power-profile case natively |
| scipy.sparse | already installed | Sparse linear algebra for solver | Already in requirements.txt; transient solver uses `splu` |
| PySide6 | already installed | Qt desktop GUI | Project standard (CLAUDE.md); all existing UI uses PySide6 |
| matplotlib | already installed | Sweep results plot, profile preview, validation comparison plots | Already in requirements.txt; `FigureCanvasQTAgg` already used in UI |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | sweep.json and materials_builtin.json load/save | All project I/O uses raw json.load/json.dump |
| copy (stdlib) | stdlib | `copy.deepcopy(project)` for sweep engine | Need independent modified project copies per sweep run |
| dataclasses (stdlib) | stdlib | SweepConfig, PowerProfile dataclasses | Project convention; every model is a dataclass |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `np.interp` for profile | Hand-coded linear interpolation | np.interp is vectorized, handles edge cases (extrapolation clips to endpoint), tested — use it |
| `copy.deepcopy` for sweep | Manual field-by-field copy | deepcopy is simpler and correct; for this project's project sizes (<<1 MB JSON) no perf concern |
| JSON schema validation | jsonschema library | Not worth adding a dependency; simple dict key checks are sufficient given sweep.json is user-visible |

**Installation:**
No new packages needed. All dependencies already in requirements.txt.

---

## Architecture Patterns

### Recommended Project Structure

New files to create:

```
thermal_sim/
├── core/
│   ├── material_library.py      # EXISTING — extend with load_builtin_library()
│   └── sweep_engine.py          # NEW — SweepConfig dataclass + SweepEngine class
├── models/
│   ├── heat_source.py           # MODIFY — add PowerProfile dataclass + field to HeatSource
│   └── sweep_result.py          # NEW — SweepResult dataclass
├── solvers/
│   ├── network_builder.py       # MODIFY — separate heat-source b_vector from boundary b_vector
│   └── transient.py             # MODIFY — per-timestep power scaling from profiles
├── ui/
│   ├── sweep_dialog.py          # NEW — parameter entry QDialog
│   └── sweep_results_widget.py  # NEW — table + plot QWidget
└── resources/
    └── materials_builtin.json   # NEW — bundled material presets (replaces/augments material_library.py)

tests/
└── test_validation_cases.py     # EXTEND — 3+ new analytical benchmark test functions
```

### Pattern 1: SweepConfig Dataclass with Parameter Path Addressing

**What:** A dataclass that holds the parameter to vary and a list of values. The "path" is a dot-separated string like `"layers[0].thickness"` or `"heat_sources[0].power_w"` or `"boundaries.top.convection_h"`.

**When to use:** When the sweep engine needs to mutate a specific field on a project copy without knowing the type at compile time.

**Example:**
```python
# thermal_sim/core/sweep_engine.py
from __future__ import annotations
import copy
import dataclasses
from dataclasses import dataclass
from typing import Any

@dataclass
class SweepConfig:
    """Sweep definition loaded from sweep.json."""
    parameter: str           # e.g. "layers[0].thickness"
    values: list[float]
    mode: str = "steady"     # "steady" | "transient"

    def to_dict(self) -> dict:
        return {"parameter": self.parameter, "values": self.values, "mode": self.mode}

    @classmethod
    def from_dict(cls, data: dict) -> "SweepConfig":
        return cls(
            parameter=str(data["parameter"]),
            values=[float(v) for v in data["values"]],
            mode=str(data.get("mode", "steady")),
        )
```

### Pattern 2: Sweep Engine with Progress Callback

**What:** A pure-function engine class that iterates project copies, calls the appropriate solver, extracts summary stats, and emits progress via callback (not signals — keeps it GUI-agnostic).

**When to use:** Sweep engine is callable from CLI (stdout) and from GUI (Qt signal) via the same callback interface.

**Example:**
```python
# thermal_sim/core/sweep_engine.py
from __future__ import annotations
import copy
from collections.abc import Callable
from dataclasses import dataclass

@dataclass
class SweepRunResult:
    """Summary stats for one sweep point."""
    parameter_value: float
    layer_stats: list[dict]   # [{name, t_max_c, t_avg_c}, ...]

@dataclass
class SweepResult:
    """Full sweep output."""
    config: SweepConfig
    runs: list[SweepRunResult]

class SweepEngine:
    def run(
        self,
        base_project: DisplayProject,
        config: SweepConfig,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> SweepResult:
        runs = []
        for i, value in enumerate(config.values):
            project_copy = copy.deepcopy(base_project)
            _apply_parameter(project_copy, config.parameter, value)
            # solve and extract summary stats only — discard full temperature array
            result = _solve(project_copy, config.mode)
            runs.append(_extract_stats(value, result, project_copy))
            if on_progress:
                on_progress(i + 1, len(config.values))
        return SweepResult(config=config, runs=runs)
```

### Pattern 3: Parameter Path Apply Function

**What:** A function that takes a project copy and applies a scalar value at a dot-path address. Supports `layers[N].field`, `heat_sources[N].field`, `boundaries.top.field`, `materials.NAME.field` patterns.

**When to use:** Central to the sweep engine. Must be robust to bad paths (raise `ValueError` with a clear message).

**Example approach (not using `eval` — explicit index parsing):**
```python
def _apply_parameter(project: DisplayProject, path: str, value: float) -> None:
    """Mutate project in-place at the given dot-path."""
    # e.g. "layers[0].thickness" -> obj=project.layers[0], field="thickness"
    # e.g. "boundaries.top.convection_h" -> obj=project.boundaries.top, field="convection_h"
    # e.g. "heat_sources[0].power_w" -> obj=project.heat_sources[0], field="power_w"
    # Parse with regex: re.match(r'(\w+)(?:\[(\d+)\])?(?:\.(.+))?', segment)
    # Walk the path, use setattr for final field.
    # Material fields: project.materials is a dict[str, Material].
    # Material is frozen=True — must replace the dict entry with a new Material.
```

**Key constraint:** `Material` is `frozen=True`. To sweep a material property, the sweep engine must replace the material in `project.materials[name]` with a new `dataclasses.replace(mat, field=value)`.

### Pattern 4: PowerProfile Dataclass on HeatSource

**What:** An optional list of `{time_s, power_w}` breakpoints stored on `HeatSource`. Absent means constant power. The transient solver calls `np.interp` with looping to get the power at time `t`.

**Example:**
```python
# In models/heat_source.py
@dataclass
class PowerBreakpoint:
    time_s: float
    power_w: float

    def to_dict(self) -> dict:
        return {"time_s": self.time_s, "power_w": self.power_w}

    @classmethod
    def from_dict(cls, data: dict) -> "PowerBreakpoint":
        return cls(time_s=float(data["time_s"]), power_w=float(data["power_w"]))

# Added field on HeatSource:
power_profile: list[PowerBreakpoint] | None = None

def power_at_time(self, t: float) -> float:
    """Return power (W) at time t, using profile if present (looping)."""
    if self.power_profile is None or len(self.power_profile) == 0:
        return self.power_w
    profile_end = self.power_profile[-1].time_s
    t_wrapped = t % profile_end if profile_end > 0 else 0.0
    times = [bp.time_s for bp in self.power_profile]
    powers = [bp.power_w for bp in self.power_profile]
    return float(np.interp(t_wrapped, times, powers))
```

### Pattern 5: Separating Heat-Source b_vector in network_builder

**What:** The current `build_thermal_network` returns a single `b_vector` that combines boundary contributions and heat-source contributions. To support per-timestep power scaling, these must be separate.

**The change:**
```python
# network_builder.py
@dataclass(frozen=True)
class ThermalNetwork:
    a_matrix: csr_matrix
    b_boundary: np.ndarray   # boundary terms only (g * T_amb per surface node)
    b_sources: np.ndarray    # heat source contributions at nominal power_w
    c_vector: np.ndarray
    grid: Grid2D
    n_layers: int
    layer_names: list[str]

    @property
    def b_vector(self) -> np.ndarray:
        """Backward-compatible property — sum of both vectors."""
        return self.b_boundary + self.b_sources
```

This preserves backward compatibility for the steady-state solver (uses `b_vector` unchanged). The transient solver can then rebuild RHS per timestep:

```python
# In TransientSolver.solve() time-step loop:
t_current = step * dt
b_power = _build_power_vector(project, network, t_current)  # scales b_sources
rhs = c_over_dt * t_vec + network.b_boundary + b_power
```

### Pattern 6: Sweep Worker in GUI (QThread)

**What:** The sweep runs N solver calls — each may take seconds for transient. Must run off the main thread using the same `_SimWorker`/`QThread` pattern already in `SimulationController`.

**Approach:** Create a `_SweepWorker(QObject)` analogous to `_SimWorker`. Emit `progress(int run_n, int total)` and `finished(SweepResult)`. Wire into `SimulationController` or a new `SweepController`.

**Progress message format:** `"Run {n} of {M}"` (matches user story success criterion 1).

### Pattern 7: Material Source Tracking

**What:** Materials loaded from `materials_builtin.json` are "builtin"; materials in the project or imported by the user are "user". This is a display concern only — `Material` dataclass is unchanged.

**Approach:** The GUI maintains a parallel `dict[str, str]` mapping material name → source label `"Built-in"` or `"User"`. Built-in rows: `QTableWidgetItem.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)` (not `Qt.ItemIsEditable`). Editing a built-in triggers a clone with name `"{name} (custom)"`.

### Anti-Patterns to Avoid

- **Storing full TransientResult per sweep run:** Each 10-layer, 30×20 mesh transient at 120 s / 1 s output = 120 samples × 10 × 20 × 30 × 8 bytes = ~5.8 MB per run. 10 runs = 58 MB — manageable but pointless. Extract T_max/T_avg per layer immediately and discard.
- **Using `eval()` for parameter path:** Security risk and fragile. Use explicit path parsing (regex + getattr/setattr/index).
- **Modifying base project directly in sweep loop:** Always `deepcopy` before `_apply_parameter`. Otherwise run N corrupts run N+1.
- **Rebuilding full LHS (splu) per timestep for power profiles:** The LHS `(C/dt + A)` is time-invariant — only the RHS changes. The existing `splu` factorization is computed once; only `b_power` changes per step.
- **Making Material mutable to support sweep:** Material is `frozen=True` by design. Use `dataclasses.replace(mat, field=value)` + dict reassignment.
- **Emitting Qt signals from sweep engine:** Keep sweep engine pure Python. GUI layer wraps it in a `QObject` worker.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Piecewise-linear interpolation | Custom loop | `np.interp(t, times, powers)` | Handles edge cases (out-of-range clips to endpoints), vectorized, already available |
| Deep copy of project for sweep | Manual field copy | `copy.deepcopy(project)` | Project has nested dataclasses, lists, dicts — manual copy will miss fields |
| CSV export for sweep results | Custom writer | Extend `io/csv_export.py` pattern | Consistent with existing CSV export; no new deps needed |
| Material JSON serialization | Custom schema | `Material.to_dict()` / `Material.from_dict()` | Already implemented and tested |
| Qt file picker dialog | Custom widget | `QFileDialog.getOpenFileName` / `getSaveFileName` | Platform-native, already used in the project for PDF export |
| Sparse matrix construction | Dense matrix | `scipy.sparse.csr_matrix` | Already in use; don't regress to dense for any new b_vector work |

**Key insight:** The sweep engine, power profiles, and material library all build on patterns already established in Phases 1–2. The main work is plumbing connections, not solving novel engineering problems.

---

## Common Pitfalls

### Pitfall 1: Material Frozen=True Sweep Crash

**What goes wrong:** `setattr(mat, 'k_in_plane', value)` raises `FrozenInstanceError` at runtime.
**Why it happens:** `Material` is `@dataclass(frozen=True)` — this is correct design (materials are value objects), but the sweep engine must account for it.
**How to avoid:** In `_apply_parameter`, when the path targets a material property, do:
```python
old_mat = project.materials[mat_name]
project.materials[mat_name] = dataclasses.replace(old_mat, **{field_name: value})
```
**Warning signs:** `FrozenInstanceError` in sweep run logs.

### Pitfall 2: Looping Power Profile Off-by-One

**What goes wrong:** Profile loops at exactly the wrong time, producing a spike or discontinuity at the loop boundary.
**Why it happens:** If profile breakpoints are `[(0, 10), (1, 0)]` and total time is 2 s, the loop must produce the same pattern for `[1..2]`. Using `t % period` where `period = last_breakpoint.time_s` is correct only if the profile starts at `t=0`.
**How to avoid:** Enforce that first breakpoint must be `time_s=0`. Validate in `__post_init__` or at load time. Use `t_wrapped = t % profile_duration` where `profile_duration = last_breakpoint.time_s`.
**Warning signs:** Validation test for periodic heating shows unexpected temperature spikes at multiples of profile duration.

### Pitfall 3: Sweep Progress Deadlock in GUI

**What goes wrong:** The sweep worker emits progress signals faster than the GUI processes them, causing event loop backup or apparent freeze.
**Why it happens:** Each sweep run is one progress tick — at most tens of ticks for v1 (single parameter, list of values). This is NOT the issue (unlike the transient sub-step progress which was capped at 100). But calling `on_progress` from within the transient solver's inner loop (step-level) during a sweep transient run would be.
**How to avoid:** In sweep mode, the transient `on_progress` callback is suppressed (or ignored); only the sweep-level progress (`"Run N of M"`) is reported.
**Warning signs:** GUI freezes during sweep of transient runs.

### Pitfall 4: Name Collision in Material Import

**What goes wrong:** User imports a JSON that has "Copper" — a built-in. The built-in gets silently overwritten.
**Why it happens:** `dict.update()` replaces existing keys.
**How to avoid:** Check each incoming material name against the current dict. If collision: rename incoming to `"{name}_imported"` and notify via `QMessageBox.information`. This is the locked decision.
**Warning signs:** Built-in materials disappear or change values after import.

### Pitfall 5: Sweep JSON Schema Drift

**What goes wrong:** User provides a sweep.json with wrong field names (e.g., `"param"` instead of `"parameter"`) and gets a `KeyError` with no guidance.
**Why it happens:** No schema validation.
**How to avoid:** Validate required keys in `SweepConfig.from_dict()` with explicit `KeyError` catch + `ValueError` re-raise with a human-readable message explaining the expected format.
**Warning signs:** Cryptic KeyErrors in CLI sweep runs.

### Pitfall 6: b_vector Split Breaks Steady-State Solver

**What goes wrong:** After splitting `b_vector` into `b_boundary + b_sources`, the steady-state solver uses the wrong vector or the network builder changes its contract.
**Why it happens:** `SteadyStateSolver` and tests both use `network.b_vector`.
**How to avoid:** Add a `b_vector` property on `ThermalNetwork` that returns `b_boundary + b_sources`. This is a pure addition — no callers break.
**Warning signs:** Existing steady-state validation test fails after network_builder refactor.

### Pitfall 7: Sweep Memory with Many Transient Runs

**What goes wrong:** 10-run transient sweep OOMs or becomes very slow.
**Why it happens:** If `TransientResult` objects are accumulated in a list, each with a large array.
**How to avoid:** In sweep engine, immediately extract `layer_stats` from each result and discard the result object. The `SweepRunResult` stores only floats (T_max/T_avg per layer), not arrays.
**Warning signs:** Memory growth visible via tracemalloc; the CONTEXT.md notes this as a known concern.

---

## Code Examples

Verified patterns from the existing codebase (all HIGH confidence — directly read from source):

### Existing transient solver time-step loop (the loop to modify for power profiles)
```python
# thermal_sim/solvers/transient.py lines 87-101 (current)
for step in range(1, n_steps + 1):
    np.multiply(c_over_dt, t_vec, out=rhs)
    rhs += network.b_vector   # <-- change to: b_boundary + b_power_at_time(step * dt)
    t_vec = lu.solve(rhs)
```

### HeatSource.to_dict / from_dict pattern to extend for power_profile
```python
# Current HeatSource.to_dict() — add power_profile key:
def to_dict(self) -> dict:
    d = {
        "name": self.name,
        "layer": self.layer,
        "power_w": self.power_w,
        "shape": self.shape,
        "x": self.x,
        "y": self.y,
        "width": self.width,
        "height": self.height,
        "radius": self.radius,
        "power_profile": [bp.to_dict() for bp in self.power_profile] if self.power_profile else None,
    }
    return d
```

### QDialog pattern for Sweep Dialog (matches existing PySide6 style)
```python
# Follows the same style as StructurePreviewDialog in thermal_sim/ui/structure_preview.py
class SweepDialog(QDialog):
    def __init__(self, project: DisplayProject, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parametric Sweep")
        self._config: SweepConfig | None = None
        layout = QVBoxLayout(self)
        # parameter dropdown populated from SWEEPABLE_PARAMETERS list
        # values line edit: "0.001,0.002,0.003" or "0.001:0.01:10" (min:step:max)
        # mode radio buttons: steady / transient
        # OK / Cancel buttons
```

### np.interp for piecewise-linear power at time t
```python
# Source: numpy docs (stdlib)
import numpy as np

def power_at_time(profile: list, t: float) -> float:
    period = profile[-1]["time_s"]
    t_wrapped = t % period if period > 0 else 0.0
    times = [bp["time_s"] for bp in profile]
    powers = [bp["power_w"] for bp in profile]
    return float(np.interp(t_wrapped, times, powers))
```

### Material.from_dict / to_dict (already exists — use directly for material library JSON)
```python
# thermal_sim/models/material.py (existing)
# Load library:
with open("materials_builtin.json") as f:
    raw = json.load(f)  # dict[str, dict]
builtin = {name: Material.from_dict(data) for name, data in raw.items()}

# Save user materials:
with open(path, "w") as f:
    json.dump({name: mat.to_dict() for name, mat in user_mats.items()}, f, indent=2)
```

### dataclasses.replace for frozen Material in sweep
```python
import dataclasses
old_mat = project.materials["Copper"]
project.materials["Copper"] = dataclasses.replace(old_mat, k_in_plane=new_value)
```

---

## Analytical Validation Benchmarks (MAT-03)

Three new test cases recommended, all exercising different physics paths. All are analytically tractable with a 1×1 mesh (single node per layer) to eliminate discretization error.

### Benchmark A: 1D Three-Layer Resistance Chain (Steady)

Extend the existing two-layer test to three layers. Validates interface resistance between layers 1-2 and 2-3.

**Hand calc:** 3×3 nodal system with g_ij conductances. Solve with Cramer's rule or substitution.

**New physics tested:** Three-layer conductance chain with two interface resistances.

### Benchmark B: Single-Node RC Transient with Time-Varying Power (Transient)

A one-node network driven by a square-wave power profile. At each half-period the node heats/cools exponentially. Compare against analytical piecewise-exponential solution.

**Hand calc:** For a 1-node RC with time constant `tau = C/G`:
- Heating phase (0 to T_on): `T(t) = T_ss_hot + (T0 - T_ss_hot) * exp(-t/tau)`
- Cooling phase (T_on to T_period): `T(t) = T_ss_cold + (T_on_end - T_ss_cold) * exp(-(t-T_on)/tau)`

**New physics tested:** `power_at_time()` looping + `np.interp` correctness; transient solver per-timestep power scaling (SIM-04).

### Benchmark C: Two-Node Side-Cooling (Steady)

Two nodes laterally connected + each cooled to ambient via a surface conductance on its lateral face. Power injected in node 1 only. Two distinct convection_h values (one per node). Tests lateral heat spreading with asymmetric cooling.

**Hand calc:** 2-node system:
- `(G_lat + G_cool1) * T1 - G_lat * T2 = Q1 + G_cool1 * T_amb`
- `-G_lat * T1 + (G_lat + G_cool2) * T2 = G_cool2 * T_amb`

**New physics tested:** Lateral conductance (k_in_plane path in network_builder); multi-node heat sharing.

### Benchmark D: Transient Convergence to Steady State (Power Profile Edge Case)

A constant power profile (single-breakpoint or two-point with same power) must behave identically to `power_profile=None`. Validates backward compatibility of the power profile implementation.

These four benchmarks (A + B + C + D) satisfy the "at least three" requirement with meaningful coverage.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `build_thermal_network` returns single `b_vector` | Split into `b_boundary` + `b_sources` with `b_vector` property | Phase 3 | Enables per-timestep power scaling without breaking steady solver |
| `default_materials()` function in code | `materials_builtin.json` bundled file + in-code fallback | Phase 3 | User-extensible; distinguishable from user materials |
| `power_w` constant on HeatSource | `power_w` + optional `power_profile` list | Phase 3 | Backward compatible; profile absent = constant behavior |

---

## Open Questions

1. **Where to store materials_builtin.json for PyInstaller (Phase 5)**
   - What we know: Phase 5 will use PyInstaller `--onedir`. The project already notes a `DIST-03` requirement for a centralized resource path helper.
   - What's unclear: The bundled JSON must be located via `importlib.resources` or a `Path(__file__)` anchor — not `Path.cwd()`.
   - Recommendation: Use `importlib.resources` (Python 3.9+) to locate `thermal_sim/resources/materials_builtin.json`. Add `thermal_sim/resources/__init__.py`. This future-proofs for Phase 5 distribution without adding work now.

2. **Sweep parameter path syntax for material properties**
   - What we know: `DisplayProject.materials` is `dict[str, Material]`. Material is frozen. Paths like `"materials.Copper.k_in_plane"` require: (a) split on `.`, (b) handle dict lookup by name string, (c) `dataclasses.replace`.
   - What's unclear: Whether users will want to sweep an unnamed/indexed material or always a named one.
   - Recommendation: Support named materials only: `"materials.{name}.{field}"`. Document this in the sweep.json schema comment.

3. **Sweep results widget location in main_window.py**
   - What we know: Results tabs already exist (`_build_result_tabs()`). The sweep results should appear after sweep completes — decision says "dedicated sweep results panel/tab appears after sweep completes."
   - What's unclear: Whether this is a new permanent tab (hidden until first sweep) or a dynamically added/removed tab.
   - Recommendation: Add a permanent "Sweep Results" tab that shows a placeholder message until a sweep is run. Simpler to implement than dynamic tab add/remove (which has PySide6 index management edge cases).

---

## Sources

### Primary (HIGH confidence)
- `thermal_sim/solvers/transient.py` — full time-step loop, LHS factorization, cancellation pattern
- `thermal_sim/solvers/network_builder.py` — `build_thermal_network`, `_apply_heat_sources`, `ThermalNetwork` dataclass
- `thermal_sim/models/heat_source.py` — `HeatSource` dataclass, `to_dict`/`from_dict`, `__post_init__` validation
- `thermal_sim/models/material.py` — `Material` frozen dataclass, serialization
- `thermal_sim/models/project.py` — `DisplayProject`, `expanded_heat_sources`, all serialization
- `thermal_sim/core/material_library.py` — `default_materials()` — current built-in list
- `thermal_sim/ui/simulation_controller.py` — `_SimWorker`, `SimulationController` QThread pattern
- `thermal_sim/ui/main_window.py` — editor tab structure, toolbar pattern, result tabs
- `thermal_sim/app/cli.py` — `build_parser()`, `argparse` patterns, `main()`
- `tests/test_validation_cases.py` — existing benchmark pattern to extend
- `tests/test_transient_solver.py` — RC decay and convergence tests (Benchmark B reuses this structure)

### Secondary (MEDIUM confidence)
- numpy.interp documentation — `np.interp` clips out-of-range values to endpoints; period looping via `t % period` is the standard approach for repeating waveforms
- Python `dataclasses.replace()` documentation — correct approach for replacing fields on frozen dataclasses
- PySide6 `QDialog` and `QTableWidget` documentation — standard patterns for sweep dialog and material type column

### Tertiary (LOW confidence)
- Memory estimate of ~350 MB for 10-run transient sweep (from STATE.md blockers note) — directionally correct; exact value depends on mesh size and duration. Use `tracemalloc` in early Phase 3 wave to validate.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already present, verified in requirements.txt and existing source code
- Architecture: HIGH — patterns derived directly from existing codebase (no external speculation)
- Pitfalls: HIGH — derived from actual code constraints (frozen dataclass, single b_vector, deepcopy requirement)
- Validation benchmarks: HIGH — analytically tractable physics, same pattern as existing test_validation_cases.py

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (dependencies are stable; no fast-moving external libs)
