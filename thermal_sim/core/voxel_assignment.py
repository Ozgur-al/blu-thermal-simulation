"""Vectorized block-to-voxel material assignment."""

from __future__ import annotations

import numpy as np

from thermal_sim.core.conformal_mesh import ConformalMesh3D
from thermal_sim.models.assembly_block import AssemblyBlock

_DEFAULT_AIR = "Air Gap"


def assign_voxel_materials(
    mesh: ConformalMesh3D,
    blocks: list[AssemblyBlock],
    air_material_name: str = _DEFAULT_AIR,
) -> np.ndarray:
    """Assign a material name to every voxel in ``mesh``.

    Returns a numpy array of shape ``(nz, ny, nx)`` with dtype=object
    containing material name strings.

    Algorithm:
    - Initialise all cells to ``air_material_name``.
    - Iterate over ``blocks`` in definition order.  For each block, build
      boolean masks for the x, y, z axes using cell-centre coordinates and
      NumPy broadcasting, then assign ``block.material`` to the 3-D sub-array
      selected by the outer product of those masks.
    - Last-defined block wins on overlap (consistent with definition-order
      iteration: later blocks overwrite earlier ones).

    Containment criterion: cell centre is inside the block if
    ``block.lo <= centre < block.lo + block.size`` (inclusive lower, exclusive
    upper bound).
    """
    cx = mesh.x_centers()  # shape (nx,)
    cy = mesh.y_centers()  # shape (ny,)
    cz = mesh.z_centers()  # shape (nz,)

    mat_array = np.full((mesh.nz, mesh.ny, mesh.nx), fill_value=air_material_name, dtype=object)

    for blk in blocks:
        mask_x = (cx >= blk.x) & (cx < blk.x + blk.width)    # shape (nx,)
        mask_y = (cy >= blk.y) & (cy < blk.y + blk.depth)    # shape (ny,)
        mask_z = (cz >= blk.z) & (cz < blk.z + blk.height)   # shape (nz,)

        # Outer product: (nz, ny, nx) boolean mask
        # np.ix_ creates open meshes for broadcasting:
        #   mask_z -> (nz,1,1), mask_y -> (1,ny,1), mask_x -> (1,1,nx)
        iz, iy, ix = np.ix_(np.where(mask_z)[0], np.where(mask_y)[0], np.where(mask_x)[0])
        mat_array[iz, iy, ix] = blk.material

    return mat_array
