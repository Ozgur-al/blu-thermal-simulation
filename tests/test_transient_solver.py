import math

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver


def _single_node_project(power_w: float, initial_c: float, total_time_s: float) -> DisplayProject:
    material = Material(
        name="NodeMat",
        k_in_plane=2.0,
        k_through=2.0,
        density=800.0,
        specific_heat=800.0,
        emissivity=0.9,
    )
    return DisplayProject(
        name="Transient single-node",
        width=0.1,
        height=0.1,
        materials={"NodeMat": material},
        layers=[Layer(name="Core", material="NodeMat", thickness=0.0002)],
        heat_sources=[HeatSource(name="Load", layer="Core", power_w=power_w, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=100.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=100.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(
            time_step_s=0.01,
            total_time_s=total_time_s,
            output_interval_s=0.01,
            method="implicit_euler",
        ),
        initial_temperature_c=initial_c,
    )


def test_transient_rc_cooling_matches_first_order_response() -> None:
    project = _single_node_project(power_w=0.0, initial_c=80.0, total_time_s=2.0)
    result = TransientSolver().solve(project)
    simulated_final = float(result.final_temperatures_c[0, 0, 0])

    area = project.width * project.height
    material = project.materials["NodeMat"]
    thickness = project.layers[0].thickness
    g_each = 1.0 / (thickness / (2.0 * material.k_through * area) + 1.0 / (100.0 * area))
    g_total = 2.0 * g_each
    c_node = material.density * material.specific_heat * thickness * area
    expected_final = 25.0 + (80.0 - 25.0) * math.exp(-(g_total / c_node) * project.transient.total_time_s)

    assert math.isclose(simulated_final, expected_final, rel_tol=0.0, abs_tol=0.25)


def test_transient_converges_to_steady_state_solution() -> None:
    project = _single_node_project(power_w=4.0, initial_c=25.0, total_time_s=8.0)
    transient = TransientSolver().solve(project)
    steady = SteadyStateSolver().solve(project)

    transient_final = float(transient.final_temperatures_c[0, 0, 0])
    steady_ref = float(steady.temperatures_c[0, 0, 0])
    assert math.isclose(transient_final, steady_ref, rel_tol=0.0, abs_tol=0.2)
