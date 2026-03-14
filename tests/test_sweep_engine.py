"""Tests for parametric sweep engine: SweepConfig, SweepResult, _apply_parameter, SweepEngine."""

from __future__ import annotations

import copy
import pytest

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_project() -> DisplayProject:
    """Minimal 1-layer, 1x1 mesh project for fast tests."""
    mat = Material(
        name="Copper",
        k_in_plane=380.0,
        k_through=380.0,
        density=8960.0,
        specific_heat=385.0,
        emissivity=0.1,
    )
    return DisplayProject(
        name="Sweep Test Project",
        width=0.1,
        height=0.1,
        materials={"Copper": mat},
        layers=[Layer(name="Base", material="Copper", thickness=0.002)],
        heat_sources=[
            HeatSource(name="Heater", layer="Base", power_w=2.0, shape="full"),
        ],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=10.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(time_step_s=0.5, total_time_s=2.0, output_interval_s=1.0),
    )


# ---------------------------------------------------------------------------
# SweepConfig tests (Task 1)
# ---------------------------------------------------------------------------

class TestSweepConfig:
    def test_from_dict_round_trip(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig

        data = {"parameter": "layers[0].thickness", "values": [0.001, 0.002], "mode": "steady"}
        config = SweepConfig.from_dict(data)
        assert config.parameter == "layers[0].thickness"
        assert config.values == [0.001, 0.002]
        assert config.mode == "steady"
        rt = config.to_dict()
        assert rt["parameter"] == "layers[0].thickness"
        assert rt["values"] == [0.001, 0.002]
        assert rt["mode"] == "steady"

    def test_from_dict_missing_parameter_raises_value_error(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig

        with pytest.raises(ValueError, match="parameter"):
            SweepConfig.from_dict({"values": [0.001, 0.002], "mode": "steady"})

    def test_from_dict_missing_values_raises_value_error(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig

        with pytest.raises(ValueError, match="values"):
            SweepConfig.from_dict({"parameter": "layers[0].thickness", "mode": "steady"})

    def test_from_dict_defaults_mode_to_steady(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig

        config = SweepConfig.from_dict({"parameter": "layers[0].thickness", "values": [0.001]})
        assert config.mode == "steady"


# ---------------------------------------------------------------------------
# _apply_parameter tests (Task 1)
# ---------------------------------------------------------------------------

class TestApplyParameter:
    def test_apply_layer_thickness(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        _apply_parameter(project, "layers[0].thickness", 0.005)
        assert project.layers[0].thickness == pytest.approx(0.005)

    def test_apply_heat_source_power(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        _apply_parameter(project, "heat_sources[0].power_w", 3.0)
        assert project.heat_sources[0].power_w == pytest.approx(3.0)

    def test_apply_boundary_top_convection_h(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        _apply_parameter(project, "boundaries.top.convection_h", 20.0)
        assert project.boundaries.top.convection_h == pytest.approx(20.0)

    def test_apply_boundary_bottom_convection_h(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        _apply_parameter(project, "boundaries.bottom.convection_h", 15.0)
        assert project.boundaries.bottom.convection_h == pytest.approx(15.0)

    def test_apply_material_k_in_plane_uses_replace(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter
        import dataclasses

        project = _make_project()
        old_mat = project.materials["Copper"]
        _apply_parameter(project, "materials.Copper.k_in_plane", 350.0)
        new_mat = project.materials["Copper"]
        # Frozen Material must be replaced, not mutated in place
        assert new_mat is not old_mat
        assert new_mat.k_in_plane == pytest.approx(350.0)
        # Other fields preserved
        assert new_mat.k_through == pytest.approx(old_mat.k_through)
        assert new_mat.density == pytest.approx(old_mat.density)

    def test_apply_material_k_through(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        _apply_parameter(project, "materials.Copper.k_through", 200.0)
        assert project.materials["Copper"].k_through == pytest.approx(200.0)

    def test_apply_invalid_path_raises_value_error(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        with pytest.raises(ValueError):
            _apply_parameter(project, "nonexistent.field", 1.0)

    def test_apply_invalid_material_name_raises_value_error(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        with pytest.raises(ValueError, match="material"):
            _apply_parameter(project, "materials.Aluminum.k_in_plane", 150.0)

    def test_apply_layer_index_out_of_range_raises_value_error(self) -> None:
        from thermal_sim.core.sweep_engine import _apply_parameter

        project = _make_project()
        with pytest.raises(ValueError):
            _apply_parameter(project, "layers[99].thickness", 0.001)


# ---------------------------------------------------------------------------
# SweepRunResult and SweepResult dataclass tests (Task 1)
# ---------------------------------------------------------------------------

class TestSweepResultDataclasses:
    def test_sweep_run_result_stores_data(self) -> None:
        from thermal_sim.models.sweep_result import SweepRunResult

        stats = [{"layer": "Base", "t_max_c": 50.0, "t_avg_c": 45.0, "t_min_c": 40.0, "delta_t_c": 10.0}]
        run = SweepRunResult(parameter_value=0.001, layer_stats=stats)
        assert run.parameter_value == pytest.approx(0.001)
        assert run.layer_stats[0]["t_max_c"] == pytest.approx(50.0)

    def test_sweep_result_stores_config_and_runs(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig
        from thermal_sim.models.sweep_result import SweepRunResult, SweepResult

        config = SweepConfig(parameter="layers[0].thickness", values=[0.001, 0.002], mode="steady")
        stats = [{"layer": "Base", "t_max_c": 50.0, "t_avg_c": 45.0, "t_min_c": 40.0, "delta_t_c": 10.0}]
        runs = [SweepRunResult(parameter_value=v, layer_stats=stats) for v in [0.001, 0.002]]
        result = SweepResult(config=config, runs=runs)
        assert len(result.runs) == 2
        assert result.runs[0].parameter_value == pytest.approx(0.001)
        assert result.config.parameter == "layers[0].thickness"

    def test_sweep_run_result_round_trip(self) -> None:
        from thermal_sim.models.sweep_result import SweepRunResult

        stats = [{"layer": "Base", "t_max_c": 50.0, "t_avg_c": 45.0, "t_min_c": 40.0, "delta_t_c": 10.0}]
        run = SweepRunResult(parameter_value=0.003, layer_stats=stats)
        d = run.to_dict()
        rt = SweepRunResult.from_dict(d)
        assert rt.parameter_value == pytest.approx(0.003)
        assert rt.layer_stats[0]["layer"] == "Base"

    def test_sweep_result_round_trip(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig
        from thermal_sim.models.sweep_result import SweepRunResult, SweepResult

        config = SweepConfig(parameter="heat_sources[0].power_w", values=[1.0, 2.0], mode="steady")
        stats = [{"layer": "Base", "t_max_c": 60.0, "t_avg_c": 55.0, "t_min_c": 50.0, "delta_t_c": 10.0}]
        runs = [SweepRunResult(parameter_value=v, layer_stats=stats) for v in [1.0, 2.0]]
        result = SweepResult(config=config, runs=runs)
        d = result.to_dict()
        rt = SweepResult.from_dict(d)
        assert len(rt.runs) == 2
        assert rt.config.parameter == "heat_sources[0].power_w"


# ---------------------------------------------------------------------------
# SweepEngine tests (Task 2)
# ---------------------------------------------------------------------------

class TestSweepEngine:
    def test_steady_sweep_produces_correct_run_count(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        config = SweepConfig(
            parameter="layers[0].thickness",
            values=[0.001, 0.002, 0.003],
            mode="steady",
        )
        result = SweepEngine().run(project, config)
        assert len(result.runs) == 3

    def test_each_run_has_correct_parameter_value(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        values = [0.001, 0.002, 0.003]
        config = SweepConfig(parameter="layers[0].thickness", values=values, mode="steady")
        result = SweepEngine().run(project, config)
        for run, expected_val in zip(result.runs, values):
            assert run.parameter_value == pytest.approx(expected_val)

    def test_each_run_has_non_empty_layer_stats(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        config = SweepConfig(parameter="layers[0].thickness", values=[0.001, 0.002], mode="steady")
        result = SweepEngine().run(project, config)
        for run in result.runs:
            assert len(run.layer_stats) > 0
            assert "layer" in run.layer_stats[0]
            assert "t_max_c" in run.layer_stats[0]
            assert "t_avg_c" in run.layer_stats[0]

    def test_progress_callback_called_for_each_run(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        config = SweepConfig(parameter="layers[0].thickness", values=[0.001, 0.002, 0.003], mode="steady")
        calls: list[tuple[int, int]] = []
        SweepEngine().run(project, config, on_progress=lambda n, m: calls.append((n, m)))
        assert len(calls) == 3
        assert calls[0] == (1, 3)
        assert calls[1] == (2, 3)
        assert calls[2] == (3, 3)

    def test_transient_sweep_produces_valid_results(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        config = SweepConfig(parameter="layers[0].thickness", values=[0.001, 0.003], mode="transient")
        result = SweepEngine().run(project, config)
        assert len(result.runs) == 2
        for run in result.runs:
            assert run.layer_stats
            assert run.layer_stats[0]["t_max_c"] > 0

    def test_sweep_does_not_modify_base_project(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        original_thickness = project.layers[0].thickness
        config = SweepConfig(parameter="layers[0].thickness", values=[0.010, 0.020], mode="steady")
        SweepEngine().run(project, config)
        # Base project should be unmodified
        assert project.layers[0].thickness == pytest.approx(original_thickness)

    def test_thicker_layer_gives_higher_t_max(self) -> None:
        """Thicker layer = higher thermal resistance = higher temperature with same heat source."""
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        # Use low-conductivity material to make resistance difference visible
        low_k_mat = Material(
            name="Copper",
            k_in_plane=1.0,
            k_through=1.0,
            density=8960.0,
            specific_heat=385.0,
            emissivity=0.1,
        )
        project.materials["Copper"] = low_k_mat
        config = SweepConfig(
            parameter="layers[0].thickness",
            values=[0.001, 0.005, 0.010],
            mode="steady",
        )
        result = SweepEngine().run(project, config)
        t_max_values = [run.layer_stats[0]["t_max_c"] for run in result.runs]
        # Temperatures should increase with thickness (higher through-thickness resistance)
        assert t_max_values[0] < t_max_values[1] < t_max_values[2]

    def test_result_config_matches_input_config(self) -> None:
        from thermal_sim.core.sweep_engine import SweepConfig, SweepEngine

        project = _make_project()
        config = SweepConfig(parameter="layers[0].thickness", values=[0.001, 0.002], mode="steady")
        result = SweepEngine().run(project, config)
        assert result.config is config


# ---------------------------------------------------------------------------
# CLI parser test (Task 2)
# ---------------------------------------------------------------------------

class TestCliSweepArgument:
    def test_cli_parser_accepts_sweep_argument(self) -> None:
        from thermal_sim.app.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--sweep", "sweep.json"])
        from pathlib import Path
        assert args.sweep == Path("sweep.json")

    def test_cli_parser_sweep_defaults_to_none(self) -> None:
        from thermal_sim.app.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        assert args.sweep is None
