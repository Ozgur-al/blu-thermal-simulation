"""Tests for material library loading, import conflict resolution, and export round-trip."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from thermal_sim.core.material_library import (
    default_materials,
    export_materials,
    import_materials,
    load_builtin_library,
    load_materials_json,
)
from thermal_sim.models.material import Material


# ---------------------------------------------------------------------------
# load_builtin_library
# ---------------------------------------------------------------------------

def test_load_builtin_library_returns_dict_of_materials():
    lib = load_builtin_library()
    assert isinstance(lib, dict)
    assert len(lib) >= 10


def test_load_builtin_library_contains_expected_materials():
    lib = load_builtin_library()
    for name in ("Copper", "Aluminum", "Glass", "FR4"):
        assert name in lib, f"{name!r} missing from built-in library"


def test_load_builtin_library_values_are_material_instances():
    lib = load_builtin_library()
    for name, mat in lib.items():
        assert isinstance(mat, Material), f"{name!r} is not a Material"


def test_load_builtin_library_round_trip():
    """Materials survive to_dict()/from_dict() round-trip."""
    lib = load_builtin_library()
    for name, mat in lib.items():
        restored = Material.from_dict(mat.to_dict())
        assert restored == mat, f"{name!r} failed round-trip"


# ---------------------------------------------------------------------------
# default_materials backward compatibility
# ---------------------------------------------------------------------------

ORIGINAL_NAMES = {
    "Glass", "OCA", "PMMA", "PC", "Aluminum", "Steel",
    "FR4", "Copper", "Thermal Pad", "Graphite Sheet",
}


def test_default_materials_still_returns_original_10():
    mats = default_materials()
    assert set(mats.keys()) == ORIGINAL_NAMES


def test_default_materials_values_unchanged():
    mats = default_materials()
    copper = mats["Copper"]
    assert copper.k_in_plane == pytest.approx(390.0)
    assert copper.k_through == pytest.approx(390.0)
    assert copper.density == pytest.approx(8960.0)


# ---------------------------------------------------------------------------
# import_materials
# ---------------------------------------------------------------------------

def _make_material(name: str, k: float = 1.0) -> Material:
    return Material(name=name, k_in_plane=k, k_through=k, density=1000.0, specific_heat=500.0, emissivity=0.9)


def test_import_materials_adds_new_material():
    existing = {"MatA": _make_material("MatA")}
    incoming = {"MatB": _make_material("MatB")}
    builtin_names: set[str] = set()

    merged, renamed = import_materials(existing, incoming, builtin_names)
    assert "MatB" in merged
    assert renamed == []


def test_import_materials_renames_on_conflict_with_existing():
    existing = {"MatA": _make_material("MatA")}
    incoming = {"MatA": _make_material("MatA", k=5.0)}
    builtin_names: set[str] = set()

    merged, renamed = import_materials(existing, incoming, builtin_names)
    assert "MatA" in merged
    assert merged["MatA"].k_in_plane == pytest.approx(1.0)  # original preserved
    assert "MatA_imported" in merged
    assert merged["MatA_imported"].k_in_plane == pytest.approx(5.0)
    assert len(renamed) == 1
    assert "MatA" in renamed[0]


def test_import_materials_renames_on_conflict_with_builtin():
    existing: dict = {}
    incoming = {"Copper": _make_material("Copper", k=1.0)}
    builtin_names = {"Copper", "Aluminum"}

    merged, renamed = import_materials(existing, incoming, builtin_names)
    assert "Copper_imported" in merged
    assert len(renamed) == 1


def test_import_materials_handles_imported_suffix_collision():
    """If Name_imported also conflicts, tries Name_imported_2."""
    existing = {
        "MatA": _make_material("MatA"),
        "MatA_imported": _make_material("MatA_imported"),
    }
    incoming = {"MatA": _make_material("MatA", k=7.0)}
    builtin_names: set[str] = set()

    merged, renamed = import_materials(existing, incoming, builtin_names)
    assert "MatA_imported_2" in merged
    assert merged["MatA_imported_2"].k_in_plane == pytest.approx(7.0)


def test_import_materials_does_not_modify_original_existing():
    existing = {"MatA": _make_material("MatA")}
    incoming = {"MatB": _make_material("MatB")}
    builtin_names: set[str] = set()

    original_existing = dict(existing)
    import_materials(existing, incoming, builtin_names)
    # existing should NOT be mutated (function returns a new merged dict)
    assert set(existing.keys()) == set(original_existing.keys())


# ---------------------------------------------------------------------------
# export_materials / load_materials_json
# ---------------------------------------------------------------------------

def test_export_materials_writes_valid_json():
    mats = {"MatA": _make_material("MatA", k=2.5)}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    try:
        export_materials(mats, path)
        with open(path) as fh:
            data = json.load(fh)
        assert "MatA" in data
    finally:
        path.unlink(missing_ok=True)


def test_load_materials_json_reads_exported_file():
    mats = {"MatA": _make_material("MatA", k=2.5)}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    try:
        export_materials(mats, path)
        loaded = load_materials_json(path)
        assert "MatA" in loaded
        assert isinstance(loaded["MatA"], Material)
        assert loaded["MatA"].k_in_plane == pytest.approx(2.5)
    finally:
        path.unlink(missing_ok=True)


def test_export_load_round_trip_preserves_all_fields():
    mat = Material("TestMat", k_in_plane=3.0, k_through=1.5, density=2000.0,
                   specific_heat=800.0, emissivity=0.85)
    mats = {"TestMat": mat}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    try:
        export_materials(mats, path)
        loaded = load_materials_json(path)
        restored = loaded["TestMat"]
        assert restored.k_in_plane == pytest.approx(3.0)
        assert restored.k_through == pytest.approx(1.5)
        assert restored.density == pytest.approx(2000.0)
        assert restored.specific_heat == pytest.approx(800.0)
        assert restored.emissivity == pytest.approx(0.85)
    finally:
        path.unlink(missing_ok=True)
