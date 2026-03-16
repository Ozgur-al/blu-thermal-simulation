"""Steady-state voxel-based 3D thermal solver."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import LinearOperator, bicgstab, spilu, spsolve

from thermal_sim.core.conformal_mesh import ConformalMesh3D
from thermal_sim.models.voxel_project import VoxelProject
from thermal_sim.solvers.voxel_network_builder import build_voxel_network

DIRECT_THRESHOLD = 5_000
WARN_THRESHOLD = 500_000


@dataclass
class VoxelSteadyStateResult:
    """Steady-state solver output for a voxel-based 3D simulation."""

    temperatures_c: np.ndarray  # shape: (nz, ny, nx)
    mesh: ConformalMesh3D
    material_grid: np.ndarray   # (nz, ny, nx) material name strings
    block_names: list[str]


class VoxelSteadyStateSolver:
    """Steady-state solver for voxel-based 3D thermal networks.

    Uses direct sparse solve (spsolve) for n <= DIRECT_THRESHOLD nodes and
    bicgstab+ILU for larger problems.
    """

    def solve(
        self,
        project: VoxelProject,
        on_progress=None,
    ) -> VoxelSteadyStateResult:
        if on_progress:
            on_progress("building")

        network = build_voxel_network(project)
        n = network.a_matrix.shape[0]

        if on_progress:
            on_progress("solving")

        if n <= DIRECT_THRESHOLD:
            T_flat = spsolve(network.a_matrix, network.b_vector)
        else:
            if n > WARN_THRESHOLD:
                import warnings
                warnings.warn(
                    f"VoxelSteadyStateSolver: {n} nodes — this may be slow.",
                    UserWarning,
                    stacklevel=2,
                )
            ilu = spilu(network.a_matrix.tocsc(), fill_factor=10, drop_tol=1e-4)
            M = LinearOperator(network.a_matrix.shape, ilu.solve)
            T_flat, info = bicgstab(
                network.a_matrix, network.b_vector, M=M, rtol=1e-8, maxiter=500
            )
            if info != 0:
                # Retry without preconditioner with looser tolerance
                T_flat, _ = bicgstab(
                    network.a_matrix, network.b_vector, rtol=1e-6, maxiter=2000
                )

        mesh = network.mesh
        temperatures = T_flat.reshape((mesh.nz, mesh.ny, mesh.nx))

        return VoxelSteadyStateResult(
            temperatures_c=temperatures,
            mesh=mesh,
            material_grid=network.material_grid,
            block_names=[blk.name for blk in project.blocks],
        )
