"""Tests for the parametric display stack generator.

TDD: these tests are written first, before the implementation exists.
They define the exact contract for generate_eled() and generate_dled().
"""

from __future__ import annotations

import pytest

from thermal_sim.generators.stack_generator import (
    DledParams,
    EdgeLedConfig,
    EledParams,
    OpticalFilm,
    generate_dled,
    generate_eled,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_eled_params() -> EledParams:
    return EledParams(panel_w=0.400, panel_d=0.300)


def _default_dled_params() -> DledParams:
    return DledParams(panel_w=0.360, panel_d=0.240)


def _aabb_overlap(b1, b2) -> bool:
    """Return True if two AssemblyBlocks overlap (not just touch)."""
    # Overlap in all 3 axes
    x_overlap = b1.x < b2.x + b2.width and b2.x < b1.x + b1.width
    y_overlap = b1.y < b2.y + b2.depth and b2.y < b1.y + b1.depth
    z_overlap = b1.z < b2.z + b2.height and b2.z < b1.z + b1.height
    return x_overlap and y_overlap and z_overlap


# ---------------------------------------------------------------------------
# ELED — z-stack order
# ---------------------------------------------------------------------------

class TestEledZStack:
    def test_back_cover_at_z0(self):
        project = generate_eled(_default_eled_params())
        back = next(b for b in project.blocks if "Back Cover" in b.name)
        assert back.z == pytest.approx(0.0)

    def test_z_order_back_cover_below_frame_below_lgp_below_panel(self):
        project = generate_eled(_default_eled_params())
        blocks = {b.name: b for b in project.blocks}

        back_cover = next(b for b in project.blocks if "Back Cover" in b.name)
        frame_back = next(b for b in project.blocks if "Frame Back" in b.name)
        lgp = next(b for b in project.blocks if b.name == "LGP")
        panel = next(b for b in project.blocks if b.name == "Panel")

        assert back_cover.z < frame_back.z + frame_back.height
        assert frame_back.z < lgp.z
        assert lgp.z < panel.z

    def test_panel_at_top(self):
        project = generate_eled(_default_eled_params())
        panel = next(b for b in project.blocks if b.name == "Panel")
        # Panel must be the topmost block
        top_z = max(b.z + b.height for b in project.blocks)
        assert (panel.z + panel.height) == pytest.approx(top_z)

    def test_panel_uses_correct_material(self):
        project = generate_eled(_default_eled_params())
        panel = next(b for b in project.blocks if b.name == "Panel")
        assert panel.material == "LCD Glass"

    def test_lgp_uses_correct_material(self):
        project = generate_eled(_default_eled_params())
        lgp = next(b for b in project.blocks if b.name == "LGP")
        assert lgp.material == "PMMA / LGP"


# ---------------------------------------------------------------------------
# ELED — frame tray geometry
# ---------------------------------------------------------------------------

class TestEledFrameTray:
    def _get_frame_blocks(self, project):
        return [b for b in project.blocks if b.name.startswith("Frame")]

    def test_frame_has_5_blocks(self):
        project = generate_eled(_default_eled_params())
        frame_blocks = self._get_frame_blocks(project)
        assert len(frame_blocks) == 5

    def test_frame_back_plate_full_footprint(self):
        params = _default_eled_params()
        project = generate_eled(params)
        back_plate = next(b for b in project.blocks if b.name == "Frame Back")
        assert back_plate.width == pytest.approx(params.panel_w)
        assert back_plate.depth == pytest.approx(params.panel_d)

    def test_frame_no_overlap_between_walls(self):
        project = generate_eled(_default_eled_params())
        frame_blocks = self._get_frame_blocks(project)
        for i, b1 in enumerate(frame_blocks):
            for j, b2 in enumerate(frame_blocks):
                if i >= j:
                    continue
                assert not _aabb_overlap(b1, b2), (
                    f"Frame blocks overlap: '{b1.name}' and '{b2.name}'"
                )

    def test_frame_left_wall_full_depth(self):
        params = _default_eled_params()
        project = generate_eled(params)
        left_wall = next(b for b in project.blocks if b.name == "Frame Left")
        assert left_wall.x == pytest.approx(0.0)
        assert left_wall.depth == pytest.approx(params.panel_d)
        assert left_wall.width == pytest.approx(params.frame_wall_t)

    def test_frame_right_wall_at_right_edge(self):
        params = _default_eled_params()
        project = generate_eled(params)
        right_wall = next(b for b in project.blocks if b.name == "Frame Right")
        assert right_wall.x == pytest.approx(params.panel_w - params.frame_wall_t)

    def test_frame_front_back_walls_inset(self):
        params = _default_eled_params()
        project = generate_eled(params)
        front_wall = next(b for b in project.blocks if b.name == "Frame Front")
        back_wall = next(b for b in project.blocks if b.name == "Frame Back Wall")
        # Must be inset by wall_t from left/right
        assert front_wall.x == pytest.approx(params.frame_wall_t)
        assert front_wall.width == pytest.approx(params.panel_w - 2 * params.frame_wall_t)
        assert back_wall.x == pytest.approx(params.frame_wall_t)

    def test_frame_correct_material(self):
        params = _default_eled_params()
        project = generate_eled(params)
        frame_blocks = self._get_frame_blocks(project)
        for b in frame_blocks:
            assert b.material == params.frame_material


# ---------------------------------------------------------------------------
# ELED — LED placement
# ---------------------------------------------------------------------------

class TestEledLedPlacement:
    def _make_led_config(self, count=4) -> EdgeLedConfig:
        return EdgeLedConfig(
            count=count,
            led_width=0.004,
            led_depth=0.003,
            led_height=0.001,
            power_per_led=0.5,
            margin=0.010,
        )

    def test_no_leds_when_no_edge_selected(self):
        params = _default_eled_params()
        project = generate_eled(params)
        led_blocks = [b for b in project.blocks if b.name.startswith("LED")]
        assert len(led_blocks) == 0

    def test_left_edge_produces_leds_and_pcb(self):
        params = _default_eled_params()
        params = EledParams(
            panel_w=params.panel_w,
            panel_d=params.panel_d,
            led_left=self._make_led_config(count=4),
        )
        project = generate_eled(params)
        left_leds = [b for b in project.blocks if "LED-L-" in b.name]
        assert len(left_leds) == 4

        pcb = next((b for b in project.blocks if b.name == "PCB Left"), None)
        assert pcb is not None

    def test_led_naming_convention_left(self):
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=self._make_led_config(count=3),
        )
        project = generate_eled(params)
        names = {b.name for b in project.blocks if "LED-L-" in b.name}
        assert names == {"LED-L-0", "LED-L-1", "LED-L-2"}

    def test_led_naming_convention_right(self):
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_right=self._make_led_config(count=2),
        )
        project = generate_eled(params)
        names = {b.name for b in project.blocks if "LED-R-" in b.name}
        assert names == {"LED-R-0", "LED-R-1"}

    def test_led_naming_convention_top_bottom(self):
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_top=self._make_led_config(count=2),
            led_bottom=self._make_led_config(count=2),
        )
        project = generate_eled(params)
        top_names = {b.name for b in project.blocks if "LED-T-" in b.name}
        bot_names = {b.name for b in project.blocks if "LED-B-" in b.name}
        assert top_names == {"LED-T-0", "LED-T-1"}
        assert bot_names == {"LED-B-0", "LED-B-1"}

    def test_led_at_lgp_z_level(self):
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=self._make_led_config(count=2),
        )
        project = generate_eled(params)
        lgp = next(b for b in project.blocks if b.name == "LGP")
        leds = [b for b in project.blocks if "LED-L-" in b.name]
        # LED center should be within LGP z range
        lgp_center_z = lgp.z + lgp.height / 2
        for led in leds:
            led_center_z = led.z + led.height / 2
            assert lgp.z <= led_center_z <= lgp.z + lgp.height, (
                f"LED z_center {led_center_z:.4f} not within LGP z=[{lgp.z:.4f}, {lgp.z + lgp.height:.4f}]"
            )

    def test_led_faces_inward_x_position(self):
        """Left LEDs must be at x = wall_t + pcb_thickness (inner face of PCB)."""
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=self._make_led_config(count=1),
        )
        project = generate_eled(params)
        pcb = next(b for b in project.blocks if b.name == "PCB Left")
        led = next(b for b in project.blocks if b.name == "LED-L-0")
        # LED must start at the inner face of PCB
        assert led.x == pytest.approx(pcb.x + pcb.width)

    def test_led_pitch_uniform_within_margin(self):
        count = 4
        margin = 0.010
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=EdgeLedConfig(
                count=count,
                led_width=0.004,
                led_depth=0.003,
                led_height=0.001,
                power_per_led=0.5,
                margin=margin,
            ),
        )
        project = generate_eled(params)
        leds = sorted(
            [b for b in project.blocks if "LED-L-" in b.name],
            key=lambda b: b.name,
        )
        # All LEDs should be within usable strip (margin to panel_d - margin)
        for led in leds:
            led_y_center = led.y + led.depth / 2
            assert led_y_center >= margin - 1e-9
            assert led_y_center <= params.panel_d - margin + 1e-9

    def test_led_power_set(self):
        power = 0.75
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=EdgeLedConfig(
                count=2, led_width=0.004, led_depth=0.003, led_height=0.001,
                power_per_led=power, margin=0.010,
            ),
        )
        project = generate_eled(params)
        leds = [b for b in project.blocks if "LED-L-" in b.name]
        for led in leds:
            assert led.power_w == pytest.approx(power)

    def test_all_four_edges(self):
        cfg = self._make_led_config(count=2)
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=cfg, led_right=cfg, led_top=cfg, led_bottom=cfg,
        )
        project = generate_eled(params)
        for prefix in ("LED-L-", "LED-R-", "LED-T-", "LED-B-"):
            leds = [b for b in project.blocks if prefix in b.name]
            assert len(leds) == 2, f"Expected 2 LEDs for {prefix}"


# ---------------------------------------------------------------------------
# ELED — optical films
# ---------------------------------------------------------------------------

class TestEledOpticalFilms:
    def test_no_optical_films_by_default(self):
        project = generate_eled(_default_eled_params())
        film_blocks = [b for b in project.blocks if "Film" in b.name]
        assert len(film_blocks) == 0

    def test_optical_films_stacked_above_lgp(self):
        film_mat = "Diffuser / Prism Film Stack (effective)"
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            optical_films=[
                OpticalFilm(material=film_mat, thickness=0.0005),
                OpticalFilm(material=film_mat, thickness=0.0005),
            ],
        )
        project = generate_eled(params)
        films = [b for b in project.blocks if "Film" in b.name]
        assert len(films) == 2

        lgp = next(b for b in project.blocks if b.name == "LGP")
        lgp_top = lgp.z + lgp.height
        for f in films:
            assert f.z >= lgp_top - 1e-9, f"Film at z={f.z:.6f} but LGP top={lgp_top:.6f}"

    def test_optical_films_below_panel(self):
        film_mat = "Diffuser / Prism Film Stack (effective)"
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            optical_films=[OpticalFilm(material=film_mat, thickness=0.0005)],
        )
        project = generate_eled(params)
        film = next(b for b in project.blocks if "Film" in b.name)
        panel = next(b for b in project.blocks if b.name == "Panel")
        assert film.z + film.height <= panel.z + 1e-9

    def test_optical_film_correct_thickness(self):
        film_mat = "Diffuser / Prism Film Stack (effective)"
        thickness = 0.0007
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            optical_films=[OpticalFilm(material=film_mat, thickness=thickness)],
        )
        project = generate_eled(params)
        film = next(b for b in project.blocks if "Film" in b.name)
        assert film.height == pytest.approx(thickness)


# ---------------------------------------------------------------------------
# DLED — z-stack order
# ---------------------------------------------------------------------------

class TestDledZStack:
    def test_back_cover_at_z0(self):
        project = generate_dled(_default_dled_params())
        back = next(b for b in project.blocks if "Back Cover" in b.name)
        assert back.z == pytest.approx(0.0)

    def test_z_order_bottom_to_top(self):
        project = generate_dled(_default_dled_params())
        back_cover = next(b for b in project.blocks if "Back Cover" in b.name)
        reflector = next(b for b in project.blocks if b.name == "Reflector")
        pcb = next(b for b in project.blocks if b.name == "PCB")
        diffuser = next(b for b in project.blocks if b.name == "Diffuser")
        panel = next(b for b in project.blocks if b.name == "Panel")

        assert back_cover.z < reflector.z
        assert reflector.z < pcb.z
        assert pcb.z < diffuser.z
        assert diffuser.z < panel.z

    def test_panel_at_top(self):
        project = generate_dled(_default_dled_params())
        panel = next(b for b in project.blocks if b.name == "Panel")
        top_z = max(b.z + b.height for b in project.blocks)
        assert (panel.z + panel.height) == pytest.approx(top_z)

    def test_panel_correct_material(self):
        project = generate_dled(_default_dled_params())
        panel = next(b for b in project.blocks if b.name == "Panel")
        assert panel.material == "LCD Glass"

    def test_diffuser_correct_material(self):
        project = generate_dled(_default_dled_params())
        diffuser = next(b for b in project.blocks if b.name == "Diffuser")
        assert diffuser.material == "PC"


# ---------------------------------------------------------------------------
# DLED — frame tray geometry (same pattern as ELED)
# ---------------------------------------------------------------------------

class TestDledFrameTray:
    def _get_frame_blocks(self, project):
        return [b for b in project.blocks if b.name.startswith("Frame")]

    def test_frame_has_5_blocks(self):
        project = generate_dled(_default_dled_params())
        frame_blocks = self._get_frame_blocks(project)
        assert len(frame_blocks) == 5

    def test_frame_no_overlap(self):
        project = generate_dled(_default_dled_params())
        frame_blocks = self._get_frame_blocks(project)
        for i, b1 in enumerate(frame_blocks):
            for j, b2 in enumerate(frame_blocks):
                if i >= j:
                    continue
                assert not _aabb_overlap(b1, b2), (
                    f"Frame blocks overlap: '{b1.name}' and '{b2.name}'"
                )


# ---------------------------------------------------------------------------
# DLED — LED grid placement
# ---------------------------------------------------------------------------

class TestDledLedGrid:
    def test_default_grid_count(self):
        params = _default_dled_params()
        project = generate_dled(params)
        leds = [b for b in project.blocks if b.name.startswith("LED-R")]
        assert len(leds) == params.led_rows * params.led_cols

    def test_led_naming_convention(self):
        params = DledParams(panel_w=0.360, panel_d=0.240, led_rows=2, led_cols=3)
        project = generate_dled(params)
        names = {b.name for b in project.blocks if b.name.startswith("LED-R")}
        expected = {f"LED-R{r}C{c}" for r in range(2) for c in range(3)}
        assert names == expected

    def test_1x1_grid_single_led_at_offset(self):
        offset_x = 0.050
        offset_y = 0.040
        params = DledParams(
            panel_w=0.360, panel_d=0.240,
            led_rows=1, led_cols=1,
            led_offset_x=offset_x, led_offset_y=offset_y,
            led_width=0.003, led_depth=0.003,
        )
        project = generate_dled(params)
        leds = [b for b in project.blocks if b.name.startswith("LED-R")]
        assert len(leds) == 1
        led = leds[0]
        # x = offset_x + 0 * pitch_x - led_w/2
        expected_x = offset_x - params.led_width / 2
        expected_y = offset_y - params.led_depth / 2
        assert led.x == pytest.approx(expected_x)
        assert led.y == pytest.approx(expected_y)

    def test_led_sits_on_pcb_top_face(self):
        project = generate_dled(_default_dled_params())
        pcb = next(b for b in project.blocks if b.name == "PCB")
        pcb_top = pcb.z + pcb.height
        leds = [b for b in project.blocks if b.name.startswith("LED-R")]
        for led in leds:
            assert led.z == pytest.approx(pcb_top), (
                f"LED {led.name} z={led.z:.6f} != PCB top={pcb_top:.6f}"
            )

    def test_led_power_set(self):
        power = 0.4
        params = DledParams(panel_w=0.360, panel_d=0.240, led_power=power, led_rows=2, led_cols=2)
        project = generate_dled(params)
        leds = [b for b in project.blocks if b.name.startswith("LED-R")]
        for led in leds:
            assert led.power_w == pytest.approx(power)

    def test_led_pitch_spacing(self):
        params = DledParams(
            panel_w=0.360, panel_d=0.240,
            led_rows=1, led_cols=3,
            led_pitch_x=0.060,
            led_offset_x=0.060,
            led_width=0.003,
        )
        project = generate_dled(params)
        leds = sorted(
            [b for b in project.blocks if b.name.startswith("LED-R0")],
            key=lambda b: b.x,
        )
        assert len(leds) == 3
        # Pitch between consecutive LED x-centers should equal led_pitch_x
        centers = [led.x + led.width / 2 for led in leds]
        for i in range(1, len(centers)):
            assert centers[i] - centers[i - 1] == pytest.approx(params.led_pitch_x)


# ---------------------------------------------------------------------------
# Boundary conditions — deduplication
# ---------------------------------------------------------------------------

class TestBoundaryGroups:
    def test_all_same_bc_produces_one_group(self):
        """When all 6 faces share identical BC, one BoundaryGroup with all faces."""
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            bc_top=(8.0, True), bc_bottom=(8.0, True),
            bc_front=(8.0, True), bc_back=(8.0, True),
            bc_left=(8.0, True), bc_right=(8.0, True),
        )
        project = generate_eled(params)
        total_faces = sum(len(bg.faces) for bg in project.boundary_groups)
        assert total_faces == 6, f"Expected 6 total faces, got {total_faces}"
        # All identical — should collapse to 1 group
        assert len(project.boundary_groups) == 1

    def test_different_bottom_bc_produces_two_groups(self):
        """Top and sides identical, bottom different — 2 BoundaryGroups."""
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            bc_top=(8.0, True), bc_bottom=(25.0, True),
            bc_front=(8.0, True), bc_back=(8.0, True),
            bc_left=(8.0, True), bc_right=(8.0, True),
        )
        project = generate_eled(params)
        assert len(project.boundary_groups) == 2

    def test_boundary_h_values_correct(self):
        h_top = 15.0
        h_bottom = 3.0
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            bc_top=(h_top, True),
            bc_bottom=(h_bottom, True),
            bc_front=(h_top, True),
            bc_back=(h_top, True),
            bc_left=(h_top, True),
            bc_right=(h_top, True),
        )
        project = generate_eled(params)
        # Collect all BoundaryGroups and their h values
        h_values = {bg.boundary.convection_h for bg in project.boundary_groups}
        assert h_top in h_values
        assert h_bottom in h_values

    def test_ambient_temperature_propagated(self):
        ambient = 40.0
        params = EledParams(panel_w=0.400, panel_d=0.300, ambient_c=ambient)
        project = generate_eled(params)
        for bg in project.boundary_groups:
            assert bg.boundary.ambient_c == pytest.approx(ambient)


# ---------------------------------------------------------------------------
# Materials dictionary
# ---------------------------------------------------------------------------

class TestMaterialsDict:
    def test_eled_all_materials_present(self):
        project = generate_eled(_default_eled_params())
        for block in project.blocks:
            assert block.material in project.materials, (
                f"Block '{block.name}' uses material '{block.material}' "
                f"not in project.materials"
            )

    def test_dled_all_materials_present(self):
        project = generate_dled(_default_dled_params())
        for block in project.blocks:
            assert block.material in project.materials, (
                f"Block '{block.name}' uses material '{block.material}' "
                f"not in project.materials"
            )

    def test_led_package_material_created_inline(self):
        """LED Package is not in builtins — must be created inline."""
        params = EledParams(
            panel_w=0.400, panel_d=0.300,
            led_left=EdgeLedConfig(
                count=1, led_width=0.004, led_depth=0.003, led_height=0.001,
                power_per_led=0.5, margin=0.010,
            ),
        )
        project = generate_eled(params)
        assert "LED Package" in project.materials
        mat = project.materials["LED Package"]
        assert mat.k_in_plane == pytest.approx(20.0)

    def test_eled_materials_are_material_instances(self):
        from thermal_sim.models.material import Material
        project = generate_eled(_default_eled_params())
        for name, mat in project.materials.items():
            assert isinstance(mat, Material), f"'{name}' is not a Material instance"


# ---------------------------------------------------------------------------
# VoxelProject structural completeness
# ---------------------------------------------------------------------------

class TestVoxelProjectStructure:
    def test_eled_returns_voxel_project(self):
        from thermal_sim.models.voxel_project import VoxelProject
        project = generate_eled(_default_eled_params())
        assert isinstance(project, VoxelProject)

    def test_dled_returns_voxel_project(self):
        from thermal_sim.models.voxel_project import VoxelProject
        project = generate_dled(_default_dled_params())
        assert isinstance(project, VoxelProject)

    def test_eled_has_probes(self):
        project = generate_eled(_default_eled_params())
        assert len(project.probes) >= 2

    def test_dled_has_probes(self):
        project = generate_dled(_default_dled_params())
        assert len(project.probes) >= 2

    def test_eled_mesh_config_set(self):
        params = EledParams(panel_w=0.400, panel_d=0.300, max_cell_size=0.003)
        project = generate_eled(params)
        assert project.mesh_config.max_cell_size == pytest.approx(0.003)

    def test_dled_mesh_config_set(self):
        params = DledParams(panel_w=0.360, panel_d=0.240, max_cell_size=0.004)
        project = generate_dled(params)
        assert project.mesh_config.max_cell_size == pytest.approx(0.004)

    def test_eled_to_dict_roundtrip(self):
        """VoxelProject.to_dict() must not raise and must round-trip."""
        from thermal_sim.models.voxel_project import VoxelProject
        project = generate_eled(_default_eled_params())
        d = project.to_dict()
        project2 = VoxelProject.from_dict(d)
        assert project2.name == project.name
        assert len(project2.blocks) == len(project.blocks)

    def test_dled_to_dict_roundtrip(self):
        from thermal_sim.models.voxel_project import VoxelProject
        project = generate_dled(_default_dled_params())
        d = project.to_dict()
        project2 = VoxelProject.from_dict(d)
        assert project2.name == project.name
        assert len(project2.blocks) == len(project.blocks)

    def test_no_qt_imports_in_generator(self):
        """Ensure stack_generator.py has no Qt imports (pure Python)."""
        import importlib.util
        import ast
        import pathlib

        gen_path = pathlib.Path("thermal_sim/generators/stack_generator.py")
        if not gen_path.exists():
            pytest.skip("Generator file not yet created")

        source = gen_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                for name in names:
                    assert "Qt" not in name and "PySide" not in name and "PyQt" not in name, (
                        f"Qt import found in stack_generator.py: {name}"
                    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_eled_zero_edges_no_leds(self):
        params = _default_eled_params()
        project = generate_eled(params)
        led_blocks = [b for b in project.blocks if b.name.startswith("LED")]
        pcb_blocks = [b for b in project.blocks if b.name.startswith("PCB")]
        assert len(led_blocks) == 0
        assert len(pcb_blocks) == 0

    def test_dled_1x1_grid(self):
        params = DledParams(
            panel_w=0.360, panel_d=0.240,
            led_rows=1, led_cols=1,
        )
        project = generate_dled(params)
        leds = [b for b in project.blocks if b.name.startswith("LED-R")]
        assert len(leds) == 1

    def test_eled_reflector_inner_dims(self):
        """Reflector must be inset by frame_wall_t on all sides."""
        params = _default_eled_params()
        project = generate_eled(params)
        reflector = next(b for b in project.blocks if b.name == "Reflector")
        assert reflector.x == pytest.approx(params.frame_wall_t)
        assert reflector.y == pytest.approx(params.frame_wall_t)
        expected_w = params.panel_w - 2 * params.frame_wall_t
        expected_d = params.panel_d - 2 * params.frame_wall_t
        assert reflector.width == pytest.approx(expected_w)
        assert reflector.depth == pytest.approx(expected_d)

    def test_dled_pcb_inner_dims(self):
        """PCB must be inset by frame_wall_t on all sides."""
        params = _default_dled_params()
        project = generate_dled(params)
        pcb = next(b for b in project.blocks if b.name == "PCB")
        assert pcb.x == pytest.approx(params.frame_wall_t)
        assert pcb.y == pytest.approx(params.frame_wall_t)
