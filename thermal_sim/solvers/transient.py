"""Transient thermal solver (implicit Euler)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu

from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.network_builder import build_thermal_network


@dataclass
class TransientResult:
    """Transient simulation output sampled over time."""

    temperatures_time_c: np.ndarray  # [nt, n_layers, ny, nx]
    times_s: np.ndarray  # [nt]
    layer_names: list[str]
    dx: float
    dy: float

    @property
    def nx(self) -> int:
        return self.temperatures_time_c.shape[3]

    @property
    def ny(self) -> int:
        return self.temperatures_time_c.shape[2]

    @property
    def final_temperatures_c(self) -> np.ndarray:
        return self.temperatures_time_c[-1]


class TransientSolver:
    """Implicit Euler transient simulation for the same thermal network as steady-state."""

    def solve(self, project: DisplayProject) -> TransientResult:
        network = build_thermal_network(project)
        dt = project.transient.time_step_s
        total = project.transient.total_time_s
        output_interval = project.transient.output_interval_s

        n_steps = int(np.ceil(total / dt))
        sample_every = max(1, int(round(output_interval / dt)))

        t_vec = np.full(network.n_nodes, project.initial_temperature_c, dtype=float)
        lhs = network.a_matrix + diags(network.c_vector / dt)
        c_over_dt = network.c_vector / dt
        lu = splu(lhs.tocsc())

        times: list[float] = [0.0]
        states: list[np.ndarray] = [
            t_vec.reshape((network.n_layers, network.grid.ny, network.grid.nx)).copy()
        ]

        for step in range(1, n_steps + 1):
            rhs = network.b_vector + c_over_dt * t_vec
            t_vec = lu.solve(rhs)

            is_sample_step = step % sample_every == 0 or step == n_steps
            if is_sample_step:
                curr_time = min(step * dt, total)
                times.append(curr_time)
                states.append(t_vec.reshape((network.n_layers, network.grid.ny, network.grid.nx)).copy())

        return TransientResult(
            temperatures_time_c=np.asarray(states, dtype=float),
            times_s=np.asarray(times, dtype=float),
            layer_names=network.layer_names,
            dx=network.grid.dx,
            dy=network.grid.dy,
        )
