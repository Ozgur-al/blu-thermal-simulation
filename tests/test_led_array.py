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


# --------------------------------------------------------------------------
# New tests for mode="custom" (backward compat)
# --------------------------------------------------------------------------

def test_led_array_custom_mode_identical_to_no_mode() -> None:
    """LEDArray with mode='custom' (default) produces identical expand() output."""
    common = dict(
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
    # default mode (no kwarg)
    a1 = LEDArray(**common)
    # explicit custom mode
    a2 = LEDArray(**common, mode="custom")
    srcs1 = a1.expand()
    srcs2 = a2.expand()
    assert len(srcs1) == len(srcs2)
    for s1, s2 in zip(srcs1, srcs2):
        assert s1.name == s2.name
        assert s1.x == pytest.approx(s2.x)
        assert s1.y == pytest.approx(s2.y)
        assert s1.power_w == pytest.approx(s2.power_w)


# --------------------------------------------------------------------------
# New tests for mode="grid"
# --------------------------------------------------------------------------

def test_led_array_grid_mode_first_led_at_offset_position() -> None:
    """mode='grid' auto-computes pitch and places first LED at offset edge."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=4,
        count_y=3,
        pitch_x=0.0,  # ignored for grid mode (auto-computed)
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.3,
        panel_height=0.2,
        offset_left=0.02,
        offset_right=0.02,
        offset_top=0.01,
        offset_bottom=0.01,
    )
    expanded = arr.expand()
    assert len(expanded) == 12  # 4*3

    # First LED at start of usable area
    first = expanded[0]
    assert first.x == pytest.approx(0.02, abs=1e-9)  # offset_left
    assert first.y == pytest.approx(0.01, abs=1e-9)  # offset_bottom

    # Auto-computed pitch: usable_w / (count-1)
    usable_w = 0.3 - 0.02 - 0.02  # 0.26
    expected_pitch_x = usable_w / 3  # ~0.0867
    second = expanded[1]  # iy=0, ix=1
    assert second.x == pytest.approx(0.02 + expected_pitch_x, abs=1e-9)


def test_led_array_grid_mode_last_led_at_offset_boundary() -> None:
    """mode='grid': last LED sits exactly at the far offset boundary."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=4,
        count_y=3,
        pitch_x=0.0,  # ignored for grid mode
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.3,
        panel_height=0.2,
        offset_left=0.02,
        offset_right=0.02,
        offset_top=0.01,
        offset_bottom=0.01,
    )
    expanded = arr.expand()
    last = expanded[-1]
    assert last.x == pytest.approx(0.3 - 0.02, abs=1e-9)  # panel_width - offset_right
    assert last.y == pytest.approx(0.2 - 0.01, abs=1e-9)  # panel_height - offset_top


def test_led_array_grid_zone_power_assignment() -> None:
    """mode='grid' with zone_powers assigns power per LED zone quadrant."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=4,
        count_y=4,
        pitch_x=0.0,  # ignored for grid mode (auto-computed)
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.3,
        panel_height=0.3,
        offset_left=0.0,
        offset_right=0.0,
        offset_top=0.0,
        offset_bottom=0.0,
        zone_count_x=2,
        zone_count_y=2,
        zone_powers=[0.1, 0.2, 0.3, 0.4],  # bottom-left, bottom-right, top-left, top-right
    )
    expanded = arr.expand()
    assert len(expanded) == 16

    # Zone power values: row 0-1 (bottom), col 0-1 (left) => zone index 0 => 0.1
    # row 0, col 0 -> zone_xi=0, zone_yi=0 -> zone_idx=0 -> 0.1
    r0c0 = expanded[0]  # iy=0, ix=0
    assert r0c0.power_w == pytest.approx(0.1)
    # row 0, col 2 -> zone_xi=1, zone_yi=0 -> zone_idx=1 -> 0.2
    r0c2 = expanded[2]  # iy=0, ix=2
    assert r0c2.power_w == pytest.approx(0.2)
    # row 2, col 0 -> zone_xi=0, zone_yi=1 -> zone_idx=2 -> 0.3
    r2c0 = expanded[8]  # iy=2, ix=0
    assert r2c0.power_w == pytest.approx(0.3)
    # row 2, col 2 -> zone_xi=1, zone_yi=1 -> zone_idx=3 -> 0.4
    r2c2 = expanded[10]  # iy=2, ix=2
    assert r2c2.power_w == pytest.approx(0.4)


def test_led_array_grid_empty_zone_powers_uses_uniform() -> None:
    """mode='grid' with empty zone_powers falls back to power_per_led_w uniformly."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=2,
        count_y=2,
        pitch_x=0.0,  # ignored for grid mode
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.2,
        panel_height=0.2,
        zone_count_x=2,
        zone_count_y=2,
        zone_powers=[],  # empty -> fallback
    )
    expanded = arr.expand()
    for src in expanded:
        assert src.power_w == pytest.approx(0.5)


# --------------------------------------------------------------------------
# New tests for mode="edge"
# --------------------------------------------------------------------------

def test_led_array_edge_bottom_places_leds_at_correct_y() -> None:
    """mode='edge', edge_config='bottom' places count_x LEDs at y=edge_offset."""
    arr = LEDArray(
        name="ELED",
        layer="LGP",
        center_x=0.0,
        center_y=0.0,
        count_x=5,
        count_y=1,
        pitch_x=0.3 / 6,
        pitch_y=0.1,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        led_width=0.002,
        led_height=0.001,
        mode="edge",
        edge_config="bottom",
        panel_width=0.3,
        panel_height=0.2,
        edge_offset=0.005,
    )
    expanded = arr.expand()
    assert len(expanded) == 5
    for src in expanded:
        assert src.y == pytest.approx(0.005, abs=1e-9)
    # x positions should span the panel
    xs = [src.x for src in expanded]
    assert min(xs) >= 0.0
    assert max(xs) <= 0.3


def test_led_array_edge_left_right_produces_correct_count() -> None:
    """mode='edge', edge_config='left_right' produces 2*count_y LEDs."""
    arr = LEDArray(
        name="ELED",
        layer="LGP",
        center_x=0.0,
        center_y=0.0,
        count_x=1,
        count_y=4,
        pitch_x=0.1,
        pitch_y=0.2 / 5,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        led_width=0.001,
        led_height=0.002,
        mode="edge",
        edge_config="left_right",
        panel_width=0.3,
        panel_height=0.2,
        edge_offset=0.005,
    )
    expanded = arr.expand()
    assert len(expanded) == 8  # 4 per side

    left_leds = [s for s in expanded if "left" in s.name]
    right_leds = [s for s in expanded if "right" in s.name]
    assert len(left_leds) == 4
    assert len(right_leds) == 4


def test_led_array_edge_all_produces_leds_on_all_four_edges() -> None:
    """mode='edge', edge_config='all' produces LEDs on all four edges."""
    arr = LEDArray(
        name="ELED",
        layer="LGP",
        center_x=0.0,
        center_y=0.0,
        count_x=5,
        count_y=4,
        pitch_x=0.3 / 6,
        pitch_y=0.2 / 5,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        led_width=0.002,
        led_height=0.001,
        mode="edge",
        edge_config="all",
        panel_width=0.3,
        panel_height=0.2,
        edge_offset=0.005,
    )
    expanded = arr.expand()
    # bottom: count_x=5, top: count_x=5, left: count_y=4, right: count_y=4 => 18
    assert len(expanded) == 18

    # Use name prefix to count by strip (avoids corner ambiguity)
    bottom = [s for s in expanded if "bot" in s.name]
    top = [s for s in expanded if "top" in s.name]
    left = [s for s in expanded if "left" in s.name]
    right = [s for s in expanded if "right" in s.name]
    assert len(bottom) == 5
    assert len(top) == 5
    assert len(left) == 4
    assert len(right) == 4


def test_led_array_edge_positions_clamped_within_panel() -> None:
    """All edge LED positions are clamped within [0, panel_width] x [0, panel_height]."""
    arr = LEDArray(
        name="ELED",
        layer="LGP",
        center_x=0.0,
        center_y=0.0,
        count_x=5,
        count_y=4,
        pitch_x=0.3 / 6,
        pitch_y=0.2 / 5,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        led_width=0.002,
        led_height=0.001,
        mode="edge",
        edge_config="all",
        panel_width=0.3,
        panel_height=0.2,
        edge_offset=0.005,
    )
    expanded = arr.expand()
    for src in expanded:
        assert 0.0 <= src.x <= 0.3
        assert 0.0 <= src.y <= 0.2


# --------------------------------------------------------------------------
# Serialization round-trip tests
# --------------------------------------------------------------------------

def test_led_array_to_dict_from_dict_roundtrip_new_fields() -> None:
    """to_dict/from_dict round-trip preserves all new fields."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.15,
        center_y=0.1,
        count_x=4,
        count_y=3,
        pitch_x=0.05,
        pitch_y=0.05,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.3,
        panel_height=0.2,
        offset_left=0.02,
        offset_right=0.02,
        offset_top=0.01,
        offset_bottom=0.01,
        zone_count_x=2,
        zone_count_y=2,
        zone_powers=[0.1, 0.2, 0.3, 0.4],
        edge_config="bottom",
        edge_offset=0.005,
    )
    d = arr.to_dict()
    arr2 = LEDArray.from_dict(d)

    assert arr2.mode == "grid"
    assert arr2.panel_width == pytest.approx(0.3)
    assert arr2.panel_height == pytest.approx(0.2)
    assert arr2.offset_left == pytest.approx(0.02)
    assert arr2.offset_right == pytest.approx(0.02)
    assert arr2.offset_top == pytest.approx(0.01)
    assert arr2.offset_bottom == pytest.approx(0.01)
    assert arr2.zone_count_x == 2
    assert arr2.zone_count_y == 2
    assert arr2.zone_powers == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert arr2.edge_config == "bottom"
    assert arr2.edge_offset == pytest.approx(0.005)


def test_led_array_from_dict_old_json_defaults_to_custom() -> None:
    """from_dict with missing new keys (old JSON format) defaults to mode='custom'."""
    old_dict = {
        "name": "legacy",
        "layer": "PCB",
        "center_x": 0.05,
        "center_y": 0.04,
        "count_x": 3,
        "count_y": 2,
        "pitch_x": 0.01,
        "pitch_y": 0.02,
        "power_per_led_w": 0.2,
        "footprint_shape": "rectangle",
        "led_width": 0.004,
        "led_height": 0.003,
        "led_radius": None,
    }
    arr = LEDArray.from_dict(old_dict)
    assert arr.mode == "custom"
    assert arr.panel_width == 0.0
    assert arr.panel_height == 0.0
    assert arr.offset_left == 0.0
    assert arr.offset_right == 0.0
    assert arr.zone_powers == []
    assert arr.edge_offset == pytest.approx(0.005)

    # Must still expand correctly
    expanded = arr.expand()
    assert len(expanded) == 6


def test_led_array_total_power_grid_with_zones() -> None:
    """total_power_w for mode='grid' with zone_powers sums all zone powers * LED count."""
    arr = LEDArray(
        name="GRID",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=4,
        count_y=4,
        pitch_x=0.0,  # ignored for grid mode
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.3,
        panel_height=0.3,
        zone_count_x=2,
        zone_count_y=2,
        zone_powers=[0.1, 0.2, 0.3, 0.4],
    )
    # 4 zones, each has 2x2=4 LEDs
    # zone 0: 4*0.1=0.4, zone 1: 4*0.2=0.8, zone 2: 4*0.3=1.2, zone 3: 4*0.4=1.6 => total=4.0
    assert arr.total_power_w == pytest.approx(4.0)


def test_led_array_total_power_edge_all() -> None:
    """total_power_w for mode='edge', edge_config='all' counts all edge LEDs."""
    arr = LEDArray(
        name="ELED",
        layer="LGP",
        center_x=0.0,
        center_y=0.0,
        count_x=5,
        count_y=4,
        pitch_x=0.05,
        pitch_y=0.05,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        led_width=0.002,
        led_height=0.001,
        mode="edge",
        edge_config="all",
        panel_width=0.3,
        panel_height=0.2,
        edge_offset=0.005,
    )
    # bottom: 5, top: 5, left: 4, right: 4 = 18 LEDs
    assert arr.total_power_w == pytest.approx(18 * 0.3)


def test_led_array_grid_dense_32x12_all_within_bounds() -> None:
    """Dense 32x12 grid on 300x120mm panel — all LEDs within panel bounds (auto-pitch)."""
    arr = LEDArray(
        name="DLED Array",
        layer="LED Board",
        center_x=0.0,
        center_y=0.0,
        count_x=32,
        count_y=12,
        pitch_x=0.0,  # auto-computed
        pitch_y=0.0,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=0.300,
        panel_height=0.120,
        offset_left=0.010,
        offset_right=0.010,
        offset_top=0.005,
        offset_bottom=0.005,
    )
    expanded = arr.expand()
    assert len(expanded) == 32 * 12

    # All LEDs within panel bounds
    for src in expanded:
        assert 0.0 <= src.x <= 0.300, f"LED {src.name} x={src.x} out of bounds"
        assert 0.0 <= src.y <= 0.120, f"LED {src.name} y={src.y} out of bounds"

    # First LED at offset position, last at panel - offset
    assert expanded[0].x == pytest.approx(0.010, abs=1e-9)
    assert expanded[0].y == pytest.approx(0.005, abs=1e-9)
    assert expanded[-1].x == pytest.approx(0.290, abs=1e-9)
    assert expanded[-1].y == pytest.approx(0.115, abs=1e-9)

    # Auto-computed pitch
    expected_pitch_x = 0.280 / 31  # ~9.03mm
    expected_pitch_y = 0.110 / 11  # 10.0mm
    assert expanded[1].x - expanded[0].x == pytest.approx(expected_pitch_x, abs=1e-9)
    assert expanded[32].y - expanded[0].y == pytest.approx(expected_pitch_y, abs=1e-9)
