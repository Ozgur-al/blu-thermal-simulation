import pytest

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import LEDArray
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver


def test_led_array_expands_to_expected_sources() -> None:
    array = LEDArray(
        name="BL",
        layer="PCB",
        center_x=0.05,
        center_y=0.04,
        count_x=3,
        count_y=2,
        pitch_x=0.01,
        pitch_y=0.02,
        power_per_led_w=0.2,
        footprint_shape="rectangle",
        led_width=0.004,
        led_height=0.003,
    )
    expanded = array.expand()
    assert len(expanded) == 6
    assert expanded[0].name == "BL_r1_c1"
    assert expanded[-1].name == "BL_r2_c3"
    assert sum(item.power_w for item in expanded) == pytest.approx(1.2)


def test_led_array_contributes_heat_in_solver() -> None:
    material = Material(
        name="FR4",
        k_in_plane=0.35,
        k_through=0.3,
        density=1900.0,
        specific_heat=1100.0,
        emissivity=0.9,
    )
    project = DisplayProject(
        name="LED array heating",
        width=0.12,
        height=0.08,
        materials={"FR4": material},
        layers=[Layer(name="PCB", material="FR4", thickness=0.0016)],
        led_arrays=[
            LEDArray(
                name="LEDs",
                layer="PCB",
                center_x=0.06,
                center_y=0.04,
                count_x=2,
                count_y=2,
                pitch_x=0.02,
                pitch_y=0.02,
                power_per_led_w=0.8,
                footprint_shape="rectangle",
                led_width=0.01,
                led_height=0.01,
            )
        ],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=2.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=18, ny=12),
        initial_temperature_c=25.0,
    )
    result = SteadyStateSolver().solve(project)
    assert float(result.temperatures_c.max()) > 25.0
