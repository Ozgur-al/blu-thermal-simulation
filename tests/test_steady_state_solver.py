import math

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver


def _base_material(name: str, k_ip: float, k_tp: float) -> Material:
    return Material(
        name=name,
        k_in_plane=k_ip,
        k_through=k_tp,
        density=2000.0,
        specific_heat=900.0,
        emissivity=0.9,
    )


def test_one_cell_matches_analytic_parallel_resistance_solution() -> None:
    area = 0.1 * 0.1
    thickness = 0.002
    k = 2.0
    q_w = 2.0
    ambient_c = 25.0
    h_top = 10.0
    h_bottom = 5.0

    project = DisplayProject(
        name="Analytic check",
        width=0.1,
        height=0.1,
        materials={"Mat": _base_material("Mat", k_ip=k, k_tp=k)},
        layers=[Layer(name="Core", material="Mat", thickness=thickness)],
        heat_sources=[HeatSource(name="Q", layer="Core", power_w=q_w, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=ambient_c, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=ambient_c, convection_h=h_bottom, include_radiation=False),
            side=SurfaceBoundary(ambient_c=ambient_c, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )

    result = SteadyStateSolver().solve(project)
    simulated = float(result.temperatures_c[0, 0, 0])

    r_top = thickness / (2.0 * k * area) + 1.0 / (h_top * area)
    r_bottom = thickness / (2.0 * k * area) + 1.0 / (h_bottom * area)
    g_total = 1.0 / r_top + 1.0 / r_bottom
    expected = ambient_c + q_w / g_total

    assert math.isclose(simulated, expected, rel_tol=1e-9, abs_tol=1e-9)


def test_localized_hotspot_raises_center_temperature() -> None:
    project = DisplayProject(
        name="Hotspot",
        width=0.2,
        height=0.2,
        materials={"Mat": _base_material("Mat", k_ip=5.0, k_tp=1.5)},
        layers=[Layer(name="PCB", material="Mat", thickness=0.001)],
        heat_sources=[
            HeatSource(
                name="IC",
                layer="PCB",
                power_w=8.0,
                shape="circle",
                x=0.1,
                y=0.1,
                radius=0.02,
            )
        ],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=15.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=3.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=3.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=21, ny=21),
    )

    result = SteadyStateSolver().solve(project)
    center = float(result.temperatures_c[0, 10, 10])
    corner = float(result.temperatures_c[0, 0, 0])
    assert center > corner


def test_higher_interface_resistance_increases_temperature() -> None:
    materials = {
        "FR4": _base_material("FR4", k_ip=0.35, k_tp=0.3),
        "Al": _base_material("Al", k_ip=200.0, k_tp=200.0),
    }
    common_kwargs = dict(
        name="Interface effect",
        width=0.1,
        height=0.1,
        materials=materials,
        heat_sources=[HeatSource(name="Load", layer="Board", power_w=3.0, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=35.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=2.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=2.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=6, ny=6),
    )

    low_res = DisplayProject(
        layers=[
            Layer(name="Board", material="FR4", thickness=0.0016, interface_resistance_to_next=0.0),
            Layer(name="Chassis", material="Al", thickness=0.001),
        ],
        **common_kwargs,
    )
    high_res = DisplayProject(
        layers=[
            Layer(name="Board", material="FR4", thickness=0.0016, interface_resistance_to_next=2e-3),
            Layer(name="Chassis", material="Al", thickness=0.001),
        ],
        **common_kwargs,
    )

    low_result = SteadyStateSolver().solve(low_res)
    high_result = SteadyStateSolver().solve(high_res)
    assert float(high_result.temperatures_c.max()) > float(low_result.temperatures_c.max())
