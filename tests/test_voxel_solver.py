"""Analytical validation tests for the voxel-based 3D thermal solver.

Tests port the classical RC-network benchmarks (1D resistance chain, 2-node
network, RC transient decay) to use VoxelProject / AssemblyBlock inputs.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from thermal_sim.models.assembly_block import AssemblyBlock
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.material import Material
from thermal_sim.models.voxel_project import (
    BoundaryGroup,
    VoxelMeshConfig,
    VoxelProject,
    VoxelTransientConfig,
)


# ---------------------------------------------------------------------------
# Helpers to build minimal VoxelProject instances
# ---------------------------------------------------------------------------


def _single_block_project(
    *,
    k: float = 1.0,
    density: float = 2000.0,
    cp: float = 900.0,
    width: float = 0.10,
    depth: float = 0.10,
    height: float = 0.005,
    h_conv: float = 10.0,
    ambient_c: float = 25.0,
    power_w: float = 0.0,
    include_radiation: bool = False,
) -> VoxelProject:
    """Return a 1-block VoxelProject with convection on all faces."""
    mat = Material("Mat", k_in_plane=k, k_through=k, density=density, specific_heat=cp)
    blk = AssemblyBlock("Block", material="Mat", x=0.0, y=0.0, z=0.0,
                        width=width, depth=depth, height=height,
                        power_w=power_w)
    bc = SurfaceBoundary(ambient_c=ambient_c, convection_h=h_conv,
                         include_radiation=include_radiation)
    bg = BoundaryGroup(name="all", boundary=bc)
    return VoxelProject(
        name="test",
        blocks=[blk],
        materials={"Mat": mat},
        boundary_groups=[bg],
        probes=[],
        mesh_config=VoxelMeshConfig(cells_per_interval=1),
    )


# ---------------------------------------------------------------------------
# Task 1 tests: VoxelThermalNetwork structure
# ---------------------------------------------------------------------------


class TestVoxelNetworkBuilder:
    """Tests for build_voxel_network — imported lazily so RED phase can run."""

    def _import_builder(self):
        from thermal_sim.solvers.voxel_network_builder import (
            VoxelThermalNetwork,
            build_voxel_network,
        )
        return build_voxel_network, VoxelThermalNetwork

    def test_network_has_correct_size(self):
        build_voxel_network, VoxelThermalNetwork = self._import_builder()
        project = _single_block_project()
        net = build_voxel_network(project)
        assert isinstance(net, VoxelThermalNetwork)
        n = net.mesh.total_cells
        assert net.a_matrix.shape == (n, n)
        assert net.b_vector.shape == (n,)
        assert net.c_vector.shape == (n,)

    def test_conductance_matrix_is_symmetric(self):
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project()
        net = build_voxel_network(project)
        diff = (net.a_matrix - net.a_matrix.T).data
        assert len(diff) == 0 or np.allclose(diff, 0.0, atol=1e-12)

    def test_conductance_matrix_is_diagonal_dominant(self):
        """Diagonal >= sum of absolute off-diagonal entries (within roundoff)."""
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project()
        net = build_voxel_network(project)
        A = net.a_matrix.toarray()
        diag = np.diag(A)
        off = np.abs(A) - np.diag(diag)
        # Each row: diag >= row_sum_of_offdiag
        assert np.all(diag >= off.sum(axis=1) - 1e-12)

    def test_diagonal_entries_are_positive(self):
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project()
        net = build_voxel_network(project)
        assert np.all(net.a_matrix.diagonal() > 0.0)

    def test_two_block_harmonic_mean_conductance(self):
        """Two blocks in z-direction: interface conductance should equal harmonic mean."""
        build_voxel_network, _ = self._import_builder()
        k1, k2 = 1.0, 10.0
        h1, h2 = 0.005, 0.005  # equal thickness blocks
        area = 0.10 * 0.10
        mat1 = Material("M1", k_in_plane=k1, k_through=k1, density=1000.0, specific_heat=900.0)
        mat2 = Material("M2", k_in_plane=k2, k_through=k2, density=1000.0, specific_heat=900.0)
        blk1 = AssemblyBlock("B1", material="M1", x=0.0, y=0.0, z=0.0,
                              width=0.10, depth=0.10, height=h1)
        blk2 = AssemblyBlock("B2", material="M2", x=0.0, y=0.0, z=h1,
                              width=0.10, depth=0.10, height=h2)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False)
        project = VoxelProject(
            name="two_block_z",
            blocks=[blk1, blk2],
            materials={"M1": mat1, "M2": mat2},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(cells_per_interval=1),
        )
        net = build_voxel_network(project)

        # With two cells in z, the off-diagonal coupling should be the
        # harmonic-mean conductance: face_area / (dz1/(2*k1) + dz2/(2*k2))
        # But the diagonal includes BCs, so just check a_matrix[0,1] == -G_harmonic
        G_expected = area / (h1 / (2.0 * k1) + h2 / (2.0 * k2))
        A = net.a_matrix.toarray()
        # Off-diagonal (0,1) should be -G_harmonic (single cell per z-level)
        assert math.isclose(A[0, 1], -G_expected, rel_tol=1e-9)

    def test_capacity_vector_correct(self):
        """C = density * cp * volume for uniform single-cell block."""
        build_voxel_network, _ = self._import_builder()
        density, cp = 2000.0, 900.0
        width, depth, height = 0.10, 0.10, 0.005
        project = _single_block_project(density=density, cp=cp,
                                        width=width, depth=depth, height=height)
        net = build_voxel_network(project)
        volume = width * depth * height
        expected_c = density * cp * volume
        assert math.isclose(float(net.c_vector[0]), expected_c, rel_tol=1e-9)

    def test_block_power_injects_into_b_vector(self):
        """b_vector should be nonzero when a block has power_w > 0."""
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project(power_w=1.0)
        net = build_voxel_network(project)
        # b_vector includes both BC forcing and source power
        # Total b_vector sum should contain the source power somewhere
        assert net.b_vector.sum() > 0.0

    def test_no_source_b_vector_only_bc_terms(self):
        """Without sources, b_vector is entirely from BC (ambient*conductance)."""
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project(power_w=0.0, ambient_c=30.0)
        net = build_voxel_network(project)
        # b_vector should be positive (convection * T_amb > 0)
        assert net.b_vector.sum() > 0.0

    def test_material_grid_shape(self):
        """material_grid should have shape (nz, ny, nx)."""
        build_voxel_network, _ = self._import_builder()
        project = _single_block_project()
        net = build_voxel_network(project)
        m = net.mesh
        assert net.material_grid.shape == (m.nz, m.ny, m.nx)


# ---------------------------------------------------------------------------
# Task 2 tests: VoxelSteadyStateSolver
# ---------------------------------------------------------------------------


class TestVoxelSteadyStateSolver:
    """Tests for VoxelSteadyStateSolver."""

    def _import_solver(self):
        from thermal_sim.solvers.steady_state_voxel import VoxelSteadyStateSolver
        return VoxelSteadyStateSolver

    def test_result_shape(self):
        VoxelSteadyStateSolver = self._import_solver()
        project = _single_block_project()
        result = VoxelSteadyStateSolver().solve(project)
        m = result.mesh
        assert result.temperatures_c.shape == (m.nz, m.ny, m.nx)

    def test_temperatures_above_ambient(self):
        """Temperatures with power input should exceed ambient."""
        VoxelSteadyStateSolver = self._import_solver()
        project = _single_block_project(power_w=1.0, ambient_c=25.0)
        result = VoxelSteadyStateSolver().solve(project)
        assert float(result.temperatures_c.max()) > 25.0

    def test_no_source_uniform_temperature(self):
        """Without sources, all cells should converge to ambient."""
        VoxelSteadyStateSolver = self._import_solver()
        project = _single_block_project(power_w=0.0, ambient_c=30.0)
        result = VoxelSteadyStateSolver().solve(project)
        assert np.allclose(result.temperatures_c, 30.0, atol=1e-6)

    def test_1d_two_layer_resistance_chain(self):
        """Two blocks stacked in z (1x1 XY cells); convection on all exposed faces.

        The builder assigns the same boundary condition to all 6 exposed faces.
        The analytical solution must account for all face conductances.

        For a 2-node z-stack (1 cell in x, 1 cell in y):
          Node 0 (bottom block): conductances to ambient from bottom, front, back, left, right faces
                                  + conductance to node 1 (harmonic mean in z)
          Node 1 (top block):    conductances to ambient from top, front, back, left, right faces
                                  + conductance from node 0

        The BC builder assigns the SAME h to ALL exposed faces (single BoundaryGroup).
        For face conductance: G_face = h * face_area (no conduction series term in the
        voxel builder — it applies h directly to the cell surface).

        Tolerance: 1e-9 (exact match with spsolve for 2-node system).
        """
        VoxelSteadyStateSolver = self._import_solver()
        k1, k2 = 0.8, 10.0
        dz1, dz2 = 0.001, 0.002
        width, depth = 0.12, 0.10
        area_z = width * depth   # top/bottom face area
        area_xz1 = depth * dz1  # front/back face area for bottom block
        area_xz2 = depth * dz2  # front/back face area for top block
        area_yz1 = width * dz1  # left/right face area for bottom block
        area_yz2 = width * dz2  # left/right face area for top block
        h = 8.0
        T_amb = 23.0
        Q = 1.7

        mat1 = Material("M1", k_in_plane=k1, k_through=k1, density=2000.0, specific_heat=900.0)
        mat2 = Material("M2", k_in_plane=k2, k_through=k2, density=2000.0, specific_heat=900.0)
        blk1 = AssemblyBlock("Bot", material="M1", x=0.0, y=0.0, z=0.0,
                              width=width, depth=depth, height=dz1,
                              power_w=Q)
        blk2 = AssemblyBlock("Top", material="M2", x=0.0, y=0.0, z=dz1,
                              width=width, depth=depth, height=dz2)
        bc = SurfaceBoundary(ambient_c=T_amb, convection_h=h, include_radiation=False)
        project = VoxelProject(
            name="two_layer_chain",
            blocks=[blk1, blk2],
            materials={"M1": mat1, "M2": mat2},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(cells_per_interval=1),
        )
        result = VoxelSteadyStateSolver().solve(project)

        # Analytical: full 6-face BC accounting
        # Node 0 (bottom block) exposed faces: bottom + front + back + left + right
        G_bot_0 = h * area_z       # bottom face
        G_sides_0 = (h * area_xz1 * 2 +   # front + back
                     h * area_yz1 * 2)      # left + right
        G_env_0 = G_bot_0 + G_sides_0

        # Node 1 (top block) exposed faces: top + front + back + left + right
        G_top_1 = h * area_z       # top face
        G_sides_1 = (h * area_xz2 * 2 +
                     h * area_yz2 * 2)
        G_env_1 = G_top_1 + G_sides_1

        # Harmonic-mean z-conductance between the two blocks
        G_between = area_z / (dz1 / (2.0 * k1) + dz2 / (2.0 * k2))

        # 2-node system:
        #   (G_env_0 + G_between)*T0 - G_between*T1 = Q + G_env_0*T_amb
        #   -G_between*T0 + (G_env_1 + G_between)*T1 = G_env_1*T_amb
        a = G_env_0 + G_between
        b_coef = -G_between
        c_coef = -G_between
        d = G_env_1 + G_between
        rhs0 = Q + G_env_0 * T_amb
        rhs1 = G_env_1 * T_amb
        det = a * d - b_coef * c_coef
        T0_expected = (rhs0 * d - b_coef * rhs1) / det
        T1_expected = (a * rhs1 - rhs0 * c_coef) / det

        T0_sim = float(result.temperatures_c[0, 0, 0])  # bottom block
        T1_sim = float(result.temperatures_c[1, 0, 0])  # top block
        assert math.isclose(T0_sim, T0_expected, rel_tol=1e-9, abs_tol=1e-9), (
            f"Bottom: sim={T0_sim:.6f} C, expected={T0_expected:.6f} C"
        )
        assert math.isclose(T1_sim, T1_expected, rel_tol=1e-9, abs_tol=1e-9), (
            f"Top: sim={T1_sim:.6f} C, expected={T1_expected:.6f} C"
        )

    def test_2_node_single_block_steady_state(self):
        """Single block, convection BCs on all faces, power injected on top.

        Analytical: T_interior = T_amb + Q / G_total where G_total is the
        effective conductance of all exposed face conductances.

        For a 1x1x1 block with equal convection h on all faces:
          G_total = sum of all face conductances
          T = T_amb + Q / G_total
        """
        VoxelSteadyStateSolver = self._import_solver()
        k = 50.0   # high conductivity -> nearly isothermal block
        h = 10.0
        T_amb = 25.0
        Q = 2.0
        width, depth, height = 0.10, 0.10, 0.005
        area_top = width * depth
        area_front_back = width * height
        area_left_right = depth * height

        bc = SurfaceBoundary(ambient_c=T_amb, convection_h=h, include_radiation=False)
        mat = Material("Mat", k_in_plane=k, k_through=k, density=2000.0, specific_heat=900.0)
        blk = AssemblyBlock("B", material="Mat", x=0.0, y=0.0, z=0.0,
                             width=width, depth=depth, height=height,
                             power_w=Q)
        project = VoxelProject(
            name="2node_single",
            blocks=[blk],
            materials={"Mat": mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(cells_per_interval=1),
        )
        result = VoxelSteadyStateSolver().solve(project)

        # For a highly conductive (k=50) single cell, the temperature should be
        # close to: T_amb + Q / G_total where G_total is sum of BC conductances.
        # Face conductances for a single node with h on all faces:
        G_top = h * area_top
        G_bot = h * area_top
        G_front = h * area_front_back
        G_back = h * area_front_back
        G_left = h * area_left_right
        G_right = h * area_left_right
        G_total = G_top + G_bot + G_front + G_back + G_left + G_right
        T_expected = T_amb + Q / G_total

        T_sim = float(result.temperatures_c[0, 0, 0])
        # With 1x1x1 mesh and high k, single-node approximation is exact
        assert math.isclose(T_sim, T_expected, rel_tol=0.01, abs_tol=0.01), (
            f"sim={T_sim:.4f} C, expected={T_expected:.4f} C"
        )


# ---------------------------------------------------------------------------
# Task 2 tests: VoxelTransientSolver
# ---------------------------------------------------------------------------


class TestVoxelTransientSolver:
    """Tests for VoxelTransientSolver."""

    def _import_solver(self):
        from thermal_sim.solvers.transient_voxel import VoxelTransientSolver
        return VoxelTransientSolver

    def test_result_shape(self):
        VoxelTransientSolver = self._import_solver()
        mat = Material("Mat", k_in_plane=1.0, k_through=1.0, density=2000.0, specific_heat=900.0)
        blk = AssemblyBlock("B", material="Mat", x=0.0, y=0.0, z=0.0,
                             width=0.10, depth=0.10, height=0.005)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False)
        blk = AssemblyBlock("B", material="Mat", x=0.0, y=0.0, z=0.0,
                             width=0.10, depth=0.10, height=0.005, power_w=1.0)
        project = VoxelProject(
            name="test_transient",
            blocks=[blk],
            materials={"Mat": mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(1),
            transient_config=VoxelTransientConfig(duration_s=5.0, dt_s=1.0, initial_temp_c=25.0),
        )
        result = VoxelTransientSolver().solve(project)
        m = result.mesh
        n_steps = int(5.0 / 1.0)
        assert result.temperatures_c.shape == (n_steps + 1, m.nz, m.ny, m.nx)
        assert result.time_points.shape == (n_steps + 1,)
        assert result.time_points[0] == 0.0

    def test_initial_temperature_is_correct(self):
        VoxelTransientSolver = self._import_solver()
        T_init = 30.0
        mat = Material("Mat", k_in_plane=1.0, k_through=1.0, density=2000.0, specific_heat=900.0)
        blk = AssemblyBlock("B", material="Mat", x=0.0, y=0.0, z=0.0,
                             width=0.10, depth=0.10, height=0.005)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False)
        project = VoxelProject(
            name="init_temp",
            blocks=[blk],
            materials={"Mat": mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(1),
            transient_config=VoxelTransientConfig(duration_s=5.0, dt_s=1.0, initial_temp_c=T_init),
        )
        result = VoxelTransientSolver().solve(project)
        assert np.allclose(result.temperatures_c[0], T_init)

    def test_rc_transient_decay(self):
        """Single block, step power input; verify exponential approach to steady state.

        T(t) = T_ss * (1 - exp(-t/tau))  where tau = RC = C / G_total.
        Check at t=tau within 2%.
        """
        VoxelTransientSolver = self._import_solver()
        k = 50.0    # high conductivity -> uniform block temperature
        density = 2700.0
        cp = 900.0
        h = 15.0
        T_init = 25.0
        T_amb = 25.0
        Q = 2.0
        width, depth, height = 0.10, 0.10, 0.002

        mat = Material("RC", k_in_plane=k, k_through=k, density=density, specific_heat=cp)
        blk = AssemblyBlock("B", material="RC", x=0.0, y=0.0, z=0.0,
                             width=width, depth=depth, height=height, power_w=Q)
        bc = SurfaceBoundary(ambient_c=T_amb, convection_h=h, include_radiation=False)

        # Analytical parameters
        area_top = width * depth
        area_sides_fb = width * height  # front + back
        area_sides_lr = depth * height  # left + right
        # All 6 faces have convection
        G_total = (h * (area_top * 2 + area_sides_fb * 2 + area_sides_lr * 2))
        C_total = density * cp * (width * depth * height)
        tau = C_total / G_total
        T_ss = T_amb + Q / G_total
        dT_steady = T_ss - T_amb  # steady-state rise

        # Run for 3 * tau seconds to see good exponential growth
        duration = 3.0 * tau
        dt = tau / 50.0  # fine enough time steps

        project = VoxelProject(
            name="rc_decay",
            blocks=[blk],
            materials={"RC": mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(1),
            transient_config=VoxelTransientConfig(
                duration_s=duration, dt_s=dt, initial_temp_c=T_init
            ),
        )
        result = VoxelTransientSolver().solve(project)

        # Find index closest to t = tau
        idx_tau = int(np.argmin(np.abs(result.time_points - tau)))
        t_actual = float(result.time_points[idx_tau])
        T_sim = float(result.temperatures_c[idx_tau, 0, 0, 0])

        # Analytical at actual t
        T_analytical = T_amb + dT_steady * (1.0 - math.exp(-t_actual / tau))

        T_rise = dT_steady
        assert math.isclose(T_sim, T_analytical, rel_tol=0.02, abs_tol=0.02 * T_rise), (
            f"At t={t_actual:.3f}s (tau={tau:.3f}s): sim={T_sim:.4f} C, "
            f"analytical={T_analytical:.4f} C, T_ss={T_ss:.4f} C"
        )


# ---------------------------------------------------------------------------
# Task 2 tests: voxel_layer_stats in postprocess
# ---------------------------------------------------------------------------


class TestVoxelLayerStats:
    """Tests for voxel_layer_stats in postprocess.py."""

    def _import_stats(self):
        from thermal_sim.core.postprocess import voxel_layer_stats
        return voxel_layer_stats

    def _get_result(self):
        from thermal_sim.solvers.steady_state_voxel import VoxelSteadyStateSolver
        mat = Material("Hot", k_in_plane=50.0, k_through=50.0, density=2000.0, specific_heat=900.0)
        blk = AssemblyBlock("B", material="Hot", x=0.0, y=0.0, z=0.0,
                             width=0.10, depth=0.10, height=0.005, power_w=1.0)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False)
        project = VoxelProject(
            name="stats_test",
            blocks=[blk],
            materials={"Hot": mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(1),
        )
        return VoxelSteadyStateSolver().solve(project), project

    def test_stats_returns_list_with_one_entry_per_block(self):
        voxel_layer_stats = self._import_stats()
        result, project = self._get_result()
        stats = voxel_layer_stats(result, project)
        assert len(stats) == len(project.blocks)

    def test_stats_has_required_keys(self):
        voxel_layer_stats = self._import_stats()
        result, project = self._get_result()
        stats = voxel_layer_stats(result, project)
        for entry in stats:
            assert "block" in entry
            assert "t_max_c" in entry
            assert "t_avg_c" in entry
            assert "t_min_c" in entry

    def test_stats_temperatures_physically_reasonable(self):
        voxel_layer_stats = self._import_stats()
        result, project = self._get_result()
        stats = voxel_layer_stats(result, project)
        entry = stats[0]
        assert entry["t_max_c"] >= entry["t_avg_c"] >= entry["t_min_c"]
        assert entry["t_max_c"] > 25.0  # heated above ambient


# ---------------------------------------------------------------------------
# Plan 07 tests: powered block contact diagnostic
# ---------------------------------------------------------------------------


class TestPoweredBlockDiagnostic:
    """Tests for diagnose_powered_block_contacts() in voxel_network_builder."""

    def _import_diagnostic(self):
        from thermal_sim.solvers.voxel_network_builder import diagnose_powered_block_contacts
        return diagnose_powered_block_contacts

    def _make_two_block_project(self) -> VoxelProject:
        """Powered LED block (small) sitting directly on top of an aluminum slab.

        Geometry (z-axis):
          z=0.000 to z=0.002 — Aluminum slab (100mm x 100mm x 2mm)
          z=0.002 to z=0.003 — LED block    ( 50mm x  50mm x 1mm, power_w=0.5)

        The LED block shares its -z face with the aluminum slab.
        """
        al_mat = Material("Aluminum", k_in_plane=205.0, k_through=205.0,
                          density=2700.0, specific_heat=900.0)
        led_mat = Material("LED", k_in_plane=1.0, k_through=1.0,
                           density=2000.0, specific_heat=900.0)
        # Slab: full 100 x 100 mm base
        slab = AssemblyBlock("Slab", material="Aluminum",
                              x=0.0, y=0.0, z=0.0,
                              width=0.10, depth=0.10, height=0.002)
        # LED block: centered, sits on slab top face
        led = AssemblyBlock("LED_1", material="LED",
                             x=0.025, y=0.025, z=0.002,
                             width=0.05, depth=0.05, height=0.001,
                             power_w=0.5)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=8.0, include_radiation=False)
        return VoxelProject(
            name="led_on_slab",
            blocks=[slab, led],
            materials={"Aluminum": al_mat, "LED": led_mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(cells_per_interval=1),
        )

    def _make_isolated_block_project(self) -> VoxelProject:
        """Single powered block with no neighboring solid blocks — all faces touch air."""
        led_mat = Material("LED", k_in_plane=1.0, k_through=1.0,
                           density=2000.0, specific_heat=900.0)
        led = AssemblyBlock("LED_alone", material="LED",
                             x=0.0, y=0.0, z=0.0,
                             width=0.05, depth=0.05, height=0.001,
                             power_w=1.0)
        bc = SurfaceBoundary(ambient_c=25.0, convection_h=8.0, include_radiation=False)
        return VoxelProject(
            name="isolated_led",
            blocks=[led],
            materials={"LED": led_mat},
            boundary_groups=[BoundaryGroup("all", bc)],
            probes=[],
            mesh_config=VoxelMeshConfig(cells_per_interval=1),
        )

    def test_powered_block_contact_diagnostic(self):
        """LED block on aluminum slab: diagnostic reports Aluminum as -z neighbor."""
        diagnose_powered_block_contacts = self._import_diagnostic()
        project = self._make_two_block_project()
        results = diagnose_powered_block_contacts(project)

        # Only the LED block has power_w > 0
        assert len(results) == 1, f"Expected 1 powered block, got {len(results)}"
        entry = results[0]
        assert entry["block_name"] == "LED_1"
        assert entry["power_w"] == pytest.approx(0.5)
        assert "neighbors" in entry

        # Find Aluminum neighbor
        al_neighbors = [n for n in entry["neighbors"] if n["material"] == "Aluminum"]
        assert len(al_neighbors) >= 1, (
            f"Expected at least one Aluminum neighbor, got: {entry['neighbors']}"
        )
        al = al_neighbors[0]
        assert al["face_area_m2"] > 0.0
        assert al["direction"] in ("+x", "-x", "+y", "-y", "+z", "-z")

        # Aluminum should be below the LED block: -z direction
        assert al["direction"] == "-z", (
            f"Expected Aluminum in -z direction, got {al['direction']}"
        )

        # Face area should equal the LED block footprint (50mm x 50mm = 0.0025 m2)
        assert al["face_area_m2"] == pytest.approx(0.05 * 0.05, rel=0.01)

    def test_powered_block_isolated_in_air(self):
        """Single powered block with no neighbors reports only air."""
        diagnose_powered_block_contacts = self._import_diagnostic()
        project = self._make_isolated_block_project()
        results = diagnose_powered_block_contacts(project)

        assert len(results) == 1
        entry = results[0]
        assert entry["block_name"] == "LED_alone"

        # All neighbors should be "Air Gap" (the default air material name)
        non_air = [n for n in entry["neighbors"]
                   if n["material"] not in ("Air Gap", "Air", "air", "air gap")]
        assert len(non_air) == 0, (
            f"Isolated block should only have air neighbors, got: {non_air}"
        )

    def test_diagnostic_return_structure(self):
        """Verify return type and dict keys match the documented contract."""
        diagnose_powered_block_contacts = self._import_diagnostic()
        project = self._make_two_block_project()
        results = diagnose_powered_block_contacts(project)

        assert isinstance(results, list)
        for entry in results:
            assert isinstance(entry, dict)
            assert "block_name" in entry
            assert "power_w" in entry
            assert "neighbors" in entry
            assert isinstance(entry["neighbors"], list)
            for n in entry["neighbors"]:
                assert "material" in n
                assert "face_area_m2" in n
                assert "direction" in n
                assert n["direction"] in ("+x", "-x", "+y", "-y", "+z", "-z")
