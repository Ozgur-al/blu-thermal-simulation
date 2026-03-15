"""Result post-processing helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.steady_state import SteadyStateResult
from thermal_sim.solvers.transient import TransientResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemperatureStats:
    max_c: float
    avg_c: float
    min_c: float


def _z_offsets_for_result(result, n_layers: int) -> list[int]:
    """Return z_offsets from result or default to [0, 1, 2, ..., n_layers] for pre-z-refinement results."""
    if hasattr(result, 'z_offsets') and result.z_offsets is not None:
        return result.z_offsets
    return list(range(n_layers + 1))


def _z_node_for_probe(probe, project: DisplayProject, z_offsets: list[int]) -> int:
    """Resolve probe z_position to an absolute z-node index."""
    l_idx = project.layer_index(probe.layer)
    nz = z_offsets[l_idx + 1] - z_offsets[l_idx]
    z_base = z_offsets[l_idx]
    z_pos = getattr(probe, 'z_position', 'top')
    if z_pos == 'top':
        return z_base + nz - 1
    elif z_pos == 'bottom':
        return z_base
    elif z_pos == 'center':
        return z_base + nz // 2
    elif isinstance(z_pos, int):
        return z_base + min(z_pos, nz - 1)
    return z_base + nz - 1  # default top


def _z_to_layer_idx(z_node: int, z_offsets: list[int]) -> int:
    """Map a z-node index to a physical layer index using z_offsets."""
    for i in range(len(z_offsets) - 1):
        if z_offsets[i] <= z_node < z_offsets[i + 1]:
            return i
    return len(z_offsets) - 2  # fallback to last layer


def basic_stats(result: SteadyStateResult) -> TemperatureStats:
    """Compute global min/max/average temperature for steady-state output."""
    return _stats_from_map(result.temperatures_c)


def basic_stats_transient(result: TransientResult) -> TemperatureStats:
    """Compute global min/max/average using the final transient state."""
    return _stats_from_map(result.final_temperatures_c)


def probe_temperatures(project: DisplayProject, result: SteadyStateResult) -> dict[str, float]:
    """Extract steady-state probe temperatures by nearest grid cell."""
    if not project.probes:
        return {}
    x_idx, y_idx = _probe_xy_indices(project, result.dx, result.dy, result.nx, result.ny)
    z_offsets = _z_offsets_for_result(result, len(project.layers))
    values: dict[str, float] = {}
    for probe, ix, iy in zip(project.probes, x_idx, y_idx):
        z_node = _z_node_for_probe(probe, project, z_offsets)
        values[probe.name] = float(result.temperatures_c[z_node, iy, ix])
    return values


def probe_temperatures_over_time(project: DisplayProject, result: TransientResult) -> dict[str, np.ndarray]:
    """Extract probe temperature history arrays keyed by probe name."""
    if not project.probes:
        return {}
    x_idx, y_idx = _probe_xy_indices(project, result.dx, result.dy, result.nx, result.ny)
    z_offsets = _z_offsets_for_result(result, len(project.layers))
    history: dict[str, np.ndarray] = {}
    for probe, ix, iy in zip(project.probes, x_idx, y_idx):
        z_node = _z_node_for_probe(probe, project, z_offsets)
        history[probe.name] = result.temperatures_time_c[:, z_node, iy, ix].copy()
    return history


def top_n_hottest_cells(result: SteadyStateResult, n: int = 10) -> list[dict]:
    """Return top-N hottest cells across all layers for steady-state output."""
    z_offsets = getattr(result, 'z_offsets', None)
    return _top_n_from_map(result.temperatures_c, result.layer_names, result.dx, result.dy, n=n, z_offsets=z_offsets)


def top_n_hottest_cells_transient(result: TransientResult, n: int = 10) -> list[dict]:
    """Return top-N hottest cells from final transient state."""
    z_offsets = getattr(result, 'z_offsets', None)
    return _top_n_from_map(result.final_temperatures_c, result.layer_names, result.dx, result.dy, n=n, z_offsets=z_offsets)


def layer_average_temperatures(
    temperature_map_c: np.ndarray,
    layer_names: list[str],
    z_offsets: list[int] | None = None,
) -> dict[str, float]:
    """Average temperature per layer from a [total_z, y, x] map."""
    if z_offsets is None:
        z_offsets = list(range(len(layer_names) + 1))
        total_z = temperature_map_c.shape[0]
        if total_z > len(layer_names):
            logger.warning(
                "layer_average_temperatures called without z_offsets but temperature array has %d "
                "z-slices for %d layers. Results will be incorrect for nz>1 layers. "
                "Pass z_offsets from result.z_offsets to fix this.",
                total_z, len(layer_names),
            )
    return {
        name: float(temperature_map_c[z_offsets[idx]:z_offsets[idx + 1]].mean())
        for idx, name in enumerate(layer_names)
    }


def layer_stats(
    temperature_map_c: np.ndarray,  # [total_z, ny, nx]
    layer_names: list[str],
    z_offsets: list[int] | None = None,
) -> list[dict]:
    """Per-layer T_max, T_avg, T_min, and delta_T."""
    if z_offsets is None:
        # Fallback: assume 1 z-node per layer (pre-z-refinement or nz=1 results).
        # WARNING: This fallback is incorrect for nz>1 results -- callers should
        # always pass z_offsets from result.z_offsets when available.
        z_offsets = list(range(len(layer_names) + 1))
        total_z = temperature_map_c.shape[0]
        if total_z > len(layer_names):
            logger.warning(
                "layer_stats called without z_offsets but temperature array has %d "
                "z-slices for %d layers. Results will be incorrect for nz>1 layers. "
                "Pass z_offsets from result.z_offsets to fix this.",
                total_z, len(layer_names),
            )
    result = []
    for idx, name in enumerate(layer_names):
        layer_slice = temperature_map_c[z_offsets[idx]:z_offsets[idx + 1]]
        t_max = float(layer_slice.max())
        t_avg = float(layer_slice.mean())
        t_min = float(layer_slice.min())
        result.append({
            "layer": name,
            "t_max_c": t_max,
            "t_avg_c": t_avg,
            "t_min_c": t_min,
            "delta_t_c": t_max - t_min,
        })
    return result


def top_n_hottest_cells_for_layer(
    temperature_map_c: np.ndarray,  # [total_z, ny, nx]
    layer_idx: int,
    layer_name: str,
    dx: float,
    dy: float,
    n: int = 3,
    z_offsets: list[int] | None = None,
) -> list[dict]:
    """Top-N hottest cells within a single layer."""
    if z_offsets is not None:
        z0 = z_offsets[layer_idx]
        z1 = z_offsets[layer_idx + 1]
        single = temperature_map_c[z0:z1]
        nz_for_layer = z1 - z0
        local_z_offsets = [0, nz_for_layer]
    else:
        single = temperature_map_c[layer_idx:layer_idx + 1]
        local_z_offsets = [0, 1]
    return _top_n_from_map(single, [layer_name], dx, dy, n=n, z_offsets=local_z_offsets)


def _stats_from_map(temperature_map_c: np.ndarray) -> TemperatureStats:
    values = temperature_map_c
    return TemperatureStats(max_c=float(values.max()), avg_c=float(values.mean()), min_c=float(values.min()))


def _probe_xy_indices(
    project: DisplayProject,
    dx: float,
    dy: float,
    nx: int,
    ny: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (x_idx, y_idx) arrays for all probes."""
    x_idx = np.clip(np.floor(np.array([p.x for p in project.probes]) / dx).astype(int), 0, nx - 1)
    y_idx = np.clip(np.floor(np.array([p.y for p in project.probes]) / dy).astype(int), 0, ny - 1)
    return x_idx, y_idx


def _probe_indices(
    project: DisplayProject,
    dx: float,
    dy: float,
    nx: int,
    ny: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Legacy helper: return (layer_idx, x_idx, y_idx) for backward compat."""
    if not project.probes:
        return np.array([], dtype=int), np.array([], dtype=int), np.array([], dtype=int)
    x_idx = np.clip(np.floor(np.array([p.x for p in project.probes]) / dx).astype(int), 0, nx - 1)
    y_idx = np.clip(np.floor(np.array([p.y for p in project.probes]) / dy).astype(int), 0, ny - 1)
    layer_idx = np.array([project.layer_index(p.layer) for p in project.probes], dtype=int)
    return layer_idx, x_idx, y_idx


def _top_n_from_map(
    temperature_map_c: np.ndarray,
    layer_names: list[str],
    dx: float,
    dy: float,
    n: int,
    z_offsets: list[int] | None = None,
) -> list[dict]:
    if z_offsets is None:
        z_offsets = list(range(len(layer_names) + 1))
    flat = temperature_map_c.ravel()
    n = max(1, min(n, flat.size))
    top_indices = np.argpartition(flat, -n)[-n:]
    top_indices = top_indices[np.argsort(flat[top_indices])[::-1]]

    _total_z, ny, nx = temperature_map_c.shape
    items = []
    for idx in top_indices:
        z_node, rem = divmod(int(idx), nx * ny)
        iy, ix = divmod(rem, nx)
        layer_idx = _z_to_layer_idx(z_node, z_offsets)
        items.append(
            {
                "layer": layer_names[layer_idx],
                "x_m": (ix + 0.5) * dx,
                "y_m": (iy + 0.5) * dy,
                "temperature_c": float(flat[idx]),
            }
        )
    return items
