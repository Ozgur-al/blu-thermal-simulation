"""Result post-processing helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.steady_state import SteadyStateResult
from thermal_sim.solvers.transient import TransientResult


@dataclass(frozen=True)
class TemperatureStats:
    max_c: float
    avg_c: float
    min_c: float


def basic_stats(result: SteadyStateResult) -> TemperatureStats:
    """Compute global min/max/average temperature for steady-state output."""
    return _stats_from_map(result.temperatures_c)


def basic_stats_transient(result: TransientResult) -> TemperatureStats:
    """Compute global min/max/average using the final transient state."""
    return _stats_from_map(result.final_temperatures_c)


def probe_temperatures(project: DisplayProject, result: SteadyStateResult) -> dict[str, float]:
    """Extract steady-state probe temperatures by nearest grid cell."""
    layer_idx, x_idx, y_idx = _probe_indices(project, result.dx, result.dy, result.nx, result.ny)
    values: dict[str, float] = {}
    for probe, l_idx, ix, iy in zip(project.probes, layer_idx, x_idx, y_idx):
        values[probe.name] = float(result.temperatures_c[l_idx, iy, ix])
    return values


def probe_temperatures_over_time(project: DisplayProject, result: TransientResult) -> dict[str, np.ndarray]:
    """Extract probe temperature history arrays keyed by probe name."""
    layer_idx, x_idx, y_idx = _probe_indices(project, result.dx, result.dy, result.nx, result.ny)
    history: dict[str, np.ndarray] = {}
    for probe, l_idx, ix, iy in zip(project.probes, layer_idx, x_idx, y_idx):
        history[probe.name] = result.temperatures_time_c[:, l_idx, iy, ix].copy()
    return history


def top_n_hottest_cells(result: SteadyStateResult, n: int = 10) -> list[dict]:
    """Return top-N hottest cells across all layers for steady-state output."""
    return _top_n_from_map(result.temperatures_c, result.layer_names, result.dx, result.dy, n=n)


def top_n_hottest_cells_transient(result: TransientResult, n: int = 10) -> list[dict]:
    """Return top-N hottest cells from final transient state."""
    return _top_n_from_map(result.final_temperatures_c, result.layer_names, result.dx, result.dy, n=n)


def layer_average_temperatures(temperature_map_c: np.ndarray, layer_names: list[str]) -> dict[str, float]:
    """Average temperature per layer from a [layer, y, x] map."""
    return {name: float(temperature_map_c[idx].mean()) for idx, name in enumerate(layer_names)}


def _stats_from_map(temperature_map_c: np.ndarray) -> TemperatureStats:
    values = temperature_map_c
    return TemperatureStats(max_c=float(values.max()), avg_c=float(values.mean()), min_c=float(values.min()))


def _probe_indices(
    project: DisplayProject,
    dx: float,
    dy: float,
    nx: int,
    ny: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
) -> list[dict]:
    flat = temperature_map_c.ravel()
    n = max(1, min(n, flat.size))
    top_indices = np.argpartition(flat, -n)[-n:]
    top_indices = top_indices[np.argsort(flat[top_indices])[::-1]]

    n_layers, ny, nx = temperature_map_c.shape
    _ = n_layers  # Explicitly keep dimensional intent readable.
    items = []
    for idx in top_indices:
        layer, rem = divmod(int(idx), nx * ny)
        iy, ix = divmod(rem, nx)
        items.append(
            {
                "layer": layer_names[layer],
                "x_m": (ix + 0.5) * dx,
                "y_m": (iy + 0.5) * dy,
                "temperature_c": float(flat[idx]),
            }
        )
    return items
