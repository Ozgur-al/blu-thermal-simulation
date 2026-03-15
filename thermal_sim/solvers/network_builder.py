"""Shared thermal network builder used by steady and transient solvers."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix

from thermal_sim.core.constants import STEFAN_BOLTZMANN
from thermal_sim.core.geometry import Grid2D
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject

if TYPE_CHECKING:
    from thermal_sim.models.layer import Layer


# ---------------------------------------------------------------------------
# NodeLayout: centralized node indexing abstraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeLayout:
    """Maps (layer, ix, iy, iz) tuples to flat node indices.

    For Phase 7 (nz=1 everywhere), ``layer_offsets[l] = l * n_per_layer``.
    The ``iz`` parameter is unused but reserved for Phase 8 z-refinement,
    which will vary nz per layer and change layer_offsets accordingly.
    """

    nx: int
    ny: int
    n_per_layer: int          # nx * ny
    n_layers: int
    layer_offsets: tuple[int, ...]  # layer_offsets[l] = first node index for layer l

    def node(self, layer_idx: int, ix: int, iy: int, iz: int = 0) -> int:
        """Return the flat node index for cell (layer_idx, ix, iy, iz)."""
        return self.layer_offsets[layer_idx] + iz * self.n_per_layer + iy * self.nx + ix

    @property
    def n_nodes(self) -> int:
        """Total node count across all layers."""
        return self.layer_offsets[-1] + self.n_per_layer


# ---------------------------------------------------------------------------
# ThermalNetwork
# ---------------------------------------------------------------------------


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
    layout: NodeLayout

    @property
    def b_vector(self) -> np.ndarray:
        """Combined forcing vector — backward-compatible sum of boundary + source terms."""
        return self.b_boundary + self.b_sources

    @property
    def n_nodes(self) -> int:
        return self.layout.n_nodes


# ---------------------------------------------------------------------------
# Air-Gap material constants (injected at build time for uncovered cells)
# ---------------------------------------------------------------------------

_AIR_GAP_KEY = "Air Gap"
_AIR_GAP_MATERIAL = Material(
    name="Air Gap",
    k_in_plane=0.026,
    k_through=0.026,
    density=1.2,
    specific_heat=1005.0,
    emissivity=0.5,
)


# ---------------------------------------------------------------------------
# Zone rasterization
# ---------------------------------------------------------------------------


def _rasterize_zones(
    layer: "Layer",
    materials_dict: dict[str, Material],
    grid: Grid2D,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rasterize zones to per-cell material property arrays.

    Returns ``(k_in_plane_map, k_through_map, density_cp_map)`` each of
    shape ``(ny, nx)``.

    Rules:
    - If ``layer.zones`` is empty, the layer material fills the whole grid.
    - Cells not covered by any zone default to Air Gap.
    - Zones are applied in list order; last-defined-wins for overlapping zones.
    - Zones that extend fully outside the grid emit a ``UserWarning``.
    - The project's ``materials_dict`` is never mutated — Air Gap is injected
      into a local working copy only.
    """
    # Work on a local copy so we never mutate the project.
    local_mats = dict(materials_dict)
    if _AIR_GAP_KEY not in local_mats:
        local_mats[_AIR_GAP_KEY] = _AIR_GAP_MATERIAL

    nx, ny = grid.nx, grid.ny
    x_centers = grid.x_centers()  # shape (nx,)
    y_centers = grid.y_centers()  # shape (ny,)
    xx, yy = np.meshgrid(x_centers, y_centers)  # each (ny, nx)
    half_dx = grid.dx / 2.0
    half_dy = grid.dy / 2.0

    # If no zones, fill entirely with the layer's base material.
    if not layer.zones:
        mat = local_mats[layer.material]
        k_ip = np.full((ny, nx), mat.k_in_plane, dtype=float)
        k_th = np.full((ny, nx), mat.k_through, dtype=float)
        d_cp = np.full((ny, nx), mat.density * mat.specific_heat, dtype=float)
        return k_ip, k_th, d_cp

    # Start with Air Gap for uncovered cells.
    air = local_mats[_AIR_GAP_KEY]
    k_ip = np.full((ny, nx), air.k_in_plane, dtype=float)
    k_th = np.full((ny, nx), air.k_through, dtype=float)
    d_cp = np.full((ny, nx), air.density * air.specific_heat, dtype=float)

    for zone in layer.zones:
        sx0 = zone.x - zone.width / 2.0
        sx1 = zone.x + zone.width / 2.0
        sy0 = zone.y - zone.height / 2.0
        sy1 = zone.y + zone.height / 2.0

        # AABB cell-overlap mask (same pattern as _source_mask for rectangles).
        mask = (
            (xx + half_dx > sx0) & (xx - half_dx < sx1) &
            (yy + half_dy > sy0) & (yy - half_dy < sy1)
        )

        if not mask.any():
            warnings.warn(
                f"MaterialZone with material='{zone.material}' in layer "
                f"'{layer.name}' lies entirely outside the grid bounds and "
                "will have no effect.",
                UserWarning,
                stacklevel=4,
            )
            continue

        mat = local_mats[zone.material]
        k_ip[mask] = mat.k_in_plane
        k_th[mask] = mat.k_through
        d_cp[mask] = mat.density * mat.specific_heat

    return k_ip, k_th, d_cp


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_thermal_network(project: DisplayProject) -> ThermalNetwork:
    """Build linear thermal network A*T=b with thermal capacities C."""
    grid = Grid2D(project.width, project.height, project.mesh.nx, project.mesh.ny)
    n_layers = len(project.layers)
    n_per_layer = grid.nx * grid.ny
    area = grid.cell_area

    # Build NodeLayout (Phase 7: nz=1, uniform layer offsets).
    layer_offsets = tuple(l * n_per_layer for l in range(n_layers))
    layout = NodeLayout(
        nx=grid.nx,
        ny=grid.ny,
        n_per_layer=n_per_layer,
        n_layers=n_layers,
        layer_offsets=layer_offsets,
    )
    n_nodes = layout.n_nodes

    # COO triplet accumulators for sparse matrix assembly.
    coo_rows: list[np.ndarray] = []
    coo_cols: list[np.ndarray] = []
    coo_data: list[np.ndarray] = []

    b_boundary = np.zeros(n_nodes, dtype=float)
    b_sources = np.zeros(n_nodes, dtype=float)
    c_vec = np.zeros(n_nodes, dtype=float)

    def _add_link_vectorized(n1: np.ndarray, n2: np.ndarray, conductance) -> None:
        """Add symmetric conductance links between node pairs in COO format.

        ``conductance`` may be a scalar ``float`` or a 1-D ``np.ndarray``
        matching ``len(n1)``.
        """
        if isinstance(conductance, (int, float)):
            if conductance <= 0.0:
                return
            g = np.full(len(n1), float(conductance), dtype=float)
        else:
            g = np.asarray(conductance, dtype=float)
            mask = g > 0.0
            if not mask.all():
                n1, n2, g = n1[mask], n2[mask], g[mask]
            if len(g) == 0:
                return

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

    # Rasterize zones once per layer; cache property maps.
    # Each entry: (k_in_plane_map, k_through_map, density_cp_map) shape (ny, nx)
    zone_maps: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for l_idx, layer in enumerate(project.layers):
        maps = _rasterize_zones(layer, project.materials, grid)
        zone_maps.append(maps)

    # Node thermal capacities (per-cell from zone maps).
    for l_idx, layer in enumerate(project.layers):
        _, _, density_cp_map = zone_maps[l_idx]
        c_per_cell = density_cp_map * layer.thickness * area  # (ny, nx)
        start = layout.layer_offsets[l_idx]
        c_vec[start : start + n_per_layer] = c_per_cell.ravel()

    # Lateral conduction inside each layer.
    # flat_idx = iy * nx + ix;  node = layer_offsets[l] + flat_idx
    iy_all = np.repeat(np.arange(grid.ny), grid.nx)   # shape (n_per_layer,)
    ix_all = np.tile(np.arange(grid.nx), grid.ny)     # shape (n_per_layer,)

    for l_idx, layer in enumerate(project.layers):
        k_ip_map, _, _ = zone_maps[l_idx]  # (ny, nx)
        base = layout.layer_offsets[l_idx]

        # Per-cell conductance arrays (ny, nx)
        g_x_per_cell = k_ip_map * layer.thickness * grid.dy / grid.dx
        g_y_per_cell = k_ip_map * layer.thickness * grid.dx / grid.dy

        # Horizontal links: (ix, iy) -- (ix+1, iy)  where ix < nx-1
        # Reshape to (ny, nx) for slicing
        g_left  = g_x_per_cell[:, :-1]   # (ny, nx-1)
        g_right = g_x_per_cell[:, 1:]    # (ny, nx-1)
        # Harmonic mean: for equal values HM = same value (backward-compatible)
        denom_x = g_left + g_right
        # Where denom is zero (both sides are zero k), set link conductance to 0
        g_x_link = np.where(denom_x > 0.0, 2.0 * g_left * g_right / denom_x, 0.0)
        # (ny, nx-1) — ravel into (ny*(nx-1),)
        g_x_flat = g_x_link.ravel()

        # Build flat indices for left/right pairs
        # For ix in 0..nx-2, iy in 0..ny-1:
        # flat_left = iy*nx + ix,  flat_right = iy*nx + ix+1
        mask_x = ix_all < (grid.nx - 1)
        flat_left = (iy_all[mask_x] * grid.nx + ix_all[mask_x])
        flat_right = flat_left + 1
        _add_link_vectorized(base + flat_left, base + flat_right, g_x_flat)

        # Vertical links: (ix, iy) -- (ix, iy+1)  where iy < ny-1
        g_bottom_y = g_y_per_cell[:-1, :]   # (ny-1, nx)
        g_top_y    = g_y_per_cell[1:,  :]   # (ny-1, nx)
        denom_y = g_bottom_y + g_top_y
        g_y_link = np.where(denom_y > 0.0, 2.0 * g_bottom_y * g_top_y / denom_y, 0.0)
        g_y_flat = g_y_link.ravel()  # (ny-1)*nx

        mask_y = iy_all < (grid.ny - 1)
        flat_bottom_y = (iy_all[mask_y] * grid.nx + ix_all[mask_y])
        flat_top_y = flat_bottom_y + grid.nx
        _add_link_vectorized(base + flat_bottom_y, base + flat_top_y, g_y_flat)

    # Through-thickness conduction between adjacent layers.
    flat_all_layer = np.arange(n_per_layer)
    for l_idx in range(n_layers - 1):
        lower = project.layers[l_idx]
        upper = project.layers[l_idx + 1]
        _, k_through_lower, _ = zone_maps[l_idx]      # (ny, nx)
        _, k_through_upper, _ = zone_maps[l_idx + 1]  # (ny, nx)

        # Per-cell resistance arrays, then per-cell conductance
        r_lower = lower.thickness / (2.0 * k_through_lower * area)      # (ny, nx)
        r_upper = upper.thickness / (2.0 * k_through_upper * area)      # (ny, nx)
        r_interface = lower.interface_resistance_to_next / area          # scalar
        g_z = 1.0 / (r_lower + r_interface + r_upper)                   # (ny, nx)

        n1 = layout.layer_offsets[l_idx]     + flat_all_layer
        n2 = layout.layer_offsets[l_idx + 1] + flat_all_layer
        _add_link_vectorized(n1, n2, g_z.ravel())

    # Top/bottom ambient sinks.
    top_layer = project.layers[-1]
    bot_layer = project.layers[0]
    _, k_through_top_map, _ = zone_maps[n_layers - 1]   # (ny, nx)
    _, k_through_bot_map, _ = zone_maps[0]              # (ny, nx)

    # Emissivity: use layer material emissivity as uniform scalar for top/bottom
    # (zone rasterization doesn't track emissivity — using layer base material)
    top_mat = project.material_for_layer(n_layers - 1)
    bot_mat = project.material_for_layer(0)

    # Per-cell surface conductance for top boundary
    g_top_map = _surface_sink_conductance_array(
        boundary=project.boundaries.top,
        emissivity=top_mat.emissivity,
        conduction_distance_map=top_layer.thickness / 2.0,
        conductivity_map=k_through_top_map,
        area=area,
    )  # (ny, nx) or scalar
    # Per-cell surface conductance for bottom boundary
    g_bot_map = _surface_sink_conductance_array(
        boundary=project.boundaries.bottom,
        emissivity=bot_mat.emissivity,
        conduction_distance_map=bot_layer.thickness / 2.0,
        conductivity_map=k_through_bot_map,
        area=area,
    )  # (ny, nx) or scalar

    # Top layer nodes.
    top_indices = layout.layer_offsets[n_layers - 1] + flat_all_layer
    g_top_flat = g_top_map.ravel() if isinstance(g_top_map, np.ndarray) else g_top_map
    if isinstance(g_top_flat, np.ndarray):
        mask_top = g_top_flat > 0.0
        if mask_top.any():
            coo_rows.append(top_indices[mask_top])
            coo_cols.append(top_indices[mask_top])
            coo_data.append(g_top_flat[mask_top])
            b_boundary[top_indices[mask_top]] += g_top_flat[mask_top] * project.boundaries.top.ambient_c
    elif g_top_flat > 0.0:
        coo_rows.append(top_indices)
        coo_cols.append(top_indices)
        coo_data.append(np.full(n_per_layer, g_top_flat, dtype=float))
        b_boundary[top_indices] += g_top_flat * project.boundaries.top.ambient_c

    # Bottom layer nodes.
    bot_indices = flat_all_layer  # 0 * n_per_layer + flat
    g_bot_flat = g_bot_map.ravel() if isinstance(g_bot_map, np.ndarray) else g_bot_map
    if isinstance(g_bot_flat, np.ndarray):
        mask_bot = g_bot_flat > 0.0
        if mask_bot.any():
            coo_rows.append(bot_indices[mask_bot])
            coo_cols.append(bot_indices[mask_bot])
            coo_data.append(g_bot_flat[mask_bot])
            b_boundary[bot_indices[mask_bot]] += g_bot_flat[mask_bot] * project.boundaries.bottom.ambient_c
    elif g_bot_flat > 0.0:
        coo_rows.append(bot_indices)
        coo_cols.append(bot_indices)
        coo_data.append(np.full(n_per_layer, g_bot_flat, dtype=float))
        b_boundary[bot_indices] += g_bot_flat * project.boundaries.bottom.ambient_c

    # Side ambient sinks (all layers, perimeter cells only).
    side_amb = project.boundaries.side.ambient_c
    for l_idx, layer in enumerate(project.layers):
        k_ip_map, _, _ = zone_maps[l_idx]  # (ny, nx)
        base = layout.layer_offsets[l_idx]
        mat = project.material_for_layer(l_idx)

        # Left/right edges: conductance driven by k_in_plane at edge cells
        # left edge: ix=0, all iy   -> k_ip_map[:, 0]  shape (ny,)
        # right edge: ix=nx-1, all iy -> k_ip_map[:, -1] shape (ny,)
        left_flat  = np.arange(grid.ny) * grid.nx           # iy*nx + 0
        right_flat = np.arange(grid.ny) * grid.nx + (grid.nx - 1)

        # Per-cell x-edge conductance for left column
        g_x_left = _surface_sink_conductance_array(
            boundary=project.boundaries.side,
            emissivity=mat.emissivity,
            conduction_distance_map=grid.dx / 2.0,
            conductivity_map=k_ip_map[:, 0],
            area=layer.thickness * grid.dy,
        )  # shape (ny,) or scalar
        g_x_right = _surface_sink_conductance_array(
            boundary=project.boundaries.side,
            emissivity=mat.emissivity,
            conduction_distance_map=grid.dx / 2.0,
            conductivity_map=k_ip_map[:, -1],
            area=layer.thickness * grid.dy,
        )  # shape (ny,) or scalar

        _apply_edge_sink(
            coo_rows, coo_cols, coo_data, b_boundary,
            base + left_flat, g_x_left, side_amb,
        )
        _apply_edge_sink(
            coo_rows, coo_cols, coo_data, b_boundary,
            base + right_flat, g_x_right, side_amb,
        )

        # Bottom/top edges: conductance driven by k_in_plane at edge cells
        bottom_flat = np.arange(grid.nx)                       # 0*nx + ix
        top_flat    = (grid.ny - 1) * grid.nx + np.arange(grid.nx)

        g_y_bottom = _surface_sink_conductance_array(
            boundary=project.boundaries.side,
            emissivity=mat.emissivity,
            conduction_distance_map=grid.dy / 2.0,
            conductivity_map=k_ip_map[0, :],
            area=layer.thickness * grid.dx,
        )  # shape (nx,) or scalar
        g_y_top = _surface_sink_conductance_array(
            boundary=project.boundaries.side,
            emissivity=mat.emissivity,
            conduction_distance_map=grid.dy / 2.0,
            conductivity_map=k_ip_map[-1, :],
            area=layer.thickness * grid.dx,
        )  # shape (nx,) or scalar

        _apply_edge_sink(
            coo_rows, coo_cols, coo_data, b_boundary,
            base + bottom_flat, g_y_bottom, side_amb,
        )
        _apply_edge_sink(
            coo_rows, coo_cols, coo_data, b_boundary,
            base + top_flat, g_y_top, side_amb,
        )

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

    _apply_heat_sources(project, grid, b_sources, layout)
    return ThermalNetwork(
        a_matrix=a_mat,
        b_boundary=b_boundary,
        b_sources=b_sources,
        c_vector=c_vec,
        grid=grid,
        n_layers=n_layers,
        layer_names=[layer.name for layer in project.layers],
        layout=layout,
    )


def _apply_edge_sink(
    coo_rows: list,
    coo_cols: list,
    coo_data: list,
    b_boundary: np.ndarray,
    node_indices: np.ndarray,
    g_edge,  # float or np.ndarray matching node_indices
    ambient_c: float,
) -> None:
    """Add diagonal sink entries and boundary forcing for edge nodes."""
    if isinstance(g_edge, np.ndarray):
        mask = g_edge > 0.0
        if not mask.any():
            return
        nodes = node_indices[mask]
        g = g_edge[mask]
        coo_rows.append(nodes)
        coo_cols.append(nodes)
        coo_data.append(g)
        b_boundary[nodes] += g * ambient_c
    else:
        if g_edge <= 0.0:
            return
        coo_rows.append(node_indices)
        coo_cols.append(node_indices)
        coo_data.append(np.full(len(node_indices), float(g_edge), dtype=float))
        b_boundary[node_indices] += g_edge * ambient_c


# ---------------------------------------------------------------------------
# Public helper: build heat source vector at a given time
# ---------------------------------------------------------------------------


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
        mask = _source_mask(source, xx, yy, grid.dx, grid.dy)
        iy_arr, ix_arr = np.where(mask)
        if iy_arr.size == 0:
            continue  # Already validated during initial network build
        power = source.power_at_time(time_s) if time_s is not None else source.power_w
        power_per_node = power / iy_arr.size
        linear = layer_idx * n_per_layer + iy_arr * grid.nx + ix_arr
        np.add.at(b_vec, linear, power_per_node)

    return b_vec


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_heat_sources(
    project: DisplayProject,
    grid: Grid2D,
    b_vec: np.ndarray,
    layout: NodeLayout,
) -> None:
    x_centers = grid.x_centers()
    y_centers = grid.y_centers()
    xx, yy = np.meshgrid(x_centers, y_centers)

    # Cache layer name -> index to avoid repeated linear search.
    layer_index_cache: dict[str, int] = {
        layer.name: idx for idx, layer in enumerate(project.layers)
    }
    n_per_layer = layout.n_per_layer

    for source in project.expanded_heat_sources():
        layer_idx = layer_index_cache[source.layer]
        mask = _source_mask(source, xx, yy, grid.dx, grid.dy)
        iy_arr, ix_arr = np.where(mask)
        if iy_arr.size == 0:
            raise ValueError(
                f"Heat source '{source.name}' does not overlap any mesh cell. "
                "Increase mesh density or adjust source geometry."
            )
        power_per_node = source.power_w / iy_arr.size
        linear = layout.layer_offsets[layer_idx] + iy_arr * grid.nx + ix_arr
        np.add.at(b_vec, linear, power_per_node)


def _source_mask(
    source: HeatSource, xx: np.ndarray, yy: np.ndarray, dx: float, dy: float,
) -> np.ndarray:
    """Return boolean mask of cells overlapping the heat source.

    Uses cell-rectangle overlap (AABB intersection) instead of
    point-in-source, so small sources on coarse meshes still hit at
    least one cell.
    """
    if source.shape == "full":
        return np.ones_like(xx, dtype=bool)
    if source.shape == "rectangle":
        # Source bounds
        sx0 = source.x - source.width / 2.0
        sx1 = source.x + source.width / 2.0
        sy0 = source.y - source.height / 2.0
        sy1 = source.y + source.height / 2.0
        # Cell bounds: center ± half-cell
        half_dx = dx / 2.0
        half_dy = dy / 2.0
        # AABB overlap: cell overlaps source if no separating axis
        return (
            (xx + half_dx > sx0) & (xx - half_dx < sx1) &
            (yy + half_dy > sy0) & (yy - half_dy < sy1)
        )
    if source.shape == "circle":
        # For circles, keep center-in-circle but also include cells whose
        # nearest edge is within the radius
        cx, cy, r = source.x, source.y, source.radius
        half_dx = dx / 2.0
        half_dy = dy / 2.0
        # Nearest point on cell to circle center
        nearest_x = np.clip(cx, xx - half_dx, xx + half_dx)
        nearest_y = np.clip(cy, yy - half_dy, yy + half_dy)
        return (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2 <= r**2
    raise ValueError(f"Unsupported heat source shape: {source.shape}")


def _surface_sink_conductance(
    boundary: SurfaceBoundary,
    emissivity: float,
    conduction_distance: float,
    conductivity: float,
    area: float,
) -> float:
    """Scalar surface conductance (kept for backward compatibility)."""
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


def _surface_sink_conductance_array(
    boundary: SurfaceBoundary,
    emissivity: float,
    conduction_distance_map,
    conductivity_map: np.ndarray,
    area: float,
):
    """Per-cell surface conductance.

    ``conduction_distance_map`` and ``conductivity_map`` may be scalars or
    ndarrays of the same shape; the result has the same shape.

    Returns a float if both inputs are scalar, otherwise an ndarray.
    """
    h_total = boundary.convection_h
    if boundary.include_radiation:
        eps = emissivity if boundary.emissivity_override is None else boundary.emissivity_override
        t_ref_k = boundary.ambient_c + 273.15
        h_total += 4.0 * eps * STEFAN_BOLTZMANN * t_ref_k**3
    if h_total <= 0.0:
        if isinstance(conductivity_map, np.ndarray):
            return np.zeros_like(conductivity_map, dtype=float)
        return 0.0

    r_cond = conduction_distance_map / (conductivity_map * area)
    r_env = 1.0 / (h_total * area)
    return 1.0 / (r_cond + r_env)
