"""Shared thermal network builder used by steady and transient solvers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix

from thermal_sim.core.constants import STEFAN_BOLTZMANN
from thermal_sim.core.geometry import Grid2D
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.project import DisplayProject


@dataclass(frozen=True)
class ThermalNetwork:
    """Discrete network representation of the project."""

    a_matrix: csr_matrix
    b_vector: np.ndarray
    c_vector: np.ndarray
    grid: Grid2D
    n_layers: int
    layer_names: list[str]

    @property
    def n_nodes(self) -> int:
        return self.n_layers * self.grid.nx * self.grid.ny


def build_thermal_network(project: DisplayProject) -> ThermalNetwork:
    """Build linear thermal network A*T=b with thermal capacities C."""
    grid = Grid2D(project.width, project.height, project.mesh.nx, project.mesh.ny)
    n_layers = len(project.layers)
    n_per_layer = grid.nx * grid.ny
    n_nodes = n_layers * n_per_layer
    area = grid.cell_area

    a_mat = lil_matrix((n_nodes, n_nodes), dtype=float)
    b_vec = np.zeros(n_nodes, dtype=float)
    c_vec = np.zeros(n_nodes, dtype=float)

    def node_index(layer_idx: int, ix: int, iy: int) -> int:
        return layer_idx * n_per_layer + iy * grid.nx + ix

    def add_link(n1: int, n2: int, conductance: float) -> None:
        if conductance <= 0.0:
            return
        a_mat[n1, n1] += conductance
        a_mat[n2, n2] += conductance
        a_mat[n1, n2] -= conductance
        a_mat[n2, n1] -= conductance

    def add_sink(n: int, conductance: float, ambient_c: float) -> None:
        if conductance <= 0.0:
            return
        a_mat[n, n] += conductance
        b_vec[n] += conductance * ambient_c

    # Node thermal capacities.
    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        c_node = material.density * material.specific_heat * layer.thickness * area
        for iy in range(grid.ny):
            for ix in range(grid.nx):
                c_vec[node_index(l_idx, ix, iy)] = c_node

    # Lateral conduction inside each layer.
    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        g_x = material.k_in_plane * layer.thickness * grid.dy / grid.dx
        g_y = material.k_in_plane * layer.thickness * grid.dx / grid.dy
        for iy in range(grid.ny):
            for ix in range(grid.nx):
                n = node_index(l_idx, ix, iy)
                if ix + 1 < grid.nx:
                    add_link(n, node_index(l_idx, ix + 1, iy), g_x)
                if iy + 1 < grid.ny:
                    add_link(n, node_index(l_idx, ix, iy + 1), g_y)

    # Through-thickness conduction between adjacent layers.
    for l_idx in range(n_layers - 1):
        lower = project.layers[l_idx]
        upper = project.layers[l_idx + 1]
        lower_mat = project.material_for_layer(l_idx)
        upper_mat = project.material_for_layer(l_idx + 1)

        r_total = (
            (lower.thickness / (2.0 * lower_mat.k_through * area))
            + (lower.interface_resistance_to_next / area)
            + (upper.thickness / (2.0 * upper_mat.k_through * area))
        )
        g_z = 1.0 / r_total
        for iy in range(grid.ny):
            for ix in range(grid.nx):
                add_link(node_index(l_idx, ix, iy), node_index(l_idx + 1, ix, iy), g_z)

    # Top/bottom ambient sinks.
    top_layer = project.layers[-1]
    bot_layer = project.layers[0]
    top_mat = project.material_for_layer(n_layers - 1)
    bot_mat = project.material_for_layer(0)
    g_top = _surface_sink_conductance(
        boundary=project.boundaries.top,
        emissivity=top_mat.emissivity,
        conduction_distance=top_layer.thickness / 2.0,
        conductivity=top_mat.k_through,
        area=area,
    )
    g_bot = _surface_sink_conductance(
        boundary=project.boundaries.bottom,
        emissivity=bot_mat.emissivity,
        conduction_distance=bot_layer.thickness / 2.0,
        conductivity=bot_mat.k_through,
        area=area,
    )
    for iy in range(grid.ny):
        for ix in range(grid.nx):
            add_sink(node_index(n_layers - 1, ix, iy), g_top, project.boundaries.top.ambient_c)
            add_sink(node_index(0, ix, iy), g_bot, project.boundaries.bottom.ambient_c)

    # Side ambient sinks (all layers, perimeter cells).
    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        for iy in range(grid.ny):
            for ix in range(grid.nx):
                n = node_index(l_idx, ix, iy)
                if ix == 0:
                    g = _surface_sink_conductance(
                        boundary=project.boundaries.side,
                        emissivity=material.emissivity,
                        conduction_distance=grid.dx / 2.0,
                        conductivity=material.k_in_plane,
                        area=layer.thickness * grid.dy,
                    )
                    add_sink(n, g, project.boundaries.side.ambient_c)
                if ix == grid.nx - 1:
                    g = _surface_sink_conductance(
                        boundary=project.boundaries.side,
                        emissivity=material.emissivity,
                        conduction_distance=grid.dx / 2.0,
                        conductivity=material.k_in_plane,
                        area=layer.thickness * grid.dy,
                    )
                    add_sink(n, g, project.boundaries.side.ambient_c)
                if iy == 0:
                    g = _surface_sink_conductance(
                        boundary=project.boundaries.side,
                        emissivity=material.emissivity,
                        conduction_distance=grid.dy / 2.0,
                        conductivity=material.k_in_plane,
                        area=layer.thickness * grid.dx,
                    )
                    add_sink(n, g, project.boundaries.side.ambient_c)
                if iy == grid.ny - 1:
                    g = _surface_sink_conductance(
                        boundary=project.boundaries.side,
                        emissivity=material.emissivity,
                        conduction_distance=grid.dy / 2.0,
                        conductivity=material.k_in_plane,
                        area=layer.thickness * grid.dx,
                    )
                    add_sink(n, g, project.boundaries.side.ambient_c)

    _apply_heat_sources(project, grid, b_vec, node_index)
    return ThermalNetwork(
        a_matrix=a_mat.tocsr(),
        b_vector=b_vec,
        c_vector=c_vec,
        grid=grid,
        n_layers=n_layers,
        layer_names=[layer.name for layer in project.layers],
    )


def _apply_heat_sources(
    project: DisplayProject,
    grid: Grid2D,
    b_vec: np.ndarray,
    node_index_fn,
) -> None:
    x_centers = grid.x_centers()
    y_centers = grid.y_centers()
    xx, yy = np.meshgrid(x_centers, y_centers)

    for source in project.expanded_heat_sources():
        layer_idx = project.layer_index(source.layer)
        mask = _source_mask(source, xx, yy)
        target_indices = np.argwhere(mask)
        if target_indices.size == 0:
            raise ValueError(
                f"Heat source '{source.name}' does not overlap any mesh cell. "
                "Increase mesh density or adjust source geometry."
            )
        power_per_node = source.power_w / target_indices.shape[0]
        for iy, ix in target_indices:
            b_vec[node_index_fn(layer_idx, int(ix), int(iy))] += power_per_node


def _source_mask(source: HeatSource, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    if source.shape == "full":
        return np.ones_like(xx, dtype=bool)
    if source.shape == "rectangle":
        x0 = source.x - source.width / 2.0
        x1 = source.x + source.width / 2.0
        y0 = source.y - source.height / 2.0
        y1 = source.y + source.height / 2.0
        return (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    if source.shape == "circle":
        return (xx - source.x) ** 2 + (yy - source.y) ** 2 <= source.radius**2
    raise ValueError(f"Unsupported heat source shape: {source.shape}")


def _surface_sink_conductance(
    boundary: SurfaceBoundary,
    emissivity: float,
    conduction_distance: float,
    conductivity: float,
    area: float,
) -> float:
    h_total = boundary.convection_h
    if boundary.include_radiation:
        eps = emissivity if boundary.emissivity_override is None else boundary.emissivity_override
        t_ref_k = boundary.ambient_c + 273.15
        h_total += 4.0 * eps * STEFAN_BOLTZMANN * t_ref_k**3
    if h_total <= 0.0:
        return 0.0

    r_cond = conduction_distance / (conductivity * area)
    r_env = 1.0 / (h_total * area)
    return 1.0 / (r_cond + r_env)
