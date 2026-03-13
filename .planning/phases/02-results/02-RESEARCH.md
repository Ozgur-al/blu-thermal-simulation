# Phase 2: Results - Research

**Researched:** 2026-03-14
**Domain:** PySide6 GUI extension, matplotlib annotations, PDF report generation, in-memory result comparison
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Results summary table:** Per-layer table layout with one row per layer showing T_max, T_avg, T_min, and ΔT (all in °C). Separate ranked hotspot list below (top 10) with rank, layer name, location in mm, and temperature. Separate probe readings section below hotspots: probe name, layer, location in mm, temperature. Displayed in a dedicated Results tab that auto-activates after a simulation run completes.
- **Hotspot map annotations:** Crosshair + text label style — thin crosshair lines at hotspot location with rank number and temperature value. Per-layer hotspots: each layer's temperature map shows its own top 3 hotspots. Probes also shown on the temperature map with a distinct marker style (diamond or triangle). Clicking a hotspot row in the summary table highlights/navigates to the corresponding marker on the temperature map.
- **PDF report:** Primary use case is personal archive. Generated using `matplotlib.backends.backend_pdf.PdfPages` (no new dependencies). Sections: stack summary (layers/materials/thickness), temperature maps with hotspot annotations, metrics table (per-layer stats + hotspot ranking), and probe history plots (transient only). Minimal header on first page: project filename, simulation date, solver mode.
- **Result snapshots & comparison:** In-memory named snapshots (lost when app closes). Comparison view: side-by-side metric table with delta column (Δ), overlay probe history plot with different colors per snapshot, and side-by-side temperature maps for the same layer. Up to 4 snapshots comparable simultaneously. Metric table columns expand per snapshot (snapshot name as column header group).

### Claude's Discretion

- Exact crosshair line styling (color, width, alpha) and label font size
- Temperature map colormap choice for comparison views (shared vs per-map scale)
- Probe marker shape (diamond, triangle, or similar)
- Results tab internal layout and spacing
- Snapshot management UI (list widget, dropdown, or similar)
- PDF page sizing and margins

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RSLT-01 | Structured results summary table showing T_max/T_avg/T_min per layer and hotspot rank | New `layer_stats()` function in postprocess.py; QTableWidget with fixed columns; dedicated Results tab auto-activated via `setCurrentWidget()` |
| RSLT-02 | Top-N hotspot locations annotated directly on temperature map plots | `ax.axvline/axhline` crosshairs + `ax.annotate()` for labels; per-layer slice of `_top_n_from_map()`; probe markers via `ax.plot()` with diamond marker; `QTableWidget.cellClicked` signal for click-to-navigate |
| RSLT-03 | User can export PDF engineering report with stack summary, temperature maps, probe data, and key metrics | `matplotlib.backends.backend_pdf.PdfPages` (already available, no new deps); `ax.table()` for summary page; one figure per PDF page; `pdf.savefig(fig, bbox_inches='tight')` |
| RSLT-04 | User can save named result snapshots and compare 2+ runs with overlay probe plots and side-by-side metric tables | `ResultSnapshot` dataclass (in-memory); `QInputDialog.getText()` for naming; comparison tab with dynamic subplot grid (1x2 or 2x2); multiple `ax.plot()` calls with distinct colors for probe overlay |
</phase_requirements>

---

## Summary

Phase 2 is a pure GUI/visualization extension with no new backend solver logic and no new dependencies. All four requirements can be satisfied using the already-installed stack: matplotlib 3.10.8, PySide6 6.10.2, and existing postprocess functions.

The dominant work pattern is: extend `postprocess.py` with one new function (`layer_stats`), extend `plotting.py` with annotation helpers, add a new `ResultSnapshot` dataclass module, and wire up three new UI sections (Results tab, Comparison tab, PDF export). The existing `_build_result_tabs()` Summary tab is a rough precursor — it shows global stats as a `QLabel` + `QTextEdit`. Phase 2 replaces and expands this with proper `QTableWidget`-based structured tables.

The trickiest interaction is click-to-navigate from the hotspot table to the map: use `QTableWidget.cellClicked(row, col)` signal, look up stored hotspot coordinates, call `QTabWidget.setCurrentWidget(map_tab)`, and re-render the map with a highlighted crosshair on the selected hotspot. This is a straightforward PySide6 signal-slot connection and requires no matplotlib pick events.

**Primary recommendation:** Build in dependency order: (1) `layer_stats()` in postprocess.py, (2) annotated map rendering helper in plotting.py, (3) `ResultSnapshot` dataclass, (4) Results tab UI, (5) PDF export function, (6) Comparison tab UI.

---

## Standard Stack

### Core (all already installed, no additions required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| matplotlib | 3.10.8 | Crosshair annotations, PDF generation via PdfPages, table rendering in figures | Already the project's plotting engine; PdfPages is built-in |
| PySide6 | 6.10.2 | QTableWidget for structured tables, QTabWidget navigation, QInputDialog for snapshot naming | Already the project's GUI framework |
| numpy | pinned >=1.26 | Temperature array slicing for per-layer stats | Already used throughout |

### Supporting (zero new installs)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `matplotlib.backends.backend_pdf.PdfPages` | bundled with matplotlib | Multi-page PDF generation | PDF export (RSLT-03) |
| `matplotlib.table` (via `ax.table()`) | bundled with matplotlib | Text tables inside matplotlib figures for PDF pages | Summary page in PDF report |
| `PySide6.QtWidgets.QInputDialog` | bundled with PySide6 | Single-line text prompt for snapshot naming | Snapshot save dialog |
| `PySide6.QtWidgets.QListWidget` or `QComboBox` | bundled with PySide6 | Snapshot management list in comparison tab | Snapshot selection UI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PdfPages (matplotlib) | reportlab | reportlab gives more layout control but is an extra dependency; user decided against it |
| `ax.axvline/axhline` crosshairs | `ax.plot([x,x], [y0,y1])` line segments | Both work; axvline/axhline span the full axis which matches engineering crosshair style |
| `QTableWidget` for comparison | `QTreeWidget` | QTreeWidget supports header groups natively but is more complex; QTableWidget with merged cells or grouped column names is sufficient for 4 snapshots |

**Installation:** No new packages — Phase 2 uses only what is already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Module Structure

```
thermal_sim/
├── core/
│   └── postprocess.py          # Add: layer_stats(), per-layer hotspot helper
├── visualization/
│   └── plotting.py             # Add: plot_temperature_map_annotated(), plot_probe_overlay()
├── io/
│   └── pdf_export.py           # NEW: generate_pdf_report() using PdfPages
├── models/
│   └── snapshot.py             # NEW: ResultSnapshot dataclass
└── ui/
    ├── main_window.py          # Extend: add Results tab, Comparison tab, wire signals
    └── comparison_window.py    # OPTIONAL: if comparison view grows too large for a tab
```

The preference is to add `pdf_export.py` and `snapshot.py` as new modules rather than bloating existing files. `main_window.py` is already 1100+ lines — keep new GUI sections as methods that delegate to helper modules.

### Pattern 1: Per-Layer Stats Extension

**What:** Add `layer_stats()` to `postprocess.py` returning a list of dicts with T_max, T_avg, T_min, ΔT per layer.
**When to use:** Called from `_on_sim_finished()` to populate the Results tab layer table.

```python
# In thermal_sim/core/postprocess.py
def layer_stats(
    temperature_map_c: np.ndarray,  # [n_layers, ny, nx]
    layer_names: list[str],
) -> list[dict]:
    """Per-layer T_max, T_avg, T_min, and delta_T."""
    result = []
    for idx, name in enumerate(layer_names):
        layer = temperature_map_c[idx]
        t_max = float(layer.max())
        t_avg = float(layer.mean())
        t_min = float(layer.min())
        result.append({
            "layer": name,
            "t_max_c": t_max,
            "t_avg_c": t_avg,
            "t_min_c": t_min,
            "delta_t_c": t_max - t_min,
        })
    return result
```

### Pattern 2: Per-Layer Hotspot Extraction

**What:** The existing `_top_n_from_map()` takes the full `[n_layers, ny, nx]` array. For per-layer top-3, slice and pass a single-layer view.
**When to use:** When rendering the temperature map for a specific layer.

```python
# In plotting.py or postprocess.py
def top_n_hottest_cells_for_layer(
    temperature_map_c: np.ndarray,  # [n_layers, ny, nx]
    layer_idx: int,
    layer_name: str,
    dx: float,
    dy: float,
    n: int = 3,
) -> list[dict]:
    """Top-N hottest cells within a single layer."""
    # Slice to [1, ny, nx] so _top_n_from_map returns correct layer name
    single = temperature_map_c[layer_idx : layer_idx + 1]
    return _top_n_from_map(single, [layer_name], dx, dy, n=n)
```

### Pattern 3: Annotated Temperature Map

**What:** Extension of `_plot_map()` that draws crosshairs and probe markers after the base `imshow`.
**When to use:** In the Temperature Map tab and when navigating from the hotspot table.

```python
# Crosshair pattern (verified working)
for rank, hotspot in enumerate(per_layer_hotspots, start=1):
    x, y = hotspot["x_m"], hotspot["y_m"]
    ax.axvline(x=x, color="white", linewidth=0.8, alpha=0.65, linestyle="--")
    ax.axhline(y=y, color="white", linewidth=0.8, alpha=0.65, linestyle="--")
    ax.annotate(
        f"#{rank}\n{hotspot['temperature_c']:.1f}°C",
        xy=(x, y),
        xytext=(x + 0.005 * width_m, y + 0.005 * height_m),
        fontsize=7,
        color="white",
        fontweight="bold",
        ha="left",
        va="bottom",
    )

# Probe markers (diamond, distinct from crosshairs)
for probe in probes:
    ax.plot(probe.x, probe.y, marker="D", markersize=5, color="cyan",
            markeredgewidth=0.8, markeredgecolor="black", zorder=5)
    ax.text(probe.x, probe.y + 0.003 * height_m, probe.name,
            fontsize=6, color="cyan", ha="center", va="bottom")
```

### Pattern 4: Click-to-Navigate Hotspot

**What:** `QTableWidget.cellClicked(row, col)` signal connected to a slot that switches to the map tab and highlights the selected hotspot.
**When to use:** When user clicks a row in the hotspot ranking table.

```python
# In MainWindow or Results tab widget
self.hotspot_table.cellClicked.connect(self._on_hotspot_row_clicked)

def _on_hotspot_row_clicked(self, row: int, col: int) -> None:
    if row >= len(self._current_hotspots):
        return
    hotspot = self._current_hotspots[row]
    # Switch layer selector to match hotspot's layer
    self.map_layer_combo.setCurrentText(hotspot["layer"])
    # Switch to Temperature Map tab
    self.result_tabs.setCurrentWidget(self.map_tab)
    # Re-render with this hotspot highlighted (pass selected_rank=row+1)
    self._plot_map_annotated(selected_rank=row + 1)
```

### Pattern 5: PdfPages Multi-Page Report

**What:** `PdfPages` context manager with one `pdf.savefig(fig)` call per page.
**When to use:** PDF export function in `io/pdf_export.py`.

```python
# In thermal_sim/io/pdf_export.py
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

def generate_pdf_report(snapshot: "ResultSnapshot", output_path: Path) -> None:
    with PdfPages(output_path) as pdf:
        # Page 1: header + stack summary table
        fig = _make_stack_summary_page(snapshot)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Pages 2..N: temperature maps per layer (with annotations)
        for layer_idx, layer_name in enumerate(snapshot.layer_names):
            fig = _make_temperature_map_page(snapshot, layer_idx, layer_name)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        # Page N+1: metrics table (per-layer stats + hotspot ranking)
        fig = _make_metrics_table_page(snapshot)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Page N+2: probe history (transient only)
        if snapshot.mode == "transient" and snapshot.times_s is not None:
            fig = _make_probe_history_page(snapshot)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        # Set PDF metadata
        d = pdf.infodict()
        d["Title"] = f"Thermal Report — {snapshot.project_name}"
        d["Subject"] = f"{snapshot.mode} simulation"
```

### Pattern 6: ResultSnapshot Dataclass

**What:** Frozen dataclass capturing all data needed for display and comparison, stored in-memory.
**When to use:** After each simulation run, if user clicks "Save Snapshot".

```python
# In thermal_sim/models/snapshot.py
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass(frozen=True)
class ResultSnapshot:
    name: str                        # User-assigned label ("baseline", "thinner PCB")
    mode: str                        # "steady" or "transient"
    project_name: str
    simulation_date: str             # ISO date string
    layer_names: list[str]
    final_temperatures_c: np.ndarray # [n_layers, ny, nx]
    temperatures_time_c: Optional[np.ndarray]  # [nt, n_layers, ny, nx] or None
    times_s: Optional[np.ndarray]   # None for steady
    layer_stats: list[dict]          # from layer_stats()
    hotspots: list[dict]             # top-10 from top_n_hottest_cells()
    probe_values: dict               # {name: float} for steady, {name: ndarray} for transient
    dx: float
    dy: float
```

Note: numpy arrays are not hashable so `frozen=True` with `eq=False` or using a regular dataclass is safer. Use `@dataclass` without `frozen=True` to avoid numpy array hashing errors.

### Pattern 7: Comparison Tab Layout

**What:** Dynamic subplot grid in a `MplCanvas` sized to the number of snapshots (1×2 for 2, 2×2 for 3-4).
**When to use:** Comparison tab with active snapshots selected.

```python
# Dynamic grid for side-by-side temperature maps
n = len(selected_snapshots)  # 2, 3, or 4
cols = min(n, 2)
rows = (n + 1) // 2
fig, axes = plt.subplots(rows, cols, figsize=(cols * 4, rows * 3.5))
axes = np.array(axes).ravel()  # Flatten for uniform indexing
for i, (snap, ax) in enumerate(zip(selected_snapshots, axes)):
    im = ax.imshow(snap.final_temperatures_c[layer_idx], ...)
    ax.set_title(snap.name)
# Hide unused axes if n is odd
for ax in axes[n:]:
    ax.set_visible(False)
```

### Anti-Patterns to Avoid

- **Re-running postprocess functions inside paint events:** Cache `layer_stats`, `hotspots`, and `probe_values` in the `ResultSnapshot` at save time — never recompute in the GUI render path.
- **Storing numpy arrays in frozen dataclasses:** Use `@dataclass` without `frozen=True` for `ResultSnapshot` — frozen dataclasses hash their fields, and numpy arrays are not hashable.
- **One monolithic `generate_pdf_report()` function:** Break PDF generation into `_make_*_page()` helpers. Each page is a separate `plt.Figure` that gets `plt.close()`d immediately after `pdf.savefig()` to avoid memory accumulation.
- **Blocking the GUI thread for PDF export:** PDF export should run in a `QThread` worker (same pattern as `_SimWorker`) if a large number of layers could make generation slow. For typical 3-5 layer stacks, inline is acceptable; for >8 layers, thread it.
- **Using `plt.show()` inside PDF helpers:** Always use `pdf.savefig(fig)` then `plt.close(fig)` — never `plt.show()` in report generation code.
- **Unlimited snapshots:** Cap at 4 in the UI. Storing more than 4 transient results risks >1 GB RAM for high-resolution grids. Guard with a warning dialog before saving a 5th.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-page PDF | Custom PDF writer or HTML-to-PDF | `matplotlib.backends.backend_pdf.PdfPages` | Handles font embedding, page sizing, metadata; already installed |
| Table in PDF | Manually positioned text strings | `ax.table(cellText, colLabels, ...)` | Handles cell sizing, borders, alignment automatically |
| Snapshot naming dialog | Custom `QDialog` subclass | `QInputDialog.getText(parent, title, label)` | One-liner, returns (text, accepted) tuple |
| Color cycling for overlay plots | Manual color list | `matplotlib.colormaps["tab10"](i / 10)` | Perceptually uniform, colorblind-friendly, consistent |
| Dynamic subplot grid | Complex layout code | `plt.subplots(rows, cols)` + `axes.ravel()` | Standard matplotlib pattern for uniform subplot iteration |

**Key insight:** Every problem in this phase has an existing matplotlib/PySide6 solution. The engineering value is in wiring these correctly, not in building any infrastructure.

---

## Common Pitfalls

### Pitfall 1: numpy arrays in frozen dataclasses
**What goes wrong:** `@dataclass(frozen=True)` calls `__hash__` on all fields; numpy arrays raise `TypeError: unhashable type`.
**Why it happens:** Frozen dataclasses auto-generate `__hash__` from all fields.
**How to avoid:** Use `@dataclass` without `frozen=True` for `ResultSnapshot`. Treat snapshots as effectively immutable by convention — no mutation after creation.
**Warning signs:** `TypeError: unhashable type: 'numpy.ndarray'` when constructing a snapshot.

### Pitfall 2: Memory accumulation from unclosed matplotlib figures
**What goes wrong:** Each call to `plt.subplots()` or `Figure()` that is not explicitly closed leaks memory. With 4 comparison snapshots × multiple layers, this can cause noticeable slowdowns.
**Why it happens:** `FigureCanvasQTAgg` holds a reference; Python's GC does not close matplotlib figures automatically.
**How to avoid:** Always call `plt.close(fig)` after `pdf.savefig(fig)`. For embedded canvases, reuse the existing `figure.clear()` pattern already used in `_plot_map()`.
**Warning signs:** Gradual memory growth after repeated comparisons or PDF exports.

### Pitfall 3: Hotspot coordinates in wrong unit for annotations
**What goes wrong:** `top_n_hottest_cells` returns `x_m`, `y_m` in metres; the summary table should display in mm; `ax.annotate` works in the axes data coordinates (metres for temperature maps with `extent=[0, width_m, 0, height_m]`).
**Why it happens:** Mixed units between display and render paths.
**How to avoid:** Store hotspot data in metres (as returned); convert to mm for table display only with `x_mm = hotspot["x_m"] * 1000`. Pass metres directly to `ax.axvline/axhline` and `ax.annotate`.
**Warning signs:** Crosshairs appearing at wrong positions relative to the heat map.

### Pitfall 4: QTabWidget index fragility
**What goes wrong:** Hard-coding `result_tabs.setCurrentIndex(3)` to navigate to the Results tab breaks if tab order changes.
**Why it happens:** Integer tab indices are positional.
**How to avoid:** Store a reference to each tab widget: `self.results_tab = results_widget; result_tabs.setCurrentWidget(self.results_tab)`. The existing code already uses named canvases — follow the same pattern for tabs.
**Warning signs:** Auto-navigation lands on the wrong tab after a tab re-ordering.

### Pitfall 5: axvline/axhline spanning beyond the data extent
**What goes wrong:** `ax.axvline()` draws a vertical line spanning the full axes height by default — on a temperature map this is correct. However if the axes has padding (from `imshow` with `aspect="auto"`), the lines may not align with the heatmap extent.
**Why it happens:** `ax.imshow()` with `origin="lower"` and `extent` sets the data range but axes can still have auto-padding.
**How to avoid:** After drawing the map, call `ax.set_xlim(0, width_m); ax.set_ylim(0, height_m)` explicitly before adding crosshairs to anchor the coordinate system.
**Warning signs:** Crosshairs visually offset from the pixel they should mark.

### Pitfall 6: Comparison table column width explosion with 4 snapshots
**What goes wrong:** 4 snapshots × 4 metrics = 16 data columns + 1 label column = 17 columns in one `QTableWidget`. At default widths this requires horizontal scrolling.
**Why it happens:** `QHeaderView.ResizeMode.Stretch` stretches all columns equally, making each column very narrow.
**How to avoid:** Use `ResizeMode.Interactive` with `setStretchLastSection(True)` and set a minimum column width of 80px. Group snapshot columns visually with a bold header row (use `QTableWidgetItem` with bold font for snapshot name rows).
**Warning signs:** Column headers are too narrow to read when 4 snapshots are active.

---

## Code Examples

### Per-layer stats (postprocess.py extension)
```python
# Source: verified against existing _stats_from_map pattern in postprocess.py
def layer_stats(
    temperature_map_c: np.ndarray,
    layer_names: list[str],
) -> list[dict]:
    result = []
    for idx, name in enumerate(layer_names):
        layer = temperature_map_c[idx]
        t_max = float(layer.max())
        t_avg = float(layer.mean())
        t_min = float(layer.min())
        result.append({
            "layer": name,
            "t_max_c": t_max,
            "t_avg_c": t_avg,
            "t_min_c": t_min,
            "delta_t_c": t_max - t_min,
        })
    return result
```

### PdfPages stack summary table page
```python
# Source: verified with matplotlib 3.10.8 ax.table() API
def _make_stack_summary_page(snapshot) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.5, 11))  # US Letter
    ax.axis("off")
    # Header text
    ax.text(0.5, 0.97, f"Thermal Report — {snapshot.project_name}",
            transform=ax.transAxes, ha="center", va="top", fontsize=14, fontweight="bold")
    ax.text(0.5, 0.93, f"Mode: {snapshot.mode}  |  Date: {snapshot.simulation_date}",
            transform=ax.transAxes, ha="center", va="top", fontsize=9)
    # Per-layer stats table
    col_labels = ["Layer", "T_max [°C]", "T_avg [°C]", "T_min [°C]", "ΔT [°C]"]
    cell_data = [
        [s["layer"], f"{s['t_max_c']:.2f}", f"{s['t_avg_c']:.2f}",
         f"{s['t_min_c']:.2f}", f"{s['delta_t_c']:.2f}"]
        for s in snapshot.layer_stats
    ]
    table = ax.table(cellText=cell_data, colLabels=col_labels,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    return fig
```

### QInputDialog snapshot naming
```python
# Source: PySide6 6.10.2 QInputDialog.getText()
from PySide6.QtWidgets import QInputDialog

def _save_snapshot_dialog(self) -> None:
    if self.last_steady_result is None and self.last_transient_result is None:
        return
    name, ok = QInputDialog.getText(self, "Save Snapshot", "Snapshot name:")
    if not ok or not name.strip():
        return
    snapshot = self._build_snapshot(name.strip())
    if len(self._snapshots) >= 4:
        self._snapshots.pop(0)  # evict oldest
    self._snapshots.append(snapshot)
    self._refresh_snapshot_list()
```

### Probe overlay plot for comparison
```python
# Source: existing plot_probe_history() pattern in plotting.py
import matplotlib.colormaps as cm

def _plot_probe_overlay(self, snapshots: list) -> None:
    self.comparison_probe_canvas.figure.clear()
    ax = self.comparison_probe_canvas.figure.add_subplot(111)
    colors = cm["tab10"]
    for i, snap in enumerate(snapshots):
        if snap.times_s is None or not snap.probe_values:
            continue
        color = colors(i / 10)
        for probe_name, values in snap.probe_values.items():
            ax.plot(snap.times_s, values, label=f"{snap.name} — {probe_name}",
                    color=color, linestyle="-" if i == 0 else "--")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("Probe Overlay Comparison")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.25)
    self.comparison_probe_canvas.figure.tight_layout()
    self.comparison_probe_canvas.draw()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `matplotlib.backends.backend_pdf.PdfPages(keep_empty=True)` | `keep_empty` parameter deprecated | matplotlib 3.9+ | The `keep_empty` kwarg now raises a deprecation warning; omit it entirely |
| `fig.savefig(pdf)` passing file object | `pdf.savefig(fig)` | matplotlib 3.x | `pdf.savefig(fig)` is the documented idiom; passing `fig` (not `pdf`) explicitly sets the figure per page |
| PySide2/PyQt5 patterns | PySide6 patterns | PySide6 6.0+ | Signal syntax unchanged; `Qt.Orientation.Horizontal` style (not `Qt.Horizontal`) required |

**Deprecated/outdated:**
- `PdfPages(filename, keep_empty=True)`: The `keep_empty` parameter is deprecated in matplotlib 3.9+. The constructor signature is now `PdfPages(filename, metadata=None)`. Verified against installed matplotlib 3.10.8.
- Global `stats_label` + `summary_text` QTextEdit pattern (current Phase 1 summary tab): Phase 2 replaces this with proper per-layer `QTableWidget` rows.

---

## Open Questions

1. **Phase 1 refactor state at Phase 2 start**
   - What we know: Phase 2 depends on Phase 1 (Foundation). Phase 1 includes `SimulationController`/`PlotManager` refactor.
   - What's unclear: Whether `MainWindow` will have been split before Phase 2 begins, affecting where Results tab code lives.
   - Recommendation: Write Results tab code as a composable `QWidget` subclass (`ResultsSummaryWidget`) that can be embedded regardless of whether MainWindow is still a god object or has been refactored.

2. **Hotspot navigation when layer changes**
   - What we know: The hotspot table shows global top-10 across all layers; the map shows per-layer top-3.
   - What's unclear: When clicking a row whose layer differs from the currently displayed layer, should the layer combo auto-switch?
   - Recommendation: Yes — auto-switch `map_layer_combo` to the hotspot's layer, then re-render. This makes the navigation feel instant and correct.

3. **Comparison tab placement**
   - What we know: The result tabs currently have: Temperature Map, Layer Profile, Probe History, Summary. Comparison needs its own tab or a separate dialog.
   - What's unclear: Whether a new tab vs a separate window is better for the 4-snapshot side-by-side map view.
   - Recommendation: Add a "Comparison" tab to the existing result tabs. A separate dialog would require managing window lifecycle; a tab keeps everything in one place. The 2×2 map grid fits in a typical 1500×900 window at 4.0×3.5 per subplot.

---

## Sources

### Primary (HIGH confidence)
- Installed matplotlib 3.10.8 — verified `PdfPages`, `ax.table()`, `ax.axvline/axhline`, `ax.annotate()`, `FigureCanvasQTAgg.mpl_connect()` all present and working via local Python execution
- Installed PySide6 6.10.2 — verified `QTableWidget.cellClicked`, `QTabWidget.setCurrentWidget`, `QInputDialog.getText`, `QListWidget`, `QComboBox` all present
- Existing codebase source — verified `postprocess.py`, `plotting.py`, `main_window.py`, `transient.py`, `steady_state.py` structure and APIs

### Secondary (MEDIUM confidence)
- matplotlib PdfPages deprecation note on `keep_empty` — verified by inspecting `PdfPages.__init__` signature in installed 3.10.8: `(self, filename, keep_empty=<deprecated parameter>, metadata=None)`

### Tertiary (LOW confidence)
- None — all claims verified against installed libraries or local source inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified all APIs against installed packages (matplotlib 3.10.8, PySide6 6.10.2)
- Architecture patterns: HIGH — derived directly from existing codebase patterns (`_SimWorker`, `MplCanvas`, `_new_table`, `_plot_map`)
- Pitfalls: HIGH — verified against actual library behavior (frozen dataclass + numpy, PdfPages keep_empty deprecation, imshow extent/xlim interaction)

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (stable libraries; matplotlib and PySide6 minor version bumps unlikely to break these APIs)
