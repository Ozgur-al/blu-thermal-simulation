"""Integration tests: DLED and ELED templates through the full solver pipeline.

Tests the complete chain: template -> DisplayProject -> solver -> results.
Uses the same style as tests/test_led_array.py (direct construction, pytest.approx).

Mesh sizing note: The solver raises ValueError if any LED footprint falls between
grid cell centers (no cell overlap). Template footprints are 3 mm and 2 mm — small
compared to typical test mesh cells. Tests use a dense-enough mesh (nx=100, ny=66)
so that 3-mm footprints span at least one cell on a 300x200 mm panel.
Cell size: dx = 300/100 = 3.0 mm, dy = 200/66 ≈ 3.0 mm.
"""

from __future__ import annotations

import json

import pytest

from thermal_sim.models.project import DisplayProject, MeshConfig
from thermal_sim.models.stack_templates import dled_template, eled_template
from thermal_sim.solvers.steady_state import SteadyStateSolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PANEL_W = 0.3   # 300 mm
_PANEL_H = 0.2   # 200 mm

# Dense enough mesh so 3-mm LED footprints overlap at least one cell.
# dx = 300/100 = 3.0 mm, dy = 200/66 ≈ 3.03 mm.
_MESH = MeshConfig(nx=100, ny=66)


def _dled_project(**overrides) -> DisplayProject:
    """Build a minimal DLED DisplayProject from the template."""
    tmpl = dled_template(_PANEL_W, _PANEL_H)
    kwargs = dict(
        name="DLED Test",
        width=_PANEL_W,
        height=_PANEL_H,
        layers=tmpl["layers"],
        materials=tmpl["materials"],
        led_arrays=tmpl["led_arrays"],
        boundaries=tmpl["boundaries"],
        mesh=_MESH,
    )
    kwargs.update(overrides)
    return DisplayProject(**kwargs)


def _eled_project(edge_config: str = "bottom", **overrides) -> DisplayProject:
    """Build a minimal ELED DisplayProject from the template."""
    tmpl = eled_template(_PANEL_W, _PANEL_H, edge_config=edge_config)
    kwargs = dict(
        name="ELED Test",
        width=_PANEL_W,
        height=_PANEL_H,
        layers=tmpl["layers"],
        materials=tmpl["materials"],
        led_arrays=tmpl["led_arrays"],
        boundaries=tmpl["boundaries"],
        mesh=_MESH,
    )
    kwargs.update(overrides)
    return DisplayProject(**kwargs)


# ---------------------------------------------------------------------------
# DLED pipeline tests
# ---------------------------------------------------------------------------

def test_dled_template_project_solves_successfully() -> None:
    """DLED template -> DisplayProject -> solver produces T_max > ambient."""
    project = _dled_project()
    result = SteadyStateSolver().solve(project)
    assert float(result.temperatures_c.max()) > project.initial_temperature_c


def test_dled_template_expanded_heat_sources_count() -> None:
    """DLED template produces 8*6=48 heat sources after expansion."""
    project = _dled_project()
    sources = project.expanded_heat_sources()
    # Default DLED template: 8x6 grid
    assert len(sources) == 8 * 6


# ---------------------------------------------------------------------------
# ELED pipeline tests
# ---------------------------------------------------------------------------

def test_eled_template_project_solves_successfully() -> None:
    """ELED template -> DisplayProject -> solver produces T_max > ambient."""
    project = _eled_project()
    result = SteadyStateSolver().solve(project)
    assert float(result.temperatures_c.max()) > project.initial_temperature_c


def test_eled_template_expanded_heat_sources_count_bottom() -> None:
    """ELED template with edge_config='bottom' produces count_x=20 heat sources."""
    project = _eled_project(edge_config="bottom")
    sources = project.expanded_heat_sources()
    # Default ELED template: 20 LEDs on bottom edge
    assert len(sources) == 20


# ---------------------------------------------------------------------------
# Zone dimming test — asymmetric thermal pattern
# ---------------------------------------------------------------------------

def test_dled_zone_dimming_produces_asymmetric_thermal_pattern() -> None:
    """DLED with 2x2 zones where top-right zone has high power is hotter near that zone."""
    from thermal_sim.models.heat_source import LEDArray

    # Build 2x2 zone configuration — high power in top-right quadrant
    # zone layout (zone_yi=0 is bottom, zone_xi=1 is right):
    #   zone_idx 0 = bottom-left  = low power
    #   zone_idx 1 = bottom-right = low power
    #   zone_idx 2 = top-left     = low power
    #   zone_idx 3 = top-right    = HIGH power
    zone_powers = [0.1, 0.1, 0.1, 1.0]  # W per LED; top-right zone much hotter

    tmpl = dled_template(_PANEL_W, _PANEL_H)
    # Override the LED array with 2x2 zones on the DLED LED Board layer
    led_array = LEDArray(
        name="DLED Zone Array",
        layer="LED Board",
        center_x=_PANEL_W / 2.0,
        center_y=_PANEL_H / 2.0,
        count_x=8,
        count_y=6,
        pitch_x=_PANEL_W / 9,
        pitch_y=_PANEL_H / 7,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=_PANEL_W,
        panel_height=_PANEL_H,
        offset_left=_PANEL_W * 0.10,
        offset_right=_PANEL_W * 0.10,
        offset_top=_PANEL_H * 0.10,
        offset_bottom=_PANEL_H * 0.10,
        zone_count_x=2,
        zone_count_y=2,
        zone_powers=zone_powers,
    )

    project = DisplayProject(
        name="DLED Zone Test",
        width=_PANEL_W,
        height=_PANEL_H,
        layers=tmpl["layers"],
        materials=tmpl["materials"],
        led_arrays=[led_array],
        boundaries=tmpl["boundaries"],
        mesh=_MESH,
    )

    result = SteadyStateSolver().solve(project)
    temps = result.temperatures_c

    # Find the LED Board layer index
    led_board_idx = project.layer_index("LED Board")

    # High-power zone: top-right quadrant
    # In the mesh, x increases left-to-right, y increases bottom-to-top
    # High-power zone: ix near right (x > panel_W/2), iy near top (y > panel_H/2)
    nx, ny = _MESH.nx, _MESH.ny
    # Sample from the high-power quadrant (top-right)
    high_zone_temp = float(
        temps[led_board_idx, ny // 2 :, nx // 2 :].max()
    )
    # Sample from the low-power quadrant (bottom-left)
    low_zone_temp = float(
        temps[led_board_idx, : ny // 2, : nx // 2].max()
    )

    assert high_zone_temp > low_zone_temp, (
        f"Expected top-right zone (T={high_zone_temp:.2f}C) hotter than "
        f"bottom-left zone (T={low_zone_temp:.2f}C)"
    )


# ---------------------------------------------------------------------------
# ELED left_right edge config test
# ---------------------------------------------------------------------------

def test_eled_left_right_produces_leds_on_both_edges() -> None:
    """ELED with edge_config='left_right' places LEDs on both left and right edges."""
    project = _eled_project(edge_config="left_right")
    sources = project.expanded_heat_sources()

    # Both "left" and "right" should appear in source names
    left_leds = [s for s in sources if "left" in s.name]
    right_leds = [s for s in sources if "right" in s.name]

    assert len(left_leds) > 0, "Expected LEDs on left edge"
    assert len(right_leds) > 0, "Expected LEDs on right edge"
    assert len(left_leds) == len(right_leds), "Left and right strips should have equal LED count"

    # Solve and verify T_max > ambient
    result = SteadyStateSolver().solve(project)
    assert float(result.temperatures_c.max()) > project.initial_temperature_c


def test_eled_left_right_led_positions_near_edges() -> None:
    """ELED left_right LEDs are positioned near x=0 and x=panel_width."""
    project = _eled_project(edge_config="left_right")
    sources = project.expanded_heat_sources()

    left_leds = [s for s in sources if "left" in s.name]
    right_leds = [s for s in sources if "right" in s.name]

    # Left LEDs should have small x values
    for src in left_leds:
        assert src.x < _PANEL_W * 0.1, f"Left LED at x={src.x:.4f} is too far from left edge"

    # Right LEDs should have x values near panel_width
    for src in right_leds:
        assert src.x > _PANEL_W * 0.9, f"Right LED at x={src.x:.4f} is too far from right edge"


# ---------------------------------------------------------------------------
# JSON round-trip tests
# ---------------------------------------------------------------------------

def test_dled_project_json_roundtrip_preserves_solve_result() -> None:
    """DLED project serializes and deserializes without altering T_max."""
    project = _dled_project()
    result_orig = SteadyStateSolver().solve(project)
    t_max_orig = float(result_orig.temperatures_c.max())

    # Round-trip via JSON string (to_dict -> json.dumps -> json.loads -> from_dict)
    data = project.to_dict()
    json_str = json.dumps(data)
    project2 = DisplayProject.from_dict(json.loads(json_str))

    result2 = SteadyStateSolver().solve(project2)
    t_max2 = float(result2.temperatures_c.max())

    assert t_max2 == pytest.approx(t_max_orig, rel=1e-6), (
        f"Round-trip changed T_max: orig={t_max_orig:.4f}C, after={t_max2:.4f}C"
    )


def test_eled_project_json_roundtrip_preserves_solve_result() -> None:
    """ELED project serializes and deserializes without altering T_max."""
    project = _eled_project(edge_config="left_right")
    result_orig = SteadyStateSolver().solve(project)
    t_max_orig = float(result_orig.temperatures_c.max())

    data = project.to_dict()
    json_str = json.dumps(data)
    project2 = DisplayProject.from_dict(json.loads(json_str))

    result2 = SteadyStateSolver().solve(project2)
    t_max2 = float(result2.temperatures_c.max())

    assert t_max2 == pytest.approx(t_max_orig, rel=1e-6), (
        f"Round-trip changed T_max: orig={t_max_orig:.4f}C, after={t_max2:.4f}C"
    )
