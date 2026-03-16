# Phase 12: Parametric Display Stack Generator - Research

**Researched:** 2026-03-16
**Domain:** PySide6 QWizard, block geometry generation, VoxelProject assembly
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Wizard structure
- Sequential QWizard with step-by-step pages: Architecture → Panel dims → LED config → Layer thicknesses → BCs → Mesh → Generate
- Back/Next/Finish navigation
- Live 3D preview panel on the right side of the wizard — updates as parameters change
- Accessible via toolbar button + File menu entry ("Generate Display Stack")
- On Finish: replaces all existing blocks in the block editor (clean slate)

#### ELED cross-section (front to back)
1. Panel (LCD)
2. Optical Films (N per-film table: material + thickness)
3. LGP (PMMA)
4. Reflector
5. Metal Frame — tray/border shape with side walls wrapping around the stack perimeter
6. Back Cover
- Air fills gaps between frame side walls and inner components
- LEDs on FR4 PCB adhered to metal frame at selected edges (at LGP z-level)

#### DLED cross-section (front to back)
1. Panel (LCD)
2. Optical Films (N per-film table: material + thickness)
3. Diffuser Plate
4. Air gap (LED cavity)
5. LED array on PCB (LEDs face forward toward diffuser)
6. PCB
7. Reflector
8. Metal Frame — same tray/border shape as ELED
9. Back Cover

#### Layer thickness configuration
- All layers configurable with sensible defaults pre-filled
- Optical films: count spinner + per-film mini-table (each film has its own material and thickness)
- Example defaults: Panel=1.5mm, LGP=4mm, Metal Frame=3mm, PCB=1.6mm, Reflector=0.3mm, Back Cover=1mm

#### LED placement — ELED
- 4 checkboxes for top/bottom/left/right edges
- Per-edge configuration table: each selected edge gets its own row with count, LED width, LED height, LED depth, power per LED
- Uniform pitch auto-calculated: pitch = usable_length / count
- Symmetric offset/margin from both ends of the edge (user-configurable, LEDs distribute within remaining span)

#### LED placement — DLED
- Grid layout: Rows × Columns
- X pitch and Y pitch (mm)
- Symmetric offset from panel edges
- LED dimensions (width, depth, height) and power per LED

#### Boundary conditions
- Preset-based: Natural convection (h=8), Forced air (h=25), Enclosed still air (h=3), Custom
- Per-face assignment in the wizard (top, bottom, front, back, left, right — each face gets its own preset/override)
- Ambient temperature field
- Include radiation checkbox
- h override field per face

#### Mesh configuration
- max_cell_size default: 2mm (hardcoded default in wizard)
- cells_per_interval: 1 (default)
- Show in wizard as a configuration step, user can adjust
- max_cell_size UI control also needs to be added to the block editor's Mesh tab (currently missing)

### Claude's Discretion
- LED naming convention (e.g. LED-L-0, LED-R-0, LED-Grid-R2C3)
- PCB block sizing relative to LEDs (how much wider/deeper than the LED row)
- Frame wall thickness default
- Air gap sizing between frame walls and inner components
- Wizard page layout and spacing details
- Material defaults for each layer type (which builtin material to pre-select)
- Estimated cell count display (nice-to-have)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 12 builds a QWizard-based parametric generator that converts high-level display module parameters (architecture, panel dimensions, LED count/dims/power, layer thicknesses, BCs, mesh settings) into a complete `VoxelProject` with all `AssemblyBlock` objects populated. The wizard then calls `BlockEditorWidget.load_project()` to replace the current editor state. The core technical challenge is the block geometry computation engine — specifically the tray-shaped metal frame (back plate + 4 side walls as separate blocks with air fill blocks inside), per-edge ELED LED placement with uniform pitch, and DLED grid layout. The live 3D preview during the wizard requires computing a preview `VoxelProject` on each page change and calling `Voxel3DView.update_structure()` inside the wizard.

The wizard also needs to expose `max_cell_size` in the block editor's Mesh tab, which is already implemented in the backend model (`VoxelMeshConfig.max_cell_size`) and already partially in the editor (`_max_cell_size_spin` exists in `BlockEditorWidget`). Inspection confirms `_max_cell_size_spin` IS already present (lines 246–258 of block_editor.py), so the "Mesh tab UI control" work may only be verifying it is visible and wired. The wizard's Mesh page sets the same default (2mm).

The geometry logic is pure Python arithmetic — no external library needed. The primary risks are: (1) frame tray geometry correctness (4 wall blocks must exactly fill the gap between inner content and outer frame boundary without overlaps); (2) ELED LED-PCB placement at the LGP z-level with correct x/y/z positioning relative to the frame walls; (3) ensuring the live preview does not block the GUI thread.

**Primary recommendation:** Implement a pure-Python `StackGenerator` class (no GUI imports) with `generate_dled(params)` and `generate_eled(params)` functions returning `VoxelProject`. The wizard pages are thin UI wrappers that call these functions. This separates geometry logic from UI and makes it unit-testable.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6.QtWidgets.QWizard | (project's PySide6) | Multi-page step-by-step dialog | Qt standard; Back/Next/Finish navigation built in |
| PySide6.QtWidgets.QWizardPage | (same) | Individual step container | Each page is a QWizardPage subclass |
| PySide6.QtWidgets.QTableWidget | (same) | Per-film / per-edge tables | Already used throughout codebase |
| VoxelProject / AssemblyBlock | (project internal) | Output model | All block data lives here |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Voxel3DView | (project internal) | Live preview widget embedded in wizard | Embedded in wizard right panel |
| `_mm()` / `_m()` | (project internal) | Unit conversion | All wizard inputs in mm, geometry in SI |
| `load_builtin_library()` | (project internal) | Pre-populate material combos | Wizard page material dropdowns |
| `QDoubleSpinBox` | PySide6 | Numeric input | All thickness/size/power inputs |
| `QComboBox` | PySide6 | Material selector, BC preset selector | Per-layer material, per-face BC preset |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| QWizard | Custom QDialog with manual step tracking | QWizard provides built-in page history, Back/Next/Finish, registerField() for inter-page data |
| Embedded Voxel3DView | Separate preview window | Embedded in right panel is the locked decision; avoids window management |

---

## Architecture Patterns

### Recommended Project Structure
```
thermal_sim/
├── ui/
│   ├── stack_generator_wizard.py   # QWizard + all QWizardPage subclasses
│   └── block_editor.py             # existing — load_project() integration point
├── generators/
│   └── stack_generator.py          # Pure-Python geometry logic, no GUI imports
```

The `generators/` package is new. It houses the geometry computation, decoupled from UI for testability.

### Pattern 1: QWizard with registerField for inter-page data sharing
**What:** QWizardPage.registerField() stores named values accessible from any page via `wizard().field("name")`. Use for architecture choice (string), panel_width_mm, panel_depth_mm, etc.
**When to use:** Fields that subsequent pages read to configure themselves (e.g., LED config page needs panel dimensions from page 2).
**Example:**
```python
# Source: PySide6 QWizard documentation pattern
class PanelDimsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Panel Dimensions")
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(10, 2000)
        self._width_spin.setValue(450)
        self._width_spin.setSuffix(" mm")
        self.registerField("panel_width_mm", self._width_spin, "value",
                           self._width_spin.valueChanged)
        # ... layout setup
```

### Pattern 2: Pure-Python geometry generator
**What:** A dataclass `StackParams` carries all wizard-collected parameters. `generate_dled(params)` and `generate_eled(params)` return `VoxelProject`. Called from `wizard().accept()` or live preview updates.
**When to use:** Always — this is the separation-of-concerns pattern that makes geometry testable.
**Example:**
```python
# stack_generator.py — no Qt imports
from dataclasses import dataclass, field
from thermal_sim.models.assembly_block import AssemblyBlock
from thermal_sim.models.voxel_project import VoxelProject, BoundaryGroup, VoxelMeshConfig

@dataclass
class EledParams:
    panel_w: float  # metres
    panel_d: float  # metres
    # ... all thicknesses, LED configs, BC presets

def generate_eled(params: EledParams) -> VoxelProject:
    blocks: list[AssemblyBlock] = []
    # compute z-stack bottom-up
    # ...
    return VoxelProject(name="ELED Generated", blocks=blocks, ...)
```

### Pattern 3: Live preview via wizard page change signal
**What:** Connect `QWizard.currentIdChanged` to a slot that calls `_update_preview()`. `_update_preview()` tries to build a partial `VoxelProject` from current field values and calls `self._preview.update_structure(project)`.
**When to use:** For the right-panel live 3D preview that updates as user navigates pages.
```python
self.currentIdChanged.connect(self._update_preview)
# also connect each spin/combo change on the current page to _update_preview
```

### Pattern 4: Metal frame tray geometry
**What:** The metal frame is NOT a single hollow block. The voxel solver uses rectangular solids, so the frame tray must be decomposed into 5 rectangles: back plate (full footprint, frame_height thick) + 4 side walls (left/right/front/back, each spanning full panel width/depth, wall_thickness wide, inner_height tall at z=frame_z_top). Air fill blocks occupy the space between inner components and the side walls.
**When to use:** Both DLED and ELED architectures share this frame decomposition.

Frame geometry (all in metres, z=0 at bottom):
```
back_plate: x=0, y=0, z=0, w=panel_w, d=panel_d, h=frame_back_h
left_wall:  x=0, y=0, z=frame_back_h, w=wall_t, d=panel_d, h=inner_h
right_wall: x=panel_w-wall_t, y=0, z=frame_back_h, w=wall_t, d=panel_d, h=inner_h
front_wall: x=wall_t, y=0, z=frame_back_h, w=panel_w-2*wall_t, d=wall_t, h=inner_h
back_wall:  x=wall_t, y=panel_d-wall_t, z=frame_back_h, w=panel_w-2*wall_t, d=wall_t, h=inner_h
```
Air fill blocks sit between the walls and the inner component stack (LGP / PCB). They fill the remaining x-y space at the LGP z-level.

### Pattern 5: ELED LED placement on frame side walls
**What:** LEDs are attached to FR4 PCB strips adhered to the inner face of the frame side walls. At the LGP z-level. For a left-edge strip:
```
pcb_strip (left): x = wall_t, y = margin_y, z = lgp_z
                  w = pcb_thickness, d = panel_d - 2*margin_y, h = lgp_h
LED-L-i:         x = wall_t + pcb_thickness,
                 y = margin_y + i * pitch - led_d/2,
                 z = lgp_z + (lgp_h - led_h) / 2,
                 w = led_w, d = led_d, h = led_h
```

### Pattern 6: DLED LED grid placement
**What:** LEDs are placed on a regular grid on the PCB surface (top face of PCB, facing toward diffuser). PCB sits above reflector.
```
LED-R{r}-C{c}:  x = offset_x + c * pitch_x - led_w/2,
                y = offset_y + r * pitch_y - led_d/2,
                z = pcb_z + pcb_h,   # face the diffuser
                w = led_w, d = led_d, h = led_h
```

### Pattern 7: Toolbar and menu integration
**What:** Add a QAction to VoxelMainWindow._build_toolbar() and _build_menus() (File menu) that opens the wizard. On wizard Finish, call `self._block_editor.load_project(wizard.generated_project())`.
```python
# In _build_toolbar():
gen_action = QAction("Generate Stack", self)
gen_action.setToolTip("Open parametric display stack generator wizard")
gen_action.triggered.connect(self._open_stack_generator)
toolbar.addSeparator()
toolbar.addAction(gen_action)

# In _build_menus() File menu, after Save As:
file_menu.addSeparator()
gen_menu_action = QAction("Generate Display Stack...", self)
gen_menu_action.triggered.connect(self._open_stack_generator)
file_menu.addAction(gen_menu_action)

# Handler:
def _open_stack_generator(self) -> None:
    from thermal_sim.ui.stack_generator_wizard import StackGeneratorWizard
    wizard = StackGeneratorWizard(self._materials, parent=self)
    if wizard.exec() == QWizard.DialogCode.Accepted:
        project = wizard.generated_project()
        if project is not None:
            self._block_editor.load_project(project)
            self._materials.update(project.materials)
            self._populate_mat_table()
            self._block_editor.update_material_list(self._materials)
            self._update_3d_structure()
```

### Anti-Patterns to Avoid
- **Computing geometry in QWizardPage subclasses:** Puts untestable math in UI code. Keep all geometry in `stack_generator.py`.
- **Using QWizard.field() for complex data (lists, dicts):** registerField() works well for scalars; store complex data (per-film table, per-edge LED config) in instance attributes on the wizard, accessed via `wizard()` cast.
- **Rebuilding Voxel3DView on every parameter change:** Expensive. Call `update_structure(project)` only on page transitions (currentIdChanged), not on every spinbox valueChanged.
- **Single large `generate()` function:** Split into `_build_frame()`, `_build_inner_stack()`, `_build_led_strip_eled()`, `_build_led_grid_dled()` helpers for readability and testing.
- **Overlap in frame decomposition:** The 4 side walls must not overlap the back plate. Back plate occupies z=[0, frame_back_h]; walls occupy z=[frame_back_h, frame_back_h + inner_h]. Front/back walls must be inset by wall_t to avoid overlapping left/right walls at the corners — or use the simpler non-overlapping layout shown in Pattern 4 above.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-step dialog with Back/Next | Custom step tracking, show/hide widgets | `QWizard` + `QWizardPage` | Qt provides page history, field propagation, button management |
| Per-page input validation | Manual flag tracking | `QWizardPage.isComplete()` override + `completeChanged` signal | Automatically disables Next when page is invalid |
| Material dropdown in wizard | Custom widget | `_make_material_combo()` pattern from BlockEditorWidget | Already built; just pass materials dict to wizard |
| Live 3D preview in a dialog | Custom OpenGL widget or external window | Embed `Voxel3DView` widget directly | Already exists, `update_structure(project)` is the public API |

**Key insight:** The existing `BlockEditorWidget.load_project()` and `Voxel3DView.update_structure()` are the two integration points. The wizard only needs to produce a `VoxelProject`.

---

## Common Pitfalls

### Pitfall 1: Z-stack ordering in DLED
**What goes wrong:** DLED cross-section is listed "front to back" (panel at top, back cover at bottom) but `AssemblyBlock.z` is bottom-up (z=0 = bottom). Confusing direction leads to inverted stacks.
**Why it happens:** Cross-section spec is optical order; model is physical Z-up.
**How to avoid:** Always build z_cursor starting at 0 (back cover bottom), accumulating upward. Order: back_cover → frame_back_plate → reflector → pcb → air_cavity → diffuser → optical_films → panel.
**Warning signs:** Panel z is lower than PCB z in the generated JSON.

### Pitfall 2: Frame side wall overlaps
**What goes wrong:** Left/right walls span full panel_d; front/back walls also span full panel_w. Corner regions are double-counted, causing AABB overlap warnings and unexpected material override.
**Why it happens:** Naive "each wall spans full dimension" geometry.
**How to avoid:** Left/right walls: full depth (y=0 to panel_d). Front/back walls: interior width only (x=wall_t to panel_w-wall_t). This is the non-overlapping corner strategy shown in Pattern 4.
**Warning signs:** `validate_blocks()` returns overlap warnings for frame walls.

### Pitfall 3: ELED LED position relative to FR4 strip
**What goes wrong:** LEDs are placed inside the PCB block (z center inside PCB height) instead of on its inner face pointing into the LGP.
**Why it happens:** Confusion about which face of the PCB the LEDs are on.
**How to avoid:** LEDs sit at x = wall_t + pcb_thickness (inner face of PCB strip, pointing toward LGP center). LED z-center = lgp_z + lgp_h/2 (centered on LGP height). LED width (x-direction) is the dimension pointing into the LGP.
**Warning signs:** LEDs overlap the PCB block in x-direction.

### Pitfall 4: ELED air fill block gaps or overlaps
**What goes wrong:** Air blocks don't cleanly fill the space between inner stack and frame walls, leaving voxels unassigned (defaulting to Air Gap anyway but creating conformal mesh complexity) or overlapping inner components.
**Why it happens:** Off-by-one in coordinate arithmetic when frame_wall_thickness != inner_margin.
**How to avoid:** Define inner_w = panel_w - 2*wall_t, inner_d = panel_d - 2*wall_t. All inner components use x_start=wall_t, y_start=wall_t, width=inner_w, depth=inner_d. No air fill block needed if inner components fill the full inner volume — air gap is the default fill material in the voxel solver.

### Pitfall 5: QWizard page ordering breaks live preview
**What goes wrong:** Preview widget tries to access fields from pages the user hasn't visited yet (fields have no value), raising KeyError or returning 0.
**Why it happens:** `wizard().field("x")` returns 0 or None for unvisited pages.
**How to avoid:** `_update_preview()` wraps the generate call in try/except and silently skips preview update on incomplete data. Use default/fallback values when fields are unset.

### Pitfall 6: Boundary group per-face assignment
**What goes wrong:** Wizard generates 6 separate BoundaryGroup objects (one per face) when most faces share the same BC. This creates 6 rows in the boundary table instead of 1–2.
**Why it happens:** Mechanically creating one group per face.
**How to avoid:** Deduplicate: group faces that share identical BC parameters into a single BoundaryGroup with a faces list. E.g., if top/front/back/left/right all have h=8, one group with faces=["top","front","back","left","right"]; bottom with h=25 gets its own group.

### Pitfall 7: max_cell_size already exists in block_editor
**What goes wrong:** Planning work to "add max_cell_size to block editor Mesh tab" when it already exists.
**Why it happens:** CONTEXT.md says it needs to be added but the code already has `_max_cell_size_spin` at line 246.
**How to avoid:** Verify before planning — the spinbox IS present. The "add to block editor" task may just be verification/testing, not new code. Check if it is correctly wired in `build_project()` and `load_project()` (it is, per lines 445–448 and 615–617 of block_editor.py).

---

## Code Examples

### QWizard structure skeleton
```python
# Source: PySide6 QWizard API (standard Qt pattern)
from PySide6.QtWidgets import QWizard, QWizardPage

class StackGeneratorWizard(QWizard):
    PAGE_ARCH = 0
    PAGE_DIMS = 1
    PAGE_LEDS = 2
    PAGE_LAYERS = 3
    PAGE_BCS = 4
    PAGE_MESH = 5

    def __init__(self, materials: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Display Stack")
        self.resize(1100, 700)
        self._materials = materials
        self._generated_project: VoxelProject | None = None

        self.setPage(self.PAGE_ARCH, ArchitecturePage())
        self.setPage(self.PAGE_DIMS, PanelDimsPage())
        self.setPage(self.PAGE_LEDS, LEDConfigPage())
        self.setPage(self.PAGE_LAYERS, LayerThicknessPage())
        self.setPage(self.PAGE_BCS, BoundaryConditionsPage())
        self.setPage(self.PAGE_MESH, MeshConfigPage())

        # Right panel: live preview
        self._preview = Voxel3DView()
        # QWizard uses setPixmap/setSideWidget — embed via layout trick:
        # place QWizard in splitter... or use WizardStyle + custom layout
        # Simplest: resize wizard wide enough, embed preview in a QSplitter
        # by overriding the wizard's main layout.

        self.currentIdChanged.connect(self._update_preview)

    def generated_project(self) -> VoxelProject | None:
        return self._generated_project

    def accept(self) -> None:
        try:
            params = self._collect_params()
            arch = self.field("architecture")
            if arch == "ELED":
                self._generated_project = generate_eled(params)
            else:
                self._generated_project = generate_dled(params)
        except Exception as exc:
            QMessageBox.critical(self, "Generation Error", str(exc))
            return
        super().accept()
```

### StackGenerator geometry helper (ELED frame walls)
```python
# stack_generator.py — pure Python, no Qt
def _build_frame_tray(
    panel_w: float, panel_d: float,
    back_h: float, inner_h: float, wall_t: float,
    material: str
) -> list[AssemblyBlock]:
    """Decompose a tray-shaped metal frame into 5 AssemblyBlock rectangles."""
    blocks = []
    # Back plate (full footprint)
    blocks.append(AssemblyBlock(
        "Frame Back", material, 0.0, 0.0, 0.0, panel_w, panel_d, back_h
    ))
    z = back_h
    # Left wall (full depth)
    blocks.append(AssemblyBlock(
        "Frame Left", material, 0.0, 0.0, z, wall_t, panel_d, inner_h
    ))
    # Right wall (full depth)
    blocks.append(AssemblyBlock(
        "Frame Right", material, panel_w - wall_t, 0.0, z, wall_t, panel_d, inner_h
    ))
    # Front wall (inset — between left and right walls)
    blocks.append(AssemblyBlock(
        "Frame Front", material, wall_t, 0.0, z, panel_w - 2 * wall_t, wall_t, inner_h
    ))
    # Back wall (inset)
    blocks.append(AssemblyBlock(
        "Frame Back Wall", material,
        wall_t, panel_d - wall_t, z,
        panel_w - 2 * wall_t, wall_t, inner_h
    ))
    return blocks
```

### BC preset lookup
```python
# Preset h values — matches CONTEXT.md locked decisions
_BC_PRESETS = {
    "Natural convection": 8.0,
    "Forced air": 25.0,
    "Enclosed still air": 3.0,
}

def _make_boundary_group(
    name: str, face: str, preset: str, h_override: float | None,
    ambient_c: float, radiation: bool
) -> BoundaryGroup:
    h = h_override if (preset == "Custom" and h_override is not None) else _BC_PRESETS.get(preset, 8.0)
    return BoundaryGroup(
        name=name,
        boundary=SurfaceBoundary(
            ambient_c=ambient_c,
            convection_h=h,
            include_radiation=radiation,
        ),
        faces=[face],
    )
```

### Embedding Voxel3DView in QWizard
**Challenge:** QWizard does not natively support a persistent side panel widget. The locked decision is a live 3D preview on the right side.

**Approach:** Don't use QWizard's built-in layout. Instead, create the wizard as a `QDialog` manually, with a `QSplitter` containing:
- Left: `QStackedWidget` of `QWizardPage`-like custom pages with manual Back/Next/Finish buttons
- Right: `Voxel3DView`

**OR:** Use `QWizard.setOption(QWizard.WizardOption.HaveCustomButton1)` and override the paintEvent — but this is fragile.

**Recommended approach:** Use a `QDialog` with a custom step-navigation system rather than `QWizard` when a persistent side panel is required. The `QWizard.setPixmap()` API only supports a small side graphic, not a full 3D widget.

This is a significant finding: **the live 3D preview requirement means QWizard's standard layout cannot be used directly**. A custom multi-page QDialog with a splitter is the correct implementation.

```python
class StackGeneratorWizard(QDialog):
    """Multi-step dialog with persistent 3D preview panel on the right."""

    def __init__(self, materials: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Display Stack")
        self.resize(1200, 750)
        self._materials = materials
        self._current_page = 0
        self._pages: list[_WizardPage] = []

        # Build layout: splitter with pages on left, preview on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: stacked pages + nav buttons
        left_w = QWidget()
        left_layout = QVBoxLayout(left_w)

        self._page_label = QLabel()
        left_layout.addWidget(self._page_label)

        self._stack = QStackedWidget()
        left_layout.addWidget(self._stack)

        nav = QHBoxLayout()
        self._back_btn = QPushButton("< Back")
        self._next_btn = QPushButton("Next >")
        self._finish_btn = QPushButton("Generate")
        self._finish_btn.setVisible(False)
        cancel_btn = QPushButton("Cancel")
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        nav.addWidget(self._finish_btn)
        nav.addStretch()
        nav.addWidget(cancel_btn)
        left_layout.addLayout(nav)

        # Right: 3D preview
        from thermal_sim.ui.voxel_3d_view import Voxel3DView
        self._preview = Voxel3DView()

        splitter.addWidget(left_w)
        splitter.addWidget(self._preview)
        splitter.setSizes([600, 600])

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)

        # Wire nav
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._finish_btn.clicked.connect(self._on_finish)
        cancel_btn.clicked.connect(self.reject)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Layer-based DisplayProject | VoxelProject with AssemblyBlock | Phase 11 | Generator targets VoxelProject, not DisplayProject |
| Single BoundaryGroup for all faces | BoundaryGroup.faces list for per-face assignment | Phase 11-06 | Wizard BC page can produce per-face groups directly |
| No max_cell_size UI | max_cell_size spinbox in BlockEditorWidget Mesh tab | Current codebase (already present) | "Add UI control" task may be a no-op — verify |

**Deprecated/outdated:**
- DisplayProject template approach (ARCH-02/ARCH-03 from old GUI): Replaced by this wizard. Old ELED/DLED template code in the layer-based main_window.py is dead code.
- `eled_voxel.json` / `dled_voxel.json` example files: These serve as reference geometry but the wizard will produce richer, more correct geometry. The example files use old material names not present in the updated `materials_builtin.json` (e.g., "Aluminum 6061", "PET", "LED Package" not in builtin library).

---

## Open Questions

1. **QWizard vs custom QDialog for live preview**
   - What we know: QWizard.setPixmap() handles only images; no API for embedding a persistent 3D widget in the wizard side panel without hacking the internal layout.
   - What's unclear: Whether using `QWizard` with a `QSplitter` wrapping approach is stable across Qt versions.
   - Recommendation: Use a custom `QDialog` with `QStackedWidget` for pages and manual nav buttons. This is simpler, more maintainable, and the locked decision (live 3D preview on right) drives this choice.

2. **Material names for generated blocks**
   - What we know: `materials_builtin.json` has 28 specific materials. Old example JSONs use names not in builtin library ("Aluminum 6061", "PET", "LED Package").
   - What's unclear: Which builtins to default for each layer type.
   - Recommendation (Claude's Discretion): Panel→"LCD Glass", LGP→"PMMA / LGP", Optical films→"Diffuser / Prism Film Stack (effective)", Reflector→"Reflector Film / PET-like Film", PCB→"PCB Effective, medium copper", Frame→"Aluminum, oxidized / rough" (or Steel), Back Cover→"Aluminum, bare/shiny", Air Gap→"Air Gap", LEDs→create "LED Package" with k=20, density=3000, Cp=800, e=0.5.

3. **Frame wall thickness default**
   - What we know: CONTEXT.md leaves this to Claude's discretion.
   - Recommendation: 3mm (0.003m) wall thickness, matching the LGP-level tray structure shown in eled_voxel.json (x=0.010 for LGP, meaning 10mm frame gap; wall_t=3mm leaves 7mm for PCB+air, consistent with CONTEXT specifics note about air fill blocks).
   - Simpler default: 4mm frame wall thickness for robustness.

4. **Air fill blocks vs relying on voxel air default**
   - What we know: Empty voxels default to Air Gap (k=0.026 W/mK) in the voxel solver. CONTEXT says "air must be represented as explicit air blocks".
   - What's unclear: Whether explicit air blocks improve mesh quality or are required for solver correctness.
   - Recommendation: Add explicit "Air Gap" blocks in the frame cavity (between walls and inner stack) so users can see them in the 3D view and the material is unambiguous. Use the "Air Gap" material from builtins.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `thermal_sim/ui/block_editor.py` — `_max_cell_size_spin` confirmed present at lines 246–258; `load_project()` confirmed at lines 582–626; `build_project()` at lines 430–467
- Direct codebase inspection: `thermal_sim/ui/main_window.py` VoxelMainWindow — `_build_menus()` at line 4092, `_build_toolbar()` at line 4139; integration pattern for load_project at lines 4210–4218
- Direct codebase inspection: `thermal_sim/models/voxel_project.py` — VoxelProject, BoundaryGroup.faces, VoxelMeshConfig.max_cell_size
- Direct codebase inspection: `thermal_sim/models/assembly_block.py` — AssemblyBlock frozen dataclass
- Direct codebase inspection: `examples/eled_voxel.json` / `examples/dled_voxel.json` — existing geometry patterns
- Direct codebase inspection: `thermal_sim/resources/materials_builtin.json` — 28 builtin materials confirmed

### Secondary (MEDIUM confidence)
- PySide6 QWizard behavior (standard Qt knowledge): registerField(), isComplete(), page navigation — standard Qt patterns, stable across Qt5/Qt6
- QWizard side-widget limitation: documented constraint; verified by reasoning about QWizard's internal layout system

### Tertiary (LOW confidence)
- None used

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are project-internal or standard Qt; confirmed in codebase
- Architecture: HIGH — patterns derived directly from existing code (SweepDialog, BlockEditorWidget, VoxelMainWindow) plus standard Qt patterns
- Pitfalls: HIGH for geometry pitfalls (derived from ELED/DLED voxel JSON geometry); MEDIUM for QWizard live-preview constraint (reasoning-based, not measured)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable internal codebase; no fast-moving external dependencies)
