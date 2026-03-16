"""Tests for ELED cross-section zone generation.

Unit tests verify generate_eled_zones() correctness.
Integration test confirms FR4+LED zone T_max > LGP bulk T_max in a zoned ELED model.
"""

from __future__ import annotations

import pytest

from thermal_sim.models.stack_templates import ELED_ZONE_MATERIALS, generate_eled_zones


# ---------------------------------------------------------------------------
# Test 1: generate_eled_zones with known symmetric inputs
# ---------------------------------------------------------------------------


def test_generate_eled_zones_symmetric_known_inputs() -> None:
    """generate_eled_zones returns 7 zones with correct materials, x-positions, widths."""
    panel_width = 0.300
    panel_height = 0.200
    frame_left = 0.003
    pcb_left = 0.005
    air_left = 0.001
    frame_right = 0.003
    pcb_right = 0.005
    air_right = 0.001

    # Expected LGP bulk width:
    # 0.300 - 2*(0.003+0.005+0.001) = 0.300 - 0.018 = 0.282
    expected_bulk = 0.282

    zones = generate_eled_zones(
        panel_width=panel_width,
        panel_height=panel_height,
        frame_width_left=frame_left,
        pcb_width_left=pcb_left,
        air_gap_left=air_left,
        frame_width_right=frame_right,
        pcb_width_right=pcb_right,
        air_gap_right=air_right,
    )

    # Should return 7 zones (all widths > 0)
    assert len(zones) == 7, f"Expected 7 zones, got {len(zones)}"

    # Zone materials in order
    expected_materials = ["Steel", "FR4", "Air Gap", "PMMA", "Air Gap", "FR4", "Steel"]
    actual_materials = [z.material for z in zones]
    assert actual_materials == expected_materials, (
        f"Expected materials {expected_materials}, got {actual_materials}"
    )

    # Expected x-positions (cumulative left edges)
    expected_x = [0.0, 0.003, 0.008, 0.009, 0.291, 0.292, 0.297]
    for i, (zone, exp_x) in enumerate(zip(zones, expected_x)):
        assert abs(zone.x - exp_x) < 1e-9, (
            f"Zone {i} ({zone.material}) x={zone.x:.9f}, expected {exp_x:.9f}"
        )

    # Expected zone widths
    expected_widths = [
        frame_left,   # Steel left
        pcb_left,     # FR4 left
        air_left,     # Air Gap left
        expected_bulk,  # PMMA bulk
        air_right,    # Air Gap right
        pcb_right,    # FR4 right
        frame_right,  # Steel right
    ]
    for i, (zone, exp_w) in enumerate(zip(zones, expected_widths)):
        assert abs(zone.width - exp_w) < 1e-9, (
            f"Zone {i} ({zone.material}) width={zone.width:.9f}, expected {exp_w:.9f}"
        )

    # All zones should span full panel height
    for i, zone in enumerate(zones):
        assert abs(zone.height - panel_height) < 1e-9, (
            f"Zone {i} height={zone.height}, expected panel_height={panel_height}"
        )
        assert abs(zone.y - 0.0) < 1e-9, (
            f"Zone {i} y={zone.y}, expected 0.0"
        )


# ---------------------------------------------------------------------------
# Test 1b: generate_eled_zones with bottom edge config (zones along y)
# ---------------------------------------------------------------------------


def test_generate_eled_zones_bottom_edge_config() -> None:
    """bottom edge_config produces zones along the y-axis (x=0, varying y)."""
    panel_width = 0.300
    panel_height = 0.200
    frame = 0.003
    pcb = 0.005
    air = 0.001

    zones = generate_eled_zones(
        panel_width=panel_width,
        panel_height=panel_height,
        frame_width_left=frame,
        pcb_width_left=pcb,
        air_gap_left=air,
        frame_width_right=frame,
        pcb_width_right=pcb,
        air_gap_right=air,
        edge_config="bottom",
    )

    assert len(zones) == 7
    expected_materials = ["Steel", "FR4", "Air Gap", "PMMA", "Air Gap", "FR4", "Steel"]
    assert [z.material for z in zones] == expected_materials

    # All zones should have x=0 and width=panel_width (full panel width)
    for z in zones:
        assert abs(z.x - 0.0) < 1e-9
        assert abs(z.width - panel_width) < 1e-9

    # y-positions should be cumulative; heights should match zone widths
    expected_y = [0.0, frame, frame + pcb, frame + pcb + air]
    for i in range(3):
        assert abs(zones[i].y - expected_y[i]) < 1e-9

    # LGP bulk height
    edge_total = 2 * (frame + pcb + air)
    expected_bulk_h = panel_height - edge_total
    assert abs(zones[3].height - expected_bulk_h) < 1e-9


# ---------------------------------------------------------------------------
# Test 2: generate_eled_zones raises ValueError on width overflow
# ---------------------------------------------------------------------------


def test_generate_eled_zones_overflow_raises_value_error() -> None:
    """Zone widths that exceed panel_width raise ValueError mentioning 'exceed panel width'."""
    # panel_width=0.010, each zone width=0.003 => total=6*0.003=0.018 > 0.010
    with pytest.raises(ValueError, match="exceed panel width"):
        generate_eled_zones(
            panel_width=0.010,
            panel_height=0.100,
            frame_width_left=0.003,
            pcb_width_left=0.003,
            air_gap_left=0.003,
            frame_width_right=0.003,
            pcb_width_right=0.003,
            air_gap_right=0.003,
        )


# ---------------------------------------------------------------------------
# Test 3: ELED_ZONE_MATERIALS constant
# ---------------------------------------------------------------------------


def test_eled_zone_materials_contains_required_keys() -> None:
    """ELED_ZONE_MATERIALS includes the four required material names."""
    assert "Steel" in ELED_ZONE_MATERIALS
    assert "FR4" in ELED_ZONE_MATERIALS
    assert "Air Gap" in ELED_ZONE_MATERIALS
    assert "PMMA" in ELED_ZONE_MATERIALS


# ---------------------------------------------------------------------------
# Test 4: Integration — ELED zoned model: FR4 zone hotter than LGP bulk
# ---------------------------------------------------------------------------


def test_eled_zoned_model_fr4_zone_hotter_than_lgp_bulk() -> None:
    """FR4+LED zone T_max > LGP bulk T_max in a zoned ELED steady-state solve.

    Physical expectation: edge LEDs dissipate heat directly into the FR4 board
    which has poor lateral conductance (k~0.35 W/mK). The LGP bulk (PMMA,
    k~0.20 W/mK) is heated only by conduction from the FR4 zone. With the
    primary heat path through the FR4 → steel frame, the FR4 zone should be
    the hottest region in the LGP layer.
    """
    import numpy as np

    from thermal_sim.core.material_library import load_builtin_library
    from thermal_sim.models.layer import Layer
    from thermal_sim.models.project import DisplayProject, MeshConfig
    from thermal_sim.models.stack_templates import eled_template
    from thermal_sim.solvers.steady_state import SteadyStateSolver

    panel_width = 0.300
    panel_height = 0.200

    # Build ELED template project with left/right edge config so LEDs are
    # placed along the left/right edges — these align with the FR4 zone columns.
    template = eled_template(panel_width=panel_width, panel_height=panel_height,
                             edge_config="left_right")

    # Generate zones for LGP cross-section
    frame_left = 0.003
    pcb_left = 0.005
    air_left = 0.001
    frame_right = 0.003
    pcb_right = 0.005
    air_right = 0.001

    zones = generate_eled_zones(
        panel_width=panel_width,
        panel_height=panel_height,
        frame_width_left=frame_left,
        pcb_width_left=pcb_left,
        air_gap_left=air_left,
        frame_width_right=frame_right,
        pcb_width_right=pcb_right,
        air_gap_right=air_right,
    )

    # Assign zones to LGP layer
    layers = template["layers"]
    lgp_layer = None
    lgp_idx = None
    for i, layer in enumerate(layers):
        if layer.name == "LGP":
            lgp_layer = layer
            lgp_idx = i
            break
    assert lgp_layer is not None, "LGP layer not found in ELED template"

    # Replace LGP layer with a copy that has zones attached
    import dataclasses
    layers[lgp_idx] = dataclasses.replace(lgp_layer, zones=zones)

    # Build complete materials dict including ELED zone materials
    library = load_builtin_library()
    materials = dict(template["materials"])
    for mat_name in ELED_ZONE_MATERIALS:
        if mat_name not in materials and mat_name in library:
            materials[mat_name] = library[mat_name]

    project = DisplayProject(
        name="ELED Zone Integration Test",
        width=panel_width,
        height=panel_height,
        layers=layers,
        materials=materials,
        heat_sources=list(
            source
            for array in template.get("led_arrays", [])
            for source in array.expand()
        ),
        boundaries=template["boundaries"],
        mesh=MeshConfig(nx=30, ny=20),
    )

    result = SteadyStateSolver().solve(project)

    # LGP is at lgp_idx in the layer stack; temperatures_c shape: [n_layers, ny, nx]
    lgp_temp_map = result.temperatures_c[lgp_idx]  # shape (ny, nx)

    nx = 30
    ny = 20

    # FR4 zone occupies columns corresponding to pcb_left <= x < pcb_left + pcb_width_left
    # and panel_width - frame_right - pcb_right <= x < panel_width - frame_right
    dx = panel_width / nx

    # Left FR4 zone: x in [frame_left, frame_left + pcb_left)
    ix_fr4_left_start = int(frame_left / dx)
    ix_fr4_left_end = int((frame_left + pcb_left) / dx)

    # Right FR4 zone: x in [panel_width - frame_right - pcb_right, panel_width - frame_right)
    ix_fr4_right_start = int((panel_width - frame_right - pcb_right) / dx)
    ix_fr4_right_end = int((panel_width - frame_right) / dx)

    # LGP bulk: central columns (excluding frame+pcb+air on both sides)
    total_left_edge = frame_left + pcb_left + air_left
    total_right_edge = frame_right + pcb_right + air_right
    ix_bulk_start = int(total_left_edge / dx) + 1
    ix_bulk_end = int((panel_width - total_right_edge) / dx) - 1

    # Clamp indices
    ix_fr4_left_start = max(0, ix_fr4_left_start)
    ix_fr4_left_end = min(nx, max(ix_fr4_left_start + 1, ix_fr4_left_end))
    ix_fr4_right_start = max(0, ix_fr4_right_start)
    ix_fr4_right_end = min(nx, max(ix_fr4_right_start + 1, ix_fr4_right_end))
    ix_bulk_start = max(0, ix_bulk_start)
    ix_bulk_end = min(nx, max(ix_bulk_start + 1, ix_bulk_end))

    fr4_left_temps = lgp_temp_map[:, ix_fr4_left_start:ix_fr4_left_end]
    fr4_right_temps = lgp_temp_map[:, ix_fr4_right_start:ix_fr4_right_end]
    bulk_temps = lgp_temp_map[:, ix_bulk_start:ix_bulk_end]

    fr4_t_max = max(float(np.max(fr4_left_temps)), float(np.max(fr4_right_temps)))
    bulk_t_max = float(np.max(bulk_temps))

    assert fr4_t_max > bulk_t_max, (
        f"Expected FR4 zone T_max ({fr4_t_max:.3f} C) > LGP bulk T_max ({bulk_t_max:.3f} C). "
        f"FR4 zone should be hotter due to direct LED heat dissipation."
    )
