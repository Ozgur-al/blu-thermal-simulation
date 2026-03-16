"""Transient voxel-based 3D thermal solver (implicit Euler)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu

from thermal_sim.core.conformal_mesh import ConformalMesh3D
from thermal_sim.models.voxel_project import VoxelProject
from thermal_sim.solvers.voxel_network_builder import build_voxel_network


@dataclass
class VoxelTransientResult:
    """Transient solver output for a voxel-based 3D simulation."""

    temperatures_c: np.ndarray  # shape: (n_steps+1, nz, ny, nx)
    time_points: np.ndarray     # shape: (n_steps+1,)
    mesh: ConformalMesh3D
    material_grid: np.ndarray   # (nz, ny, nx) material name strings
    block_names: list[str]


class VoxelTransientSolver:
    """Transient implicit Euler solver for voxel-based 3D thermal networks.

    Uses splu LU prefactoring for efficient time-stepping.
    Time discretisation: (C/dt + A) * T_{n+1} = b + (C/dt) * T_n
    """

    def solve(
        self,
        project: VoxelProject,
        on_progress: Callable[[int, int, float], None] | None = None,
    ) -> VoxelTransientResult:
        if project.transient_config is None:
            raise ValueError(
                "VoxelTransientSolver requires VoxelProject.transient_config to be set."
            )

        network = build_voxel_network(project)
        tc = project.transient_config
        dt = tc.dt_s
        duration = tc.duration_s
        T_init_c = tc.initial_temp_c

        n_steps = int(round(duration / dt))
        mesh = network.mesh
        state_shape = (mesh.nz, mesh.ny, mesh.nx)
        n_nodes = network.a_matrix.shape[0]

        # Prefactor LHS: (C/dt + A)
        C_dt = network.c_vector / dt
        lhs = network.a_matrix + diags(C_dt, format="csr")
        lu = splu(lhs.tocsc())

        # Initial temperature vector
        T_vec = np.full(n_nodes, T_init_c, dtype=float)

        # Pre-allocate output arrays
        temperatures_out = np.empty((n_steps + 1, *state_shape), dtype=float)
        time_points_out = np.empty(n_steps + 1, dtype=float)

        temperatures_out[0] = T_vec.reshape(state_shape)
        time_points_out[0] = 0.0

        # Pre-allocate RHS buffer
        rhs = np.empty(n_nodes, dtype=float)
        b = network.b_vector  # constant forcing (no time-varying sources)

        progress_every = max(1, n_steps // 100)

        for step in range(1, n_steps + 1):
            # RHS: b + (C/dt) * T_n
            np.multiply(C_dt, T_vec, out=rhs)
            rhs += b
            T_vec = lu.solve(rhs)

            time_points_out[step] = step * dt
            temperatures_out[step] = T_vec.reshape(state_shape)

            if on_progress and (step % progress_every == 0 or step == n_steps):
                on_progress(step, n_steps, float(T_vec.max()))

        return VoxelTransientResult(
            temperatures_c=temperatures_out,
            time_points=time_points_out,
            mesh=mesh,
            material_grid=network.material_grid,
            block_names=[blk.name for blk in project.blocks],
        )
