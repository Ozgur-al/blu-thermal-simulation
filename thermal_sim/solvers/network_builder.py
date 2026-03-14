"""Shared thermal network builder used by steady and transient solvers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix

from thermal_sim.core.constants import STEFAN_BOLTZMANN
from thermal_sim.core.geometry import Grid2D
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.project import DisplayProject


@dataclass(frozen=True)
class ThermalNetwork:
    """Discrete network representation of the project."""

    a_matrix: csr_matrix
    b_boundary: np.ndarray   # boundary contributions (g * T_amb for surface nodes)
    b_sources: np.ndarray    # heat source contributions at nominal power_w
    c_vector: np.ndarray
    grid: Grid2D
    n_layers: int
    layer_names: list[str]

    @property
    def b_vector(self) -> np.ndarray:
        """Combined forcing vector — backward-compatible sum of boundary + source terms."""
        return self.b_boundary + self.b_sources

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

    # COO triplet accumulators for sparse matrix assembly.
    coo_rows: list[np.ndarray] = []
    coo_cols: list[np.ndarray] = []
    coo_data: list[np.ndarray] = []

    b_boundary = np.zeros(n_nodes, dtype=float)
    b_sources = np.zeros(n_nodes, dtype=float)
    c_vec = np.zeros(n_nodes, dtype=float)

    def node_index(layer_idx: int, ix: int, iy: int) -> int:
        return layer_idx * n_per_layer + iy * grid.nx + ix

    def _add_link_vectorized(n1: np.ndarray, n2: np.ndarray, conductance: float) -> None:
        """Add symmetric conductance links between node pairs in COO format."""
        if conductance <= 0.0:
            return
        g = np.full(len(n1), conductance, dtype=float)
        # Four COO entries per link: diagonal +=g, off-diagonal -=g.
        coo_rows.append(n1)
        coo_cols.append(n1)
        coo_data.append(g)

        coo_rows.append(n2)
        coo_cols.append(n2)
        coo_data.append(g)

        coo_rows.append(n1)
        coo_cols.append(n2)
        coo_data.append(-g)

        coo_rows.append(n2)
        coo_cols.append(n1)
        coo_data.append(-g)

    # Node thermal capacities (vectorized per layer).
    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        c_node = material.density * material.specific_heat * layer.thickness * area
        start = l_idx * n_per_layer
        c_vec[start : start + n_per_layer] = c_node

    # Lateral conduction inside each layer.
    # flat_idx = iy * nx + ix;  node = l_idx * n_per_layer + flat_idx
    iy_all = np.repeat(np.arange(grid.ny), grid.nx)   # shape (n_per_layer,)
    ix_all = np.tile(np.arange(grid.nx), grid.ny)     # shape (n_per_layer,)
    flat_all = iy_all * grid.nx + ix_all              # shape (n_per_layer,)

    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        g_x = material.k_in_plane * layer.thickness * grid.dy / grid.dx
        g_y = material.k_in_plane * layer.thickness * grid.dx / grid.dy
        base = l_idx * n_per_layer

        # Horizontal links: (ix, iy) -- (ix+1, iy)  where ix < nx-1
        mask_x = ix_all < (grid.nx - 1)
        flat_left = flat_all[mask_x]
        flat_right = flat_left + 1
        _add_link_vectorized(base + flat_left, base + flat_right, g_x)

        # Vertical links: (ix, iy) -- (ix, iy+1)  where iy < ny-1
        mask_y = iy_all < (grid.ny - 1)
        flat_bottom = flat_all[mask_y]
        flat_top = flat_bottom + grid.nx
        _add_link_vectorized(base + flat_bottom, base + flat_top, g_y)

    # Through-thickness conduction between adjacent layers.
    flat_all_layer = np.arange(n_per_layer)
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
        n1 = l_idx * n_per_layer + flat_all_layer
        n2 = (l_idx + 1) * n_per_layer + flat_all_layer
        _add_link_vectorized(n1, n2, g_z)

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
    # Top layer nodes.
    top_indices = (n_layers - 1) * n_per_layer + flat_all_layer
    if g_top > 0.0:
        coo_rows.append(top_indices)
        coo_cols.append(top_indices)
        coo_data.append(np.full(n_per_layer, g_top, dtype=float))
        b_boundary[top_indices] += g_top * project.boundaries.top.ambient_c

    # Bottom layer nodes.
    bot_indices = flat_all_layer  # 0 * n_per_layer + flat
    if g_bot > 0.0:
        coo_rows.append(bot_indices)
        coo_cols.append(bot_indices)
        coo_data.append(np.full(n_per_layer, g_bot, dtype=float))
        b_boundary[bot_indices] += g_bot * project.boundaries.bottom.ambient_c

    # Side ambient sinks (all layers, perimeter cells only).
    side_amb = project.boundaries.side.ambient_c
    for l_idx, layer in enumerate(project.layers):
        material = project.material_for_layer(l_idx)
        g_x_edge = _surface_sink_conductance(
            boundary=project.boundaries.side,
            emissivity=material.emissivity,
            conduction_distance=grid.dx / 2.0,
            conductivity=material.k_in_plane,
            area=layer.thickness * grid.dy,
        )
        g_y_edge = _surface_sink_conductance(
            boundary=project.boundaries.side,
            emissivity=material.emissivity,
            conduction_distance=grid.dy / 2.0,
            conductivity=material.k_in_plane,
            area=layer.thickness * grid.dx,
        )
        base = l_idx * n_per_layer

        # Left edge: ix=0, all iy.
        left_flat = np.arange(grid.ny) * grid.nx       # iy*nx + 0
        # Right edge: ix=nx-1, all iy.
        right_flat = np.arange(grid.ny) * grid.nx + (grid.nx - 1)
        # Bottom edge: iy=0, all ix.
        bottom_flat = np.arange(grid.nx)               # 0*nx + ix
        # Top edge: iy=ny-1, all ix.
        top_flat = (grid.ny - 1) * grid.nx + np.arange(grid.nx)

        if g_x_edge > 0.0:
            lr_flat = np.concatenate([left_flat, right_flat])
            lr_nodes = base + lr_flat
            coo_rows.append(lr_nodes)
            coo_cols.append(lr_nodes)
            coo_data.append(np.full(len(lr_nodes), g_x_edge, dtype=float))
            b_boundary[lr_nodes] += g_x_edge * side_amb

        if g_y_edge > 0.0:
            tb_flat = np.concatenate([bottom_flat, top_flat])
            tb_nodes = base + tb_flat
            coo_rows.append(tb_nodes)
            coo_cols.append(tb_nodes)
            coo_data.append(np.full(len(tb_nodes), g_y_edge, dtype=float))
            b_boundary[tb_nodes] += g_y_edge * side_amb

    # Assemble COO -> CSR in one shot.
    if coo_rows:
        all_rows = np.concatenate(coo_rows)
        all_cols = np.concatenate(coo_cols)
        all_data = np.concatenate(coo_data)
        a_mat = coo_matrix(
            (all_data, (all_rows, all_cols)), shape=(n_nodes, n_nodes), dtype=float
        ).tocsr()
    else:
        a_mat = csr_matrix((n_nodes, n_nodes), dtype=float)

    _apply_heat_sources(project, grid, b_sources, node_index)
    return ThermalNetwork(
        a_matrix=a_mat,
        b_boundary=b_boundary,
        b_sources=b_sources,
        c_vector=c_vec,
        grid=grid,
        n_layers=n_layers,
        layer_names=[layer.name for layer in project.layers],
    )


def build_heat_source_vector(
    project: DisplayProject,
    grid: Grid2D,
    time_s: float | None = None,
) -> np.ndarray:
    """Build the heat-source forcing vector at a given simulation time.

    When ``time_s`` is None (or sources have no power_profile), this is
    equivalent to the nominal ``b_sources`` from ``build_thermal_network``.
    When ``time_s`` is provided, each source is scaled by its
    ``power_at_time(time_s)`` instead of its static ``power_w``.
    """
    n_per_layer = grid.nx * grid.ny
    n_layers = len(project.layers)
    n_nodes = n_layers * n_per_layer
    b_vec = np.zeros(n_nodes, dtype=float)

    x_centers = grid.x_centers()
    y_centers = grid.y_centers()
    xx, yy = np.meshgrid(x_centers, y_centers)

    layer_index_cache: dict[str, int] = {
        layer.name: idx for idx, layer in enumerate(project.layers)
    }

    for source in project.expanded_heat_sources():
        layer_idx = layer_index_cache[source.layer]
        mask = _source_mask(source, xx, yy)
        iy_arr, ix_arr = np.where(mask)
        if iy_arr.size == 0:
            continue  # Already validated during initial network build
        power = source.power_at_time(time_s) if time_s is not None else source.power_w
        power_per_node = power / iy_arr.size
        linear = layer_idx * n_per_layer + iy_arr * grid.nx + ix_arr
        np.add.at(b_vec, linear, power_per_node)

    return b_vec


def _apply_heat_sources(
    project: DisplayProject,
    grid: Grid2D,
    b_vec: np.ndarray,
    node_index_fn,
) -> None:
    x_centers = grid.x_centers()
    y_centers = grid.y_centers()
    xx, yy = np.meshgrid(x_centers, y_centers)

    # Cache layer name -> index to avoid repeated linear search.
    layer_index_cache: dict[str, int] = {
        layer.name: idx for idx, layer in enumerate(project.layers)
    }
    n_per_layer = grid.nx * grid.ny

    for source in project.expanded_heat_sources():
        layer_idx = layer_index_cache[source.layer]
        mask = _source_mask(source, xx, yy)
        iy_arr, ix_arr = np.where(mask)
        if iy_arr.size == 0:
            raise ValueError(
                f"Heat source '{source.name}' does not overlap any mesh cell. "
                "Increase mesh density or adjust source geometry."
            )
        power_per_node = source.power_w / iy_arr.size
        linear = layer_idx * n_per_layer + iy_arr * grid.nx + ix_arr
        np.add.at(b_vec, linear, power_per_node)


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
