import pytest

from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, TransientConfig


def test_material_validation_rejects_nonpositive_conductivity() -> None:
    with pytest.raises(ValueError):
        Material(
            name="Bad",
            k_in_plane=0.0,
            k_through=1.0,
            density=1000.0,
            specific_heat=1000.0,
            emissivity=0.9,
        )


def test_project_validation_detects_missing_material_reference() -> None:
    materials = {
        "Glass": Material(
            name="Glass",
            k_in_plane=1.0,
            k_through=1.0,
            density=2500.0,
            specific_heat=800.0,
            emissivity=0.9,
        )
    }
    with pytest.raises(ValueError):
        DisplayProject(
            name="Invalid",
            width=0.1,
            height=0.1,
            layers=[Layer(name="Layer1", material="Missing", thickness=1e-3)],
            materials=materials,
            heat_sources=[HeatSource(name="HS", layer="Layer1", power_w=1.0, shape="full")],
        )


def test_project_roundtrip_includes_transient_settings() -> None:
    mat = Material(
        name="Mat",
        k_in_plane=1.0,
        k_through=1.0,
        density=1000.0,
        specific_heat=1000.0,
        emissivity=0.9,
    )
    project = DisplayProject(
        name="Roundtrip",
        width=0.2,
        height=0.1,
        layers=[Layer(name="L1", material="Mat", thickness=0.001)],
        materials={"Mat": mat},
        transient=TransientConfig(time_step_s=0.5, total_time_s=10.0, output_interval_s=1.0),
    )
    restored = DisplayProject.from_dict(project.to_dict())
    assert restored.transient.time_step_s == pytest.approx(0.5)
    assert restored.transient.total_time_s == pytest.approx(10.0)


def test_project_roundtrip_includes_led_arrays() -> None:
    from thermal_sim.models.heat_source import LEDArray

    mat = Material(
        name="Mat",
        k_in_plane=1.0,
        k_through=1.0,
        density=1000.0,
        specific_heat=1000.0,
        emissivity=0.9,
    )
    project = DisplayProject(
        name="LED roundtrip",
        width=0.2,
        height=0.1,
        layers=[Layer(name="PCB", material="Mat", thickness=0.001)],
        materials={"Mat": mat},
        led_arrays=[
            LEDArray(
                name="BL",
                layer="PCB",
                center_x=0.1,
                center_y=0.05,
                count_x=2,
                count_y=2,
                pitch_x=0.02,
                pitch_y=0.02,
                power_per_led_w=0.2,
                footprint_shape="rectangle",
                led_width=0.005,
                led_height=0.005,
            )
        ],
    )
    restored = DisplayProject.from_dict(project.to_dict())
    assert len(restored.led_arrays) == 1
    assert restored.led_arrays[0].name == "BL"
