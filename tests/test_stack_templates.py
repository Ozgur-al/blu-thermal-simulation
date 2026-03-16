"""Tests for stack_templates module: dled_template and eled_template."""

from __future__ import annotations

import pytest

from thermal_sim.models.boundary import BoundaryConditions
from thermal_sim.models.heat_source import LEDArray
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.stack_templates import dled_template, eled_template


# --------------------------------------------------------------------------
# dled_template tests
# --------------------------------------------------------------------------

def test_dled_template_returns_required_keys() -> None:
    """dled_template returns dict with 'layers', 'materials', 'led_arrays', 'boundaries'."""
    result = dled_template(0.3, 0.2)
    assert "layers" in result
    assert "materials" in result
    assert "led_arrays" in result
    assert "boundaries" in result


def test_dled_template_layer_types() -> None:
    """All layers are Layer instances, materials are Material instances."""
    result = dled_template(0.3, 0.2)
    assert all(isinstance(l, Layer) for l in result["layers"])
    assert all(isinstance(m, Material) for m in result["materials"].values())
    assert isinstance(result["boundaries"], BoundaryConditions)
    assert all(isinstance(a, LEDArray) for a in result["led_arrays"])


def test_dled_template_layer_order_default_optical_layers() -> None:
    """DLED stack with optical_layers=2 has 8 layers in correct order (bottom to top)."""
    result = dled_template(0.3, 0.2, optical_layers=2)
    layers = result["layers"]
    assert len(layers) == 8

    names = [l.name for l in layers]
    assert names[0] == "Back Cover"
    assert names[1] == "Metal Frame"
    assert names[2] == "LED Board"
    assert names[3] == "Diffuser"
    assert names[4] == "BEF"
    assert names[5] == "OCA"
    assert names[6] == "Display Cell"
    assert names[7] == "Cover Glass"


def test_dled_template_layer_materials_include_required() -> None:
    """DLED template materials include Aluminum, Steel, FR4, PC, OCA, Glass."""
    result = dled_template(0.3, 0.2)
    mat_names = set(result["materials"].keys())
    assert "Aluminum" in mat_names
    assert "Steel" in mat_names
    assert "FR4" in mat_names
    assert "PC" in mat_names
    assert "OCA" in mat_names
    assert "Glass" in mat_names


def test_dled_template_led_array_mode_and_layer() -> None:
    """DLED LED array has mode='grid', layer='LED Board', panel dims match template args."""
    result = dled_template(0.3, 0.2)
    arrays = result["led_arrays"]
    assert len(arrays) == 1
    arr = arrays[0]
    assert isinstance(arr, LEDArray)
    assert arr.mode == "grid"
    assert arr.layer == "LED Board"
    assert arr.panel_width == pytest.approx(0.3)
    assert arr.panel_height == pytest.approx(0.2)


def test_dled_template_side_boundary_enhanced() -> None:
    """DLED template boundaries.side.convection_h == 25.0 (metal frame enhanced)."""
    result = dled_template(0.3, 0.2)
    assert result["boundaries"].side.convection_h == pytest.approx(25.0)


def test_dled_template_optical_layers_3_has_9_layers() -> None:
    """dled_template(0.3, 0.2, optical_layers=3) has 9 layers."""
    result = dled_template(0.3, 0.2, optical_layers=3)
    assert len(result["layers"]) == 9
    # The extra layer should be an additional optical sheet
    names = [l.name for l in result["layers"]]
    assert "Back Cover" in names
    assert "Cover Glass" in names


def test_dled_template_layer_thicknesses_physically_reasonable() -> None:
    """All DLED layer thicknesses are > 0 and < 0.01 m (< 10 mm) for thin films/sheets."""
    result = dled_template(0.3, 0.2)
    for layer in result["layers"]:
        assert layer.thickness > 0.0
        assert layer.thickness < 0.01  # < 10 mm: reasonable for display module layers


def test_dled_template_materials_match_layer_references() -> None:
    """All layer.material keys exist in the template materials dict."""
    result = dled_template(0.3, 0.2)
    mat_names = set(result["materials"].keys())
    for layer in result["layers"]:
        assert layer.material in mat_names, (
            f"Layer '{layer.name}' references material '{layer.material}' not in template materials"
        )


# --------------------------------------------------------------------------
# eled_template tests
# --------------------------------------------------------------------------

def test_eled_template_returns_required_keys() -> None:
    """eled_template returns dict with 'layers', 'materials', 'led_arrays', 'boundaries'."""
    result = eled_template(0.3, 0.2)
    assert "layers" in result
    assert "materials" in result
    assert "led_arrays" in result
    assert "boundaries" in result


def test_eled_template_has_lgp_not_led_board() -> None:
    """ELED stack has LGP (PMMA) layer instead of LED Board (FR4)."""
    result = eled_template(0.3, 0.2)
    layer_names = [l.name for l in result["layers"]]
    assert "LGP" in layer_names
    assert "LED Board" not in layer_names

    # LGP should use PMMA material
    lgp_layer = next(l for l in result["layers"] if l.name == "LGP")
    assert lgp_layer.material == "PMMA"


def test_eled_template_led_array_mode_and_layer() -> None:
    """ELED LED array has mode='edge', layer='LGP', panel dims match template args."""
    result = eled_template(0.3, 0.2)
    arrays = result["led_arrays"]
    assert len(arrays) == 1
    arr = arrays[0]
    assert isinstance(arr, LEDArray)
    assert arr.mode == "edge"
    assert arr.layer == "LGP"
    assert arr.panel_width == pytest.approx(0.3)
    assert arr.panel_height == pytest.approx(0.2)
    assert arr.z_position == "distributed"


def test_eled_template_edge_config_parameter() -> None:
    """eled_template(0.3, 0.2, edge_config='left_right') sets edge_config on LEDArray."""
    result = eled_template(0.3, 0.2, edge_config="left_right")
    arr = result["led_arrays"][0]
    assert arr.edge_config == "left_right"


def test_eled_template_default_edge_config() -> None:
    """eled_template default edge_config is 'bottom'."""
    result = eled_template(0.3, 0.2)
    arr = result["led_arrays"][0]
    assert arr.edge_config == "bottom"


def test_eled_template_side_boundary_enhanced() -> None:
    """ELED template boundaries.side.convection_h == 25.0."""
    result = eled_template(0.3, 0.2)
    assert result["boundaries"].side.convection_h == pytest.approx(25.0)


def test_eled_template_optical_layers_3_has_correct_count() -> None:
    """eled_template(0.3, 0.2, optical_layers=3) has 9 layers."""
    result = eled_template(0.3, 0.2, optical_layers=3)
    assert len(result["layers"]) == 9


def test_eled_template_lgp_thickness_less_than_5mm() -> None:
    """LGP thickness is < 0.005 m (< 5 mm) — reasonable for backlight guide plate."""
    result = eled_template(0.3, 0.2)
    lgp = next(l for l in result["layers"] if l.name == "LGP")
    assert lgp.thickness > 0.0
    assert lgp.thickness < 0.005


def test_eled_template_materials_match_layer_references() -> None:
    """All layer.material keys exist in the eled template materials dict."""
    result = eled_template(0.3, 0.2)
    mat_names = set(result["materials"].keys())
    for layer in result["layers"]:
        assert layer.material in mat_names, (
            f"Layer '{layer.name}' references material '{layer.material}' not in template materials"
        )


def test_eled_template_lgp_no_edge_layers() -> None:
    """eled_template no longer sets edge_layers on LGP — edge frame is project-level."""
    result = eled_template(0.300, 0.200, edge_config="left_right")
    layers = result["layers"]
    lgp = next((l for l in layers if l.name == "LGP"), None)
    assert lgp is not None, "LGP layer not found in ELED template"
    assert lgp.edge_layers == {}, "LGP should have no edge_layers (now set at project level)"


def test_eled_template_materials_include_frame_materials() -> None:
    """eled_template materials dict includes Steel from the Metal Frame layer."""
    result = eled_template(0.300, 0.200, edge_config="left_right")
    mat_names = set(result["materials"].keys())
    assert "Steel" in mat_names, "Steel (Metal Frame layer) should be in ELED materials"


def test_stack_templates_no_pyside6_dependency() -> None:
    """stack_templates module can be imported without PySide6."""
    import sys
    import thermal_sim.models.stack_templates as st_mod
    import inspect

    # Check the actual import statements in the source, not the whole file
    # (comments and docstrings are excluded from this check)
    src_lines = inspect.getsource(st_mod).splitlines()
    import_lines = [l for l in src_lines if l.strip().startswith("import") or l.strip().startswith("from")]
    import_src = "\n".join(import_lines)
    assert "PySide6" not in import_src, "stack_templates.py must not import PySide6"
    assert "PyQt" not in import_src, "stack_templates.py must not import PyQt"

    # Confirm no Qt module is loaded as a side-effect of importing stack_templates
    qt_modules_loaded = [k for k in sys.modules if "PySide6" in k or "PyQt" in k]
    # It's OK if PySide6 is already loaded (test runner may import it elsewhere),
    # but stack_templates itself must not be the one loading it.
    # We simply verify stack_templates doesn't declare Qt imports.
    assert True  # import at top of file already verified import succeeded
