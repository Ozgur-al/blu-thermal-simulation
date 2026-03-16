"""Voxel3DView — interactive 3D PyVista view for the voxel-based solver.

Shows assembly blocks as color-coded solids with slice planes, block
transparency/hide controls, temperature threshold filter, and probe markers.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

os.environ.setdefault("QT_API", "pyside6")

import numpy as np
import pyvista as pv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from thermal_sim.models.voxel_project import VoxelProject
    from thermal_sim.solvers.steady_state_voxel import VoxelSteadyStateResult
    from thermal_sim.solvers.transient_voxel import VoxelTransientResult

logger = logging.getLogger(__name__)

# Fixed recognizable colors for common display-module materials (same as assembly_3d.py)
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
    """Return a mapping from material name to (R, G, B) in [0, 1]."""
    try:
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap("tab20")
    except Exception:
        cmap = None

    result: dict[str, tuple[float, float, float]] = {}
    tab20_index = 0
    for name in material_names:
        matched = _FIXED_COLORS.get(name)
        if matched is None:
            for key, color in _FIXED_COLORS.items():
                if key in name:
                    matched = color
                    break
        if matched is not None:
            result[name] = matched
        else:
            if cmap is not None:
                rgba = cmap(tab20_index % 20)
                result[name] = (rgba[0], rgba[1], rgba[2])
            else:
                g = 0.3 + 0.07 * (tab20_index % 10)
                result[name] = (g, g, g)
            tab20_index += 1
    return result


class Voxel3DView(QWidget):
    """Interactive 3D view for the voxel-based solver.

    Pre-solve: shows assembly blocks as color-coded rectangular solids.
    Post-solve: overlays temperature data via RectilinearGrid with interactive
    slice planes in X, Y, Z.

    Controls:
    - Block visibility/transparency toggles
    - Temperature threshold filter
    - X/Y/Z slice planes via sliders
    - Reset camera button
    - Toggle between structure and temperature modes
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._last_project: "VoxelProject | None" = None
        self._last_result: "VoxelSteadyStateResult | VoxelTransientResult | None" = None
        self._in_results_mode: bool = False

        # Block actors: block_name -> actor
        self._block_actors: dict[str, object] = {}
        self._temp_grid: pv.RectilinearGrid | None = None
        self._temp_grid_actor: object | None = None
        self._slice_actors: dict[str, object] = {}  # 'x', 'y', 'z' -> actor
        self._probe_actors: list[object] = []

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # Left panel: PyVista plotter
        from pyvistaqt import QtInteractor
        self._plotter = QtInteractor(self)
        self._plotter.set_background("dimgray")
        main_layout.addWidget(self._plotter.interactor, stretch=3)

        # Right panel: controls
        ctrl_widget = QWidget()
        ctrl_widget.setMaximumWidth(240)
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(2, 2, 2, 2)
        ctrl_layout.setSpacing(4)

        # Toolbar: Reset Camera, Toggle mode
        btn_row = QHBoxLayout()
        self._reset_btn = QPushButton("Reset Camera")
        self._reset_btn.setToolTip("Reset the camera to fit all visible objects")
        self._reset_btn.clicked.connect(self._on_reset_camera)
        btn_row.addWidget(self._reset_btn)

        self._toggle_btn = QPushButton("Show Temp")
        self._toggle_btn.setToolTip("Toggle between structure and temperature result view")
        self._toggle_btn.setEnabled(False)
        self._toggle_btn.clicked.connect(self._on_toggle_mode)
        btn_row.addWidget(self._toggle_btn)
        ctrl_layout.addLayout(btn_row)

        # Block visibility controls
        vis_group = QGroupBox("Block Visibility")
        vis_layout = QVBoxLayout(vis_group)
        self._block_list = QListWidget()
        self._block_list.setMaximumHeight(150)
        self._block_list.setToolTip("Check/uncheck blocks to toggle visibility")
        self._block_list.itemChanged.connect(self._on_block_visibility_changed)
        vis_layout.addWidget(self._block_list)
        ctrl_layout.addWidget(vis_group)

        # Slice planes
        slice_group = QGroupBox("Slice Planes")
        slice_layout = QVBoxLayout(slice_group)

        for axis in ("X", "Y", "Z"):
            row = QHBoxLayout()
            chk = QCheckBox(f"{axis} slice")
            chk.setToolTip(f"Show a cutting plane perpendicular to the {axis}-axis")
            chk.setObjectName(f"slice_chk_{axis.lower()}")
            chk.stateChanged.connect(self._on_slice_toggled)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(50)
            slider.setObjectName(f"slice_slider_{axis.lower()}")
            slider.setToolTip(f"Position of the {axis} slice plane (0=min, 100=max)")
            slider.valueChanged.connect(self._on_slice_changed)
            row.addWidget(chk)
            row.addWidget(slider)
            slice_layout.addLayout(row)
        ctrl_layout.addWidget(slice_group)

        # Temperature threshold
        thresh_group = QGroupBox("Threshold Filter")
        thresh_layout = QVBoxLayout(thresh_group)
        thresh_row = QHBoxLayout()
        self._thresh_spin = QDoubleSpinBox()
        self._thresh_spin.setRange(-100.0, 2000.0)
        self._thresh_spin.setValue(50.0)
        self._thresh_spin.setSuffix(" °C")
        self._thresh_spin.setToolTip("Show only voxels above this temperature")
        self._thresh_apply_btn = QPushButton("Apply")
        self._thresh_apply_btn.setToolTip("Apply temperature threshold filter")
        self._thresh_apply_btn.clicked.connect(self._on_apply_threshold)
        self._thresh_clear_btn = QPushButton("Clear")
        self._thresh_clear_btn.setToolTip("Remove threshold filter and show all voxels")
        self._thresh_clear_btn.clicked.connect(self._on_clear_threshold)
        thresh_row.addWidget(self._thresh_spin)
        thresh_row.addWidget(self._thresh_apply_btn)
        thresh_row.addWidget(self._thresh_clear_btn)
        thresh_layout.addLayout(thresh_row)
        ctrl_layout.addWidget(thresh_group)

        ctrl_layout.addStretch()
        main_layout.addWidget(ctrl_widget, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_structure(self, project: "VoxelProject") -> None:
        """Rebuild block visualization from a VoxelProject."""
        self._last_project = project
        self._in_results_mode = False
        self._toggle_btn.setText("Show Temp")
        self._toggle_btn.setEnabled(self._last_result is not None)

        self._plotter.clear()
        self._block_actors.clear()
        self._temp_grid = None
        self._temp_grid_actor = None
        self._slice_actors.clear()
        self._probe_actors.clear()

        if not project.blocks:
            self._plotter.render()
            return

        all_mat = list(project.materials.keys())
        color_map = _material_color_map(all_mat)

        # Populate block-list widget (block signals while rebuilding)
        self._block_list.blockSignals(True)
        self._block_list.clear()

        for blk in project.blocks:
            # Geometry in mm for sensible VTK viewport
            x0 = blk.x * 1000.0
            y0 = blk.y * 1000.0
            z0 = blk.z * 1000.0
            x1 = x0 + blk.width * 1000.0
            y1 = y0 + blk.depth * 1000.0
            z1 = z0 + blk.height * 1000.0
            mesh = pv.Box(bounds=[x0, x1, y0, y1, z0, z1])
            color = color_map.get(blk.material, (0.6, 0.6, 0.6))

            actor = self._plotter.add_mesh(
                mesh,
                color=color,
                opacity=1.0,
                smooth_shading=False,
                show_edges=True,
                edge_color="black",
                line_width=0.5,
                label=blk.name,
            )
            if actor is not None:
                self._block_actors[blk.name] = actor

            # Visibility list item
            item = QListWidgetItem(blk.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._block_list.addItem(item)

        self._block_list.blockSignals(False)

        # Block labels
        label_points = []
        label_texts = []
        for blk in project.blocks:
            cx = (blk.x + blk.width / 2.0) * 1000.0
            cy = (blk.y + blk.depth / 2.0) * 1000.0
            cz = (blk.z + blk.height) * 1000.0  # top face
            label_points.append([cx, cy, cz])
            label_texts.append(blk.name)

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
                logger.debug("Block labels skipped: %s", exc)

        # Probe markers
        self._render_probe_markers(project)

        self._plotter.reset_camera()
        self._plotter.render()

    def update_temperature(
        self,
        result: "VoxelSteadyStateResult | VoxelTransientResult",
        timestep: int | None = None,
    ) -> None:
        """Overlay temperature data on the 3D view after solving.

        Uses a RectilinearGrid with cell_data['Temperature_C'] derived from
        the result mesh edges. VTK expects Fortran-order raveling.
        """
        try:
            temps_c = result.temperatures_c  # type: ignore[union-attr]
        except AttributeError:
            logger.warning("update_temperature: result has no temperatures_c")
            return

        # For transient results, pick the requested timestep or last
        if temps_c.ndim == 4:
            idx = timestep if timestep is not None else (temps_c.shape[0] - 1)
            temps_3d = temps_c[idx]
        else:
            temps_3d = temps_c  # already (nz, ny, nx)

        self._last_result = result
        self._in_results_mode = True
        self._toggle_btn.setText("Show Structure")
        self._toggle_btn.setEnabled(True)

        # Clear existing temperature actors
        if self._temp_grid_actor is not None:
            try:
                self._plotter.remove_actor(self._temp_grid_actor)
            except Exception:
                pass
            self._temp_grid_actor = None
        for actor in self._slice_actors.values():
            try:
                self._plotter.remove_actor(actor)
            except Exception:
                pass
        self._slice_actors.clear()

        # Build RectilinearGrid using the mesh edge arrays (in mm)
        mesh = result.mesh
        x_edges_mm = mesh.x_edges * 1000.0
        y_edges_mm = mesh.y_edges * 1000.0
        z_edges_mm = mesh.z_edges * 1000.0

        grid = pv.RectilinearGrid(x_edges_mm, y_edges_mm, z_edges_mm)
        # VTK/PyVista RectilinearGrid expects Fortran order: x varies fastest
        grid.cell_data["Temperature_C"] = temps_3d.ravel(order="F")

        self._temp_grid = grid

        t_min = float(np.min(temps_3d))
        t_max = float(np.max(temps_3d))
        if t_max - t_min < 0.01:
            t_max = t_min + 1.0

        # Hide block structure actors to show temperature overlay
        for actor in self._block_actors.values():
            try:
                actor.SetVisibility(False)
            except Exception:
                pass

        self._temp_grid_actor = self._plotter.add_mesh(
            grid,
            scalars="Temperature_C",
            cmap="hot",
            clim=(t_min, t_max),
            show_scalar_bar=True,
            scalar_bar_args={"title": "Temperature [C]"},
        )

        # Probe markers with temperature annotation
        if self._last_project is not None:
            self._render_probe_markers(self._last_project, temps_3d, mesh)

        self._plotter.reset_camera()
        self._plotter.render()

    def clear(self) -> None:
        """Reset the view to an empty state."""
        self._plotter.clear()
        self._block_actors.clear()
        self._temp_grid = None
        self._temp_grid_actor = None
        self._slice_actors.clear()
        self._probe_actors.clear()
        self._block_list.clear()
        self._in_results_mode = False
        self._toggle_btn.setText("Show Temp")
        self._toggle_btn.setEnabled(False)
        self._plotter.render()

    # ------------------------------------------------------------------
    # Probe rendering
    # ------------------------------------------------------------------

    def _render_probe_markers(
        self,
        project: "VoxelProject",
        temps_3d: np.ndarray | None = None,
        mesh=None,
    ) -> None:
        """Add labeled probe markers to the plotter."""
        for actor in self._probe_actors:
            try:
                self._plotter.remove_actor(actor)
            except Exception:
                pass
        self._probe_actors.clear()

        if not project.probes:
            return

        pts_coords = []
        pts_labels = []

        for probe in project.probes:
            px = probe.x * 1000.0
            py = probe.y * 1000.0
            pz = probe.z * 1000.0
            pts_coords.append([px, py, pz])

            # Look up temperature at probe location if available
            label = probe.name
            if temps_3d is not None and mesh is not None:
                try:
                    ix = int(np.searchsorted(mesh.x_centers(), probe.x) - 1)
                    iy = int(np.searchsorted(mesh.y_centers(), probe.y) - 1)
                    iz = int(np.searchsorted(mesh.z_centers(), probe.z) - 1)
                    ix = max(0, min(ix, mesh.nx - 1))
                    iy = max(0, min(iy, mesh.ny - 1))
                    iz = max(0, min(iz, mesh.nz - 1))
                    t = temps_3d[iz, iy, ix]
                    label = f"{probe.name}\n{t:.1f}°C"
                except Exception:
                    pass
            pts_labels.append(label)

        if pts_coords:
            try:
                pts = pv.PolyData(np.array(pts_coords, dtype=float))
                pts["labels"] = pts_labels
                actor = self._plotter.add_point_labels(
                    pts,
                    "labels",
                    point_size=10,
                    font_size=9,
                    text_color="cyan",
                    shape_opacity=0.5,
                    always_visible=True,
                    show_points=True,
                )
                self._probe_actors.append(actor)
            except Exception as exc:
                logger.debug("Probe markers skipped: %s", exc)

    # ------------------------------------------------------------------
    # Toolbar handlers
    # ------------------------------------------------------------------

    def _on_reset_camera(self) -> None:
        self._plotter.reset_camera()
        self._plotter.render()

    def _on_toggle_mode(self) -> None:
        if self._in_results_mode:
            # Switch back to structure
            if self._last_project is not None:
                self.update_structure(self._last_project)
        else:
            # Switch to temperature
            if self._last_result is not None:
                self.update_temperature(self._last_result)

    # ------------------------------------------------------------------
    # Block visibility
    # ------------------------------------------------------------------

    def _on_block_visibility_changed(self, item: QListWidgetItem) -> None:
        name = item.text()
        visible = item.checkState() == Qt.CheckState.Checked
        actor = self._block_actors.get(name)
        if actor is not None:
            try:
                actor.SetVisibility(visible)
                self._plotter.render()
            except Exception as exc:
                logger.debug("Could not set block visibility: %s", exc)

    # ------------------------------------------------------------------
    # Slice planes
    # ------------------------------------------------------------------

    def _get_slice_widgets(self, axis: str) -> tuple[QCheckBox | None, QSlider | None]:
        chk = self.findChild(QCheckBox, f"slice_chk_{axis.lower()}")
        slider = self.findChild(QSlider, f"slice_slider_{axis.lower()}")
        return chk, slider  # type: ignore[return-value]

    def _on_slice_toggled(self) -> None:
        self._update_slices()

    def _on_slice_changed(self) -> None:
        self._update_slices()

    def _update_slices(self) -> None:
        if self._temp_grid is None:
            return

        for axis in ("x", "y", "z"):
            actor_key = axis
            chk, slider = self._get_slice_widgets(axis)
            if chk is None or slider is None:
                continue

            # Remove existing slice actor for this axis
            if actor_key in self._slice_actors:
                try:
                    self._plotter.remove_actor(self._slice_actors[actor_key])
                except Exception:
                    pass
                del self._slice_actors[actor_key]

            if not chk.isChecked():
                continue

            # Compute position along this axis
            bounds = self._temp_grid.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)
            axis_idx = {"x": (0, 1), "y": (2, 3), "z": (4, 5)}[axis]
            lo = bounds[axis_idx[0]]
            hi = bounds[axis_idx[1]]
            pos = lo + (slider.value() / 100.0) * (hi - lo)

            try:
                # Slice requires point_data for interpolation; convert from cell_data
                grid_pd = self._temp_grid.cell_data_to_point_data()
                origin = list(grid_pd.center)
                origin[{"x": 0, "y": 1, "z": 2}[axis]] = pos
                sliced = grid_pd.slice(normal=axis, origin=origin)
                t_min = float(self._temp_grid.cell_data["Temperature_C"].min())
                t_max = float(self._temp_grid.cell_data["Temperature_C"].max())
                if t_max - t_min < 0.01:
                    t_max = t_min + 1.0

                actor = self._plotter.add_mesh(
                    sliced,
                    scalars="Temperature_C",
                    cmap="hot",
                    clim=(t_min, t_max),
                    show_scalar_bar=False,
                )
                self._slice_actors[actor_key] = actor
            except Exception as exc:
                logger.debug("Slice %s failed: %s", axis, exc)

        # Hide the full temperature grid when any slice is active so slices
        # aren't obscured; restore it when all slices are cleared.
        any_slice_active = len(self._slice_actors) > 0
        if self._temp_grid_actor is not None:
            try:
                self._temp_grid_actor.SetVisibility(not any_slice_active)
            except Exception:
                pass

        self._plotter.render()

    # ------------------------------------------------------------------
    # Threshold
    # ------------------------------------------------------------------

    def _on_apply_threshold(self) -> None:
        if self._temp_grid is None:
            return

        threshold_val = self._thresh_spin.value()
        try:
            thresholded = self._temp_grid.threshold(
                threshold_val, scalars="Temperature_C"
            )

            # Remove old temperature actor
            if self._temp_grid_actor is not None:
                try:
                    self._plotter.remove_actor(self._temp_grid_actor)
                except Exception:
                    pass

            t_min = float(self._temp_grid.cell_data["Temperature_C"].min())
            t_max = float(self._temp_grid.cell_data["Temperature_C"].max())
            if t_max - t_min < 0.01:
                t_max = t_min + 1.0

            self._temp_grid_actor = self._plotter.add_mesh(
                thresholded,
                scalars="Temperature_C",
                cmap="hot",
                clim=(t_min, t_max),
                show_scalar_bar=True,
                scalar_bar_args={"title": "Temperature [C]"},
            )
            self._plotter.render()
        except Exception as exc:
            logger.warning("Threshold apply failed: %s", exc)

    def _on_clear_threshold(self) -> None:
        if self._temp_grid is None or not self._in_results_mode:
            return
        if self._last_result is not None:
            self.update_temperature(self._last_result)

    # ------------------------------------------------------------------
    # Window cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._plotter.close()
        except Exception:
            pass
        super().closeEvent(event)
