# Phase 9: 3D GUI and ELED Zone Preset - Research

**Researched:** 2026-03-16
**Domain:** PySide6 GUI extension, matplotlib overlay patterns, model serialization
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Z-plane slice navigation**
- Integrated combo: single QComboBox replacing the current layer combo, listing all z-sublayers across all layers (e.g., "LGP (z=1/5)", "LGP (z=2/5)", ..., "FR4", "Metal Cover")
- Layers with nz=1 show plain name only (no "(z=1/1)" suffix)
- Ordering is bottom-to-top, matching the existing layer stacking convention
- The combo replaces `map_layer_combo` — no separate slider or secondary dropdown

**Material zone editor UX**
- Table rows per layer: each layer gets an expandable zone sub-table below its row in the Layers tab
- Expand/collapse via toggle (arrow or "Zones" button) — collapsed by default
- Zone table columns: Material (QComboBox from project materials), X start, X end, Y start, Y end
- Zone coordinates entered in mm, auto-converted to SI (meters) internally — consistent with heat source and mesh input convention
- Add/remove zone rows via [+] [-] buttons

**Zone preview overlay**
- Dashed boundary lines drawn over the temperature heatmap showing zone edges, with material name labels at zone corners
- Always-on: overlay appears automatically whenever the displayed layer has material zones (no toggle checkbox)
- Editor preview: inline matplotlib canvas below the zone sub-table when expanded, showing zone rectangles on the layer footprint — updates immediately as zone coordinates change
- Same dashed style on both the editor preview and the results temperature map

**ELED auto-zone configuration**
- ELED panel gets spinboxes for each zone width: frame width, PCB+LED width, air gap width, LGP width (remaining)
- Per-edge control: separate width spinboxes for left and right edges — supports asymmetric ELED configurations
- Explicit "Generate Zones" button to populate zone table from spinbox values (not auto-updating)
- Zones applied to LGP layer only — other layers (diffuser, backplate) remain uniform material

### Claude's Discretion
- nz spinbox placement and styling in the Layers tab
- Node count display format in status bar and warning threshold presentation (>300k)
- Combo selection behavior when nz changes (auto-select middle vs stay on current)
- Exact dashed line styling (color, dash pattern, label font size)
- Editor preview canvas sizing and aspect ratio
- Default ELED zone widths for the spinbox presets

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GUI3D-01 | Z-plane slice selector in temperature map (QComboBox to pick z-sublayer within a layer) | Combo populated from Phase 8 `nz_per_layer` + `z_offsets`; `_refresh_layer_choices` replacement; `_plot_map` reads flat z-axis index from combo selection |
| GUI3D-02 | Live node count display in status bar, warning at >300k nodes before solve | Status bar already has four label zones; node count = `sum(nz_i) * nx * ny`; warning via QMessageBox before run |
| GUI3D-03 | Per-layer `nz` spinbox in Layers tab | Phase 8 adds `Layer.nz`; GUI adds QSpinBox per row inline — must refresh combo on change |
| GUI3D-04 | Material zone editor per layer (add/remove rectangular zones with material assignment) | Phase 7 adds `Layer.zones: list[MaterialZone]`; GUI adds expandable sub-table following power-profile sub-panel pattern |
| GUI3D-05 | Zone preview overlay on temperature map showing material region boundaries | `plot_temperature_map_annotated()` extended with optional `zones` arg; dashed rectangles drawn after imshow |
| ELED-01 | ELED template generates correct cross-section zones: metal frame, FR4+LED PCB, air gap, LGP as lateral material zones at LGP z-level | Add `generate_eled_zones()` function in `stack_templates.py` or inline in `_on_architecture_changed`; widths from GUI spinboxes |
| ELED-02 | ELED thermal model captures both heat paths: LED→FR4→metal (primary) and LED→air→LGP (secondary) | Verified by running ELED zoned project — higher T on FR4+LED zone, secondary gradient toward LGP bulk — integration test |
</phase_requirements>

---

## Summary

Phase 9 is entirely a GUI and model-wiring phase — no new solver math. All solver infrastructure (per-cell material zones, z-refinement, `nz_per_layer`/`z_offsets` in result objects) is delivered by Phases 7 and 8. Phase 9 surfaces those capabilities through the existing PySide6 UI patterns already established in `main_window.py`.

The three main work streams are independent and can be developed in parallel after any blocking model-field changes (Layer.nz, Layer.zones) are confirmed present from upstream phases:

1. **Z-slice combo** — replace `map_layer_combo` with a combo that lists flat z-sublayers, mapping each combo index to a `(layer_idx, sublayer_offset)` pair drawn from `nz_per_layer` and `z_offsets` on the result.
2. **Zone editor + overlay** — add an expand/collapse zone sub-table per layer row (modeled on the power-profile sub-panel), store zone data in `Layer.zones`, and draw dashed overlays in `plot_temperature_map_annotated`.
3. **ELED zone preset** — add width spinboxes to `_build_eled_panel()` and a "Generate Zones" button that calls a pure function to compute `MaterialZone` objects from the spinbox values and writes them into the LGP layer.

The codebase already contains every reusable building block needed. No new dependencies are required.

**Primary recommendation:** Wire Phase 9 directly onto the existing `QTableWidget` expand/collapse and `MplCanvas` patterns. Do not introduce new widget libraries. The power-profile sub-panel in `_build_sources_tab()` is the exact template for the zone sub-table.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | already installed | Qt widgets for all GUI changes | Project-wide, all existing UI is PySide6 |
| matplotlib (FigureCanvasQTAgg) | already installed | Embedded canvases, overlay drawing | `MplCanvas` already wraps this; zone preview reuses same class |
| numpy | already installed | Array indexing for z-sublayer lookup | Result arrays are numpy; no extra usage needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PySide6.QtWidgets.QTableWidget | — | Zone sub-table per layer | Follows existing pattern for all editor tables |
| matplotlib.patches.Rectangle | — | Zone overlay drawing | Use `ax.add_patch(Rectangle(...))` for filled/dashed zone boxes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| QTableWidget per-layer zones | QTreeWidget with child rows | QTableWidget is simpler and already used everywhere; QTreeWidget adds complexity for no gain |
| matplotlib.patches.Rectangle | ax.plot() with line segments | Rectangle is cleaner for filled+edge zones; line segments require 5 points per zone |
| QComboBox for z-slice | QSlider | Combo maps directly to named sublayer strings; slider requires tooltip to show name |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes slot into existing files:

```
thermal_sim/
├── models/layer.py             # ADD: nz field (Phase 8), zones field (Phase 7)
├── models/stack_templates.py   # ADD: generate_eled_zones() helper function
├── visualization/plotting.py   # EXTEND: plot_temperature_map_annotated() with zones overlay
├── ui/main_window.py           # MAJOR: z-slice combo, zone sub-table, ELED zone spinboxes,
│                               #        node count in status bar
└── ui/plot_manager.py          # MINOR: pass zones to plot_temperature_map_annotated
```

### Pattern 1: Z-Slice Combo Population

**What:** Replace `map_layer_combo` with a flat list of all z-sublayers. Each combo item stores a `(flat_z_index)` as user data so `_plot_map` can extract `final_map_c[flat_z_index]` directly.

**When to use:** Whenever solver result has `nz_per_layer` and `z_offsets`.

**Key design:**
```python
# In _refresh_layer_choices(project, result=None):
self.map_layer_combo.clear()
if result is None or all(nz == 1 for nz in result.nz_per_layer):
    # Simple case: one entry per layer, no z-suffix
    for layer in project.layers:
        self.map_layer_combo.addItem(layer.name)
else:
    for layer_idx, (layer, nz) in enumerate(zip(project.layers, result.nz_per_layer)):
        z_offset = result.z_offsets[layer_idx]
        if nz == 1:
            self.map_layer_combo.addItem(layer.name, userData=z_offset)
        else:
            for z in range(nz):
                label = f"{layer.name} (z={z+1}/{nz})"
                self.map_layer_combo.addItem(label, userData=z_offset + z)
```

**In `_plot_map`:** Replace `layer_names.index(layer_name)` lookup with `self.map_layer_combo.currentData()` to get flat z-index directly.

**Naming:** Rename internal variable from `layer_idx` to `flat_z_idx` in `_plot_map` to avoid confusion.

### Pattern 2: Zone Sub-Table (Expand/Collapse)

**What:** Each layer row in `layers_table` gets a toggle button that shows/hides a per-layer zone `QTableWidget` below it.

**When to use:** When user clicks the "Zones" toggle button.

**Template to follow:** `_build_sources_tab()` power-profile sub-panel pattern — a `QGroupBox` with `setVisible(False)`, toggled by a row-selection or button event.

**Key design:**
- Store zone sub-tables in `self._layer_zone_widgets: dict[int, dict]` keyed by layer row index, each holding `{"toggle_btn", "group_box", "table", "canvas"}`.
- Zone table columns: `Material` (QComboBox), `X start [mm]`, `X end [mm]`, `Y start [mm]`, `Y end [mm]`.
- The per-layer editor canvas is a small `MplCanvas(width=3.0, height=2.0, dpi=80)` placed inside the group box.
- On zone table change: call `_refresh_zone_preview(layer_row)` which draws rectangles onto the small canvas.

**Rebuild on layers table change:** When layers are added/removed, `_rebuild_zone_widgets()` reconstructs the zone widget dict. This is equivalent to how the sources table handles power profiles via `_source_profiles`.

### Pattern 3: Zone Overlay on Temperature Map

**What:** Draw dashed rectangle outlines on the results temperature map for every zone in the displayed layer.

**When to use:** After every `plot_temperature_map_annotated()` call, if the current layer has zones.

**Extend `plot_temperature_map_annotated()` signature:**
```python
def plot_temperature_map_annotated(
    ax,
    temperature_map_c: np.ndarray,
    width_m: float,
    height_m: float,
    title: str,
    hotspots=None,
    probes=None,
    selected_hotspot_rank=None,
    zones=None,           # NEW: list[MaterialZone] | None
):
    ...
    # After imshow, hotspots, probes:
    if zones:
        from matplotlib.patches import Rectangle
        for zone in zones:
            x_mm = zone.x * 1000.0
            y_mm = zone.y * 1000.0
            w_mm = zone.width * 1000.0
            h_mm = zone.height * 1000.0
            rect = Rectangle((x_mm, y_mm), w_mm, h_mm,
                              linewidth=1.2, edgecolor="white",
                              linestyle="--", facecolor="none", zorder=6)
            ax.add_patch(rect)
            ax.text(x_mm + 0.5, y_mm + 0.5, zone.material,
                    fontsize=6, color="white", va="bottom", ha="left", zorder=7)
```

### Pattern 4: ELED Zone Generation

**What:** Pure function that takes ELED geometry parameters and returns a list of `MaterialZone` objects describing the cross-section.

**Location:** Add `generate_eled_zones()` to `thermal_sim/models/stack_templates.py`.

**Physical arrangement:** `[left_frame | left_PCB+LED | left_air | LGP_bulk | right_air | right_PCB+LED | right_frame]`

```python
def generate_eled_zones(
    panel_width: float,   # metres
    panel_height: float,  # metres
    frame_width_left: float,
    pcb_width_left: float,
    air_gap_left: float,
    frame_width_right: float,
    pcb_width_right: float,
    air_gap_right: float,
) -> list:
    """Return MaterialZone list for ELED LGP cross-section (left-to-right)."""
    zones = []
    x = 0.0
    for (mat, w) in [
        ("Steel", frame_width_left),
        ("FR4",   pcb_width_left),
        ("Air",   air_gap_left),
        ("PMMA",  panel_width - frame_width_left - pcb_width_left - air_gap_left
                              - frame_width_right - pcb_width_right - air_gap_right),
        ("Air",   air_gap_right),
        ("FR4",   pcb_width_right),
        ("Steel", frame_width_right),
    ]:
        zones.append(MaterialZone(material=mat, x=x, y=0.0, width=w, height=panel_height))
        x += w
    return zones
```

The `MaterialZone` class is defined in Phase 7 (`thermal_sim/models/material_zone.py` or similar). Phase 9 imports it.

### Pattern 5: Node Count in Status Bar

**What:** Compute `total_nodes = sum(layer.nz for layer in project.layers) * nx * ny` and display in status bar. Warn before solve if > 300k.

**Where:** Add `_update_node_count_label()` called from `_collect_project()` or as part of any mesh/nz change. Add `_node_count_label = QLabel("")` to the status bar in `_build_ui()`, inserted after `_run_info_label`.

**Warning:** Before calling `self._sim_controller.start(...)`, compute node count and if > 300k, show `QMessageBox.warning(...)` with "Proceed" / "Cancel" buttons.

### Anti-Patterns to Avoid

- **Don't re-create the matplotlib figure on every z-slice change.** The existing pattern clears axes with `ax.clear()` and redraws — keep this. Do not destroy and recreate `MplCanvas`. The current `_plot_map` method already follows this pattern.
- **Don't use QTreeWidget for the zone sub-table.** QTableWidget with a collapsible group box is sufficient and follows the established codebase pattern.
- **Don't wire zone spinbox changes to auto-generate ELED zones.** The user decision is an explicit "Generate Zones" button. Auto-generation causes confusion when the user is mid-edit.
- **Don't add zones to the layers_table directly as extra columns.** The layers_table has a fixed column set. Use a separate sub-widget below each row.
- **Don't hold zone editor data only in the GUI widget.** Zones must be collected into `Layer.zones` (list of `MaterialZone`) when `_collect_project()` is called, following the existing pattern of reading from all editor tables.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Zone rectangle drawing on canvas | Custom line-drawing loop | `matplotlib.patches.Rectangle` | Handles clipping, zorder, fill/edge correctly |
| Expand/collapse animation | Custom show/hide animation | `QGroupBox.setVisible(True/False)` | The power-profile sub-panel does this already — copy the pattern |
| QComboBox with associated data | Parallel dict mapping index->value | `QComboBox.addItem(text, userData=value)` and `currentData()` | Built-in Qt mechanism; no sync issues |
| Node count computation | Scraping table widget text | `sum(layer.nz for layer in project.layers) * nx * ny` from the model | Model is source of truth, not the table widget |

**Key insight:** Every problem in Phase 9 has a direct analogue already implemented in the codebase. Match patterns exactly; avoid novel approaches.

---

## Common Pitfalls

### Pitfall 1: Z-Index Mismatch After Layer Add/Remove
**What goes wrong:** User adds or removes a layer, making `nz_per_layer` and `z_offsets` from the last result stale. The combo still shows old sublayer entries. Selecting one causes an out-of-bounds index into `result.temperatures_c`.
**Why it happens:** The combo is only refreshed after a solve, not after project edits.
**How to avoid:** When the layers table changes (row add/remove), call `_refresh_layer_choices(project, result=None)` to collapse back to simple layer names until the next solve. This already happens in the current code for `map_layer_combo` — extend the same logic to the new flat-z combo.
**Warning signs:** `IndexError` or `KeyError` when switching z-combo after an edit without re-running.

### Pitfall 2: Layer.zones Serialization Gap
**What goes wrong:** `Layer.to_dict()` doesn't include `zones`, so zones are silently dropped when saving to JSON. User loses zone configuration on save/reload.
**Why it happens:** Phase 7 must add `zones` to Layer's `to_dict()`/`from_dict()`. Phase 9 trusts this is done, but if Phase 7 only adds it to the model field without serialization, zones vanish.
**How to avoid:** Explicitly verify `Layer.to_dict()` includes zones before wiring the zone editor. If Phase 7 left this out, add it in Phase 9 as a prerequisite task.
**Warning signs:** Round-trip test: save project with zones, reload, zones list is empty.

### Pitfall 3: Zone Sub-Table / Layers Table Sync
**What goes wrong:** The layers table has rows added/removed via Add/Remove buttons. The zone sub-widget dict (`_layer_zone_widgets`) is keyed by row index. When row 2 is deleted, what was row 3 becomes row 2, but the zone widgets dict still has old indices.
**Why it happens:** Row indices shift on deletion; the widget dict doesn't know.
**How to avoid:** On any layers table row add/remove, rebuild the entire `_layer_zone_widgets` dict. This is analogous to how `_source_profiles` is rebuilt — accept the small cost. Or key by layer name (str) rather than row index, which is more stable.
**Warning signs:** Zone editor shows wrong layer's zones after a row deletion.

### Pitfall 4: ELED Zone Materials Not in Project
**What goes wrong:** `generate_eled_zones()` emits zones referencing `"Steel"`, `"FR4"`, `"Air"`, `"PMMA"`. If the current project doesn't have these materials in `project.materials`, the Phase 7 builder will fail validation or silently use defaults.
**Why it happens:** The ELED template populates a standard material set, but if the user has a Custom project and clicks "Generate Zones", required materials may be missing.
**How to avoid:** The "Generate Zones" button should also inject the required materials (Steel, FR4, Air, PMMA) into the materials table if not already present — or show a warning listing missing materials. The ELED template already calls `_filter_materials()` which handles this for the initial template load. For zone-only generation, add a `_ensure_eled_materials()` helper.
**Warning signs:** `KeyError` in `DisplayProject.__post_init__` when validating material references after zone generation.

### Pitfall 5: blockSignals and Zone Canvas Refresh Loop
**What goes wrong:** The zone table `cellChanged` signal triggers `_refresh_zone_preview()`, which updates the zone canvas. If canvas update somehow emits another signal, infinite loop.
**Why it happens:** Indirect signal chains are common in Qt — less so here but worth noting.
**How to avoid:** Wrap `_refresh_zone_preview()` with `blockSignals(True)` on the canvas widget during update, or use a `_updating_zone_preview` flag. The existing `_undoing` flag in MainWindow is the pattern to follow.
**Warning signs:** Stack overflow / recursion depth error on zone coordinate edit.

### Pitfall 6: nz Spinbox Not Reflected in Node Count Before Solve
**What goes wrong:** User changes `nz` spinbox for a layer, but the node count label doesn't update until the next full project collect. Engineer doesn't get the 300k warning in time.
**Why it happens:** Node count is computed from the project model, which is only collected at solve time.
**How to avoid:** Connect nz spinbox `valueChanged` signals to `_update_node_count_label()`. Since nz spinboxes are created dynamically (per layer row), wire them in the zone widget construction loop.
**Warning signs:** Status bar shows stale node count; 300k warning fires too late (at solve time is still acceptable per the requirement, but earlier feedback is better).

---

## Code Examples

### Adding userData to QComboBox items
```python
# Source: PySide6 QComboBox.addItem documentation (Qt 6)
combo = QComboBox()
combo.addItem("LGP (z=1/5)", userData=0)   # flat z-index
combo.addItem("LGP (z=2/5)", userData=1)
flat_z = combo.currentData()               # returns int
```

### Drawing dashed zone rectangles on matplotlib axes
```python
from matplotlib.patches import Rectangle
rect = Rectangle(
    (x_mm, y_mm), width_mm, height_mm,
    linewidth=1.2,
    edgecolor="white",
    linestyle="--",
    facecolor="none",
    zorder=6,
)
ax.add_patch(rect)
```

### CollapsibleGroup pattern (existing codebase analog)
```python
# In _build_sources_tab() — existing pattern:
self._profile_panel = QGroupBox("Power Profile (time-varying)")
self._profile_panel.setVisible(False)
# Toggle:
self._profile_panel.setVisible(row >= 0)
```
For zone sub-tables, use the same `QGroupBox.setVisible()` toggle wired to a QPushButton per layer row.

### Reading Layer.nz for node count
```python
def _compute_node_count(self) -> int:
    project = self._collect_project_safe()
    if project is None:
        return 0
    return sum(layer.nz for layer in project.layers) * project.mesh.nx * project.mesh.ny
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Layer combo lists layer names | Flat z-combo lists sublayer entries | Phase 9 | Combo items map to flat z-axis index, not layer index |
| Layer has single material | Layer has base material + optional MaterialZone list | Phase 7 | Zone editor reads/writes `Layer.zones` |
| Result shape `[n_layers, ny, nx]` | Result shape `[total_z, ny, nx]` with z_offsets | Phase 8 | Map display indexes flat z-axis; combo userData = flat z-index |
| ELED template has uniform LGP material | LGP layer gets cross-section MaterialZone list | Phase 9 | Both heat paths become thermally distinct |

---

## Key Integration Points with Upstream Phases

### Phase 7 deliverables Phase 9 consumes
- `MaterialZone` dataclass with fields: `material: str`, `x: float`, `y: float`, `width: float`, `height: float` (all SI). Location TBD — likely `thermal_sim/models/material_zone.py`.
- `Layer.zones: list[MaterialZone]` field, default `[]`.
- `Layer.to_dict()` includes `zones`.
- Auto-injection of Air material at build time when uncovered cells exist.

### Phase 8 deliverables Phase 9 consumes
- `Layer.nz: int`, default 1.
- `SteadyStateResult.nz_per_layer: list[int]` and `SteadyStateResult.z_offsets: list[int]`.
- `TransientResult.nz_per_layer: list[int]` and `TransientResult.z_offsets: list[int]`.
- Result `temperatures_c` shape: `[total_z, ny, nx]`.

### Blocker check (from STATE.md)
The STATE.md records this concern: "verify that Phase 6 ELED stack template exposes frame width, LED board width, and air gap width as named fields before committing to preset implementation approach."

**Verified:** The current `eled_template()` in `stack_templates.py` does NOT expose frame/PCB/air widths as parameters — it has only `panel_width`, `panel_height`, `edge_config`, and `optical_layers`. The `edge_offset=0.005` (5 mm) is hardcoded. Phase 9 must add the width spinboxes to `_build_eled_panel()` (GUI only) and compute zones from those GUI values — the template function itself does not need changing, since zone generation is a new path separate from `eled_template()`.

---

## Open Questions

1. **MaterialZone class location**
   - What we know: Phase 7 defines it; likely `thermal_sim/models/` but exact file unknown until Phase 7 is complete.
   - What's unclear: Is it in `layer.py` inline, a separate `material_zone.py`, or `heat_source.py` alongside HeatSource?
   - Recommendation: Phase 9 first task should verify import path and adjust accordingly. Plan for `from thermal_sim.models.material_zone import MaterialZone` and fall back to inline if it's defined in `layer.py`.

2. **nz spinbox in Layers tab — inline vs separate column**
   - What we know: It is Claude's discretion. Options are: (a) extra column in `layers_table`, (b) separate QSpinBox per row below the table, (c) QSpinBox in zone sub-table header.
   - Recommendation: Add `nz` as an extra column in `layers_table` (like adding a 5th column). This is the least disruptive UI change and fits the existing table-based pattern. Column header: `nz`.

3. **Zone sub-table widget lifecycle**
   - What we know: The layers table supports add/remove rows via existing buttons.
   - What's unclear: How zone sub-widgets are embedded relative to `layers_table` rows — QTableWidget doesn't support sub-widgets inside cells natively without setCellWidget.
   - Recommendation: Do NOT use `setCellWidget` to embed zone tables inside the layers table rows. Instead, place zone group-boxes as separate widgets in the Layers tab layout, below the main table, shown/hidden per the selected row. This matches how `_profile_panel` works for sources. The "toggle" is row-selection in `layers_table.itemSelectionChanged`, not a per-row button.

4. **Transient result z-slice display**
   - What we know: Transient result has shape `[nt, total_z, ny, nx]`. The existing `_plot_map` uses `final_temperatures_c` which is the last timestep slice `[total_z, ny, nx]`.
   - What's unclear: Whether the z-combo should affect transient display identically.
   - Recommendation: Yes — apply the same z-index logic to `last_transient_result.final_temperatures_c[flat_z_idx]`. No additional complexity needed.

---

## Sources

### Primary (HIGH confidence)
- Codebase direct read — `thermal_sim/ui/main_window.py` (full file), `thermal_sim/models/layer.py`, `thermal_sim/models/project.py`, `thermal_sim/models/stack_templates.py`, `thermal_sim/visualization/plotting.py`, `thermal_sim/ui/plot_manager.py`, `thermal_sim/solvers/steady_state.py`, `thermal_sim/solvers/network_builder.py`
- `.planning/phases/07-3d-solver-core/07-CONTEXT.md` — Phase 7 decisions on MaterialZone, Layer.zones
- `.planning/phases/08-z-refinement/08-CONTEXT.md` — Phase 8 decisions on Layer.nz, result shape, nz_per_layer, z_offsets
- `.planning/phases/09-3d-gui-and-eled-zone-preset/09-CONTEXT.md` — User decisions for this phase

### Secondary (MEDIUM confidence)
- PySide6 QComboBox `addItem(text, userData)` / `currentData()` — standard Qt 6 API, well-established

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already present in the project; no new dependencies
- Architecture: HIGH — all patterns directly observed in existing codebase code
- Pitfalls: HIGH — derived from direct code inspection, not speculation
- Phase 7/8 integration: MEDIUM — based on CONTEXT.md decisions, not implemented code (Phases 7/8 not yet executed)

**Research date:** 2026-03-16
**Valid until:** After Phase 7 and 8 are implemented — verify MaterialZone import path and result shape fields are exactly as described in their CONTEXT.md before beginning Phase 9 task 1.
