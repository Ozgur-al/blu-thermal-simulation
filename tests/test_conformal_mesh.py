"""Tests for ConformalMesh3D and voxel model data models."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Model round-trip tests (AssemblyBlock, SurfaceSource, VoxelProject)
# ---------------------------------------------------------------------------


def test_assembly_block_round_trip():
    from thermal_sim.models.assembly_block import AssemblyBlock

    block = AssemblyBlock(
        name="frame",
        material="Steel",
        x=0.0,
        y=0.0,
        z=0.0,
        width=0.45,
        depth=0.3,
        height=0.003,
    )
    d = block.to_dict()
    restored = AssemblyBlock.from_dict(d)
    assert restored == block


def test_assembly_block_empty_name_raises():
    from thermal_sim.models.assembly_block import AssemblyBlock

    with pytest.raises(ValueError, match="name"):
        AssemblyBlock(name="", material="Steel", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.01)


def test_assembly_block_empty_material_raises():
    from thermal_sim.models.assembly_block import AssemblyBlock

    with pytest.raises(ValueError, match="material"):
        AssemblyBlock(name="a", material="", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.01)


def test_assembly_block_zero_dimension_raises():
    from thermal_sim.models.assembly_block import AssemblyBlock

    with pytest.raises(ValueError):
        AssemblyBlock(name="a", material="Steel", x=0, y=0, z=0, width=0.0, depth=0.1, height=0.01)

    with pytest.raises(ValueError):
        AssemblyBlock(name="a", material="Steel", x=0, y=0, z=0, width=0.1, depth=0.0, height=0.01)

    with pytest.raises(ValueError):
        AssemblyBlock(name="a", material="Steel", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.0)


def test_assembly_block_negative_dimension_raises():
    from thermal_sim.models.assembly_block import AssemblyBlock

    with pytest.raises(ValueError):
        AssemblyBlock(
            name="a", material="Steel", x=0, y=0, z=0, width=-0.1, depth=0.1, height=0.01
        )


def test_surface_source_round_trip():
    from thermal_sim.models.surface_source import SurfaceSource

    src = SurfaceSource(
        name="led1",
        block="pcb_left",
        face="top",
        power_w=0.5,
        shape="rectangle",
        x=0.01,
        y=0.05,
        width=0.002,
        height=0.002,
    )
    d = src.to_dict()
    restored = SurfaceSource.from_dict(d)
    assert restored == src


def test_surface_source_invalid_face_raises():
    from thermal_sim.models.surface_source import SurfaceSource

    with pytest.raises(ValueError, match="face"):
        SurfaceSource(name="led1", block="pcb", face="diagonal", power_w=0.5)


def test_surface_source_valid_faces():
    from thermal_sim.models.surface_source import SurfaceSource

    for face in ("top", "bottom", "left", "right", "front", "back"):
        src = SurfaceSource(name="s", block="blk", face=face, power_w=1.0)
        assert src.face == face


def test_surface_source_negative_power_raises():
    from thermal_sim.models.surface_source import SurfaceSource

    with pytest.raises(ValueError, match="power"):
        SurfaceSource(name="s", block="blk", face="top", power_w=-1.0)


def test_surface_source_rectangle_needs_width_height():
    from thermal_sim.models.surface_source import SurfaceSource

    with pytest.raises(ValueError):
        SurfaceSource(name="s", block="b", face="top", power_w=1.0, shape="rectangle")


def test_surface_source_circle_needs_radius():
    from thermal_sim.models.surface_source import SurfaceSource

    with pytest.raises(ValueError):
        SurfaceSource(name="s", block="b", face="top", power_w=1.0, shape="circle")


def test_voxel_project_round_trip():
    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.models.boundary import SurfaceBoundary
    from thermal_sim.models.material import Material
    from thermal_sim.models.surface_source import SurfaceSource
    from thermal_sim.models.voxel_project import (
        BoundaryGroup,
        VoxelMeshConfig,
        VoxelProbe,
        VoxelProject,
        VoxelTransientConfig,
    )

    mat = Material(
        name="Aluminum",
        k_in_plane=160.0,
        k_through=160.0,
        density=2700.0,
        specific_heat=900.0,
    )
    block = AssemblyBlock(
        name="frame", material="Aluminum", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.003
    )
    src = SurfaceSource(name="led1", block="frame", face="top", power_w=0.5)
    probe = VoxelProbe(name="p1", x=0.05, y=0.05, z=0.003)
    bg = BoundaryGroup(
        name="top_exposed", boundary=SurfaceBoundary(convection_h=8.0, include_radiation=True)
    )
    mesh_cfg = VoxelMeshConfig(cells_per_interval=1)
    t_cfg = VoxelTransientConfig(duration_s=60.0, dt_s=1.0, initial_temp_c=25.0)

    project = VoxelProject(
        name="test_project",
        blocks=[block],
        materials={"Aluminum": mat},
        sources=[src],
        boundary_groups=[bg],
        probes=[probe],
        mesh_config=mesh_cfg,
        transient_config=t_cfg,
    )

    d = project.to_dict()
    restored = VoxelProject.from_dict(d)

    assert restored.name == project.name
    assert len(restored.blocks) == 1
    assert restored.blocks[0] == block
    assert len(restored.sources) == 1
    assert restored.sources[0] == src
    assert len(restored.probes) == 1
    assert restored.probes[0].z == 0.003
    assert len(restored.boundary_groups) == 1
    assert restored.mesh_config.cells_per_interval == 1
    assert restored.transient_config is not None
    assert restored.transient_config.duration_s == 60.0


def test_voxel_project_no_transient_config():
    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.models.material import Material
    from thermal_sim.models.voxel_project import VoxelMeshConfig, VoxelProject

    mat = Material(
        name="Aluminum",
        k_in_plane=160.0,
        k_through=160.0,
        density=2700.0,
        specific_heat=900.0,
    )
    block = AssemblyBlock(
        name="b", material="Aluminum", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.003
    )
    project = VoxelProject(
        name="p",
        blocks=[block],
        materials={"Aluminum": mat},
        sources=[],
        boundary_groups=[],
        probes=[],
        mesh_config=VoxelMeshConfig(),
        transient_config=None,
    )
    d = project.to_dict()
    restored = VoxelProject.from_dict(d)
    assert restored.transient_config is None


# ---------------------------------------------------------------------------
# ConformalMesh3D tests
# ---------------------------------------------------------------------------


def test_conformal_mesh_edge_collection():
    """Overlapping blocks produce sorted, deduplicated edges."""
    import numpy as np

    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    block_a = AssemblyBlock(
        name="a", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    block_b = AssemblyBlock(
        name="b", material="M", x=0.05, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    mesh = build_conformal_mesh([block_a, block_b])
    # Expected x_edges: 0.0, 0.05, 0.1, 0.15
    np.testing.assert_allclose(mesh.x_edges, [0.0, 0.05, 0.1, 0.15])
    assert mesh.nx == 3


def test_conformal_mesh_cell_counts():
    import numpy as np

    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    block = AssemblyBlock(
        name="b", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.02
    )
    mesh = build_conformal_mesh([block])
    assert mesh.nx == 1
    assert mesh.ny == 1
    assert mesh.nz == 1
    assert mesh.total_cells == 1


def test_conformal_mesh_centers():
    import numpy as np

    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    block_a = AssemblyBlock(
        name="a", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    block_b = AssemblyBlock(
        name="b", material="M", x=0.1, y=0.0, z=0.0, width=0.2, depth=0.05, height=0.01
    )
    mesh = build_conformal_mesh([block_a, block_b])
    # x_edges = [0.0, 0.1, 0.3]  => centers [0.05, 0.2]
    np.testing.assert_allclose(mesh.x_centers(), [0.05, 0.2])


def test_conformal_mesh_spacing():
    import numpy as np

    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    block_a = AssemblyBlock(
        name="a", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    block_b = AssemblyBlock(
        name="b", material="M", x=0.1, y=0.0, z=0.0, width=0.2, depth=0.05, height=0.01
    )
    mesh = build_conformal_mesh([block_a, block_b])
    assert pytest.approx(mesh.dx(0)) == 0.1
    assert pytest.approx(mesh.dx(1)) == 0.2


def test_conformal_mesh_node_index():
    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    # 2x3x4 mesh: nx=2, ny=3, nz=4
    blocks = [
        AssemblyBlock(name="a", material="M", x=0, y=0, z=0, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="b", material="M", x=0.1, y=0, z=0, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="c", material="M", x=0, y=0.1, z=0, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="d", material="M", x=0, y=0.2, z=0, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="e", material="M", x=0, y=0, z=0.1, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="f", material="M", x=0, y=0, z=0.2, width=0.1, depth=0.1, height=0.1),
        AssemblyBlock(name="g", material="M", x=0, y=0, z=0.3, width=0.1, depth=0.1, height=0.1),
    ]
    mesh = build_conformal_mesh(blocks)
    assert mesh.nx == 2
    assert mesh.ny == 3
    assert mesh.nz == 4
    # C-order: iz * ny * nx + iy * nx + ix
    assert mesh.node_index(0, 0, 0) == 0
    assert mesh.node_index(1, 0, 0) == 1
    assert mesh.node_index(0, 1, 0) == 2
    assert mesh.node_index(0, 0, 1) == 6   # 1 * 3 * 2 + 0 * 2 + 0
    assert mesh.node_index(1, 2, 3) == 3 * 3 * 2 + 2 * 2 + 1  # 18+4+1=23
    assert mesh.total_cells == 2 * 3 * 4


def test_conformal_mesh_cells_per_interval():
    """cells_per_interval=2 doubles the cell count in each direction."""
    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    block = AssemblyBlock(
        name="b", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.02
    )
    mesh1 = build_conformal_mesh([block], cells_per_interval=1)
    mesh2 = build_conformal_mesh([block], cells_per_interval=2)
    assert mesh2.nx == mesh1.nx * 2
    assert mesh2.ny == mesh1.ny * 2
    assert mesh2.nz == mesh1.nz * 2


def test_conformal_mesh_deduplication():
    """Coincident edges from two touching blocks are deduplicated."""
    import numpy as np

    from thermal_sim.models.assembly_block import AssemblyBlock
    from thermal_sim.core.conformal_mesh import build_conformal_mesh

    # Block A: x=[0, 0.1], Block B: x=[0.1, 0.2] — they share x=0.1
    block_a = AssemblyBlock(
        name="a", material="M", x=0.0, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    block_b = AssemblyBlock(
        name="b", material="M", x=0.1, y=0.0, z=0.0, width=0.1, depth=0.05, height=0.01
    )
    mesh = build_conformal_mesh([block_a, block_b])
    # x_edges: [0.0, 0.1, 0.2] — NOT [0.0, 0.1, 0.1, 0.2]
    np.testing.assert_allclose(mesh.x_edges, [0.0, 0.1, 0.2])
    assert mesh.nx == 2
