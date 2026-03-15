"""Unit tests for MaterialZone and Layer.zones field.

Tests cover:
- MaterialZone frozen dataclass creation and validation
- MaterialZone round-trip serialization via to_dict()/from_dict()
- Layer with zones=[] omits "zones" key in to_dict()
- Layer with zones=[...] includes "zones" key in to_dict()
- Layer.from_dict() with no "zones" key produces zones=[]
- Layer.from_dict() with "zones" key produces correct zones list
- Backward compatibility: all 4 example JSON projects still load cleanly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thermal_sim.models.layer import Layer
from thermal_sim.models.material_zone import MaterialZone

REPO_ROOT = Path(__file__).parent.parent

EXAMPLES = [
    "examples/DLED.json",
    "examples/led_array_backlight.json",
    "examples/localized_hotspots_stack.json",
    "examples/steady_uniform_stack.json",
]


# ---------------------------------------------------------------------------
# MaterialZone creation and validation
# ---------------------------------------------------------------------------


def test_material_zone_creates_with_valid_args() -> None:
    """MaterialZone can be constructed with valid arguments."""
    mz = MaterialZone(material="Aluminum", x=0.05, y=0.04, width=0.02, height=0.01)
    assert mz.material == "Aluminum"
    assert mz.x == 0.05
    assert mz.y == 0.04
    assert mz.width == 0.02
    assert mz.height == 0.01


def test_material_zone_is_frozen() -> None:
    """MaterialZone is immutable (frozen dataclass)."""
    mz = MaterialZone(material="Aluminum", x=0.05, y=0.04, width=0.02, height=0.01)
    with pytest.raises((AttributeError, TypeError)):
        mz.material = "Steel"  # type: ignore[misc]


def test_material_zone_rejects_empty_material() -> None:
    """MaterialZone raises ValueError for empty material string."""
    with pytest.raises(ValueError, match="material"):
        MaterialZone(material="", x=0.0, y=0.0, width=0.01, height=0.01)


def test_material_zone_rejects_zero_width() -> None:
    """MaterialZone raises ValueError for width <= 0."""
    with pytest.raises(ValueError, match="width"):
        MaterialZone(material="Steel", x=0.0, y=0.0, width=0.0, height=0.01)


def test_material_zone_rejects_negative_height() -> None:
    """MaterialZone raises ValueError for height <= 0."""
    with pytest.raises(ValueError, match="height"):
        MaterialZone(material="Steel", x=0.0, y=0.0, width=0.01, height=-0.005)


def test_material_zone_allows_negative_x_y() -> None:
    """MaterialZone allows x and y to be any float (including negative)."""
    mz = MaterialZone(material="Steel", x=-0.01, y=-0.02, width=0.05, height=0.03)
    assert mz.x == -0.01
    assert mz.y == -0.02


# ---------------------------------------------------------------------------
# MaterialZone serialization
# ---------------------------------------------------------------------------


def test_material_zone_to_dict() -> None:
    """MaterialZone.to_dict() returns correct key-value mapping."""
    mz = MaterialZone(material="Aluminum", x=0.05, y=0.04, width=0.02, height=0.01)
    d = mz.to_dict()
    assert d == {
        "material": "Aluminum",
        "x": 0.05,
        "y": 0.04,
        "width": 0.02,
        "height": 0.01,
    }


def test_material_zone_from_dict_round_trip() -> None:
    """MaterialZone round-trips through to_dict()/from_dict() correctly."""
    original = MaterialZone(material="FR4", x=0.03, y=0.07, width=0.015, height=0.008)
    restored = MaterialZone.from_dict(original.to_dict())
    assert restored == original


def test_material_zone_from_dict_exact_values() -> None:
    """MaterialZone.from_dict() produces exact values from raw dict."""
    d = {"material": "Glass", "x": 0.1, "y": 0.2, "width": 0.05, "height": 0.03}
    mz = MaterialZone.from_dict(d)
    assert mz.material == "Glass"
    assert mz.x == 0.1
    assert mz.y == 0.2
    assert mz.width == 0.05
    assert mz.height == 0.03


# ---------------------------------------------------------------------------
# Layer.zones field
# ---------------------------------------------------------------------------


def test_layer_with_no_zones_omits_zones_key() -> None:
    """Layer with zones=[] (default) does not include 'zones' in to_dict()."""
    layer = Layer(name="Test", material="Aluminum", thickness=0.001)
    d = layer.to_dict()
    assert "zones" not in d


def test_layer_with_zones_includes_zones_key() -> None:
    """Layer with non-empty zones list includes 'zones' in to_dict()."""
    mz = MaterialZone(material="Steel", x=0.05, y=0.04, width=0.02, height=0.01)
    layer = Layer(name="Test", material="Aluminum", thickness=0.001, zones=[mz])
    d = layer.to_dict()
    assert "zones" in d
    assert len(d["zones"]) == 1
    assert d["zones"][0] == mz.to_dict()


def test_layer_from_dict_no_zones_key_produces_empty_list() -> None:
    """Layer.from_dict() without 'zones' key produces zones=[]."""
    d = {"name": "Base", "material": "FR4", "thickness": 0.002}
    layer = Layer.from_dict(d)
    assert layer.zones == []


def test_layer_from_dict_with_zones_key_produces_correct_zones() -> None:
    """Layer.from_dict() with 'zones' key produces correct MaterialZone list."""
    d = {
        "name": "Base",
        "material": "FR4",
        "thickness": 0.002,
        "zones": [
            {"material": "Aluminum", "x": 0.05, "y": 0.04, "width": 0.02, "height": 0.01}
        ],
    }
    layer = Layer.from_dict(d)
    assert len(layer.zones) == 1
    assert layer.zones[0].material == "Aluminum"
    assert layer.zones[0].x == 0.05


def test_layer_zones_round_trip() -> None:
    """Layer with zones round-trips through to_dict()/from_dict()."""
    mz1 = MaterialZone(material="Steel", x=0.05, y=0.04, width=0.02, height=0.01)
    mz2 = MaterialZone(material="Aluminum", x=0.10, y=0.03, width=0.015, height=0.008)
    original = Layer(name="Mixed", material="FR4", thickness=0.001, zones=[mz1, mz2])
    restored = Layer.from_dict(original.to_dict())
    assert restored.zones == original.zones


def test_layer_defaults_to_empty_zones() -> None:
    """Layer constructor defaults zones to empty list."""
    layer = Layer(name="Test", material="Aluminum", thickness=0.001)
    assert layer.zones == []
    assert isinstance(layer.zones, list)


# ---------------------------------------------------------------------------
# Backward compatibility: existing example JSON files still load
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("example_path", [pytest.param(p, id=Path(p).stem) for p in EXAMPLES])
def test_example_projects_still_load_after_layer_zones_field(example_path: str) -> None:
    """Existing JSON projects without 'zones' deserialize cleanly after Layer.zones addition."""
    from thermal_sim.io.project_io import load_project
    project = load_project(REPO_ROOT / example_path)
    # All layers should have zones=[] since old JSON has no zones key
    for layer in project.layers:
        assert layer.zones == [], f"Layer {layer.name!r} should have zones=[] from old JSON"
