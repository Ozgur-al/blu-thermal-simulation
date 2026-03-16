"""Parametric display stack geometry generator.

Pure Python — no Qt/PySide6 imports. Converts high-level display module
parameters (EledParams / DledParams) into complete VoxelProject objects
with all AssemblyBlocks, BoundaryGroups, and materials pre-populated.

Usage:
    from thermal_sim.generators.stack_generator import (
        EledParams, DledParams, OpticalFilm, EdgeLedConfig,
        generate_eled, generate_dled,
    )

    project = generate_eled(EledParams(panel_w=0.400, panel_d=0.300))
    project = generate_dled(DledParams(panel_w=0.360, panel_d=0.240))
"""

from __future__ import annotations

from dataclasses import dataclass, field

from thermal_sim.models.assembly_block import AssemblyBlock
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.material import Material
from thermal_sim.models.voxel_project import (
    BoundaryGroup,
    VoxelMeshConfig,
    VoxelProbe,
    VoxelProject,
)


# ---------------------------------------------------------------------------
# LED Package — custom material not in builtins
# ---------------------------------------------------------------------------

_LED_PACKAGE_MATERIAL = Material(
    name="LED Package",
    k_in_plane=20.0,
    k_through=20.0,
    density=3000.0,
    specific_heat=800.0,
    emissivity=0.5,
)


# ---------------------------------------------------------------------------
# Parameter dataclasses (all dimensions in metres)
# ---------------------------------------------------------------------------

@dataclass
class OpticalFilm:
    """A single optical film layer between LGP/diffuser top and panel bottom."""

    material: str   # key into builtin materials
    thickness: float  # metres


@dataclass
class EdgeLedConfig:
    """Configuration for LEDs on a single edge (ELED architecture)."""

    count: int
    led_width: float    # x-direction (into LGP), metres
    led_depth: float    # y-direction (along edge), metres
    led_height: float   # z-direction, metres
    power_per_led: float  # watts
    margin: float       # symmetric offset from edge ends, metres


@dataclass
class EledParams:
    """Parameters for the ELED (edge-lit) display stack generator.

    panel_w, panel_d define the outer footprint of the module.
    All thicknesses and positions are in SI metres.
    """

    panel_w: float  # total panel width (x), metres
    panel_d: float  # total panel depth (y), metres

    # Layer thicknesses (metres)
    panel_h: float = 0.0015        # 1.5 mm
    lgp_h: float = 0.004           # 4 mm
    reflector_h: float = 0.0003    # 0.3 mm
    frame_back_h: float = 0.001    # 1 mm back plate
    frame_wall_t: float = 0.004    # 4 mm wall thickness
    back_cover_h: float = 0.001    # 1 mm

    # Optical films (stacked between LGP top and panel bottom)
    optical_films: list[OpticalFilm] = field(default_factory=list)

    # LED edges (None = no LEDs on that edge)
    led_left: EdgeLedConfig | None = None
    led_right: EdgeLedConfig | None = None
    led_top: EdgeLedConfig | None = None     # y = panel_d edge
    led_bottom: EdgeLedConfig | None = None  # y = 0 edge

    # Materials (keys into builtin library)
    panel_material: str = "LCD Glass"
    lgp_material: str = "PMMA / LGP"
    reflector_material: str = "Reflector Film / PET-like Film"
    frame_material: str = "Aluminum, oxidized / rough"
    back_cover_material: str = "Aluminum, bare/shiny"
    pcb_material: str = "PCB Effective, medium copper"
    led_material: str = "LED Package"

    # Boundary conditions per face: (h_convection, include_radiation)
    bc_top: tuple[float, bool] = (8.0, True)
    bc_bottom: tuple[float, bool] = (8.0, True)
    bc_front: tuple[float, bool] = (8.0, True)
    bc_back: tuple[float, bool] = (8.0, True)
    bc_left: tuple[float, bool] = (8.0, True)
    bc_right: tuple[float, bool] = (8.0, True)
    ambient_c: float = 25.0

    # Mesh
    max_cell_size: float | None = 0.002  # 2 mm default
    cells_per_interval: int = 1


@dataclass
class DledParams:
    """Parameters for the DLED (direct-lit) display stack generator.

    panel_w, panel_d define the outer footprint of the module.
    All thicknesses and positions are in SI metres.
    """

    panel_w: float
    panel_d: float

    # Layer thicknesses (metres)
    panel_h: float = 0.0015       # 1.5 mm
    diffuser_h: float = 0.002     # 2 mm diffuser plate
    air_cavity_h: float = 0.010   # 10 mm LED cavity
    pcb_h: float = 0.0016         # 1.6 mm
    reflector_h: float = 0.0003   # 0.3 mm
    frame_back_h: float = 0.001   # 1 mm back plate
    frame_wall_t: float = 0.004   # 4 mm wall thickness
    back_cover_h: float = 0.001   # 1 mm

    # Optical films (stacked between diffuser top and panel bottom)
    optical_films: list[OpticalFilm] = field(default_factory=list)

    # LED grid
    led_rows: int = 4
    led_cols: int = 6
    led_pitch_x: float = 0.060    # 60 mm
    led_pitch_y: float = 0.060    # 60 mm
    led_width: float = 0.003      # 3 mm
    led_depth: float = 0.003      # 3 mm
    led_height: float = 0.001     # 1 mm
    led_power: float = 0.5        # 0.5 W per LED
    led_offset_x: float = 0.030   # symmetric offset from panel edge (x), metres
    led_offset_y: float = 0.030   # symmetric offset from panel edge (y), metres

    # Materials
    panel_material: str = "LCD Glass"
    diffuser_material: str = "PC"
    pcb_material: str = "PCB Effective, medium copper"
    reflector_material: str = "Reflector Film / PET-like Film"
    frame_material: str = "Aluminum, oxidized / rough"
    back_cover_material: str = "Aluminum, bare/shiny"
    led_material: str = "LED Package"

    # Boundary conditions per face
    bc_top: tuple[float, bool] = (8.0, True)
    bc_bottom: tuple[float, bool] = (8.0, True)
    bc_front: tuple[float, bool] = (8.0, True)
    bc_back: tuple[float, bool] = (8.0, True)
    bc_left: tuple[float, bool] = (8.0, True)
    bc_right: tuple[float, bool] = (8.0, True)
    ambient_c: float = 25.0

    # Mesh
    max_cell_size: float | None = 0.002
    cells_per_interval: int = 1


# ---------------------------------------------------------------------------
# Private geometry helpers
# ---------------------------------------------------------------------------

def _build_frame_tray(
    panel_w: float,
    panel_d: float,
    back_h: float,
    inner_h: float,
    wall_t: float,
    material: str,
    z_base: float,
) -> list[AssemblyBlock]:
    """Decompose a tray-shaped metal frame into 5 non-overlapping AssemblyBlocks.

    Pattern (from RESEARCH Pattern 4):
    - Back plate:  full footprint at z_base, height=back_h
    - Left wall:   x=0, full depth, z=z_base+back_h, w=wall_t
    - Right wall:  x=panel_w-wall_t, full depth
    - Front wall:  inset between left/right walls (y=0 edge), d=wall_t
    - Back wall:   inset between left/right walls (y=panel_d-wall_t edge)

    The left/right walls span full panel_d so front/back walls are inset by
    wall_t on each side to avoid corner overlap.
    """
    z_wall = z_base + back_h
    blocks = [
        # Back plate — full footprint, at z_base
        AssemblyBlock(
            "Frame Back", material,
            0.0, 0.0, z_base,
            panel_w, panel_d, back_h,
        ),
        # Left wall — full depth
        AssemblyBlock(
            "Frame Left", material,
            0.0, 0.0, z_wall,
            wall_t, panel_d, inner_h,
        ),
        # Right wall — full depth
        AssemblyBlock(
            "Frame Right", material,
            panel_w - wall_t, 0.0, z_wall,
            wall_t, panel_d, inner_h,
        ),
        # Front wall — inset (y=0 side, between left/right)
        AssemblyBlock(
            "Frame Front", material,
            wall_t, 0.0, z_wall,
            panel_w - 2 * wall_t, wall_t, inner_h,
        ),
        # Back wall — inset (y=panel_d side, between left/right)
        AssemblyBlock(
            "Frame Back Wall", material,
            wall_t, panel_d - wall_t, z_wall,
            panel_w - 2 * wall_t, wall_t, inner_h,
        ),
    ]
    return blocks


def _build_optical_films(
    films: list[OpticalFilm],
    inner_w: float,
    inner_d: float,
    wall_t: float,
    z_base: float,
) -> tuple[list[AssemblyBlock], float]:
    """Stack optical films bottom-to-top starting at z_base.

    Films span the inner footprint (offset from outer edge by wall_t).
    Returns (blocks, z_cursor_after_last_film).
    """
    blocks: list[AssemblyBlock] = []
    z = z_base
    for i, film in enumerate(films):
        blocks.append(AssemblyBlock(
            f"Film {i + 1}", film.material,
            wall_t, wall_t, z,
            inner_w, inner_d, film.thickness,
        ))
        z += film.thickness
    return blocks, z


def _build_boundary_groups(
    bc_map: dict[str, tuple[float, bool]],
    ambient_c: float,
) -> list[BoundaryGroup]:
    """Collect per-face BC tuples and deduplicate into BoundaryGroups.

    Faces with identical (h, radiation) are merged into one BoundaryGroup.
    """
    # Group faces by (h, radiation) key
    groups: dict[tuple[float, bool], list[str]] = {}
    for face, (h, rad) in bc_map.items():
        key = (h, rad)
        groups.setdefault(key, []).append(face)

    boundary_groups: list[BoundaryGroup] = []
    for (h, rad), faces in groups.items():
        name = "BC " + "+".join(faces) if len(faces) < 6 else "BC All Faces"
        boundary_groups.append(BoundaryGroup(
            name=name,
            boundary=SurfaceBoundary(
                ambient_c=ambient_c,
                convection_h=h,
                include_radiation=rad,
            ),
            faces=faces,
        ))
    return boundary_groups


def _collect_materials(
    blocks: list[AssemblyBlock],
) -> dict[str, Material]:
    """Look up each unique material name in the builtin library.

    For 'LED Package' (not in builtins), create the custom material inline.
    """
    from thermal_sim.core.material_library import load_builtin_library

    builtins = load_builtin_library()
    used_names = {b.material for b in blocks}
    materials: dict[str, Material] = {}

    for name in used_names:
        if name == "LED Package":
            materials[name] = _LED_PACKAGE_MATERIAL
        elif name in builtins:
            materials[name] = builtins[name]
        else:
            # Unknown material — create a placeholder with sensible defaults
            # so the project is still valid (rule 2: correctness)
            materials[name] = Material(
                name=name,
                k_in_plane=1.0,
                k_through=1.0,
                density=1000.0,
                specific_heat=1000.0,
                emissivity=0.9,
            )

    return materials


def _build_eled_led_strips(
    params: EledParams,
    lgp_z: float,
) -> list[AssemblyBlock]:
    """Build PCB strips and LED blocks for all active ELED edges.

    For each active edge:
    - One PCB strip adhered to the frame inner wall at LGP z-level
    - N LED blocks on the inner face of the PCB, uniformly pitched

    PCB strip thickness (x or y direction perpendicular to edge): 2mm default.
    """
    PCB_THICKNESS = 0.002  # 2mm PCB strip thickness

    blocks: list[AssemblyBlock] = []
    wall_t = params.frame_wall_t
    lgp_h = params.lgp_h

    def _add_lr_strip(cfg: EdgeLedConfig, side: str) -> None:
        """Left or right edge strip (LEDs face in x-direction)."""
        is_left = side == "left"
        prefix = "LED-L" if is_left else "LED-R"
        pcb_name = "PCB Left" if is_left else "PCB Right"

        # PCB strip: adhered to frame inner wall, spanning LGP z-height
        # Left: x = wall_t (inner face of left frame wall)
        # Right: x = panel_w - wall_t - pcb_thickness
        if is_left:
            pcb_x = wall_t
        else:
            pcb_x = params.panel_w - wall_t - PCB_THICKNESS

        # PCB depth: panel_d, y_start=0 (spans full depth, no margin needed for strip)
        pcb = AssemblyBlock(
            pcb_name, params.pcb_material,
            pcb_x, 0.0, lgp_z,
            PCB_THICKNESS, params.panel_d, lgp_h,
        )
        blocks.append(pcb)

        # LED x: inner face of PCB strip, pointing into LGP
        if is_left:
            led_x = pcb_x + PCB_THICKNESS
        else:
            led_x = pcb_x - cfg.led_width  # inner face (toward center)

        usable_d = params.panel_d - 2 * cfg.margin
        if cfg.count == 1:
            pitch = 0.0
        else:
            pitch = usable_d / (cfg.count - 1) if cfg.count > 1 else usable_d
        if cfg.count == 1:
            pitch = usable_d  # unused; center placement

        for i in range(cfg.count):
            if cfg.count == 1:
                led_y_center = cfg.margin + usable_d / 2
            else:
                led_y_center = cfg.margin + i * (usable_d / (cfg.count - 1))
            led_y = led_y_center - cfg.led_depth / 2
            led_z = lgp_z + (lgp_h - cfg.led_height) / 2  # centered on LGP height

            blocks.append(AssemblyBlock(
                f"{prefix}-{i}", params.led_material,
                led_x, led_y, led_z,
                cfg.led_width, cfg.led_depth, cfg.led_height,
                cfg.power_per_led,
            ))

    def _add_tb_strip(cfg: EdgeLedConfig, side: str) -> None:
        """Top or bottom edge strip (LEDs face in y-direction)."""
        is_bottom = side == "bottom"
        prefix = "LED-B" if is_bottom else "LED-T"
        pcb_name = "PCB Bottom" if is_bottom else "PCB Top"

        if is_bottom:
            pcb_y = wall_t
        else:
            pcb_y = params.panel_d - wall_t - PCB_THICKNESS

        pcb = AssemblyBlock(
            pcb_name, params.pcb_material,
            0.0, pcb_y, lgp_z,
            params.panel_w, PCB_THICKNESS, lgp_h,
        )
        blocks.append(pcb)

        if is_bottom:
            led_y = pcb_y + PCB_THICKNESS
        else:
            led_y = pcb_y - cfg.led_depth  # inner face

        usable_w = params.panel_w - 2 * cfg.margin
        for i in range(cfg.count):
            if cfg.count == 1:
                led_x_center = cfg.margin + usable_w / 2
            else:
                led_x_center = cfg.margin + i * (usable_w / (cfg.count - 1))
            led_x = led_x_center - cfg.led_width / 2
            led_z = lgp_z + (lgp_h - cfg.led_height) / 2

            blocks.append(AssemblyBlock(
                f"{prefix}-{i}", params.led_material,
                led_x, led_y, led_z,
                cfg.led_width, cfg.led_depth, cfg.led_height,
                cfg.power_per_led,
            ))

    if params.led_left is not None:
        _add_lr_strip(params.led_left, "left")
    if params.led_right is not None:
        _add_lr_strip(params.led_right, "right")
    if params.led_bottom is not None:
        _add_tb_strip(params.led_bottom, "bottom")
    if params.led_top is not None:
        _add_tb_strip(params.led_top, "top")

    return blocks


def _build_dled_led_grid(params: DledParams, pcb_top_z: float) -> list[AssemblyBlock]:
    """Build the DLED LED grid on top of the PCB.

    Placement formula (from RESEARCH Pattern 6):
      LED-R{r}C{c}:
        x = offset_x + c * pitch_x - led_w/2
        y = offset_y + r * pitch_y - led_d/2
        z = pcb_top_z
    """
    blocks: list[AssemblyBlock] = []
    for r in range(params.led_rows):
        for c in range(params.led_cols):
            x = params.led_offset_x + c * params.led_pitch_x - params.led_width / 2
            y = params.led_offset_y + r * params.led_pitch_y - params.led_depth / 2
            blocks.append(AssemblyBlock(
                f"LED-R{r}C{c}", params.led_material,
                x, y, pcb_top_z,
                params.led_width, params.led_depth, params.led_height,
                params.led_power,
            ))
    return blocks


def _params_to_bc_map(
    params: EledParams | DledParams,
) -> dict[str, tuple[float, bool]]:
    """Extract the per-face BC map from params."""
    return {
        "top": params.bc_top,
        "bottom": params.bc_bottom,
        "front": params.bc_front,
        "back": params.bc_back,
        "left": params.bc_left,
        "right": params.bc_right,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_eled(params: EledParams) -> VoxelProject:
    """Generate a complete VoxelProject for an edge-lit (ELED) display module.

    Z-stack (bottom to top):
    1. Back cover
    2. Frame tray (back plate + 4 side walls)
    3. Reflector (inner dims)
    4. LGP (inner dims)
    5. PCB strips + LEDs for each active edge (at LGP z-level)
    6. Optical films (inner dims, above LGP)
    7. Panel (full footprint at top)

    Default probes: LGP Centre, Panel Centre.
    """
    blocks: list[AssemblyBlock] = []
    wall_t = params.frame_wall_t
    inner_w = params.panel_w - 2 * wall_t
    inner_d = params.panel_d - 2 * wall_t

    # 1. Back cover — full footprint at z=0
    z = 0.0
    blocks.append(AssemblyBlock(
        "Back Cover", params.back_cover_material,
        0.0, 0.0, z,
        params.panel_w, params.panel_d, params.back_cover_h,
    ))
    z += params.back_cover_h

    # 2. Frame tray — 5 blocks starting at z=back_cover_h
    # Inner height = height of everything from reflector bottom to panel top
    inner_h = (
        params.reflector_h
        + params.lgp_h
        + sum(f.thickness for f in params.optical_films)
        + params.panel_h
    )
    frame_z_base = z
    frame_blocks = _build_frame_tray(
        params.panel_w, params.panel_d,
        params.frame_back_h, inner_h,
        wall_t, params.frame_material,
        z_base=frame_z_base,
    )
    blocks.extend(frame_blocks)
    z += params.frame_back_h  # skip past back plate; walls start here

    # 3. Reflector — inner dims
    reflector_z = z
    blocks.append(AssemblyBlock(
        "Reflector", params.reflector_material,
        wall_t, wall_t, reflector_z,
        inner_w, inner_d, params.reflector_h,
    ))
    z += params.reflector_h

    # 4. LGP — inner dims
    lgp_z = z
    blocks.append(AssemblyBlock(
        "LGP", params.lgp_material,
        wall_t, wall_t, lgp_z,
        inner_w, inner_d, params.lgp_h,
    ))
    z += params.lgp_h

    # 5. LED strips (at LGP z-level, within the frame cavity)
    led_blocks = _build_eled_led_strips(params, lgp_z)
    blocks.extend(led_blocks)

    # 6. Optical films — stacked above LGP
    film_blocks, z = _build_optical_films(
        params.optical_films, inner_w, inner_d, wall_t, z,
    )
    blocks.extend(film_blocks)

    # 7. Panel — full footprint at top
    blocks.append(AssemblyBlock(
        "Panel", params.panel_material,
        0.0, 0.0, z,
        params.panel_w, params.panel_d, params.panel_h,
    ))
    z += params.panel_h

    # Materials
    materials = _collect_materials(blocks)

    # Boundary groups
    bc_map = _params_to_bc_map(params)
    boundary_groups = _build_boundary_groups(bc_map, params.ambient_c)

    # Default probes
    lgp_centre_z = lgp_z + params.lgp_h / 2
    panel_centre_z = (z - params.panel_h) + params.panel_h / 2
    probes = [
        VoxelProbe("LGP Centre", params.panel_w / 2, params.panel_d / 2, lgp_centre_z),
        VoxelProbe("Panel Centre", params.panel_w / 2, params.panel_d / 2, panel_centre_z),
    ]

    return VoxelProject(
        name="ELED Generated",
        blocks=blocks,
        materials=materials,
        boundary_groups=boundary_groups,
        probes=probes,
        mesh_config=VoxelMeshConfig(
            cells_per_interval=params.cells_per_interval,
            max_cell_size=params.max_cell_size,
        ),
    )


def generate_dled(params: DledParams) -> VoxelProject:
    """Generate a complete VoxelProject for a direct-lit (DLED) display module.

    Z-stack (bottom to top):
    1. Back cover
    2. Frame tray (back plate + 4 side walls)
    3. Reflector (inner dims)
    4. PCB (inner dims)
    5. LED grid on PCB top face
    6. Diffuser (inner dims, above PCB + air_cavity_h)
    7. Optical films (inner dims, above diffuser)
    8. Panel (full footprint at top)

    Air cavity is left as implicit (voxel solver default-fills with Air Gap).
    Default probes: PCB Centre, Panel Centre.
    """
    blocks: list[AssemblyBlock] = []
    wall_t = params.frame_wall_t
    inner_w = params.panel_w - 2 * wall_t
    inner_d = params.panel_d - 2 * wall_t

    # 1. Back cover — full footprint at z=0
    z = 0.0
    blocks.append(AssemblyBlock(
        "Back Cover", params.back_cover_material,
        0.0, 0.0, z,
        params.panel_w, params.panel_d, params.back_cover_h,
    ))
    z += params.back_cover_h

    # 2. Frame tray — inner height = everything from reflector bottom to panel top
    inner_h = (
        params.reflector_h
        + params.pcb_h
        + params.air_cavity_h
        + params.diffuser_h
        + sum(f.thickness for f in params.optical_films)
        + params.panel_h
    )
    frame_z_base = z
    frame_blocks = _build_frame_tray(
        params.panel_w, params.panel_d,
        params.frame_back_h, inner_h,
        wall_t, params.frame_material,
        z_base=frame_z_base,
    )
    blocks.extend(frame_blocks)
    z += params.frame_back_h

    # 3. Reflector — inner dims
    blocks.append(AssemblyBlock(
        "Reflector", params.reflector_material,
        wall_t, wall_t, z,
        inner_w, inner_d, params.reflector_h,
    ))
    z += params.reflector_h

    # 4. PCB — inner dims
    pcb_z = z
    blocks.append(AssemblyBlock(
        "PCB", params.pcb_material,
        wall_t, wall_t, pcb_z,
        inner_w, inner_d, params.pcb_h,
    ))
    z += params.pcb_h

    # 5. LED grid — placed on PCB top face, facing upward toward diffuser
    led_blocks = _build_dled_led_grid(params, pcb_top_z=z)
    blocks.extend(led_blocks)

    # Skip air_cavity_h — voxel solver fills remaining space with Air Gap default
    z += params.air_cavity_h

    # 6. Diffuser — inner dims
    diffuser_z = z
    blocks.append(AssemblyBlock(
        "Diffuser", params.diffuser_material,
        wall_t, wall_t, diffuser_z,
        inner_w, inner_d, params.diffuser_h,
    ))
    z += params.diffuser_h

    # 7. Optical films — stacked above diffuser
    film_blocks, z = _build_optical_films(
        params.optical_films, inner_w, inner_d, wall_t, z,
    )
    blocks.extend(film_blocks)

    # 8. Panel — full footprint at top
    panel_z = z
    blocks.append(AssemblyBlock(
        "Panel", params.panel_material,
        0.0, 0.0, panel_z,
        params.panel_w, params.panel_d, params.panel_h,
    ))
    z += params.panel_h

    # Materials
    materials = _collect_materials(blocks)

    # Boundary groups
    bc_map = _params_to_bc_map(params)
    boundary_groups = _build_boundary_groups(bc_map, params.ambient_c)

    # Default probes
    pcb_centre_z = pcb_z + params.pcb_h / 2
    panel_centre_z = panel_z + params.panel_h / 2
    probes = [
        VoxelProbe("PCB Centre", params.panel_w / 2, params.panel_d / 2, pcb_centre_z),
        VoxelProbe("Panel Centre", params.panel_w / 2, params.panel_d / 2, panel_centre_z),
    ]

    return VoxelProject(
        name="DLED Generated",
        blocks=blocks,
        materials=materials,
        boundary_groups=boundary_groups,
        probes=probes,
        mesh_config=VoxelMeshConfig(
            cells_per_interval=params.cells_per_interval,
            max_cell_size=params.max_cell_size,
        ),
    )
