import math

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver


def test_1d_two_layer_resistance_chain_matches_hand_calculation() -> None:
    area = 0.12 * 0.08
    amb = 23.0
    q = 1.7
    mat1 = Material("L1", 0.8, 0.8, 2000.0, 900.0, 0.9)
    mat2 = Material("L2", 10.0, 10.0, 2000.0, 900.0, 0.9)
    t1 = 0.001
    t2 = 0.002
    r_int = 4e-4
    h_top = 12.0
    h_bottom = 4.0

    project = DisplayProject(
        name="1D chain",
        width=0.12,
        height=0.08,
        materials={"L1": mat1, "L2": mat2},
        layers=[
            Layer(name="Bottom", material="L1", thickness=t1, interface_resistance_to_next=r_int),
            Layer(name="Top", material="L2", thickness=t2),
        ],
        heat_sources=[HeatSource(name="Power", layer="Bottom", power_w=q, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=amb, convection_h=h_bottom, include_radiation=False),
            side=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )
    result = SteadyStateSolver().solve(project)

    # 2-node thermal network solved analytically by nodal equation.
    g_bottom = 1.0 / (t1 / (2.0 * mat1.k_through * area) + 1.0 / (h_bottom * area))
    g_top = 1.0 / (t2 / (2.0 * mat2.k_through * area) + 1.0 / (h_top * area))
    g_between = 1.0 / (
        t1 / (2.0 * mat1.k_through * area)
        + r_int / area
        + t2 / (2.0 * mat2.k_through * area)
    )

    # [g_bottom+g_between, -g_between] [T0] = [q + g_bottom*amb]
    # [-g_between, g_top+g_between]   [T1]   [g_top*amb]
    a = g_bottom + g_between
    b = -g_between
    c = -g_between
    d = g_top + g_between
    rhs0 = q + g_bottom * amb
    rhs1 = g_top * amb
    det = a * d - b * c
    expected_t0 = (rhs0 * d - b * rhs1) / det
    expected_t1 = (a * rhs1 - rhs0 * c) / det

    assert math.isclose(float(result.temperatures_c[0, 0, 0]), expected_t0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(float(result.temperatures_c[1, 0, 0]), expected_t1, rel_tol=1e-9, abs_tol=1e-9)
