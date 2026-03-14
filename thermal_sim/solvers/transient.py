"""Transient thermal solver (implicit Euler)."""

from __future__ import annotations

from collections.abc import Callable
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

    def solve(
        self,
        project: DisplayProject,
        on_progress: Callable[[int, int, float], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> TransientResult:
        """Solve the transient problem with optional progress and cancel callbacks.

        Args:
            project: The DisplayProject to simulate.
            on_progress: Optional callback ``on_progress(step, n_steps, t_max_c)``
                called at most ~100 times per simulation to report progress.
            cancel_check: Optional callable returning True when the caller wants
                the solver to stop early. A valid partial result is always returned.
        """
        network = build_thermal_network(project)
        dt = project.transient.time_step_s
        total = project.transient.total_time_s
        output_interval = project.transient.output_interval_s

        n_steps = int(np.ceil(total / dt))
        sample_every = max(1, int(round(output_interval / dt)))
        # Cap cross-thread progress signals to ~100 regardless of timestep count.
        progress_every = max(1, n_steps // 100)

        t_vec = np.full(network.n_nodes, project.initial_temperature_c, dtype=float)
        c_over_dt = network.c_vector / dt
        lhs = network.a_matrix.copy()
        lhs.setdiag(lhs.diagonal() + c_over_dt)
        lu = splu(lhs.tocsc())

        # Pre-allocate output arrays instead of growing lists.
        state_shape = (network.n_layers, network.grid.ny, network.grid.nx)
        n_samples = sum(
            1 for s in range(1, n_steps + 1) if s % sample_every == 0 or s == n_steps
        ) + 1  # +1 for initial state
        temperatures_out = np.empty((n_samples, *state_shape), dtype=float)
        times_out = np.empty(n_samples, dtype=float)
        temperatures_out[0] = t_vec.reshape(state_shape)
        times_out[0] = 0.0
        sample_idx = 1

        # Pre-allocate RHS buffer to avoid per-step allocation.
        rhs = np.empty(network.n_nodes, dtype=float)

        for step in range(1, n_steps + 1):
            np.multiply(c_over_dt, t_vec, out=rhs)
            rhs += network.b_vector
            t_vec = lu.solve(rhs)

            if cancel_check and cancel_check():
                break

            if on_progress and (step % progress_every == 0 or step == n_steps):
                on_progress(step, n_steps, float(t_vec.max()))

            if step % sample_every == 0 or step == n_steps:
                times_out[sample_idx] = min(step * dt, total)
                temperatures_out[sample_idx] = t_vec.reshape(state_shape)
                sample_idx += 1

        # If cancelled before any sample was collected, sample_idx is still 1
        # (the initial state was already stored at index 0).
        return TransientResult(
            temperatures_time_c=temperatures_out[:sample_idx],
            times_s=times_out[:sample_idx],
            layer_names=network.layer_names,
            dx=network.grid.dx,
            dy=network.grid.dy,
        )
