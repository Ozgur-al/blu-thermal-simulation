"""Steady-state thermal solver for layered display modules."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import spsolve

from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.network_builder import build_thermal_network


@dataclass
class SteadyStateResult:
    """Steady-state simulation output."""

    temperatures_c: np.ndarray  # shape: [total_z, ny, nx] where total_z = sum(nz_per_layer)
    layer_names: list[str]
    dx: float
    dy: float
    nz_per_layer: list[int] | None = None
    z_offsets: list[int] | None = None

    @property
    def nx(self) -> int:
        return self.temperatures_c.shape[2]

    @property
    def ny(self) -> int:
        return self.temperatures_c.shape[1]

    def layer_temperatures(self, layer_idx: int) -> np.ndarray:
        """Return temperatures for all z-sublayers of a layer: [nz, ny, nx]."""
        if self.z_offsets is not None:
            z0 = self.z_offsets[layer_idx]
            z1 = self.z_offsets[layer_idx + 1]
            return self.temperatures_c[z0:z1]
        # Fallback for pre-z-refinement results
        return self.temperatures_c[layer_idx:layer_idx + 1]


class SteadyStateSolver:
    """2.5D thermal network solver (lateral + through-thickness conduction)."""

    def solve(
        self,
        project: DisplayProject,
        on_progress: callable | None = None,
    ) -> SteadyStateResult:
        if on_progress:
            on_progress("building")
        network = build_thermal_network(project)
        if on_progress:
            on_progress("solving")
        solution = spsolve(network.a_matrix, network.b_vector)
        temperatures = solution.reshape((network.n_layers, network.grid.ny, network.grid.nx))
        return SteadyStateResult(
            temperatures_c=temperatures,
            layer_names=network.layer_names,
            dx=network.grid.dx,
            dy=network.grid.dy,
        )
