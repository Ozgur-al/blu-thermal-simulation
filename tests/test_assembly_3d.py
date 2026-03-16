"""Smoke tests for Assembly3DWidget (offscreen, no GPU required).

build_assembly_blocks() tests run unconditionally.
Widget tests require VTK rendering — skipped if render window cannot initialise
(common in headless / background environments on Windows).
"""
from __future__ import annotations

import pytest

import pyvista as pv  # noqa: E402  (OFF_SCREEN set by conftest.py)

from thermal_sim.ui.assembly_3d import build_assembly_blocks  # noqa: E402
from thermal_sim.models.project import DisplayProject  # noqa: E402
from thermal_sim.models.layer import Layer  # noqa: E402
from thermal_sim.models.material import Material  # noqa: E402
from thermal_sim.models.material_zone import MaterialZone  # noqa: E402


# ---------------------------------------------------------------------------
# Check whether VTK rendering is available in this environment
# ---------------------------------------------------------------------------

def _vtk_renderer_available() -> bool:
    """Return True if a VTK render window can be created without hanging.

    Uses a subprocess with a hard timeout so the test suite does not freeze
    in headless Windows environments where DirectX/OpenGL context creation
    blocks indefinitely.
    """
    import subprocess, sys
    script = (
        "import pyvista as pv; pv.OFF_SCREEN = True; "
        "p = pv.Plotter(off_screen=True); p.close(); print('OK')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            timeout=12,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "OK" in result.stdout
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


_VTK_RENDER_AVAILABLE = _vtk_renderer_available()

vtk_render = pytest.mark.skipif(
    not _VTK_RENDER_AVAILABLE,
    reason="VTK render window cannot initialise in this environment (headless/no GPU)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_project() -> DisplayProject:
    """Two-layer project: Aluminum bottom, Glass top."""
    return DisplayProject(
        name="test_3d",
        width=0.100,
        height=0.050,
        layers=[
            Layer(name="Bottom", material="Aluminum", thickness=0.002),
            Layer(name="Top",    material="Glass",    thickness=0.001),
        ],
        materials={
            "Aluminum": Material(
                name="Aluminum",
                k_in_plane=237.0,
                k_through=237.0,
                density=2700.0,
                specific_heat=900.0,
            ),
            "Glass": Material(
                name="Glass",
                k_in_plane=1.0,
                k_through=1.0,
                density=2500.0,
                specific_heat=840.0,
            ),
        },
    )


def _project_with_zones() -> DisplayProject:
    """Project with a material zone on the bottom layer."""
    zones = [
        MaterialZone(
            material="Glass",
            x=0.025,
            y=0.012,
            width=0.020,
            height=0.008,
        )
    ]
    layers = [
        Layer(name="Base", material="Aluminum", thickness=0.002, zones=zones),
        Layer(name="Cover", material="Glass", thickness=0.001),
    ]
    return DisplayProject(
        name="test_zones",
        width=0.100,
        height=0.050,
        layers=layers,
        materials={
            "Aluminum": Material(
                name="Aluminum",
                k_in_plane=237.0,
                k_through=237.0,
                density=2700.0,
                specific_heat=900.0,
            ),
            "Glass": Material(
                name="Glass",
                k_in_plane=1.0,
                k_through=1.0,
                density=2500.0,
                specific_heat=840.0,
            ),
        },
    )


# ---------------------------------------------------------------------------
# Tests: build_assembly_blocks (no VTK renderer needed)
# ---------------------------------------------------------------------------

class TestBuildAssemblyBlocks:
    def test_returns_one_main_block_per_layer(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        main_blocks = [b for b in blocks if not b["is_zone"]]
        assert len(main_blocks) == len(project.layers)

    def test_block_has_required_keys(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        for b in blocks:
            for key in ("mesh", "color", "label", "z_base", "layer_index", "is_zone"):
                assert key in b, f"Missing key '{key}' in block"

    def test_z_base_increases_monotonically(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        main_blocks = [b for b in blocks if not b["is_zone"]]
        z_bases = [b["z_base"] for b in main_blocks]
        assert z_bases == sorted(z_bases)

    def test_first_layer_z_base_is_zero(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        main_blocks = [b for b in blocks if not b["is_zone"]]
        assert main_blocks[0]["z_base"] == pytest.approx(0.0)

    def test_z_base_in_millimetres(self):
        """Bottom layer 2mm thick; second layer z_base should be ~2.0 mm."""
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        main_blocks = [b for b in blocks if not b["is_zone"]]
        assert main_blocks[1]["z_base"] == pytest.approx(2.0, abs=1e-6)

    def test_zone_blocks_created_for_layer_with_zones(self):
        project = _project_with_zones()
        blocks = build_assembly_blocks(project)
        zone_blocks = [b for b in blocks if b["is_zone"]]
        assert len(zone_blocks) >= 1

    def test_no_zone_blocks_for_simple_project(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        zone_blocks = [b for b in blocks if b["is_zone"]]
        assert len(zone_blocks) == 0

    def test_color_is_rgb_tuple_in_range(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        for b in blocks:
            color = b["color"]
            assert len(color) == 3
            for ch in color:
                assert 0.0 <= ch <= 1.0, f"Color channel out of range: {ch}"

    def test_label_matches_layer_name(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        main_blocks = [b for b in blocks if not b["is_zone"]]
        for layer, block in zip(project.layers, main_blocks):
            assert block["label"] == layer.name

    def test_mesh_is_pyvista_polydata(self):
        project = _minimal_project()
        blocks = build_assembly_blocks(project)
        for b in blocks:
            assert hasattr(b["mesh"], "n_cells"), "mesh should be a pyvista PolyData"


# ---------------------------------------------------------------------------
# Tests: Assembly3DWidget (require VTK renderer)
# ---------------------------------------------------------------------------

@vtk_render
class TestAssembly3DWidget:
    def setup_method(self):
        from PySide6.QtWidgets import QApplication
        self._app = QApplication.instance() or QApplication([])

    def test_widget_instantiates_offscreen(self):
        """Assembly3DWidget can be created without a live display."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        assert widget is not None
        widget.close()

    def test_update_assembly_creates_actors(self):
        """update_assembly() populates the plotter with actors for each layer."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        project = _minimal_project()
        widget.update_assembly(project)
        assert len(widget._plotter.actors) >= len(project.layers)
        widget.close()

    def test_explode_does_not_raise(self):
        """Moving the explode slider after update_assembly does not crash."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        project = _minimal_project()
        widget.update_assembly(project)
        widget._on_explode(0)
        widget._on_explode(50)
        widget._on_explode(100)
        widget._on_explode(0)
        widget.close()

    def test_update_assembly_with_zones(self):
        """update_assembly() handles a project with material zones."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        project = _project_with_zones()
        widget.update_assembly(project)
        assert len(widget._plotter.actors) >= len(project.layers)
        widget.close()

    def test_double_update_does_not_accumulate_actors(self):
        """Calling update_assembly() twice clears the previous actors."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        project = _minimal_project()
        widget.update_assembly(project)
        count_after_first = len(widget._plotter.actors)
        widget.update_assembly(project)
        count_after_second = len(widget._plotter.actors)
        assert count_after_second == count_after_first
        widget.close()

    def test_close_releases_resources(self):
        """closeEvent() does not raise even after update_assembly."""
        from thermal_sim.ui.assembly_3d import Assembly3DWidget
        widget = Assembly3DWidget()
        project = _minimal_project()
        widget.update_assembly(project)
        widget.close()
