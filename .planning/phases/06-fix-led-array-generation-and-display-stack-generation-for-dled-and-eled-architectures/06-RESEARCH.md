# Phase 6: Fix LED Array Generation and Display Stack Generation for DLED and ELED Architectures - Research

**Researched:** 2026-03-15
**Domain:** Python domain model extension + PySide6 GUI architecture
**Confidence:** HIGH — all findings are from direct source code inspection, no external dependencies to verify

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### ELED LED Placement
- Support all four edge configurations: bottom-only, top-only, left/right (dual-edge), and all-four-sides
- LEDs are positioned with a configurable offset from the panel edge (not at the edge itself, not outside the panel)
- Discrete LEDs with pitch along the edge — expands to individual HeatSource objects like current LEDArray
- Edge LEDs live on a separate LED board layer (thin PCB/FPC) adjacent to the LGP, not on the LGP layer itself

#### Stack Templates — DLED
- Layer order (bottom to top): Back Cover (Al) → Metal Frame (Steel/Al) → LED Board (FR4) → Optical Sheets (variable count, customizable) → OCA → Display Cell (Glass) → Cover Glass
- Optical sheet stack (diffuser, BEF, DBEF, etc.) must be customizable — user can add/remove optical layers
- Templates provide full defaults: material assignments and typical thicknesses pre-filled
- Metal bezel/frame modeled as enhanced side boundary conditions (higher effective h) — the frame bottom is captured by the Metal Frame layer in the stack

#### Stack Templates — ELED
- Layer order (bottom to top): Back Cover (Al) → Metal Frame (Steel/Al) → LGP (PMMA/acrylic) → Optical Sheets (variable) → OCA → Display Cell (Glass) → Cover Glass
- Edge LED board is a separate thin layer adjacent to the LGP (not stacked in the Z-direction — this is an edge-mounted component)
- Same metal frame treatment as DLED: frame layer in stack + enhanced side boundary

#### DLED Array Configuration
- Auto-center LED array on the panel dimensions (derive from width/2, height/2)
- Independent edge offsets per side: offset_top, offset_bottom, offset_left, offset_right — LEDs don't extend to panel border when offset > 0
- Zone-based dimming: user specifies zone grid (zone_count_x, zone_count_y), system divides LED grid evenly across zones, user sets power per zone
- Uniform power within each zone

#### GUI Workflow
- Architecture dropdown at the top of the editor: DLED / ELED / Custom
- Selecting DLED or ELED auto-populates layers table, materials, and LED array config with template defaults
- Switching architecture replaces the project silently (no confirmation dialog)
- LED Arrays tab adapts based on architecture: DLED shows grid config + edge offsets + zone power table; ELED shows edge selection + strip parameters (offset, count, pitch, LED footprint)
- "Custom" keeps the current fully manual workflow unchanged

### Claude's Discretion
- Default thickness values for each template layer
- Default material assignments from the existing material library
- Zone power table UI layout within the LED Arrays tab
- How edge LED board layer is represented in the 2.5D model (since it's alongside the LGP, not stacked)
- Loading skeleton / transition when switching architectures

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 6 extends the existing thermal simulator to support two industry-standard display backlight architectures — Direct-LED (DLED) and Edge-LED (ELED) — without modifying the solver or postprocessing pipeline. The entire feature is a model + GUI layer change: new fields on `LEDArray`, a new stack template module, and an architecture-aware LED Arrays tab in `MainWindow`.

The existing `LEDArray.expand()` → `list[HeatSource]` contract is the stable interface between the new architecture-specific generation logic and the solver pipeline. As long as `expand()` produces correct `HeatSource` objects, the network builder, solvers, postprocessor, and visualization code need no changes at all. The project's JSON serialization pattern (`to_dict()` / `from_dict()`) must be extended for all new fields — this is the established convention throughout every model class.

The most structurally significant change is the GUI: the current `_build_led_arrays_tab()` is a single static table. It must become a mode-switching widget that shows different sub-panels depending on the architecture dropdown. The `QUndoStack` integration and `TableDataParser` stateless pattern must be maintained throughout.

**Primary recommendation:** Implement in three ordered layers — (1) extend `LEDArray` model with mode fields, (2) build a `stack_templates.py` module, (3) replace the static LED Arrays tab with an architecture-aware panel connected to the new architecture dropdown.

---

## Standard Stack

### Core (no new external dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | stdlib | Model extension | All existing models (LEDArray, HeatSource, Layer) use `@dataclass` |
| PySide6 | already in requirements.txt | GUI framework | All existing UI code uses PySide6 |
| numpy | already in requirements.txt | LED position arithmetic | pitch * count grid math, edge offset calculations |

No new pip dependencies are required. This phase is pure Python / PySide6 code reorganization and extension.

### No Alternatives Needed

This is an internal domain extension. The technology choices are locked by the existing project. No library selection decisions are required.

---

## Architecture Patterns

### Recommended New File Layout

```
thermal_sim/
├── models/
│   ├── heat_source.py          # EXTEND: LEDArray gets mode/zone/edge fields
│   └── stack_templates.py      # NEW: dled_template() and eled_template() functions
├── ui/
│   ├── main_window.py          # MODIFY: architecture dropdown + tab switching
│   ├── led_arrays_panel.py     # NEW: architecture-aware LED Arrays widget
│   └── table_data_parser.py    # EXTEND: parse_led_arrays_table handles new fields
└── resources/
    └── materials_builtin.json  # EXISTS: already has all needed materials
```

### Pattern 1: LEDArray Model Extension — Mode Field + Zone Power

**What:** Add a `mode` field to `LEDArray` distinguishing `"grid"` (DLED), `"edge"` (ELED), and `"custom"` (current behavior, the default for backward compatibility). Add optional fields for zone configuration and edge configuration.

**Backward compatibility rule:** All new fields must have defaults. `from_dict()` must use `.get()` with defaults for all new keys. Existing JSON project files must load without modification.

**Expansion contract:** `expand()` must return `list[HeatSource]` regardless of mode. Zone power means each LED's `power_w` is set from the zone table. Edge strip means LEDs are placed along panel edges rather than in a 2D center grid.

```python
# Source: models/heat_source.py — extend existing LEDArray

from typing import Literal

LEDMode = Literal["grid", "edge", "custom"]
EdgeConfig = Literal["bottom", "top", "left_right", "all"]

@dataclass
class LEDArray:
    # --- existing fields (unchanged) ---
    name: str
    layer: str
    center_x: float
    center_y: float
    count_x: int
    count_y: int
    pitch_x: float
    pitch_y: float
    power_per_led_w: float
    footprint_shape: LedFootprintType = "rectangle"
    led_width: float | None = None
    led_height: float | None = None
    led_radius: float | None = None

    # --- new fields ---
    mode: LEDMode = "custom"          # "custom" = legacy behavior, no behavior change
    # DLED-specific:
    offset_top: float = 0.0
    offset_bottom: float = 0.0
    offset_left: float = 0.0
    offset_right: float = 0.0
    zone_count_x: int = 1
    zone_count_y: int = 1
    zone_powers: list[float] = field(default_factory=list)  # len = zone_count_x * zone_count_y
    # ELED-specific:
    edge_config: EdgeConfig = "bottom"
    edge_offset: float = 0.005        # 5mm default offset from panel edge
    panel_width: float = 0.0          # set by template; used for edge position calculation
    panel_height: float = 0.0         # set by template; used for edge position calculation
```

**Key insight on zone_powers:** `zone_powers` is a flat list of length `zone_count_x * zone_count_y`. Zone index = `iy * zone_count_x + ix`. When `zone_powers` is empty or wrong length, fall back to `power_per_led_w` uniformly. This avoids errors during partial configuration.

**expand() for grid mode (DLED):**
```python
def _grid_start(self) -> tuple[float, float]:
    """Compute first LED position considering edge offsets."""
    usable_w = self.panel_width - self.offset_left - self.offset_right
    usable_h = self.panel_height - self.offset_bottom - self.offset_top
    x_start = self.offset_left + (usable_w - (self.count_x - 1) * self.pitch_x) / 2.0
    y_start = self.offset_bottom + (usable_h - (self.count_y - 1) * self.pitch_y) / 2.0
    return x_start, y_start
```

**expand() for edge mode (ELED):**
Each configured edge produces a 1D strip of LEDs. "bottom" edge: LEDs at `y = edge_offset`, `x` values spaced by `pitch_x` centered on panel width. "top": `y = panel_height - edge_offset`. "left_right": two strips. "all": four strips. All strips use `count_x` for horizontal edges, `count_y` for vertical edges.

### Pattern 2: Stack Template Module

**What:** A pure-function module `stack_templates.py` that returns `(list[Layer], dict[str, Material], BoundaryConditions, list[LEDArray])` tuples — no GUI dependencies, fully testable.

**When to use:** Called when user selects DLED or ELED from the architecture dropdown.

```python
# Source: models/stack_templates.py — new file

from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import LEDArray
from thermal_sim.core.material_library import load_builtin_library


def dled_template(
    panel_width: float,
    panel_height: float,
    optical_layers: int = 2,
) -> dict:
    """Return default DLED stack as a dict with keys: layers, materials, led_arrays, boundaries."""
    ...

def eled_template(
    panel_width: float,
    panel_height: float,
    edge_config: str = "bottom",
    optical_layers: int = 2,
) -> dict:
    """Return default ELED stack."""
    ...
```

**Default thickness assignments (Claude's Discretion):**

| Layer | Material | Default Thickness |
|-------|----------|-------------------|
| Back Cover | Aluminum | 0.8 mm |
| Metal Frame | Steel | 1.0 mm |
| LED Board (DLED) | FR4 | 1.0 mm |
| LGP (ELED only) | PMMA | 4.0 mm |
| Diffuser (optical sheet 1) | PC | 2.0 mm |
| BEF (optical sheet 2) | PC | 0.3 mm |
| OCA | OCA | 0.15 mm |
| Display Cell | Glass | 1.1 mm |
| Cover Glass | Glass | 1.8 mm |

These are rationale-backed defaults for a typical 32" consumer/automotive display range. All materials already exist in `materials_builtin.json` except "Diffuser" and "BEF" which can use "PC" (polycarbonate) as an approximation — PC is already in the library.

**Metal frame side boundary (Claude's Discretion):** Metal frame enhances side heat transfer. Use `convection_h = 25.0 W/m²K` for the side boundary when DLED/ELED templates are applied (vs the default 3.0). This represents a metal-framed enclosure with moderate natural convection.

### Pattern 3: Architecture-Aware LED Arrays Panel

**What:** Replace the static table in `_build_led_arrays_tab()` with a `QStackedWidget` containing three panels: DLED config panel, ELED config panel, and the existing custom table. The architecture dropdown in `_build_top_controls()` drives the stack.

**Architecture dropdown placement:** Add to `_build_top_controls()` as a row above the existing row1. Connect to a new `_on_architecture_changed(arch: str)` method.

**DLED panel sub-widgets:**
- Grid config spinboxes: `count_x`, `count_y`, `pitch_x`, `pitch_y`, `power_per_led_w`
- Edge offset spinboxes: `offset_top`, `offset_bottom`, `offset_left`, `offset_right` (all in mm)
- Zone config: `zone_count_x`, `zone_count_y` spinboxes
- Zone power table: `QTableWidget` with `zone_count_x * zone_count_y` rows, columns "Zone (row, col)" + "Power [W]"
- LED footprint sub-group (shape, width, height, radius)

**ELED panel sub-widgets:**
- Edge selection: `QComboBox` with options "bottom", "top", "left/right", "all"
- `count_along_edge` spinbox, `pitch` spinbox, `edge_offset` spinbox
- LED footprint sub-group (shape, width, height, radius)

**Custom panel:** The existing `led_arrays_table` (unchanged).

**`_on_architecture_changed` behavior:**
1. Build the template for the selected arch using current panel width/height from spinboxes
2. Call `_populate_ui_from_project()` equivalent but only for layers, materials, led_arrays, boundaries
3. Do NOT push to undo stack (silent replacement per locked decision)
4. Do NOT confirm with dialog (silent replacement per locked decision)

### Pattern 4: Undo Stack Integration for New Spinboxes

**What:** The existing `_wire_table_undo()` handles table cells. The new DLED/ELED spinboxes are not tables. These spinboxes should NOT be individually undoable via the undo stack — the architecture switch itself is undoable as a macro (the whole template replacement is one macro).

**Why:** Per the locked decision, "switching architecture replaces the project silently (no confirmation dialog)." The simplest correct implementation: the architecture combo change triggers template application, and the undo stack is cleared after template application (same as `_populate_ui_from_project()` behavior). This matches how loading a project works — it clears the undo stack.

### Anti-Patterns to Avoid

- **Don't make `stack_templates.py` depend on PySide6:** It must be a pure Python model module so it is testable without a display.
- **Don't change `expand()` return type:** It must still return `list[HeatSource]`. The solver pipeline depends on `DisplayProject.expanded_heat_sources()` which calls `expand()`.
- **Don't add `architecture` field to `DisplayProject`:** The architecture is a GUI concept only. The JSON project format stores the resulting layers, materials, and LED arrays — not a named architecture. This keeps the file format simple and stable.
- **Don't add architecture to `DisplayProject.from_dict()`:** Projects loaded from disk are always displayed as "Custom" (the user's explicit configuration). Architecture dropdown is a creation/editing convenience, not a persistent property.
- **Don't forget `panel_width`/`panel_height` on LEDArray for edge mode:** Edge LED positions depend on panel dimensions. The template must set these when creating ELED arrays. When building the project from the ELED GUI panel, read current width/height spinboxes and inject into the LEDArray.
- **Don't wire LED arrays panel spinboxes to `_wire_table_undo()`:** Those spinboxes change when the panel mode switches — they should not create undo entries individually. Undo clears on template switch.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Zone power flat list → per-LED power lookup | Custom indexing | `zone_powers[iy_zone * zone_count_x + ix_zone]` simple index | Trivial once zone boundaries are computed |
| Edge LED positions | Custom geometry engine | numpy linspace pattern | `np.linspace(edge_offset, panel_width - edge_offset, count_x)` |
| Blocking signals during template population | Manual flag tracking | `table.blockSignals(True)` / `table.blockSignals(False)` | Already used throughout `_populate_ui_from_project()` — same pattern |
| QStackedWidget page switching | Custom show/hide logic | `QStackedWidget.setCurrentIndex(idx)` | PySide6 built-in, handles geometry correctly |

**Key insight:** The existing `_populate_ui_from_project()` method already does everything needed for template application — it blocks signals, clears the undo stack, and populates all tables. Template application is just calling it with a `DisplayProject` built from the template function.

---

## Common Pitfalls

### Pitfall 1: Zone Count vs Zone Power List Out of Sync
**What goes wrong:** User changes `zone_count_x` or `zone_count_y` spinboxes, zone table row count doesn't update, old zone power data has wrong length when `expand()` is called.
**Why it happens:** Spinbox value-changed signal not connected to zone table rebuild.
**How to avoid:** Connect `zone_count_x.valueChanged` and `zone_count_y.valueChanged` to a `_rebuild_zone_table()` method that resizes the table and preserves existing power values where rows still exist.
**Warning signs:** `expand()` silently falls back to `power_per_led_w` uniform — no error but thermal results are wrong.

### Pitfall 2: `LEDArray` with `mode="custom"` Has No `panel_width`/`panel_height`
**What goes wrong:** Old-style `LEDArray` objects (mode=custom) don't have panel dimensions. If `expand()` branches on mode and uses `panel_width` for grid mode, it must not fail for custom mode.
**How to avoid:** Use `center_x`/`center_y` grid math (existing behavior) for `mode="custom"`. Only use `panel_width`/`offset_*` math for `mode="grid"`. Guard with `if self.mode == "grid"`.

### Pitfall 3: Signal Cascade During Template Population
**What goes wrong:** Populating led_arrays spinboxes triggers `valueChanged` → `_rebuild_zone_table()` → updates zone table → `cellChanged` fires → `_on_cell_changed()` pushes undo commands — multiple spurious undo entries.
**How to avoid:** Wrap all template population in `blockSignals(True)` on all affected widgets, including the architecture combo itself. Restore signals only after all widgets are set. Pattern: same as `_populate_ui_from_project()` pattern for tables.

### Pitfall 4: Edge LED Positions Outside Panel Bounds
**What goes wrong:** ELED strip LEDs placed at positions beyond panel width/height. Solver distributes power to out-of-bounds mesh cells, which silently clips or gives wrong power density.
**Why it happens:** `edge_offset` larger than panel dimension, or `count_along_edge * pitch > usable_length`.
**How to avoid:** In `expand()`, assert or clamp all LED positions to `[0, panel_width]` and `[0, panel_height]`. Emit a warning if positions are clamped.

### Pitfall 5: Undo Stack Accumulates During Architecture Switch
**What goes wrong:** Architecture combo triggers template population, which changes many table cells. Each cell change creates an undo command — user presses Ctrl+Z and gets dozens of individual cell reverts instead of the whole architecture switch undoing.
**How to avoid:** Call `self._undo_stack.clear()` after template population completes, matching the behavior of `_populate_ui_from_project()`. This is consistent with the "silent replacement" locked decision.

### Pitfall 6: `to_dict()` / `from_dict()` Missing New Fields
**What goes wrong:** New LEDArray fields (`mode`, `zone_powers`, `edge_config`, etc.) are not serialized. Projects saved in DLED/ELED mode lose their zone config on reload.
**How to avoid:** Every new field in `LEDArray.__init__` must have a matching entry in `to_dict()` and a `.get(key, default)` in `from_dict()`. Test: serialize → deserialize → re-serialize, compare dicts.

---

## Code Examples

### DLED expand() — Grid with Zone Power and Edge Offsets

```python
# Source: thermal_sim/models/heat_source.py — expand() branch for mode="grid"

def expand(self) -> list[HeatSource]:
    if self.mode == "grid":
        return self._expand_grid()
    elif self.mode == "edge":
        return self._expand_edge()
    else:
        return self._expand_custom()  # existing behavior

def _expand_grid(self) -> list[HeatSource]:
    """DLED: 2D grid with edge offsets and zone-based power."""
    import numpy as np
    sources: list[HeatSource] = []

    usable_w = self.panel_width - self.offset_left - self.offset_right
    usable_h = self.panel_height - self.offset_bottom - self.offset_top
    x0 = self.offset_left + (usable_w - (self.count_x - 1) * self.pitch_x) / 2.0
    y0 = self.offset_bottom + (usable_h - (self.count_y - 1) * self.pitch_y) / 2.0

    n_zones_x = max(1, self.zone_count_x)
    n_zones_y = max(1, self.zone_count_y)
    has_zones = len(self.zone_powers) == n_zones_x * n_zones_y

    for iy in range(self.count_y):
        for ix in range(self.count_x):
            x = x0 + ix * self.pitch_x
            y = y0 + iy * self.pitch_y

            if has_zones:
                iz_x = min(int(ix * n_zones_x / self.count_x), n_zones_x - 1)
                iz_y = min(int(iy * n_zones_y / self.count_y), n_zones_y - 1)
                power = self.zone_powers[iz_y * n_zones_x + iz_x]
            else:
                power = self.power_per_led_w

            sources.append(HeatSource(
                name=f"{self.name}_r{iy + 1}_c{ix + 1}",
                layer=self.layer,
                power_w=power,
                shape=self.footprint_shape,
                x=x, y=y,
                width=self.led_width if self.footprint_shape == "rectangle" else None,
                height=self.led_height if self.footprint_shape == "rectangle" else None,
                radius=self.led_radius if self.footprint_shape == "circle" else None,
            ))
    return sources
```

### ELED expand() — Edge Strip

```python
def _expand_edge(self) -> list[HeatSource]:
    """ELED: one or more edge strips of discrete LEDs."""
    sources: list[HeatSource] = []
    edges_to_process: list[tuple[str, int]] = []  # (edge_name, count)

    if self.edge_config in ("bottom", "all"):
        edges_to_process.append(("bottom", self.count_x))
    if self.edge_config in ("top", "all"):
        edges_to_process.append(("top", self.count_x))
    if self.edge_config in ("left_right", "all"):
        edges_to_process.append(("left", self.count_y))
        edges_to_process.append(("right", self.count_y))

    for edge_name, count in edges_to_process:
        if edge_name == "bottom":
            xs = [self.panel_width / 2.0 + (i - (count - 1) / 2.0) * self.pitch_x
                  for i in range(count)]
            ys = [self.edge_offset] * count
        elif edge_name == "top":
            xs = [self.panel_width / 2.0 + (i - (count - 1) / 2.0) * self.pitch_x
                  for i in range(count)]
            ys = [self.panel_height - self.edge_offset] * count
        elif edge_name == "left":
            xs = [self.edge_offset] * count
            ys = [self.panel_height / 2.0 + (i - (count - 1) / 2.0) * self.pitch_y
                  for i in range(count)]
        else:  # right
            xs = [self.panel_width - self.edge_offset] * count
            ys = [self.panel_height / 2.0 + (i - (count - 1) / 2.0) * self.pitch_y
                  for i in range(count)]

        for idx, (x, y) in enumerate(zip(xs, ys)):
            sources.append(HeatSource(
                name=f"{self.name}_{edge_name}_{idx + 1}",
                layer=self.layer,
                power_w=self.power_per_led_w,
                shape=self.footprint_shape,
                x=x, y=y,
                width=self.led_width if self.footprint_shape == "rectangle" else None,
                height=self.led_height if self.footprint_shape == "rectangle" else None,
                radius=self.led_radius if self.footprint_shape == "circle" else None,
            ))
    return sources
```

### Architecture Dropdown + QStackedWidget Pattern

```python
# Source: thermal_sim/ui/main_window.py — _build_top_controls() extension

# Architecture combo (add to top controls)
self.arch_combo = QComboBox()
self.arch_combo.addItems(["Custom", "DLED", "ELED"])
self.arch_combo.setToolTip("Select display backlight architecture to auto-populate stack")
self.arch_combo.currentTextChanged.connect(self._on_architecture_changed)

# In _build_led_arrays_tab():
from PySide6.QtWidgets import QStackedWidget
self._led_arrays_stack = QStackedWidget()
self._led_arrays_stack.addWidget(self._build_custom_led_panel())   # index 0
self._led_arrays_stack.addWidget(self._build_dled_panel())          # index 1
self._led_arrays_stack.addWidget(self._build_eled_panel())          # index 2

def _on_architecture_changed(self, arch: str) -> None:
    index = {"Custom": 0, "DLED": 1, "ELED": 2}.get(arch, 0)
    self._led_arrays_stack.setCurrentIndex(index)
    if arch == "Custom":
        return  # no template — keep existing data
    # Apply template
    w = self.width_spin.value() / 1000.0
    h = self.height_spin.value() / 1000.0
    from thermal_sim.models.stack_templates import dled_template, eled_template
    if arch == "DLED":
        template_data = dled_template(w, h)
    else:
        template_data = eled_template(w, h)
    # Populate tables from template data
    # Block signals, populate, clear undo stack
    self._apply_template(template_data)
```

### Template Function Signature

```python
# Source: thermal_sim/models/stack_templates.py — new file

def dled_template(
    panel_width: float,    # metres
    panel_height: float,   # metres
    optical_layer_count: int = 2,
) -> dict:
    """
    Returns:
        {
            "layers": list[Layer],
            "materials": dict[str, Material],   # subset used by template
            "led_arrays": list[LEDArray],
            "boundaries": BoundaryConditions,
        }
    """
```

---

## Integration Points Summary

| What changes | Where | Impact |
|---|---|---|
| `LEDArray` new fields | `models/heat_source.py` | Must add to `to_dict()`, `from_dict()`, `__post_init__`, `expand()` |
| `LEDArray.expand()` branching | `models/heat_source.py` | Existing `mode="custom"` path must be unchanged |
| `stack_templates.py` | `models/stack_templates.py` | New file; no dependencies on PySide6 |
| Architecture dropdown | `ui/main_window.py` `_build_top_controls()` | New `QComboBox` wired to `_on_architecture_changed()` |
| LED Arrays tab becomes stacked | `ui/main_window.py` `_build_led_arrays_tab()` | `QStackedWidget` replaces single table; Custom panel = existing table |
| `_tables_dict` property | `ui/main_window.py` | Must still return `{"led_arrays": self.led_arrays_table}` for the custom panel; the DLED/ELED panels build `LEDArray` objects differently — directly from spinboxes in `_build_project_from_ui()` |
| `_build_project_from_ui()` | `ui/main_window.py` | Must branch on `arch_combo.currentText()` to parse DLED/ELED spinboxes vs the custom table |
| `validate_tables()` | `ui/table_data_parser.py` | Only validates the custom led_arrays_table — DLED/ELED panels are validated via `__post_init__` on construction |
| `populate_tables_from_project()` | `ui/table_data_parser.py` | Unchanged — fills the custom led_arrays_table from a project; when loading a project, arch stays "Custom" |

---

## Key Insight: Edge LED Board Layer in the 2.5D Model

The CONTEXT.md identifies the edge LED board representation as a discretion area. The 2.5D model is strictly layered in Z. An edge FPC/PCB cannot be stacked above the LGP — physically it is beside it. Three options:

1. **Treat it as a heat source on the LGP layer** (recommended): Add a `HeatSource` (shape="rectangle", covering the edge strip area) on the LGP layer. This is physically approximate but matches the 2.5D constraint — the LGP node at the edge receives the LED heat. The LEDArray with `mode="edge"` and `layer="LGP"` implements this naturally.

2. **Add a separate "Edge LED Board" layer** (physically correct, model-complex): Requires a full-width layer in the stack which wastes mesh resolution. Not recommended for this model fidelity.

3. **Ignore the LED board as a layer** (simplest): Just model the heat input into the LGP edge. The thin FPC thermal resistance is negligible at 2.5D resolution.

**Recommendation:** Use option 1 — `LEDArray(mode="edge", layer="LGP")`. The template does not add an "Edge LED Board" layer to the stack. Document this as a model approximation in tooltips.

---

## State of the Art (project-specific)

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Single static LED Arrays table | Architecture-aware QStackedWidget | Phase 6 | Tab becomes mode-dependent |
| `LEDArray` always 2D grid, center-based | `LEDArray` supports mode: grid/edge/custom | Phase 6 | Backward compatible via `mode="custom"` default |
| No stack presets | `stack_templates.py` | Phase 6 | Users get sensible starting points |
| No architecture concept in GUI | Architecture dropdown drives template | Phase 6 | Guided workflow for DLED/ELED |

---

## Open Questions

1. **Zone power table UI layout (Claude's Discretion)**
   - What we know: Zone grid is `zone_count_x * zone_count_y` cells. User sets power per zone.
   - What's unclear: Whether to show a visual 2D grid of zone power inputs vs a flat table with "Zone (row, col)" labels.
   - Recommendation: Use a flat `QTableWidget` with columns "Zone" (label like "Z1,1") and "Power [W]". Two columns, N rows. This is simpler to implement and avoids custom widget complexity. The zone visual layout can be inferred from column/row counts shown above the table.

2. **`_build_project_from_ui()` dual-path for DLED/ELED panels**
   - What we know: Current `_build_project_from_ui()` calls `TableDataParser.parse_led_arrays_table(tables_dict["led_arrays"])` for the custom table.
   - What's unclear: Whether to keep `tables_dict["led_arrays"]` pointing to the custom table always, and build DLED/ELED `LEDArray` objects directly from spinboxes outside `TableDataParser`.
   - Recommendation: Build `LEDArray` objects directly from spinboxes in a new private method `_build_led_arrays_from_arch_panel()` that `_build_project_from_ui()` calls instead of `parse_led_arrays_table()` when arch != Custom. `TableDataParser.parse_led_arrays_table()` remains unchanged.

---

## Sources

### Primary (HIGH confidence)
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/models/heat_source.py` — LEDArray class, expand() method, to_dict/from_dict pattern
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/ui/main_window.py` — _build_led_arrays_tab(), _build_top_controls(), _populate_ui_from_project(), _build_project_from_ui()
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/ui/table_data_parser.py` — parse_led_arrays_table(), populate_tables_from_project(), validate_tables()
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/models/project.py` — DisplayProject, expanded_heat_sources()
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/resources/materials_builtin.json` — all 15 available materials confirmed
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/core/material_library.py` — default_materials(), load_builtin_library()
- Direct source inspection: `G:/blu-thermal-simulation/thermal_sim/ui/structure_preview.py` — how expanded sources are rendered
- Direct source inspection: `G:/blu-thermal-simulation/tests/test_led_array.py` — existing test patterns to follow

### No External Sources Required
This phase involves no new library dependencies. All findings derive from the existing codebase.

---

## Metadata

**Confidence breakdown:**
- Model extension (LEDArray fields): HIGH — pattern is identical to existing optional fields in LEDArray
- Stack templates (layer/material defaults): HIGH — all materials exist in library; thickness defaults are Claude's Discretion backed by engineering judgment
- GUI architecture (QStackedWidget pattern): HIGH — PySide6 QStackedWidget is the standard widget for mode-switching panels
- Integration points: HIGH — traced through the complete call chain from architecture dropdown to solver
- Edge LED board representation: MEDIUM — the 2.5D limitation is real; the "heat on LGP" approximation is documented as an engineering tradeoff

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable project, no external library changes expected)
