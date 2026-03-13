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

    temperatures_c: np.ndarray  # shape: [n_layers, ny, nx]
    layer_names: list[str]
    dx: float
    dy: float

    @property
    def nx(self) -> int:
        return self.temperatures_c.shape[2]

    @property
    def ny(self) -> int:
        return self.temperatures_c.shape[1]


class SteadyStateSolver:
    """2.5D thermal network solver (lateral + through-thickness conduction)."""

    def solve(self, project: DisplayProject) -> SteadyStateResult:
        network = build_thermal_network(project)
        solution = spsolve(network.a_matrix, network.b_vector)
        temperatures = solution.reshape((network.n_layers, network.grid.ny, network.grid.nx))
        return SteadyStateResult(
            temperatures_c=temperatures,
            layer_names=network.layer_names,
            dx=network.grid.dx,
            dy=network.grid.dy,
        )
