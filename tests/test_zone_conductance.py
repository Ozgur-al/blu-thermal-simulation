"""Unit tests for zone rasterization, harmonic-mean conductance, and NodeLayout.

Tests construct DisplayProject objects directly (no JSON loading).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.material_zone import MaterialZone
from thermal_sim.models.project import DisplayProject, MeshConfig
from thermal_sim.solvers.network_builder import NodeLayout, build_thermal_network
from thermal_sim.solvers.steady_state import SteadyStateSolver


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_material(name: str, k: float, density: float = 2700.0, cp: float = 900.0) -> Material:
    """Create a material with isotropic conductivity."""
    return Material(name=name, k_in_plane=k, k_through=k, density=density, specific_heat=cp)


def _adiabatic_boundaries(amb: float = 25.0) -> BoundaryConditions:
    """Return boundaries with no heat loss (all h=0, no radiation)."""
    surf = SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False)
    return BoundaryConditions(top=surf, bottom=surf, side=surf)


def _top_convection_only(h: float = 10.0, amb: float = 25.0) -> BoundaryConditions:
    """Return boundaries with top convection only."""
    zero = SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False)
    top  = SurfaceBoundary(ambient_c=amb, convection_h=h,   include_radiation=False)
    return BoundaryConditions(top=top, bottom=zero, side=zero)


# ---------------------------------------------------------------------------
# Test 1: NodeLayout identity with nz=1
# ---------------------------------------------------------------------------

def test_node_layout_identity_with_nz1() -> None:
    """NodeLayout.node(l, ix, iy) equals l*(nx*ny) + iy*nx + ix for nz=1."""
    nx, ny, n_layers = 5, 4, 3
    n_per_layer = nx * ny
    layer_offsets = tuple(l * n_per_layer for l in range(n_layers))

    layout = NodeLayout(
        nx=nx,
        ny=ny,
        n_per_layer=n_per_layer,
        n_layers=n_layers,
        layer_offsets=layer_offsets,
    )

    # Verify n_nodes
    assert layout.n_nodes == n_layers * nx * ny, (
        f"Expected n_nodes={n_layers * nx * ny}, got {layout.n_nodes}"
    )

    # Verify node() matches old formula for all valid combinations
    for l in range(n_layers):
        for iy in range(ny):
            for ix in range(nx):
                expected = l * n_per_layer + iy * nx + ix
                actual = layout.node(l, ix, iy)
                assert actual == expected, (
                    f"NodeLayout.node({l}, {ix}, {iy}) = {actual}, expected {expected}"
                )


# ---------------------------------------------------------------------------
# Test 2: Harmonic-mean conductance at zone boundary
# ---------------------------------------------------------------------------

def test_harmonic_mean_conductance_at_zone_boundary() -> None:
    """A-matrix off-diagonal equals the negative harmonic-mean conductance.

    Uses a 3x1 mesh with three zones so each zone covers exactly one cell.
    The harmonic mean of the left-cell and middle-cell conductances is checked
    against the A-matrix off-diagonal entry.
    """
    # 3x1 mesh: left cell = high-k, center cell = low-k, right cell = high-k
    # Using 3 cells ensures clear zone boundaries without floating-point ambiguity.
    width = 0.03    # m -> dx = 0.01 m per cell
    height = 0.01   # m -> dy = 0.01 m (1 cell)
    thickness = 0.001  # m
    k_high = 200.0  # W/mK
    k_low  =   1.0  # W/mK

    dx = width / 3   # = 0.01 m
    dy = height      # = 0.01 m

    # Each zone covers exactly one cell. Zones are centered at cell centers,
    # with width slightly less than 2*dx to avoid touching adjacent cell edges.
    zone_left   = MaterialZone(material="HighK", x=0.5 * dx,  y=0.5 * dy, width=0.9 * dx, height=dy)
    zone_center = MaterialZone(material="LowK",  x=1.5 * dx,  y=0.5 * dy, width=0.9 * dx, height=dy)
    zone_right  = MaterialZone(material="HighK", x=2.5 * dx,  y=0.5 * dy, width=0.9 * dx, height=dy)

    mat_high = _make_material("HighK", k_high)
    mat_low  = _make_material("LowK",  k_low)

    project = DisplayProject(
        name="HarmonicMeanTest",
        width=width,
        height=height,
        materials={"HighK": mat_high, "LowK": mat_low},
        layers=[Layer(
            name="L",
            material="HighK",  # base material (overridden by zones)
            thickness=thickness,
            zones=[zone_left, zone_center, zone_right],
        )],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=0.001, shape="full")],
        boundaries=_adiabatic_boundaries(),
        mesh=MeshConfig(nx=3, ny=1),
    )

    network = build_thermal_network(project)
    A = network.a_matrix.toarray()  # shape (3, 3)

    # Per-cell conductances before harmonic mean
    g_high = k_high * thickness * dy / dx   # W/K
    g_low  = k_low  * thickness * dy / dx   # W/K

    # Harmonic mean between left (HighK) and center (LowK)
    g_lc_expected = 2.0 * g_high * g_low / (g_high + g_low)
    # Harmonic mean between center (LowK) and right (HighK)
    g_cr_expected = 2.0 * g_low * g_high / (g_low + g_high)

    # A[0, 1] = -g_lc (left-center link)
    assert abs(A[0, 1] - (-g_lc_expected)) < 1e-10, (
        f"A[0,1]={A[0, 1]:.6e}, expected {-g_lc_expected:.6e}"
    )
    assert abs(A[1, 0] - (-g_lc_expected)) < 1e-10, (
        f"A[1,0]={A[1, 0]:.6e}, expected {-g_lc_expected:.6e}"
    )
    # A[1, 2] = -g_cr (center-right link)
    assert abs(A[1, 2] - (-g_cr_expected)) < 1e-10, (
        f"A[1,2]={A[1, 2]:.6e}, expected {-g_cr_expected:.6e}"
    )
    assert abs(A[2, 1] - (-g_cr_expected)) < 1e-10, (
        f"A[2,1]={A[2, 1]:.6e}, expected {-g_cr_expected:.6e}"
    )


# ---------------------------------------------------------------------------
# Test 3: Two-zone temperature contrast (aluminum vs FR4)
# ---------------------------------------------------------------------------

def test_two_zone_temperature_contrast() -> None:
    """Aluminum cells (high k) reach lower T than FR4 cells (low k) under uniform power."""
    width  = 0.10  # m  (10 cells wide)
    height = 0.01  # m  (1 cell tall)
    thickness = 0.002  # m
    h_top = 10.0   # W/m²K
    amb = 25.0     # °C

    nx = 10
    ny = 1

    dx = width / nx   # = 0.01 m
    half_width = width / 2  # = 0.05 m

    # Aluminum: left half
    zone_al  = MaterialZone(material="Al",  x=half_width / 2,          y=height / 2, width=half_width, height=height)
    # FR4: right half
    zone_fr4 = MaterialZone(material="FR4", x=half_width + half_width / 2, y=height / 2, width=half_width, height=height)

    mat_al  = Material("Al",  k_in_plane=200.0, k_through=200.0, density=2700.0, specific_heat=900.0)
    mat_fr4 = Material("FR4", k_in_plane=0.3,   k_through=0.3,   density=1850.0, specific_heat=1100.0)

    project = DisplayProject(
        name="TwoZoneContrast",
        width=width,
        height=height,
        materials={"Al": mat_al, "FR4": mat_fr4},
        layers=[Layer(
            name="L",
            material="Al",
            thickness=thickness,
            zones=[zone_al, zone_fr4],
        )],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=1.0, shape="full")],
        boundaries=_top_convection_only(h=h_top, amb=amb),
        mesh=MeshConfig(nx=nx, ny=ny),
    )

    result = SteadyStateSolver().solve(project)
    temps = result.temperatures_c[0, 0, :]  # shape (nx,), iy=0 layer=0

    T_al_avg  = float(np.mean(temps[:5]))   # left 5 cells = aluminum
    T_fr4_avg = float(np.mean(temps[5:]))   # right 5 cells = FR4

    assert T_al_avg < T_fr4_avg, (
        f"Expected aluminum cells (k=200) cooler than FR4 (k=0.3), "
        f"got Al_avg={T_al_avg:.3f} C, FR4_avg={T_fr4_avg:.3f} C"
    )


# ---------------------------------------------------------------------------
# Test 4: Uncovered cells default to Air Gap
# ---------------------------------------------------------------------------

def test_uncovered_cells_default_to_air() -> None:
    """Cells not covered by any zone get Air Gap material (density=1.2, cp=1005)."""
    width  = 0.04
    height = 0.04
    thickness = 0.001
    nx, ny = 4, 4
    n_per_layer = nx * ny

    dx = width / nx    # = 0.01 m
    dy = height / ny   # = 0.01 m

    # One small zone covering only the center 4 cells (2x2 at center of 4x4 grid)
    # Center cells are at indices (ix=1, iy=1), (ix=2, iy=1), (ix=1, iy=2), (ix=2, iy=2)
    # Their centers are at x=[0.015, 0.025], y=[0.015, 0.025]
    # Zone covers 2x2 block: center at (0.02, 0.02), width=0.02, height=0.02
    zone_center = MaterialZone(
        material="Steel",
        x=0.02,
        y=0.02,
        width=2 * dx,
        height=2 * dy,
    )
    mat_steel = Material("Steel", k_in_plane=50.0, k_through=50.0, density=7850.0, specific_heat=500.0)

    project = DisplayProject(
        name="UncoveredCellsTest",
        width=width,
        height=height,
        materials={"Steel": mat_steel},
        layers=[Layer(
            name="L",
            material="Steel",
            thickness=thickness,
            zones=[zone_center],
        )],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=0.001, shape="full")],
        boundaries=_top_convection_only(h=10.0),
        mesh=MeshConfig(nx=nx, ny=ny),
    )

    network = build_thermal_network(project)
    c_vec = network.c_vector  # shape (n_per_layer,)

    # Air Gap: density=1.2, cp=1005, -> density*cp = 1206
    air_density_cp = 1.2 * 1005.0
    air_c_per_node = air_density_cp * thickness * (dx * dy)

    # Steel: density=7850, cp=500 -> density*cp = 3925000
    steel_density_cp = 7850.0 * 500.0
    steel_c_per_node = steel_density_cp * thickness * (dx * dy)

    # Corner cell (ix=0, iy=0) should be Air Gap
    corner_node = 0  # iy=0, ix=0 -> flat=0
    assert abs(c_vec[corner_node] - air_c_per_node) < 1e-15, (
        f"Corner cell C={c_vec[corner_node]:.6e}, expected air gap C={air_c_per_node:.6e}"
    )

    # Center cell (ix=1, iy=1) should be Steel
    center_node = 1 * nx + 1  # iy=1, ix=1 -> flat=5
    assert abs(c_vec[center_node] - steel_c_per_node) < 1e-15, (
        f"Center cell C={c_vec[center_node]:.6e}, expected steel C={steel_c_per_node:.6e}"
    )


# ---------------------------------------------------------------------------
# Test 5: Zone clipping at layer bounds — no error, no warning for partial overlap
# ---------------------------------------------------------------------------

def test_zone_clipping_at_layer_bounds() -> None:
    """A zone that partially extends beyond grid bounds is silently clipped."""
    width  = 0.10
    height = 0.10
    thickness = 0.001

    mat_al = Material("Al", k_in_plane=200.0, k_through=200.0, density=2700.0, specific_heat=900.0)

    # Zone centered at (0, 0) with width=10 m, height=10 m — extends far beyond panel
    # but DOES overlap the panel (partial overlap), so no warning expected
    big_zone = MaterialZone(material="Al", x=0.0, y=0.0, width=10.0, height=10.0)

    project = DisplayProject(
        name="ClippingTest",
        width=width,
        height=height,
        materials={"Al": mat_al},
        layers=[Layer(
            name="L",
            material="Al",
            thickness=thickness,
            zones=[big_zone],
        )],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=0.001, shape="full")],
        boundaries=_top_convection_only(h=10.0),
        mesh=MeshConfig(nx=5, ny=5),
    )

    # Should succeed without error; no warning for partially-overlapping zone
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        network = build_thermal_network(project)  # must not raise

    # All cells should have aluminum's thermal capacity
    dx = width / 5
    dy = height / 5
    al_c_per_node = 2700.0 * 900.0 * thickness * dx * dy
    np.testing.assert_allclose(
        network.c_vector,
        al_c_per_node,
        rtol=1e-12,
        err_msg="All cells should have aluminum thermal capacity when zone covers entire panel",
    )
