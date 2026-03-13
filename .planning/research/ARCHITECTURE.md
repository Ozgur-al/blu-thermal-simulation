# Architecture Research

**Domain:** Desktop thermal simulation engineering tool (Python, PySide6)
**Researched:** 2026-03-14
**Confidence:** HIGH — based on direct codebase inspection, official Qt docs, and verified library patterns

---

## Standard Architecture

### System Overview

This is an extension of the existing Phase 3 layered architecture. The new components for Phase 4 plug into the pipeline at well-defined seams without requiring structural surgery.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Entry Points (app/)                            │
│   ┌────────────────────┐          ┌──────────────────────────────────┐  │
│   │   cli.py           │          │   gui.py → MainWindow            │  │
│   │   (batch / sweep)  │          │   (interactive + sweep dialog)   │  │
│   └────────┬───────────┘          └───────────────┬──────────────────┘  │
└────────────┼──────────────────────────────────────┼────────────────────┘
             │                                      │
┌────────────▼──────────────────────────────────────▼────────────────────┐
│                     Sweep Engine (NEW: sweeps/)                         │
│   ┌──────────────────────┐     ┌───────────────────────────────────┐   │
│   │  SweepSpec (model)   │     │  SweepRunner (QRunnable worker)   │   │
│   │  SweepResult         │     │  Signals: progress / done / error │   │
│   └──────────────────────┘     └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
             │                           │
┌────────────▼───────────────────────────▼────────────────────────────────┐
│                   Existing Solver Pipeline (unchanged)                   │
│   models/ → network_builder → steady_state / transient → postprocess    │
└──────────────────────────────────────────────────────────────────────────┘
             │                           │
┌────────────▼───────────────────────────▼────────────────────────────────┐
│                      Output Layer (io/ + NEW report/)                   │
│   ┌───────────────────┐    ┌──────────────────┐    ┌─────────────────┐  │
│   │   csv_export.py   │    │  project_io.py   │    │ report_gen.py   │  │
│   │ (existing)        │    │  (existing)      │    │ (NEW: ReportLab)│  │
│   └───────────────────┘    └──────────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

The **key architectural insight**: all four Phase 4 features share one structural pattern — they are consumers of `DisplayProject` and emitters of result data. They never touch the solver internals. The solver pipeline remains completely unchanged.

---

## Component Boundaries

### New Components Required

| Component | Module Path | Responsibility | Communicates With |
|-----------|-------------|---------------|-------------------|
| `SweepSpec` | `thermal_sim/sweeps/spec.py` | Defines which parameter to vary and over what range (dataclass) | `DisplayProject` (reads), `SweepRunner` (input) |
| `SweepRunner` | `thermal_sim/sweeps/runner.py` | Executes N solver calls sequentially; emits per-step progress signals | `SteadyStateSolver` / `TransientSolver`, `SweepSpec`, Qt signals |
| `SweepResult` | `thermal_sim/sweeps/spec.py` | Holds all N result dataclasses and the parameter values used | `SweepResultsPanel` (GUI display), `report_gen` |
| `PowerProfile` | `thermal_sim/models/power_profile.py` | Piecewise linear or stepped time-series power function for a named heat source | `TransientSolver` (consulted per time step), project I/O |
| `ReportGenerator` | `thermal_sim/io/report_gen.py` | Assembles PDF using ReportLab Platypus; embeds matplotlib figures via BytesIO | `SteadyStateResult` / `TransientResult`, `SweepResult`, `visualization/` |
| `SweepDialog` | `thermal_sim/ui/sweep_dialog.py` | QDialog for configuring and launching a sweep; shows live progress bar | `SweepRunner` (via QThread + signals), `MainWindow` |
| `SweepResultsPanel` | `thermal_sim/ui/sweep_results.py` | Results panel comparing N sweep runs; comparison table + overlaid plots | `SweepResult`, matplotlib canvas |
| `MaterialLibraryDialog` | `thermal_sim/ui/material_library_dialog.py` | Browse, import, export materials from JSON library files | `material_library.py`, project model |

### Unchanged Components (boundaries respected)

| Component | Why Unchanged |
|-----------|--------------|
| `models/` (all existing) | Sweeps modify copies of `DisplayProject`, never mutate in-place |
| `solvers/` (steady_state, transient, network_builder) | Solvers are already stateless; sweep runner just calls them N times |
| `core/postprocess.py` | Postprocessing is already a pure function; report gen calls it the same way CLI does |
| `io/project_io.py` | JSON round-trip unchanged; backward compat preserved |
| `visualization/plotting.py` | Report generator calls same functions already used by CLI |

---

## Recommended Project Structure (additions only)

```
thermal_sim/
├── sweeps/                        # NEW: parametric sweep engine
│   ├── __init__.py
│   ├── spec.py                    # SweepSpec, SweepResult dataclasses
│   ├── runner.py                  # SweepRunner (QRunnable + signals)
│   └── mutator.py                 # ProjectMutator: applies one sweep step to a project copy
├── models/
│   ├── power_profile.py           # NEW: PowerProfile (time-varying heat source)
│   └── ... (existing unchanged)
├── io/
│   ├── report_gen.py              # NEW: PDF report generation (ReportLab)
│   └── ... (existing unchanged)
└── ui/
    ├── sweep_dialog.py            # NEW: sweep configuration + progress UI
    ├── sweep_results.py           # NEW: comparison results panel
    ├── material_library_dialog.py # NEW: expanded material library browser
    └── ... (existing unchanged)
```

**Why this structure:** Each concern gets its own module. `sweeps/` is a sibling to `solvers/` because it orchestrates solvers but is not a solver itself. `report_gen.py` goes in `io/` because it is an output format, just like `csv_export.py`. Power profiles go in `models/` because they are domain input data, not logic.

---

## Architectural Patterns

### Pattern 1: Project Mutation via Deep Copy for Sweeps

**What:** `SweepRunner` never modifies the user's live `DisplayProject`. For each sweep step it calls `ProjectMutator.apply(base_project, param_name, value)` which returns a new `DisplayProject` with the one target field replaced. All other fields are shared (safe because project fields are immutable dataclasses).

**When to use:** Any time multiple solver calls must run over variants of the same project.

**Trade-offs:** Cheap because only the mutated scalar differs; no full deep-copy required in practice — only the containing dataclass needs re-instantiation since children are frozen.

**Example:**
```python
# thermal_sim/sweeps/mutator.py
from dataclasses import replace
from thermal_sim.models.project import DisplayProject

class ProjectMutator:
    @staticmethod
    def apply(base: DisplayProject, param: str, value: float) -> DisplayProject:
        # param examples: "layers[0].thickness", "boundaries.top.convection_h"
        # Uses dataclasses.replace() at each level — no mutation
        if param.startswith("layers["):
            idx, field = _parse_layer_param(param)
            new_layer = replace(base.layers[idx], **{field: value})
            new_layers = list(base.layers)
            new_layers[idx] = new_layer
            return replace(base, layers=new_layers)
        # ... other param types
```

### Pattern 2: QRunnable + WorkerSignals for Background Sweeps

**What:** Sweep execution runs in a background thread via `QThreadPool`. A `WorkerSignals(QObject)` companion class carries typed Qt signals. The `SweepRunner(QRunnable)` holds a reference to signals and emits progress as each step completes.

**When to use:** Any long-running batch operation initiated from the GUI (sweep, report generation, large transient).

**Trade-offs:** Keeps GUI responsive during N-step sweep. Cancellation requires a thread-safe flag checked at each loop iteration. `QRunnable` cannot be directly inherited from `QObject`, hence the separate signals object.

**Example:**
```python
# thermal_sim/sweeps/runner.py
from PySide6.QtCore import QObject, QRunnable, Signal

class SweepSignals(QObject):
    progress = Signal(int, int)          # step, total
    step_done = Signal(int, object)      # step_idx, SweepStepResult
    finished = Signal(object)            # SweepResult
    error = Signal(str)

class SweepRunner(QRunnable):
    def __init__(self, spec, base_project):
        super().__init__()
        self.signals = SweepSignals()
        self._spec = spec
        self._base = base_project
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        results = []
        for i, value in enumerate(self._spec.values):
            if self._cancel:
                return
            project = ProjectMutator.apply(self._base, self._spec.param, value)
            result = SteadyStateSolver().solve(project)
            results.append(result)
            self.signals.progress.emit(i + 1, len(self._spec.values))
        self.signals.finished.emit(SweepResult(self._spec, results))
```

### Pattern 3: PowerProfile as a Callable Injected into TransientSolver

**What:** `PowerProfile` encodes a piecewise-linear (or stepped) power-vs-time function per heat source. The `TransientSolver` accepts an optional `power_profiles: dict[str, PowerProfile]` argument. On each time step it queries `profile(t)` to override the static `power_w` from the project model.

**When to use:** Any scenario where heat sources turn on/off or follow duty cycles.

**Trade-offs:** Keeps the domain model clean (static `power_w` remains the default / steady-state value). Solver is the only place that needs to know about time-varying power. No change to model serialization is needed for the basic case — profiles are separate from the project JSON or stored as an optional extra field.

**Example:**
```python
# thermal_sim/models/power_profile.py
from dataclasses import dataclass

@dataclass
class PowerProfile:
    """Piecewise-linear power vs time for a named heat source."""
    source_name: str
    times_s: list[float]     # breakpoints, must be ascending
    powers_w: list[float]    # power at each breakpoint

    def __call__(self, t: float) -> float:
        """Return interpolated power at time t."""
        import numpy as np
        return float(np.interp(t, self.times_s, self.powers_w))
```

### Pattern 4: ReportLab Platypus with In-Memory Matplotlib Figures

**What:** `ReportGenerator.generate(result, output_path)` assembles a PDF using ReportLab's Platypus high-level layout engine. Matplotlib figures are rendered to `io.BytesIO` buffers and inserted as `reportlab.platypus.Image` objects. No intermediate PNG files are written to disk.

**When to use:** Every time the user requests a PDF report.

**Trade-offs:** ReportLab's Platypus handles pagination automatically. In-memory render avoids temp-file cleanup. Use `figure.tight_layout()` before saving to BytesIO to prevent label clipping in the PDF.

**Example:**
```python
# thermal_sim/io/report_gen.py
import io
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Table
from reportlab.lib.units import inch

def _fig_to_image(fig, width_in=6.0) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    aspect = fig.get_figheight() / fig.get_figwidth()
    return Image(buf, width=width_in * inch, height=width_in * aspect * inch)
```

### Pattern 5: QDockWidget-Based Professional GUI Layout

**What:** Replace the current fixed QSplitter left/right division with `QDockWidget` panels anchored to `QMainWindow`. The editor panels (materials, layers, sources, boundaries, probes) become dockable/collapsible. The results area (map, profile, history, summary) occupies the central widget. A `QToolBar` provides the primary action buttons.

**When to use:** Phase 4 GUI overhaul.

**Trade-offs:** QDockWidget is built into Qt — no third-party package needed. Users can arrange panels to match their workflow. Zemax-style aesthetic is achievable with a custom `QStyleSheet`. The existing tab structure within each dock can be kept or flattened.

**Build order note:** This is pure visual refactoring and should be done after the new feature components (sweep engine, power profiles, report gen) are working. Refactoring the GUI shell while also wiring new backend components is a reliability risk.

---

## Data Flow

### Parametric Sweep Flow

```
User configures sweep in SweepDialog
    │  (param: "layers[0].thickness", values: [0.001..0.005, 10 steps])
    ▼
SweepDialog validates → creates SweepSpec
    ▼
SweepRunner(QRunnable) submitted to QThreadPool
    │
    ├─ For each value:
    │     ProjectMutator.apply(base_project, param, value)
    │         → new DisplayProject (copy)
    │     SteadyStateSolver().solve(new_project)
    │         → SteadyStateResult
    │     signals.progress.emit(step, total)
    │     signals.step_done.emit(step, result)
    │         → SweepDialog updates progress bar (via queued signal, main thread)
    │
    └─ signals.finished.emit(SweepResult)
           → MainWindow receives SweepResult
           → SweepResultsPanel.display(sweep_result) renders comparison
```

### Time-Varying Heat Source Flow

```
User defines PowerProfile per heat source (new UI panel or JSON field)
    ▼
DisplayProject loaded (static power_w = peak/nominal value, unchanged)
    ▼
TransientSolver.solve(project, power_profiles=profiles_dict)
    │
    ├─ Time loop step n at time t:
    │     For each heat source:
    │         power = profiles_dict[source.name](t) if source.name in profiles_dict
    │                 else source.power_w
    │     Reassemble RHS b_vector with overridden powers
    │     Solve LU system → T_{n+1}
    │
    └─ Returns TransientResult (same shape as before)
```

**Critical implementation note:** The LHS matrix (A + C/dt) does NOT change when only power values change between time steps. The LU factorization from `splu()` remains valid for the entire simulation. Only the RHS `b_vector` must be recomputed at each step. This preserves the existing O(n) per-step performance.

### PDF Report Generation Flow

```
User clicks "Generate Report" button (after simulation run)
    ▼
ReportGenerator.generate(
    project=DisplayProject,
    result=SteadyStateResult | TransientResult | SweepResult,
    output_path=Path
)
    │
    ├─ Build cover section: project name, date, stack summary table
    ├─ Build thermal maps section:
    │     For each layer: plot_temperature_map() → BytesIO → Image
    ├─ Build probe section:
    │     probe_temperatures() → Table rows
    │     plot_probe_history() → BytesIO → Image  (transient only)
    ├─ Build sweep comparison section (if SweepResult):
    │     matplotlib comparison plot → BytesIO → Image
    │     Table of peak temperatures vs parameter
    └─ SimpleDocTemplate.build([...all story elements])
           → writes PDF to output_path
```

### State Management (unchanged + extended)

The existing pattern of `DisplayProject` as single source of truth continues. New state additions to `MainWindow`:

```
MainWindow state (additions):
  last_sweep_result: SweepResult | None
  last_power_profiles: dict[str, PowerProfile]
  active_sweep_runner: SweepRunner | None  (for cancellation)
```

Sweep results are never merged back into `DisplayProject`. They live in `last_sweep_result` as a read-only artifact, just like `last_steady_result`.

---

## Build Order (Phase Dependencies)

The four Phase 4 features have these dependencies:

```
1. PowerProfile model            (no dependencies — pure domain model)
        ↓
2. TransientSolver integration   (depends on PowerProfile)
        ↓ (independent branch)
3. SweepSpec + ProjectMutator    (depends only on existing models)
        ↓
4. SweepRunner (background)      (depends on SweepSpec + existing solvers)
        ↓
5. ReportGenerator               (depends on existing result types; optionally SweepResult)
        ↓
6. GUI: SweepDialog + panel      (depends on SweepRunner)
7. GUI: Power profile editor     (depends on PowerProfile model)
8. GUI: Report trigger button    (depends on ReportGenerator)
9. GUI: QDockWidget overhaul     (purely presentational — last)
10. Packaging (PyInstaller)      (everything must be complete first)
```

**Recommended sequencing for roadmap:**
- Milestone A: Backend features first (1–5) — allows CLI testing without GUI
- Milestone B: Wire backend into GUI (6–8) — incremental, each can ship independently
- Milestone C: Visual polish + packaging (9–10) — surface-level, no risk to physics

---

## Anti-Patterns

### Anti-Pattern 1: Mutating DisplayProject In-Place for Sweeps

**What people do:** Modify `project.layers[0].thickness = value` directly inside the sweep loop.

**Why it's wrong:** `DisplayProject` is the single source of truth and is shared by reference throughout the GUI. Mutating it mid-sweep corrupts the displayed project, breaks undo semantics, and creates race conditions if the solver runs in a background thread.

**Do this instead:** Always call `ProjectMutator.apply()` which uses `dataclasses.replace()` to produce a new object. The base project is never touched.

### Anti-Pattern 2: Running the Sweep Loop on the Main Thread

**What people do:** Call `SteadyStateSolver().solve()` in a loop inside a button click handler.

**Why it's wrong:** The Qt event loop is blocked for the full sweep duration. The GUI freezes. Progress updates cannot render. There is no way to cancel.

**Do this instead:** Submit a `SweepRunner(QRunnable)` to `QThreadPool.globalInstance().start(runner)`. Connect `runner.signals.progress` to the progress bar update slot. This is the canonical PySide6 pattern per official Qt documentation.

### Anti-Pattern 3: Rebuilding LU Factorization Per Time Step for Time-Varying Power

**What people do:** Call `build_thermal_network()` and `splu()` again at every time step when power changes.

**Why it's wrong:** The LHS matrix `A + C/dt` does not include the power vector `b`. Power appears only on the RHS. Rebuilding `splu()` at every step is O(n^1.5) per step — catastrophically slow for long simulations.

**Do this instead:** Compute `splu(A + C/dt)` once at the start, then recompute only the RHS `b_vector` at each step using the current `PowerProfile(t)` value. Solver performance is unchanged.

### Anti-Pattern 4: Writing Matplotlib PNGs to Disk for Report Generation

**What people do:** Call `fig.savefig("temp_plot.png")`, embed the file in the PDF, then try to delete it.

**Why it's wrong:** Requires write access to a temp directory, leaves files behind on crash, and the path may be relative (wrong working directory when packaged with PyInstaller).

**Do this instead:** Render to `io.BytesIO()` in memory. Pass the buffer to `reportlab.platypus.Image`. No temp files, no cleanup, no path issues.

### Anti-Pattern 5: Adding Sweep UI Directly to main_window.py

**What people do:** Add sweep controls and results tables directly into the 940-line `MainWindow` class.

**Why it's wrong:** `main_window.py` is already a large god object. Adding sweep UI inline makes it harder to test, harder to refactor, and harder to navigate.

**Do this instead:** Create `thermal_sim/ui/sweep_dialog.py` (QDialog for configuration and progress) and `thermal_sim/ui/sweep_results.py` (QWidget for comparison display). `MainWindow` instantiates these and connects their signals. The existing main window only needs a "Run Sweep" button and a results tab slot.

---

## Integration Points

### Solver ↔ PowerProfile Integration

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `TransientSolver` ↔ `PowerProfile` | Direct call: `profile(t)` returns float | Profiles passed as `dict[str, PowerProfile]` optional kwarg; absent = use static `power_w` |
| `SweepRunner` ↔ `Solvers` | Direct instantiation and call | Runner imports solver classes; solvers have no knowledge of runner |
| `ReportGenerator` ↔ `visualization/plotting.py` | Direct function calls (same as CLI) | No new interface needed; report gen passes result objects to existing plot functions |
| `SweepDialog` ↔ `SweepRunner` | Qt signals/slots across thread boundary | Only signal-based communication; never call runner methods from main thread except `cancel()` |
| `MainWindow` ↔ `ReportGenerator` | Direct call in response to button click | Report generation is fast enough (~1–2s) to run on main thread initially; move to QRunnable only if user reports blocking |

### Packaging Integration

| Concern | Approach | Notes |
|---------|----------|-------|
| PyInstaller entry point | `--windowed` flag (no console), `--onefile` for single EXE | Verified: PyInstaller supports PySide6 natively; see Qt for Python docs |
| Resource files | Bundle `examples/` and any material library JSON via `--add-data` | Paths must use `sys._MEIPASS` at runtime when frozen |
| No-admin requirement | PyInstaller EXE runs fully in user space; no system DLLs needed | Must use a clean venv without system-installed PySide6 to avoid contamination |

---

## Scaling Considerations

This is a single-user desktop tool. "Scaling" means adding model complexity, not serving more users.

| Concern | Current (Phase 4) | If model grows significantly |
|---------|-------------------|------------------------------|
| Sweep size | 10–50 steps, single-threaded fine | >100 steps: use `concurrent.futures.ProcessPoolExecutor` instead of QThreadPool (GIL-limited for numpy workloads) |
| Transient time-varying power | Per-step RHS recompute, O(n) per step | No change needed; already optimal |
| Report with many layers | In-memory BytesIO per figure | Still fine at 10–15 layers; above that, consider reducing figure DPI |
| PDF size | Full-res figures can produce large PDFs | Use `dpi=150` for embedded figures (not 300) |

---

## Sources

- Qt for Python official docs — QThread and QRunnable: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html
- Qt for Python official docs — QDockWidget: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html
- Qt for Python deployment with PyInstaller: https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html (MEDIUM confidence — docs note Qt 6 windeployqt step still manual)
- PySide6 QThreadPool multithreading pattern: https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/ (MEDIUM confidence — verified against Qt docs)
- ReportLab official docs: https://docs.reportlab.com/
- Matplotlib BytesIO + ReportLab integration: https://woteq.com/how-to-generate-charts-with-reportlab-and-matplotlib/ (MEDIUM confidence — verified against matplotlib savefig docs)
- PyPI reportlab: https://pypi.org/project/reportlab/
- Existing codebase: direct inspection of `thermal_sim/` Phase 3 source (HIGH confidence)

---

*Architecture research for: Python desktop thermal simulation tool (Phase 4 extensions)*
*Researched: 2026-03-14*
