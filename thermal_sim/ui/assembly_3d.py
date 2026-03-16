"""Interactive 3D assembly preview using PyVista/VTK."""
from __future__ import annotations

import os
os.environ.setdefault("QT_API", "pyside6")

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyvista as pv

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from thermal_sim.models.project import DisplayProject

logger = logging.getLogger(__name__)

# Fixed recognizable colors for common display-module materials
_FIXED_COLORS: dict[str, tuple[float, float, float]] = {
    "Steel": (0.60, 0.60, 0.65),
    "Aluminum": (0.75, 0.78, 0.82),
    "FR4": (0.00, 0.50, 0.00),
    "PMMA": (0.85, 0.92, 0.95),
    "Glass": (0.70, 0.85, 0.95),
    "PC": (0.90, 0.90, 0.85),
    "Air Gap": (1.00, 1.00, 1.00),
    "Air": (0.95, 0.95, 1.00),
    "Copper": (0.85, 0.53, 0.10),
    "LGP": (0.80, 0.90, 0.98),
    "Diffuser": (0.95, 0.95, 0.88),
    "Reflector": (0.98, 0.98, 0.98),
}


def _material_color_map(material_names: list[str]) -> dict[str, tuple[float, float, float]]:
    """Return a mapping from material name to (R, G, B) in [0, 1].

    Known materials get fixed recognizable colors. Unknown materials cycle through
    matplotlib's tab20 colormap — consistent with structure_preview.py.
    """
    try:
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap("tab20")
    except Exception:
        cmap = None

    result: dict[str, tuple[float, float, float]] = {}
    tab20_index = 0
    for name in material_names:
        if name in _FIXED_COLORS:
            result[name] = _FIXED_COLORS[name]
        else:
            if cmap is not None:
                rgba = cmap(tab20_index % 20)
                result[name] = (rgba[0], rgba[1], rgba[2])
            else:
                # fallback grey palette
                g = 0.3 + 0.07 * (tab20_index % 10)
                result[name] = (g, g, g)
            tab20_index += 1
    return result


def build_assembly_blocks(project: "DisplayProject") -> list[dict]:
    """Convert a DisplayProject into a list of block descriptors for 3D rendering.

    All geometry is in millimetres for sensible VTK viewport scaling.

    Returns:
        List of dicts with keys:
            "mesh"    : pyvista.PolyData box mesh
            "color"   : (R, G, B) in [0, 1]
            "label"   : display label string
            "z_base"  : base z-position in mm (unmodified, used for explode)
            "layer_index" : physical layer index (0 = bottom)
            "is_zone" : True if this block represents a material zone
    """
    W_mm = project.width * 1000.0
    H_mm = project.height * 1000.0

    # Collect all material names for color assignment
    all_mat_names: list[str] = list(project.materials.keys())
    color_map = _material_color_map(all_mat_names)

    blocks: list[dict] = []
    z_base_mm = 0.0

    for layer_idx, layer in enumerate(project.layers):
        t_mm = layer.thickness * 1000.0
        z_top_mm = z_base_mm + t_mm

        # Main layer block
        main_color = color_map.get(layer.material, (0.6, 0.6, 0.6))
        main_mesh = pv.Box(bounds=[0.0, W_mm, 0.0, H_mm, z_base_mm, z_top_mm])
        blocks.append({
            "mesh": main_mesh,
            "color": main_color,
            "label": layer.name,
            "z_base": z_base_mm,
            "layer_index": layer_idx,
            "is_zone": False,
        })

        # Zone overlays (edge_layers + manual zones)
        zones = list(getattr(layer, "zones", []))

        # Generate edge layer zones (if any) and prepend to manual zones
        edge_layers_dict = getattr(layer, "edge_layers", {})
        if edge_layers_dict:
            try:
                from thermal_sim.models.stack_templates import generate_edge_zones
                edge_zones = generate_edge_zones(layer, project.width, project.height)
                zones = edge_zones + zones  # edge first, manual wins on overlap
            except (ValueError, ImportError):
                pass  # skip if edge layers are invalid or import fails

        for zone in zones:
            zmat = zone.material
            zone_color = color_map.get(zmat, (0.6, 0.6, 0.6))

            # MaterialZone uses centre-based x/y; convert to bounds
            x_c_mm = zone.x * 1000.0
            y_c_mm = zone.y * 1000.0
            w_mm = zone.width * 1000.0
            h_mm = zone.height * 1000.0
            x0 = x_c_mm - w_mm / 2.0
            x1 = x_c_mm + w_mm / 2.0
            y0 = y_c_mm - h_mm / 2.0
            y1 = y_c_mm + h_mm / 2.0
            # Clamp to layer bounds
            x0 = max(x0, 0.0)
            x1 = min(x1, W_mm)
            y0 = max(y0, 0.0)
            y1 = min(y1, H_mm)

            if x1 > x0 and y1 > y0:
                # Inset zone Z by 5% of layer thickness to avoid Z-fighting
                z_inset = t_mm * 0.05
                zone_mesh = pv.Box(bounds=[x0, x1, y0, y1, z_base_mm + z_inset, z_top_mm - z_inset])
                blocks.append({
                    "mesh": zone_mesh,
                    "color": zone_color,
                    "label": f"{layer.name} / {zmat}",
                    "z_base": z_base_mm,
                    "layer_index": layer_idx,
                    "is_zone": True,
                })

        z_base_mm = z_top_mm

    return blocks


class Assembly3DWidget(QWidget):
    """Interactive 3D assembly preview using PyVista/VTK QtInteractor.

    Shows the display stack as color-coded solid blocks. An explode slider
    separates layers vertically to inspect internal structure.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # PyVista plotter (embedded VTK widget)
        from pyvistaqt import QtInteractor
        self._plotter = QtInteractor(self)
        layout.addWidget(self._plotter.interactor)

        # Toggle button: Show Results / Show Structure
        btn_row = QHBoxLayout()
        self._toggle_btn = QPushButton("Show Results")
        self._toggle_btn.setEnabled(False)
        self._toggle_btn.setToolTip(
            "Switch between structure (material colors) and results (temperature) view"
        )
        self._toggle_btn.clicked.connect(self._on_toggle_view)
        btn_row.addWidget(self._toggle_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Explode slider row
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Explode:"))
        self._explode_slider = QSlider(Qt.Orientation.Horizontal)
        self._explode_slider.setRange(0, 100)
        self._explode_slider.setValue(0)
        self._explode_slider.setToolTip("Separate layers vertically to inspect internal structure")
        self._explode_slider.valueChanged.connect(self._on_explode)
        slider_row.addWidget(self._explode_slider)
        layout.addLayout(slider_row)

        # Cached state
        self._actors: list[tuple] = []    # (actor, base_z_mm, layer_index)
        self._blocks: list[dict] = []     # most-recently-built blocks
        self._max_explode_mm: float = 20.0  # default gap per layer in mm
        self._in_results_mode: bool = False
        self._last_project: "DisplayProject | None" = None
        self._last_result = None

    def update_assembly(self, project: "DisplayProject") -> None:
        """Rebuild the 3D assembly from the current project state.

        Clears the plotter, adds a block actor for each layer (and zone), adds
        layer name labels, then resets the camera.  Do NOT call plotter.show() —
        QtInteractor manages its own render loop.
        """
        self._last_project = project
        self._in_results_mode = False
        self._toggle_btn.setText("Show Results")
        self._toggle_btn.setEnabled(self._last_result is not None)

        try:
            self._blocks = build_assembly_blocks(project)
        except Exception as exc:
            logger.warning("Failed to build assembly blocks: %s", exc)
            return

        self._plotter.clear()
        self._actors = []

        # Set a dark background for contrast
        self._plotter.set_background("dimgray")

        for block in self._blocks:
            if block["is_zone"]:
                # Zones are slightly transparent to let main layer show through
                actor = self._plotter.add_mesh(
                    block["mesh"],
                    color=block["color"],
                    opacity=0.85,
                    smooth_shading=False,
                    show_edges=True,
                    edge_color="black",
                    line_width=0.5,
                )
            else:
                actor = self._plotter.add_mesh(
                    block["mesh"],
                    color=block["color"],
                    opacity=1.0,
                    smooth_shading=False,
                    show_edges=True,
                    edge_color="black",
                    line_width=0.5,
                )
            if actor is not None:
                self._actors.append((actor, block["z_base"], block["layer_index"]))

        # Add layer name labels at the top-center of each main (non-zone) layer block
        label_points = []
        label_texts = []
        for block in self._blocks:
            if not block["is_zone"]:
                # Place label at center-x, center-y, top of block
                W_mm = project.width * 1000.0
                H_mm = project.height * 1000.0
                t_mm = project.layers[block["layer_index"]].thickness * 1000.0
                label_points.append([W_mm / 2.0, H_mm / 2.0, block["z_base"] + t_mm])
                label_texts.append(block["label"])

        if label_points:
            try:
                pts = pv.PolyData(np.array(label_points, dtype=float))
                pts["labels"] = label_texts
                self._plotter.add_point_labels(
                    pts,
                    "labels",
                    point_size=5,
                    font_size=10,
                    text_color="white",
                    shape_opacity=0.4,
                    always_visible=True,
                    show_points=False,
                )
            except Exception as exc:
                logger.debug("Layer labels skipped: %s", exc)

        # Compute max explode gap as 20% of total height
        total_height_mm = sum(layer.thickness * 1000.0 for layer in project.layers)
        self._max_explode_mm = max(5.0, total_height_mm * 0.20)

        self._plotter.reset_camera()
        self._plotter.render()

        # Apply current slider position to any new actors
        current_value = self._explode_slider.value()
        if current_value > 0:
            self._on_explode(current_value)

    def _on_explode(self, value: int) -> None:
        """Translate actors vertically by an explode offset proportional to layer index.

        Args:
            value: Slider value in [0, 100].
        """
        if not self._actors:
            return

        explode_per_layer = (value / 100.0) * self._max_explode_mm

        for actor, base_z_mm, layer_idx in self._actors:
            z_offset = layer_idx * explode_per_layer
            try:
                actor.SetPosition(0.0, 0.0, z_offset)
            except Exception as exc:
                logger.debug("Could not set actor position: %s", exc)

        try:
            self._plotter.render()
        except Exception:
            pass

    def _on_toggle_view(self) -> None:
        """Toggle between structure and results view."""
        if self._last_project is None:
            return
        if self._in_results_mode:
            # Switch back to structure
            self._in_results_mode = False
            self._toggle_btn.setText("Show Results")
            # Re-render structure
            self.update_assembly(self._last_project)
        else:
            # Switch to results
            if self._last_result is None:
                return
            self.update_temperature(self._last_project, self._last_result)

    def update_temperature(self, project: "DisplayProject", result: object) -> None:
        """Overlay temperature data on the 3D assembly after a solve.

        Shows each layer as a structured grid colored by temperature using a
        "hot" colormap. A shared colorbar is shown on the first layer.

        Parameters
        ----------
        project:
            The solved DisplayProject (used for dimensions and layer metadata).
        result:
            SteadyStateResult or TransientResult — must have .temperatures_c
            attribute of shape (total_sublayers, ny, nx).
        """
        try:
            all_temps = result.temperatures_c  # type: ignore[union-attr]
        except AttributeError:
            logger.warning("update_temperature: result has no temperatures_c attribute")
            return

        t_min = float(np.min(all_temps))
        t_max = float(np.max(all_temps))
        if t_max - t_min < 0.01:
            t_max = t_min + 1.0  # avoid zero-range colormap

        # Store state for toggle; remember we are in results mode
        self._last_project = project
        self._last_result = result
        self._in_results_mode = True
        if hasattr(self, "_toggle_btn"):
            self._toggle_btn.setText("Show Structure")
            self._toggle_btn.setEnabled(True)

        self._plotter.clear()
        self._actors = []

        W_mm = project.width * 1000.0
        H_mm = project.height * 1000.0

        nz_per_layer = getattr(result, "nz_per_layer", None) or [1] * len(project.layers)
        z_offsets = getattr(result, "z_offsets", None) or list(range(len(project.layers)))

        z_base_mm = 0.0
        for l_idx, layer in enumerate(project.layers):
            t_mm = layer.thickness * 1000.0

            nz = nz_per_layer[l_idx]
            z_flat = z_offsets[l_idx] + nz - 1
            try:
                temp_map = all_temps[z_flat]  # (ny, nx)
            except (IndexError, TypeError):
                temp_map = all_temps[0] if len(all_temps) > 0 else np.zeros((1, 1))

            ny, nx = temp_map.shape
            dx = W_mm / nx
            dy = H_mm / ny

            grid = pv.ImageData(
                dimensions=(nx + 1, ny + 1, 2),
                spacing=(dx, dy, t_mm),
                origin=(0.0, 0.0, z_base_mm),
            )
            grid.cell_data["Temperature [C]"] = temp_map.ravel(order="C")

            actor = self._plotter.add_mesh(
                grid,
                scalars="Temperature [C]",
                cmap="hot",
                clim=(t_min, t_max),
                show_scalar_bar=(l_idx == 0),
                scalar_bar_args={"title": "Temperature [C]"},
            )
            if actor is not None:
                self._actors.append((actor, z_base_mm, l_idx))
            z_base_mm += t_mm

        self._plotter.reset_camera()
        self._plotter.render()

        # Apply current explode level
        current_value = self._explode_slider.value()
        if current_value > 0:
            self._on_explode(current_value)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Release VTK resources when the widget closes."""
        try:
            self._plotter.close()
        except Exception:
            pass
        super().closeEvent(event)
