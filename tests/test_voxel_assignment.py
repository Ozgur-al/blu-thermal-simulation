"""Tests for vectorized voxel material assignment."""

from __future__ import annotations

import numpy as np
import pytest


def _make_block(name, material, x, y, z, width, depth, height):
    from thermal_sim.models.assembly_block import AssemblyBlock

    return AssemblyBlock(
        name=name,
        material=material,
        x=x,
        y=y,
        z=z,
        width=width,
        depth=depth,
        height=height,
    )


def test_single_block_fills_all_cells():
    """Single block: every cell gets the block's material."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    block = _make_block("b", "Aluminum", 0, 0, 0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block])
    mat_array = assign_voxel_materials(mesh, [block])
    # shape is (nz, ny, nx)
    assert mat_array.shape == (mesh.nz, mesh.ny, mesh.nx)
    assert np.all(mat_array == "Aluminum")


def test_two_non_overlapping_blocks_no_air():
    """Two adjacent non-overlapping blocks: correct materials, no air gap."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    block_a = _make_block("a", "Aluminum", 0.0, 0.0, 0.0, 0.1, 0.05, 0.02)
    block_b = _make_block("b", "Steel", 0.1, 0.0, 0.0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block_a, block_b])
    mat_array = assign_voxel_materials(mesh, [block_a, block_b])

    # Two cells in x, one in y, one in z
    assert mesh.nx == 2
    assert mat_array[0, 0, 0] == "Aluminum"
    assert mat_array[0, 0, 1] == "Steel"


def test_air_gap_for_empty_voxels():
    """Voxels not inside any block get the air material name."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    # Two blocks separated by a gap in x
    block_a = _make_block("a", "Aluminum", 0.0, 0.0, 0.0, 0.1, 0.05, 0.02)
    block_b = _make_block("b", "Steel", 0.2, 0.0, 0.0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block_a, block_b])
    mat_array = assign_voxel_materials(mesh, [block_a, block_b])

    # mesh has x_edges=[0, 0.1, 0.2, 0.3] => 3 cells
    # Cell centers: 0.05, 0.15, 0.25
    # 0.05 is in block_a, 0.25 is in block_b, 0.15 is in neither
    assert mesh.nx == 3
    assert mat_array[0, 0, 0] == "Aluminum"
    assert mat_array[0, 0, 1] == "Air Gap"
    assert mat_array[0, 0, 2] == "Steel"


def test_overlap_last_defined_wins():
    """When two blocks overlap, last-defined block's material wins."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    # block_a covers full domain, block_b covers right half — overlapping
    block_a = _make_block("a", "Aluminum", 0.0, 0.0, 0.0, 0.2, 0.05, 0.02)
    block_b = _make_block("b", "Steel", 0.1, 0.0, 0.0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block_a, block_b])
    mat_array = assign_voxel_materials(mesh, [block_a, block_b])

    # 2 cells in x: [0,0.1] and [0.1,0.2]
    # Left cell center at 0.05 => inside block_a only => Aluminum
    # Right cell center at 0.15 => inside both; block_b last => Steel
    assert mat_array[0, 0, 0] == "Aluminum"
    assert mat_array[0, 0, 1] == "Steel"


def test_custom_air_material_name():
    """Custom air material name is used for empty voxels."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    block_a = _make_block("a", "Aluminum", 0.0, 0.0, 0.0, 0.1, 0.05, 0.02)
    block_b = _make_block("b", "Steel", 0.2, 0.0, 0.0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block_a, block_b])
    mat_array = assign_voxel_materials(mesh, [block_a, block_b], air_material_name="Vacuum")

    assert mat_array[0, 0, 1] == "Vacuum"


def test_cells_per_interval_doubles_resolution():
    """cells_per_interval=2 produces 8x the cells (2^3) for a single block."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    block = _make_block("b", "FR4", 0.0, 0.0, 0.0, 0.1, 0.05, 0.02)
    mesh = build_conformal_mesh([block], cells_per_interval=2)
    mat_array = assign_voxel_materials(mesh, [block])

    assert mat_array.shape == (2, 2, 2)
    assert np.all(mat_array == "FR4")


def test_voxel_assignment_shape_is_nz_ny_nx():
    """Result array shape is (nz, ny, nx) for correct C-order indexing."""
    from thermal_sim.core.conformal_mesh import build_conformal_mesh
    from thermal_sim.core.voxel_assignment import assign_voxel_materials

    # Create mesh with nx=2, ny=3, nz=1
    blocks = [
        _make_block("a", "M", 0.0, 0.0, 0.0, 0.1, 0.1, 0.02),
        _make_block("b", "M", 0.1, 0.0, 0.0, 0.1, 0.1, 0.02),
        _make_block("c", "M", 0.0, 0.1, 0.0, 0.1, 0.1, 0.02),
        _make_block("d", "M", 0.1, 0.1, 0.0, 0.1, 0.1, 0.02),
        _make_block("e", "M", 0.0, 0.2, 0.0, 0.1, 0.1, 0.02),
        _make_block("f", "M", 0.1, 0.2, 0.0, 0.1, 0.1, 0.02),
    ]
    mesh = build_conformal_mesh(blocks)
    assert mesh.nx == 2
    assert mesh.ny == 3
    assert mesh.nz == 1
    mat_array = assign_voxel_materials(mesh, blocks)
    assert mat_array.shape == (1, 3, 2)
