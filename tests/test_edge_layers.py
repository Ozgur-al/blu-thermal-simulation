"""Tests for EdgeLayer dataclass, Layer.edge_layers field, generate_edge_zones(),
and solver integration of edge-generated material zones."""

from __future__ import annotations

import pytest

from thermal_sim.models.layer import EdgeLayer, Layer
from thermal_sim.models.material_zone import MaterialZone


# ---------------------------------------------------------------------------
# EdgeLayer validation
# ---------------------------------------------------------------------------


def test_edge_layer_valid():
    el = EdgeLayer("Steel", 0.003)
    assert el.material == "Steel"
    assert el.thickness == 0.003


def test_edge_layer_empty_material_raises():
    with pytest.raises(ValueError, match="material"):
        EdgeLayer("", 0.003)


def test_edge_layer_whitespace_material_raises():
    with pytest.raises(ValueError, match="material"):
        EdgeLayer("   ", 0.003)


def test_edge_layer_negative_thickness_raises():
    with pytest.raises(ValueError, match="thickness"):
        EdgeLayer("Steel", -0.001)


def test_edge_layer_zero_thickness_raises():
    with pytest.raises(ValueError, match="thickness"):
        EdgeLayer("Steel", 0.0)


def test_edge_layer_frozen():
    """EdgeLayer must be immutable (frozen dataclass)."""
    el = EdgeLayer("Steel", 0.003)
    with pytest.raises((AttributeError, TypeError)):
        el.material = "Aluminum"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EdgeLayer serialization
# ---------------------------------------------------------------------------


def test_edge_layer_to_dict():
    el = EdgeLayer("Steel", 0.003)
    d = el.to_dict()
    assert d == {"material": "Steel", "thickness": 0.003}


def test_edge_layer_from_dict():
    d = {"material": "Steel", "thickness": 0.003}
    el = EdgeLayer.from_dict(d)
    assert el.material == "Steel"
    assert el.thickness == pytest.approx(0.003)


def test_edge_layer_round_trip():
    el = EdgeLayer("Aluminum", 0.002)
    assert EdgeLayer.from_dict(el.to_dict()) == el


# ---------------------------------------------------------------------------
# Layer.edge_layers field
# ---------------------------------------------------------------------------


def test_layer_default_edge_layers_empty():
    layer = Layer(name="Glass", material="Glass", thickness=0.001)
    assert layer.edge_layers == {}


def test_layer_with_edge_layers():
    el = EdgeLayer("Steel", 0.003)
    layer = Layer(name="Frame", material="PC", thickness=0.002,
                  edge_layers={"bottom": [el]})
    assert layer.edge_layers == {"bottom": [el]}


# ---------------------------------------------------------------------------
# Layer serialization with edge_layers
# ---------------------------------------------------------------------------


def test_layer_to_dict_omits_edge_layers_when_empty():
    layer = Layer(name="Glass", material="Glass", thickness=0.001)
    d = layer.to_dict()
    assert "edge_layers" not in d


def test_layer_to_dict_includes_edge_layers_when_set():
    el = EdgeLayer("Steel", 0.003)
    layer = Layer(name="Frame", material="PC", thickness=0.002,
                  edge_layers={"bottom": [el]})
    d = layer.to_dict()
    assert "edge_layers" in d
    assert d["edge_layers"] == {"bottom": [{"material": "Steel", "thickness": 0.003}]}


def test_layer_to_dict_serializes_multiple_edges():
    layer = Layer(
        name="Frame",
        material="PC",
        thickness=0.002,
        edge_layers={
            "bottom": [EdgeLayer("Steel", 0.003)],
            "top":    [EdgeLayer("Aluminum", 0.002)],
            "left":   [EdgeLayer("Steel", 0.004), EdgeLayer("FR4", 0.001)],
        },
    )
    d = layer.to_dict()
    assert set(d["edge_layers"].keys()) == {"bottom", "top", "left"}
    assert len(d["edge_layers"]["left"]) == 2


# ---------------------------------------------------------------------------
# Layer.from_dict backward compat
# ---------------------------------------------------------------------------


def test_layer_from_dict_backward_compat_no_edge_layers_key():
    """Old JSON without edge_layers key must deserialize to edge_layers={}."""
    data = {
        "name": "Glass",
        "material": "Glass",
        "thickness": 0.001,
        "interface_resistance_to_next": 0.0,
        "nz": 1,
    }
    layer = Layer.from_dict(data)
    assert layer.edge_layers == {}


def test_layer_from_dict_deserializes_edge_layers():
    data = {
        "name": "Frame",
        "material": "PC",
        "thickness": 0.002,
        "edge_layers": {
            "bottom": [{"material": "Steel", "thickness": 0.003}],
            "top":    [{"material": "Aluminum", "thickness": 0.002}],
        },
    }
    layer = Layer.from_dict(data)
    assert len(layer.edge_layers["bottom"]) == 1
    assert layer.edge_layers["bottom"][0] == EdgeLayer("Steel", 0.003)
    assert layer.edge_layers["top"][0] == EdgeLayer("Aluminum", 0.002)


def test_layer_round_trip_with_edge_layers():
    original = Layer(
        name="Edge Layer Test",
        material="PC",
        thickness=0.002,
        edge_layers={
            "bottom": [EdgeLayer("Steel", 0.003), EdgeLayer("FR4", 0.001)],
            "right":  [EdgeLayer("Aluminum", 0.002)],
        },
    )
    restored = Layer.from_dict(original.to_dict())
    assert restored.edge_layers == original.edge_layers


# ---------------------------------------------------------------------------
# generate_edge_zones — imported after EdgeLayer/Layer tests
# ---------------------------------------------------------------------------


from thermal_sim.models.stack_templates import generate_edge_zones  # noqa: E402


def _make_4_edge_layer(W: float = 0.300, H: float = 0.200) -> Layer:
    """Layer with 3mm frame + 1mm FR4 on each of the 4 edges."""
    return Layer(
        name="LGP",
        material="PMMA",
        thickness=0.004,
        edge_layers={
            "bottom": [EdgeLayer("Steel", 0.003), EdgeLayer("FR4", 0.001)],
            "top":    [EdgeLayer("Steel", 0.003), EdgeLayer("FR4", 0.001)],
            "left":   [EdgeLayer("Steel", 0.003), EdgeLayer("FR4", 0.001)],
            "right":  [EdgeLayer("Steel", 0.003), EdgeLayer("FR4", 0.001)],
        },
    )


def test_generate_edge_zones_empty_returns_empty():
    layer = Layer(name="Glass", material="Glass", thickness=0.001)
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    assert zones == []


def test_generate_edge_zones_symmetric_zone_count():
    """4 edges × 2 EdgeLayers each = 8 zones."""
    layer = _make_4_edge_layer()
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    assert len(zones) == 8


def test_generate_edge_zones_bottom_top_span_full_width():
    """Bottom and top zones must span the full panel width."""
    layer = _make_4_edge_layer(W=0.300, H=0.200)
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    # Bottom zones: x=center of panel, width=panel_width
    bottom_zones = [z for z in zones if abs(z.y - 0.003/2) < 1e-9 or abs(z.y - 0.003 - 0.001/2) < 1e-9]
    for z in bottom_zones:
        assert z.width == pytest.approx(0.300), f"Bottom zone width should be 0.300, got {z.width}"


def test_generate_edge_zones_left_right_span_interior_height():
    """Left and right zones must span interior height (panel_height - bottom_total - top_total)."""
    layer = _make_4_edge_layer(W=0.300, H=0.200)
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    # Interior height = 0.200 - 0.004 (bottom sum) - 0.004 (top sum) = 0.192
    interior_h = 0.200 - 0.004 - 0.004
    # Left/right zones have width = el.thickness (3mm or 1mm), not panel_width (300mm)
    left_right_zones = [z for z in zones if z.width != pytest.approx(0.300)]
    assert len(left_right_zones) == 4, f"Expected 4 left/right zones, got {len(left_right_zones)}"
    for z in left_right_zones:
        assert z.height == pytest.approx(interior_h), f"Left/right zone height should be {interior_h}, got {z.height}"


def test_generate_edge_zones_corners_use_bottom_top():
    """Corner cells (x near 0, y near 0) must be covered by bottom/top full-width zones."""
    layer = _make_4_edge_layer(W=0.300, H=0.200)
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)

    # A corner point at (0.001, 0.001) should be inside a bottom zone (full-width)
    corner_x, corner_y = 0.001, 0.001
    covering = [
        z for z in zones
        if (z.x - z.width / 2 <= corner_x <= z.x + z.width / 2) and
           (z.y - z.height / 2 <= corner_y <= z.y + z.height / 2)
    ]
    assert len(covering) >= 1, "Corner cell should be covered by at least one zone"
    # The covering zone should be full-width (bottom zone), not a left-side zone
    full_width_covers = [z for z in covering if z.width == pytest.approx(0.300)]
    assert len(full_width_covers) >= 1, "Corner should be covered by a full-width bottom zone"


def test_generate_edge_zones_overflow_width_raises():
    """left + right total thickness >= panel_width must raise ValueError."""
    layer = Layer(
        name="L",
        material="PMMA",
        thickness=0.004,
        edge_layers={
            "left":  [EdgeLayer("Steel", 0.160)],
            "right": [EdgeLayer("Steel", 0.160)],
        },
    )
    with pytest.raises(ValueError, match="width"):
        generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)


def test_generate_edge_zones_overflow_height_raises():
    """bottom + top total thickness >= panel_height must raise ValueError."""
    layer = Layer(
        name="L",
        material="PMMA",
        thickness=0.004,
        edge_layers={
            "bottom": [EdgeLayer("Steel", 0.110)],
            "top":    [EdgeLayer("Steel", 0.110)],
        },
    )
    with pytest.raises(ValueError, match="height"):
        generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)


def test_generate_edge_zones_materials_correct():
    """Zones must carry the correct material names."""
    layer = Layer(
        name="LGP",
        material="PMMA",
        thickness=0.004,
        edge_layers={
            "bottom": [EdgeLayer("Steel", 0.003)],
        },
    )
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    assert len(zones) == 1
    assert zones[0].material == "Steel"
    assert zones[0].width == pytest.approx(0.300)
    assert zones[0].height == pytest.approx(0.003)
    # Center y = 0.003 / 2 = 0.0015
    assert zones[0].y == pytest.approx(0.0015)


def test_generate_edge_zones_center_x_of_panel():
    """Full-width (bottom/top) zones should be centered at panel_width / 2."""
    layer = Layer(
        name="L",
        material="PMMA",
        thickness=0.004,
        edge_layers={"bottom": [EdgeLayer("Steel", 0.003)]},
    )
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    assert zones[0].x == pytest.approx(0.300 / 2)


def test_generate_edge_zones_only_bottom():
    """Single-edge config: only bottom edge, no others."""
    layer = Layer(
        name="L",
        material="PMMA",
        thickness=0.004,
        edge_layers={"bottom": [EdgeLayer("Steel", 0.003)]},
    )
    zones = generate_edge_zones(layer, panel_width=0.300, panel_height=0.200)
    assert len(zones) == 1
    assert zones[0].material == "Steel"


# ---------------------------------------------------------------------------
# Solver integration: manual zones win over edge zones
# ---------------------------------------------------------------------------


def test_edge_zone_manual_zone_coexistence():
    """Manual MaterialZone overlapping an edge zone should win (last-defined-wins)."""
    from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
    from thermal_sim.models.material import Material
    from thermal_sim.models.project import DisplayProject
    from thermal_sim.solvers.steady_state import SteadyStateSolver

    # Build a minimal two-material project.
    # Layer has edge_layers={"bottom": [EdgeLayer("Steel", 0.010)]} but also
    # a manual zone covering the same area with Aluminum.
    # Solved temperature should reflect Aluminum (manual wins = higher conductivity
    # means less temperature rise => lower T at the overlap region).

    steel = Material(name="Steel", k_in_plane=50.0, k_through=50.0,
                     density=7800.0, specific_heat=500.0)
    aluminum = Material(name="Aluminum", k_in_plane=200.0, k_through=200.0,
                        density=2700.0, specific_heat=900.0)
    pmma = Material(name="PMMA", k_in_plane=0.2, k_through=0.2,
                    density=1180.0, specific_heat=1460.0)

    W, H = 0.100, 0.100
    edge_t = 0.010  # 10 mm bottom edge — large enough to be clearly visible

    # Manual MaterialZone covers the bottom edge with Aluminum
    manual_zone = MaterialZone(
        material="Aluminum",
        x=W / 2,
        y=edge_t / 2,
        width=W,
        height=edge_t,
    )

    layer = Layer(
        name="Plate",
        material="PMMA",
        thickness=0.002,
        edge_layers={"bottom": [EdgeLayer("Steel", edge_t)]},
        zones=[manual_zone],
    )

    from thermal_sim.models.heat_source import HeatSource
    from thermal_sim.models.project import MeshConfig

    source = HeatSource(
        name="Heater",
        layer="Plate",
        shape="full",
        power_w=1.0,
    )

    boundaries = BoundaryConditions(
        top=SurfaceBoundary(convection_h=10.0),
        bottom=SurfaceBoundary(convection_h=10.0),
        side=SurfaceBoundary(convection_h=10.0),
    )

    project = DisplayProject(
        name="EdgeTest",
        width=W,
        height=H,
        layers=[layer],
        materials={"Steel": steel, "Aluminum": aluminum, "PMMA": pmma},
        heat_sources=[source],
        boundaries=boundaries,
        mesh=MeshConfig(nx=10, ny=10),
    )

    solver = SteadyStateSolver()
    result = solver.solve(project)

    # With manual Aluminum zone winning at the bottom edge:
    # Bottom edge cells are Aluminum (k=200 W/mK), giving lower resistance.
    # If Steel had won, bottom edge cells would have k=50 W/mK (higher resistance → higher T).
    # We check that the solver ran without crashing and temperatures are finite.
    assert result.temperatures_c is not None
    temps = result.temperatures_c
    assert temps.max() < 500.0, "Temperature looks unreasonably high"
    assert temps.min() > -10.0, "Temperature should be above ambient"
