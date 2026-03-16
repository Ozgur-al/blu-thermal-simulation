# Phase 10: Edge Layers and 3D Preview - Research

**Researched:** 2026-03-16
**Domain:** Data model extension (edge layers), zone generation geometry, PyVista/VTK Qt integration, PySide6 GUI patterns
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Edge definition model**
- Per-edge layer list: each edge (bottom, top, left, right) gets its own ordered list of lateral layers with material + thickness
- Per z-layer scope: edge layers are a property of a specific Layer in the z-stack (e.g., only the LGP gets edge structure; the diffuser above might have none)
- Auto-computed bulk: the central region (e.g., LGP bulk) is whatever remains after subtracting edge layer thicknesses from the panel dimensions. Error if edges exceed panel size
- "Copy from" button per edge to duplicate another edge's layer list for symmetric configs
- Serialized as `edge_layers` dict field on Layer: `{"bottom": [{"material": "Steel", "thickness": 0.003}, ...], ...}` — round-trips through JSON. Zones are generated at solve time only

**GUI workflow**
- Edge layer editor lives in the Layers tab, below the existing zone panel — appears when a layer row is selected
- Tab buttons for each edge (Bottom / Top / Left / Right), each showing a table of material + thickness rows with Add/Remove/Copy-from controls
- Edge layers and manual zones coexist: edge layers define the perimeter structure, manual zones overlay on top for partial features (PCB cards, copper traces). Manual zones win on overlap
- ELED architecture preset auto-populates the LGP layer's edge layers when ELED is selected from the dropdown (no separate Generate button)

**3D structure preview**
- Interactive 3D view using PyVista/VTK (new dependency)
- Rotation, pan, zoom with color-coded blocks per material and layer labels
- Explode slider that separates layers vertically for inspecting internal structure
- Two placements: (1) live dock panel that updates while editing layers/edges, (2) results tab showing the same 3D geometry with temperature data overlaid after solving
- Both views share the same 3D rendering logic

**Zone generation strategy**
- Edge layers are converted to MaterialZone rectangles internally — user never sees the generated rectangles in the zone table (fully transparent)
- Corner handling: when two edges meet, the corner square always gets the outermost material (typically Steel frame — physically accurate since frame corners are continuous metal)
- Edge-generated zones are prepended to the layer's zone list; manual zones come after and win on overlap (last-defined-wins, consistent with existing rasterizer behavior)

### Claude's Discretion
- PyVista/VTK widget integration with PySide6 (QtInteractor or BackgroundPlotter)
- Explode slider range and animation smoothness
- Edge layer table styling and sizing
- Default edge layer thicknesses for the ELED preset
- 3D colormap choice and material color mapping
- How the dock panel and results tab share the 3D rendering code

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EDGE-01 | Layer model supports `edge_layers` dict field with per-edge (bottom/top/left/right) ordered lists of lateral layers (material + thickness), serialized in project JSON | `Layer.to_dict()`/`from_dict()` pattern verified; `edge_layers` field added as dict[str, list[EdgeLayer]] using `.get()` for backward compat |
| EDGE-02 | Edge layers auto-generate MaterialZone rectangles at solve time; corners use outermost material; edge zones + manual zones coexist with manual winning on overlap | `_rasterize_zones()` already handles last-defined-wins; zone prepend strategy directly usable; corner geometry is pure arithmetic |
| EDGE-03 | ELED architecture selection auto-populates LGP layer edge layers with correct perimeter structure (frame+air+PCB on LED edges, frame+air on non-LED edges) | `_on_architecture_changed()` → `_apply_template()` → `_populate_ui_from_project()` chain is the correct hook; `eled_template()` already returns Layer objects that can carry `edge_layers` |
| VIS3D-01 | Interactive 3D view (PyVista/VTK) showing assembly as color-coded blocks with rotation, pan, zoom, and layer labels | pyvista 0.47.1 + pyvistaqt 0.11.3 confirmed; `QtInteractor` embeds as QWidget via `qtpy`; `QT_API=pyside6` env var routes to PySide6 |
| VIS3D-02 | Explode slider separates layers vertically for inspecting internal structure including edge layers | PyVista `PolyData` boxes + actor `position` mutation on slider callback; `QSlider` in PySide6 wired to plotter update |
| VIS3D-03 | 3D results view shows temperature data overlaid on assembly geometry after solving | PyVista point/cell data coloring; `add_mesh(scalars=...)` API; colormap via `cmap=` parameter; clim set from result min/max |
</phase_requirements>

---

## Summary

Phase 10 has two largely independent subsystems: (1) the `EdgeLayer` data model and zone generation logic, and (2) the PyVista-based 3D preview. Each can be planned and implemented in its own wave with no hard cross-dependency between them — the 3D view works with or without edge layers populated, and edge layers work without the 3D view.

The data model work (EDGE-01/02/03) is purely additive to existing Python dataclasses. `Layer` gets an `edge_layers` field; a new `EdgeLayer` dataclass holds `material` + `thickness`; a pure function `generate_edge_zones()` converts `edge_layers` to a list of `MaterialZone` rectangles at solve time. The existing `_rasterize_zones()` is unchanged — only the zone list fed to it changes. The GUI work follows the well-established `_layer_zones` / `_populate_*` / `_refresh_*` pattern already used for manual zones.

The 3D view (VIS3D-01/02/03) requires adding `pyvista>=0.47.1`, `pyvistaqt>=0.11.3`, and `qtpy>=2.4.2` as new dependencies. `pyvistaqt.QtInteractor` is a `QWidget` subclass that embeds the VTK render window directly into a PySide6 layout using `qtpy` as a binding abstraction; setting `QT_API=pyside6` (or auto-detecting PySide6) is sufficient. The render model for this project is simple: one `pyvista.Box` per (layer × material zone) with color-coded actors. Explode is implemented by translating actors in z on slider change. Temperature overlay maps scalar arrays onto the same geometry.

**Primary recommendation:** Implement in three waves — Wave 1: EdgeLayer model + zone generation + tests (no GUI); Wave 2: Edge layer editor GUI + ELED auto-populate; Wave 3: PyVista 3D dock + results overlay. The PyInstaller spec will need VTK hook additions.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyvista | >=0.47.1 (latest: 0.47.1) | High-level VTK wrapper for mesh/geometry creation and rendering | Decided in CONTEXT.md; wraps raw VTK API cleanly; Python-native |
| pyvistaqt | >=0.11.3 (latest: 0.11.3) | `QtInteractor` QWidget for embedding VTK in Qt app | The standard Qt integration for pyvista; uses `qtpy` abstraction |
| qtpy | >=2.4.2 | Qt binding abstraction layer (routes to PySide6 when `QT_API=pyside6`) | Required by pyvistaqt; supports PySide6 natively |
| vtk | >=9.2.2, !=9.4.0, !=9.4.1, <9.7.0 | Low-level VTK rendering engine | Pulled in automatically by pyvista as a dependency |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PySide6 | >=6.7 (6.10.2 installed) | Qt widgets for edge layer editor UI (QTabWidget, QTableWidget, QSlider) | All new GUI code |
| numpy | >=1.26 | Zone coordinate arithmetic for edge→zone conversion | In generate_edge_zones() |
| pytest | >=8.0 | Unit tests for edge layer model and zone generation | Test wave for EDGE-01/02 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyvistaqt.QtInteractor | matplotlib 3D (mpl_toolkits.mplot3d) | Matplotlib has no interactive rotation of solid blocks without workarounds; VTK is the right tool for this |
| pyvistaqt.QtInteractor | vedo (VTK wrapper) | vedo is less maintained and less common for Qt embedding; pyvistaqt is the established Qt wrapper |
| pyvistaqt.QtInteractor | pyqtgraph GLViewWidget | GLViewWidget uses OpenGL directly but lacks VTK's solid-block rendering quality |

**Installation:**
```bash
pip install "pyvista>=0.47.1" "pyvistaqt>=0.11.3" "qtpy>=2.4.2"
```

Then add to `requirements.txt`:
```
pyvista>=0.47.1
pyvistaqt>=0.11.3
qtpy>=2.4.2
```

---

## Architecture Patterns

### Recommended Project Structure

```
thermal_sim/
├── models/
│   ├── layer.py           # Add edge_layers field + EdgeLayer dataclass
│   └── stack_templates.py # eled_template() returns LGP with edge_layers; add generate_edge_zones()
├── solvers/
│   └── network_builder.py # build_thermal_network(): call generate_edge_zones() before rasterize
├── ui/
│   ├── main_window.py     # Add edge layer sub-panel below zone panel; wire ELED auto-populate
│   └── assembly_3d.py     # NEW: Assembly3DWidget (QWidget containing QtInteractor)
tests/
├── test_edge_layers.py    # Unit: EdgeLayer model, generate_edge_zones(), corner logic
└── test_assembly_3d.py    # Smoke: widget instantiates without crash (offscreen mode)
```

### Pattern 1: EdgeLayer Dataclass (follows MaterialZone frozen pattern)

**What:** A frozen dataclass with `material: str` and `thickness: float`, following the `to_dict()`/`from_dict()` pattern already used for `MaterialZone` and `Material`.

**When to use:** Everywhere an individual lateral layer slice is stored (inside `Layer.edge_layers`).

```python
# thermal_sim/models/layer.py
@dataclass(frozen=True)
class EdgeLayer:
    """One lateral layer slice on an edge (material + thickness in metres)."""
    material: str
    thickness: float

    def __post_init__(self) -> None:
        if not self.material.strip():
            raise ValueError("EdgeLayer material must not be empty.")
        if self.thickness <= 0.0:
            raise ValueError(f"EdgeLayer thickness must be > 0, got {self.thickness}.")

    def to_dict(self) -> dict:
        return {"material": self.material, "thickness": self.thickness}

    @classmethod
    def from_dict(cls, data: dict) -> "EdgeLayer":
        return cls(material=data["material"], thickness=float(data["thickness"]))
```

### Pattern 2: Layer.edge_layers Field with Backward-Compat Serialization

**What:** Add `edge_layers: dict[str, list[EdgeLayer]]` to `Layer`. The `to_dict()` omits the key when empty (consistent with existing `zones` behavior). `from_dict()` uses `.get("edge_layers", {})`.

```python
# In Layer.to_dict():
if self.edge_layers:
    d["edge_layers"] = {
        edge: [el.to_dict() for el in layers]
        for edge, layers in self.edge_layers.items()
    }

# In Layer.from_dict():
edge_layers_raw = data.get("edge_layers", {})
edge_layers = {
    edge: [EdgeLayer.from_dict(el) for el in lst]
    for edge, lst in edge_layers_raw.items()
}
```

### Pattern 3: generate_edge_zones() — Pure Function (no GUI dependency)

**What:** Converts `edge_layers` dict + panel dimensions to a list of `MaterialZone` rectangles. Called in `build_thermal_network()` before rasterization. Follows `generate_eled_zones()` pattern but generalized to all 4 edges.

**Corner handling algorithm:**
- bottom edge zones span full panel width (x: 0→W)
- top edge zones span full panel width (x: 0→W)
- left/right edge zones span only the bulk height (y: bottom_thickness → H - top_thickness)
- Corner cells are filled by bottom/top zones that extend full width — this gives the outermost material (frame) at corners

Actually the geometric approach is:
1. Compute `bottom_total` = sum of bottom edge layer thicknesses
2. Compute `top_total` = sum of top edge layer thicknesses
3. Compute `left_total` = sum of left edge layer thicknesses
4. Compute `right_total` = sum of right edge layer thicknesses
5. Validate `left_total + right_total < panel_width` and `bottom_total + top_total < panel_height`
6. Bottom zones: full-width rectangles stacked from y=0 upward
7. Top zones: full-width rectangles stacked from y=H downward
8. Left zones: rectangles from x=0, height = H - bottom_total - top_total, y starting at bottom_total
9. Right zones: same, from x=W right edge
10. Bulk zone: LGP base material fills remaining center (optional explicit zone not needed — `_rasterize_zones` falls back to layer.material for uncovered cells)

This gives physically correct corners: bottom/top full-width zones cover corners.

### Pattern 4: QtInteractor Embedding in PySide6

**What:** `pyvistaqt.QtInteractor` is a `QWidget` subclass. Embed it like any other widget. Use `QT_API=pyside6` environment variable before importing `qtpy`.

```python
# thermal_sim/ui/assembly_3d.py
import os
os.environ.setdefault("QT_API", "pyside6")  # must be before qtpy import

from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSlider, QLabel
from PySide6.QtCore import Qt
import pyvista as pv

class Assembly3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter)
        # Explode slider
        self._explode_slider = QSlider(Qt.Orientation.Horizontal)
        self._explode_slider.setRange(0, 100)
        self._explode_slider.valueChanged.connect(self._on_explode)
        layout.addWidget(self._explode_slider)
        self._actors = []  # list of (actor, base_z)
```

**Key detail:** `pyvistaqt.QtInteractor` uses `qtpy` which detects PySide6 when `QT_API=pyside6`. Without this env var, if only PySide6 is installed, qtpy will auto-detect it. But setting it explicitly is safer for PyInstaller bundling.

### Pattern 5: Color-Coded Block Assembly

**What:** Build one `pv.Box` per layer × zone region. Color by material using a discrete colormap. Store actors with their base z-position for explode slider.

```python
import pyvista as pv
import numpy as np

def build_assembly_mesh(project, explode_factor=0.0):
    """Build pyvista PolyData list for each layer block."""
    material_colors = _assign_material_colors(project)
    actors_data = []
    z_base = 0.0
    for layer in project.layers:
        z_offset = z_base + explode_factor * layer_index  # explode
        # Main bulk block
        box = pv.Box(bounds=[0, W, 0, H, z_offset, z_offset + layer.thickness])
        actors_data.append({"mesh": box, "color": material_colors[layer.material]})
        # Zone blocks (edge zones + manual zones) overlay as separate meshes
        ...
        z_base += layer.thickness
    return actors_data
```

### Pattern 6: Temperature Scalar Overlay (VIS3D-03)

**What:** After solving, map temperature array onto each layer's block geometry using `plotter.add_mesh(mesh, scalars=temps, cmap="hot")`. Temperature arrays are reshaped from solver output `result.temperatures_c[layer_idx]`.

```python
# Flatten 2D temp map to match grid points
temps_flat = result.temperatures_c[layer_idx].flatten()
# Create structured grid matching layer geometry
grid = pv.ImageData(
    dimensions=(nx+1, ny+1, 2),
    spacing=(dx, dy, thickness),
    origin=(0, 0, z_base),
)
grid.cell_data["temperature"] = temps_flat
plotter.add_mesh(grid, scalars="temperature", cmap="hot", clim=(t_min, t_max))
```

### Anti-Patterns to Avoid

- **Storing generated edge zones in `_layer_zones`:** Edge zones are internal; the zone table only shows user-defined manual zones. Merging happens in `build_thermal_network()`, not in the GUI.
- **Importing pyvistaqt at module level in main_window.py:** VTK loads many DLLs — delay import until the 3D widget is first shown to keep startup time fast.
- **Calling `plotter.show()` in embedded mode:** `QtInteractor` handles its own render loop; never call `.show()` — it opens a blocking separate window.
- **Mixing qtpy and PySide6 imports in Assembly3DWidget:** Use PySide6 directly for the surrounding widget code; only pyvistaqt internals use qtpy. Don't `from qtpy import ...` in project code.
- **Applying explode via mesh recreation:** Recreate meshes on every slider tick is slow; instead cache actors and translate their `position` property.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 3D block rendering with rotation/zoom | Custom OpenGL in QOpenGLWidget | pyvistaqt.QtInteractor | VTK handles backface culling, lighting, interaction modes, picking — weeks of work to replicate |
| VTK Qt event loop integration | Manual QTimer + vtkRenderWindowInteractor | pyvistaqt | pyvistaqt solves the VTK/Qt event loop conflict that makes vanilla VTK+Qt fragile |
| Corner zone geometry | Polygon clipping library | Simple full-width rectangle stacking | Bottom/top edges span full width naturally; corners are covered without any clipping math |
| Material colormap | Custom color assignment | `matplotlib.colormaps["tab20"]` (already used in structure_preview.py) or pyvista's built-in discrete coloring | Consistent with existing codebase pattern |

**Key insight:** The most complex part of the 3D view is VTK/Qt event loop integration. pyvistaqt exists specifically to solve this — it monkey-patches `BasePlotter.__init__` to work around Qt widget initialization order conflicts that are extremely hard to fix manually.

---

## Common Pitfalls

### Pitfall 1: QT_API Auto-Detection Race Condition
**What goes wrong:** When pyvistaqt is first imported, qtpy reads `QT_API`. If PySide6 is not the only Qt binding available, or if qtpy loads before `QT_API` is set, it may pick a different binding (PyQt5 if installed, though unlikely here).
**Why it happens:** qtpy detects installed bindings at import time; once set, it cannot be changed.
**How to avoid:** Set `os.environ["QT_API"] = "pyside6"` at the top of `assembly_3d.py`, before any pyvistaqt or qtpy import. The `setdefault` form is safe even if already set.
**Warning signs:** `ImportError: cannot import name 'Signal' from 'qtpy.QtCore'` or mixing errors.

### Pitfall 2: VTK DLL Loading in PyInstaller Bundle
**What goes wrong:** VTK ships many DLLs that PyInstaller's static analysis misses. The bundled `.exe` crashes on launch with "VTK not found" or missing `.pyd` errors.
**Why it happens:** VTK uses lazy loading and `__init__.py` tricks that PyInstaller can't follow.
**How to avoid:** Add `collect_all("pyvista")`, `collect_all("pyvistaqt")`, `collect_all("vtkmodules")` hooks to `ThermalSim.spec`. Also add `"vtkmodules.all"` to `hiddenimports`. This adds ~80-120 MB to the bundle.
**Warning signs:** Works in dev, crashes in dist. Check crash.log (already present in repo for a past crash).

### Pitfall 3: Edge Zone Corner Overlap with Manual Zones
**What goes wrong:** If a manual zone and an edge-generated zone occupy the same cell, the wrong material wins.
**Why it happens:** Zone list order in `_rasterize_zones` is last-defined-wins. If edge zones are appended after manual zones instead of prepended, edge zones win instead of manual zones.
**How to avoid:** In `build_thermal_network()`, prepend edge-generated zones: `all_zones = generate_edge_zones(layer, project) + list(layer.zones)` then pass `all_zones` to rasterization. Manual zones (in `layer.zones`) come last and win.

### Pitfall 4: Edge Layer Thickness Exceeds Panel Dimension
**What goes wrong:** If `left_total + right_total >= panel_width` or `bottom_total + top_total >= panel_height`, the bulk region has zero or negative size, and `MaterialZone` creation fails (width/height <= 0 validation).
**Why it happens:** User entered overlarge thicknesses without noticing constraints.
**How to avoid:** Validate in `generate_edge_zones()` (same pattern as existing `generate_eled_zones()` overflow check). Also add inline validation in the edge layer table — highlight cells red if sum exceeds panel dimension (consistent with Phase 4 PLSH-03 inline validation pattern).

### Pitfall 5: Layer.edge_layers Not Initialized for All Existing Layers
**What goes wrong:** Old project JSON files don't have `edge_layers` field. `from_dict()` fails or returns None.
**Why it happens:** Backward compat not handled.
**How to avoid:** `from_dict()` uses `data.get("edge_layers", {})` (empty dict = no edge layers). `Layer.__post_init__` accepts an empty dict. `to_dict()` omits `edge_layers` key entirely when dict is empty (same pattern as `zones` field).

### Pitfall 6: QtInteractor.close() Must Be Called on Widget Destroy
**What goes wrong:** When the dock widget containing `QtInteractor` is closed/deleted, VTK's render window keeps a reference that prevents Python GC, leaking GPU memory.
**Why it happens:** VTK objects hold circular C++ references.
**How to avoid:** Connect `closeEvent` or `destroyed` signal to `self.plotter.close()` (same pattern used in `StructurePreviewDialog.closeEvent`).

---

## Code Examples

Verified patterns from existing codebase and pyvistaqt source:

### Edge Zone Generation Corner Algorithm
```python
# thermal_sim/models/stack_templates.py (new function)
def generate_edge_zones(
    layer: "Layer",
    panel_width: float,
    panel_height: float,
) -> list[MaterialZone]:
    """Convert layer.edge_layers to MaterialZone rectangles.

    Corner strategy: bottom/top zones span full panel width.
    Left/right zones span only the interior height (after bottom/top).
    This means bottom/top outermost material fills corners.
    """
    el = layer.edge_layers  # dict[str, list[EdgeLayer]]
    zones = []

    bottom_layers = el.get("bottom", [])
    top_layers = el.get("top", [])
    left_layers = el.get("left", [])
    right_layers = el.get("right", [])

    bottom_total = sum(e.thickness for e in bottom_layers)
    top_total = sum(e.thickness for e in top_layers)
    left_total = sum(e.thickness for e in left_layers)
    right_total = sum(e.thickness for e in right_layers)

    if left_total + right_total >= panel_width:
        raise ValueError(...)
    if bottom_total + top_total >= panel_height:
        raise ValueError(...)

    # Bottom zones: full-width strips from y=0 upward
    y = 0.0
    for el_layer in bottom_layers:
        zones.append(MaterialZone(
            material=el_layer.material,
            x=panel_width / 2.0, y=y + el_layer.thickness / 2.0,
            width=panel_width, height=el_layer.thickness,
        ))
        y += el_layer.thickness

    # Top zones: full-width strips from y=H downward
    y = panel_height
    for el_layer in top_layers:
        zones.append(MaterialZone(
            material=el_layer.material,
            x=panel_width / 2.0, y=y - el_layer.thickness / 2.0,
            width=panel_width, height=el_layer.thickness,
        ))
        y -= el_layer.thickness

    # Left zones: interior height only
    interior_y0 = bottom_total
    interior_height = panel_height - bottom_total - top_total
    x = 0.0
    for el_layer in left_layers:
        zones.append(MaterialZone(
            material=el_layer.material,
            x=x + el_layer.thickness / 2.0,
            y=interior_y0 + interior_height / 2.0,
            width=el_layer.thickness, height=interior_height,
        ))
        x += el_layer.thickness

    # Right zones: interior height only
    x = panel_width
    for el_layer in right_layers:
        zones.append(MaterialZone(
            material=el_layer.material,
            x=x - el_layer.thickness / 2.0,
            y=interior_y0 + interior_height / 2.0,
            width=el_layer.thickness, height=interior_height,
        ))
        x -= el_layer.thickness

    return zones
```

**Important:** `MaterialZone` uses center coordinates (x, y are center, not corner). See `material_zone.py` — the rasterizer computes `sx0 = zone.x - zone.width/2.0`.

### build_thermal_network() Integration Point
```python
# In network_builder.py, before calling _rasterize_zones:
from thermal_sim.models.stack_templates import generate_edge_zones

# Merge edge zones + manual zones (edge first = manual wins on overlap)
if layer.edge_layers:
    edge_zones = generate_edge_zones(layer, project.width, project.height)
    effective_zones = edge_zones + list(layer.zones)
else:
    effective_zones = list(layer.zones)

# Pass effective_zones to rasterization instead of layer.zones directly
# NOTE: _rasterize_zones takes a Layer; either wrap in a temp dataclass.replace()
# or refactor _rasterize_zones to accept a zones list directly
import dataclasses
layer_with_merged = dataclasses.replace(layer, zones=effective_zones)
k_ip, k_th, d_cp = _rasterize_zones(layer_with_merged, project.materials, grid)
```

### QtInteractor Minimal Embed
```python
import os
os.environ.setdefault("QT_API", "pyside6")

from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QWidget, QVBoxLayout

class Assembly3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = QtInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plotter)

    def closeEvent(self, event):
        self._plotter.close()
        super().closeEvent(event)

    def update_assembly(self, project):
        self._plotter.clear()
        # Add blocks...
        self._plotter.reset_camera()
        self._plotter.render()
```

### ELED Default Edge Layers for LGP
The existing `eled_template()` creates an LGP Layer with no edge_layers. Phase 10 extends it to return a Layer with edge_layers populated. CONTEXT.md specifies:
- LED edges (e.g., left/right for `edge_config="left_right"`): frame 3mm + air 1mm + PCB+LED 5mm
- Non-LED edges (bottom/top): frame 3mm + air 1mm

```python
# In eled_template(), for the LGP layer:
from thermal_sim.models.layer import EdgeLayer

frame = 0.003   # 3mm
air = 0.001     # 1mm
pcb_led = 0.005 # 5mm

led_edge = [
    EdgeLayer("Steel", frame),
    EdgeLayer("Air Gap", air),
    EdgeLayer("FR4", pcb_led),
]
non_led_edge = [
    EdgeLayer("Steel", frame),
    EdgeLayer("Air Gap", air),
]

# edge_config maps to which edges have LEDs
edge_layers_by_config = {
    "left_right": {"left": led_edge, "right": led_edge, "bottom": non_led_edge, "top": non_led_edge},
    "bottom":     {"bottom": led_edge, "top": non_led_edge, "left": non_led_edge, "right": non_led_edge},
    "top":        {"top": led_edge, "bottom": non_led_edge, "left": non_led_edge, "right": non_led_edge},
    "all":        {"bottom": led_edge, "top": led_edge, "left": led_edge, "right": led_edge},
}

lgp_layer = Layer(
    name="LGP", material="PMMA", thickness=0.004,
    edge_layers=edge_layers_by_config.get(edge_config, {}),
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual zone entry for ELED cross-section (Phase 9 Plan 03) | Edge layer stacking abstraction (this phase) | 2026-03-16 (redesign decision) | User never sees generated rectangles; perimeter defined at higher abstraction |
| No 3D preview (structure_preview.py is 2D matplotlib) | PyVista 3D interactive blocks | Phase 10 | Engineers can rotate/inspect assembly; explode reveals internal layers |
| generate_eled_zones() with 6 spinboxes UI | edge_layers dict on Layer model + auto-populate on ELED select | Phase 10 | Declarative per-edge structure; works for all 4 edges without UI spinbox proliferation |

**Deprecated/outdated:**
- `generate_eled_zones()`: This function is superseded by `generate_edge_zones()` for new ELED use cases. However, it remains in `stack_templates.py` for backward compat (existing projects that manually placed ELED zones still round-trip correctly). The ELED panel spinboxes and "Generate Zones" button are removed/replaced by the new edge layer editor.

---

## Open Questions

1. **Should `_rasterize_zones` be refactored to accept a zones list, or use `dataclasses.replace`?**
   - What we know: `_rasterize_zones` takes a `Layer` object; the merged zones list is built in `build_thermal_network`
   - What's unclear: refactor risk vs. `dataclasses.replace` overhead per layer per solve call
   - Recommendation: Use `dataclasses.replace(layer, zones=merged_zones)` — zero-risk, negligible overhead for typical layer counts (<20), consistent with the Phase 8 pattern already using `dataclasses.replace` in tests

2. **PyInstaller VTK bundle size and hook strategy**
   - What we know: VTK requires `collect_all("vtkmodules")` hooks; adds ~80-120 MB to dist
   - What's unclear: exact hooks needed; whether PyInstaller `pyinstaller-hooks-contrib` already has pyvista/vtkmodules hooks
   - Recommendation: Check `pyinstaller-hooks-contrib` version for vtkmodules hook availability before writing custom hooks; defer bundle testing to the plan that adds the PyInstaller spec changes

3. **Edge layer `_layer_edge_layers` dict in GUI (mirror of `_layer_zones`)**
   - What we know: `_layer_zones` uses `dict[int, list[dict]]` keyed by layer row index
   - What's unclear: whether edge layers should follow identical dict pattern or hold typed `EdgeLayer` objects
   - Recommendation: Use `dict[int, dict[str, list[dict]]]` (layer_row → edge_name → list of {material, thickness} dicts in mm for display) — mirrors `_layer_zones` pattern exactly, avoids introducing a new type into the GUI layer

4. **Whether `generate_edge_zones` belongs in `stack_templates.py` or a new `edge_layers.py` module**
   - What we know: `generate_eled_zones()` is in `stack_templates.py`; the test file is `test_eled_zones.py`
   - What's unclear: will module grow large enough to warrant splitting
   - Recommendation: Keep in `stack_templates.py` for this phase — the new function is ~50 lines; split later if needed

---

## Validation Architecture

**Note:** `workflow.nyquist_validation` is not present in `.planning/config.json` — the key does not exist so this section is included using the standard research approach.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none (pytest auto-discovers `tests/`) |
| Quick run command | `py -m pytest tests/test_edge_layers.py -q` |
| Full suite command | `py -m pytest -q tests` |

Current test count: 207 tests.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDGE-01 | `EdgeLayer` dataclass round-trips to/from dict; `Layer.edge_layers` serializes correctly; backward compat with old JSON (no edge_layers key) | unit | `py -m pytest tests/test_edge_layers.py::test_edge_layer_roundtrip -x` | ❌ Wave 0 |
| EDGE-01 | `Layer.from_dict` with missing `edge_layers` key uses empty dict default | unit | `py -m pytest tests/test_edge_layers.py::test_layer_backward_compat_no_edge_layers -x` | ❌ Wave 0 |
| EDGE-02 | `generate_edge_zones()` returns correct zones for symmetric 4-edge config; corners use outermost material | unit | `py -m pytest tests/test_edge_layers.py::test_generate_edge_zones_symmetric -x` | ❌ Wave 0 |
| EDGE-02 | `generate_edge_zones()` raises ValueError when edge widths exceed panel dimension | unit | `py -m pytest tests/test_edge_layers.py::test_generate_edge_zones_overflow -x` | ❌ Wave 0 |
| EDGE-02 | Edge zones prepended to manual zones; manual zone material wins on overlap in solved result | integration | `py -m pytest tests/test_edge_layers.py::test_edge_zone_manual_zone_coexistence -x` | ❌ Wave 0 |
| EDGE-03 | `eled_template()` with `edge_config="left_right"` returns LGP with correct edge_layers populated | unit | `py -m pytest tests/test_stack_templates.py::test_eled_template_edge_layers_populated -x` | ❌ add to existing file |
| VIS3D-01 | `Assembly3DWidget` instantiates without crash in offscreen mode | smoke | `py -m pytest tests/test_assembly_3d.py::test_widget_instantiates_offscreen -x` | ❌ Wave 0 |
| VIS3D-02 | Explode slider callback changes actor z-positions | unit | `py -m pytest tests/test_assembly_3d.py::test_explode_translates_actors -x` | ❌ Wave 0 |
| VIS3D-03 | Temperature scalars are applied to mesh actors after solve | unit | `py -m pytest tests/test_assembly_3d.py::test_temperature_overlay -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `py -m pytest tests/test_edge_layers.py -q`
- **Per wave merge:** `py -m pytest -q tests`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_edge_layers.py` — covers EDGE-01, EDGE-02, EDGE-03 unit/integration tests
- [ ] `tests/test_assembly_3d.py` — covers VIS3D-01/02/03 smoke tests (requires pyvista offscreen rendering)
- [ ] Framework install: `pip install "pyvista>=0.47.1" "pyvistaqt>=0.11.3" "qtpy>=2.4.2"` — required before Wave 1

---

## Sources

### Primary (HIGH confidence)
- PyPI pyvista 0.47.1 metadata — confirmed version, dependencies (vtk, numpy, matplotlib, pillow, etc.), Python >=3.10 requirement
- PyPI pyvistaqt 0.11.3 metadata + pyproject.toml — confirmed `pyvista>=0.39.0` + `QtPy>=1.9.0` dependencies; Python >=3.10
- pyvistaqt source `plotting.py` (GitHub main) — confirmed uses `from qtpy import ...` throughout; `QtInteractor` is a `QWidget` subclass; `BackgroundPlotter` is for standalone windows (not embedded use)
- qtpy README (GitHub master) — confirmed PySide6 support via `QT_API=pyside6`; supports Python 3.10+
- Existing codebase `thermal_sim/models/layer.py`, `material_zone.py`, `stack_templates.py` — confirmed exact serialization patterns, `frozen=True` dataclass pattern, `generate_eled_zones()` implementation
- Existing codebase `thermal_sim/solvers/network_builder.py` — confirmed `_rasterize_zones` signature and last-defined-wins zone behavior
- Existing codebase `ThermalSim.spec` — confirmed PyInstaller configuration, existing exclusions, `collect_data_files` pattern

### Secondary (MEDIUM confidence)
- PyPI vtk 9.6.0 available — consistent with pyvista's `vtk>=9.2.2, <9.7.0` constraint
- pyvistaqt docs reference to `QtInteractor` and `BackgroundPlotter` — confirmed from source code inspection

### Tertiary (LOW confidence)
- VTK PyInstaller bundle size estimate (~80-120 MB) — from general knowledge; not verified against exact pyvista 0.47.1 + vtk 9.6.0 build
- `collect_all("vtkmodules")` as the correct PyInstaller hook — not verified against pyinstaller-hooks-contrib version; recommend checking at implementation time

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified from PyPI metadata and source
- Architecture: HIGH — patterns derived from existing codebase (same serialization, same zone rasterization)
- Pitfalls: HIGH for backward compat and zone ordering; MEDIUM for PyInstaller VTK bundling (size estimate LOW)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (pyvista/pyvistaqt are stable; 30-day window)
