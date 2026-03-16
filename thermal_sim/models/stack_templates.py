"""Stack template functions for DLED and ELED display architectures.

Pure Python module — no PySide6 or GUI dependencies.
All units are SI (metres, watts, etc.).
"""

from __future__ import annotations

from thermal_sim.core.material_library import load_builtin_library
from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import LEDArray
from thermal_sim.models.layer import EdgeLayer, Layer
from thermal_sim.models.project import EdgeFrame


def dled_template(
    panel_width: float,
    panel_height: float,
    optical_layers: int = 2,
) -> dict:
    """Return a Direct LED (DLED) display stack template.

    Parameters
    ----------
    panel_width:
        Panel width in metres.
    panel_height:
        Panel height in metres.
    optical_layers:
        Number of optical diffuser/film layers. Minimum 2 (Diffuser + BEF).
        Each additional layer beyond 2 is added as "Optical Sheet N".

    Returns
    -------
    dict with keys:
        "layers"     : list[Layer]  — bottom-to-top layer stack
        "materials"  : dict[str, Material]  — only materials used by layers
        "led_arrays" : list[LEDArray]
        "boundaries" : BoundaryConditions
    """
    # -----------------------------------------------------------------------
    # Build layer stack (bottom-to-top)
    # -----------------------------------------------------------------------
    layers: list[Layer] = [
        Layer(name="Back Cover",   material="Aluminum", thickness=0.0008),
        Layer(name="Metal Frame",  material="Steel",    thickness=0.001),
        Layer(name="LED Board",    material="FR4",      thickness=0.001),
        Layer(name="Diffuser",     material="PC",       thickness=0.002),   # 1st optical
        Layer(name="BEF",          material="PC",       thickness=0.0003),  # 2nd optical
    ]

    # Optional extra optical sheets (optical_layers 3, 4, ...)
    for n in range(3, optical_layers + 1):
        layers.append(Layer(name=f"Optical Sheet {n}", material="PC", thickness=0.0003))

    layers += [
        Layer(name="OCA",          material="OCA",      thickness=0.00015),
        Layer(name="Display Cell", material="Glass",    thickness=0.0011),
        Layer(name="Cover Glass",  material="Glass",    thickness=0.0018),
    ]

    # -----------------------------------------------------------------------
    # LED array
    # -----------------------------------------------------------------------
    count_x = 8
    count_y = 6
    pitch_x = panel_width / (count_x + 1)
    pitch_y = panel_height / (count_y + 1)
    offset_x = panel_width * 0.10
    offset_y = panel_height * 0.10

    led_array = LEDArray(
        name="DLED Array",
        layer="LED Board",
        center_x=panel_width / 2.0,
        center_y=panel_height / 2.0,
        count_x=count_x,
        count_y=count_y,
        pitch_x=pitch_x,
        pitch_y=pitch_y,
        power_per_led_w=0.5,
        footprint_shape="rectangle",
        led_width=0.003,
        led_height=0.003,
        mode="grid",
        panel_width=panel_width,
        panel_height=panel_height,
        offset_left=offset_x,
        offset_right=offset_x,
        offset_top=offset_y,
        offset_bottom=offset_y,
        zone_count_x=1,
        zone_count_y=1,
    )

    # -----------------------------------------------------------------------
    # Boundaries — enhanced side h for metal frame
    # -----------------------------------------------------------------------
    boundaries = BoundaryConditions(
        top=SurfaceBoundary(),
        bottom=SurfaceBoundary(),
        side=SurfaceBoundary(convection_h=25.0),
    )

    # -----------------------------------------------------------------------
    # Materials — only those referenced by the layer stack
    # -----------------------------------------------------------------------
    materials = _filter_materials(layers)

    edge_frame = EdgeFrame(metal_thickness=0.003, air_gap_thickness=0.001)

    return {
        "layers": layers,
        "materials": materials,
        "led_arrays": [led_array],
        "boundaries": boundaries,
        "edge_frame": edge_frame,
    }


def eled_template(
    panel_width: float,
    panel_height: float,
    edge_config: str = "bottom",
    optical_layers: int = 2,
) -> dict:
    """Return an Edge LED (ELED) display stack template.

    Parameters
    ----------
    panel_width:
        Panel width in metres.
    panel_height:
        Panel height in metres.
    edge_config:
        Which edges to place LEDs on: 'bottom', 'top', 'left_right', or 'all'.
    optical_layers:
        Number of optical diffuser/film layers. Minimum 2 (Diffuser + BEF).

    Returns
    -------
    dict with keys:
        "layers"     : list[Layer]  — bottom-to-top layer stack
        "materials"  : dict[str, Material]  — only materials used by layers
        "led_arrays" : list[LEDArray]
        "boundaries" : BoundaryConditions
    """
    # -----------------------------------------------------------------------
    # Edge frame — project-level uniform frame for all layers
    # -----------------------------------------------------------------------
    edge_frame = EdgeFrame(metal_thickness=0.003, air_gap_thickness=0.001)

    # -----------------------------------------------------------------------
    # Build layer stack (bottom-to-top) — LGP replaces LED Board
    # Edge layers are now set at project level via EdgeFrame, not per-layer.
    # -----------------------------------------------------------------------
    layers: list[Layer] = [
        Layer(name="Back Cover",   material="Aluminum", thickness=0.0008),
        Layer(name="Metal Frame",  material="Steel",    thickness=0.001),
        Layer(name="LGP",          material="PMMA",     thickness=0.004),   # Light Guide Plate
        Layer(name="Diffuser",     material="PC",       thickness=0.002),
        Layer(name="BEF",          material="PC",       thickness=0.0003),
    ]

    for n in range(3, optical_layers + 1):
        layers.append(Layer(name=f"Optical Sheet {n}", material="PC", thickness=0.0003))

    layers += [
        Layer(name="OCA",          material="OCA",      thickness=0.00015),
        Layer(name="Display Cell", material="Glass",    thickness=0.0011),
        Layer(name="Cover Glass",  material="Glass",    thickness=0.0018),
    ]

    # -----------------------------------------------------------------------
    # LED array — edge mode on LGP layer
    # -----------------------------------------------------------------------
    count_x = 20  # bottom/top horizontal
    count_y = 15  # left/right vertical
    pitch_x = panel_width / (count_x + 1)
    pitch_y = panel_height / (count_y + 1)

    led_array = LEDArray(
        name="ELED Array",
        layer="LGP",
        center_x=panel_width / 2.0,
        center_y=panel_height / 2.0,
        count_x=count_x,
        count_y=count_y,
        pitch_x=pitch_x,
        pitch_y=pitch_y,
        power_per_led_w=0.3,
        footprint_shape="rectangle",
        # Use half-pitch footprint so each LED covers its local LGP area.
        # This ensures overlap with at least one mesh cell at any reasonable
        # mesh density (nx >= 20, ny >= 15 on a 300x200 mm panel).
        led_width=pitch_x * 0.5,
        led_height=pitch_y * 0.5,
        mode="edge",
        edge_config=edge_config,
        edge_offset=0.005,
        panel_width=panel_width,
        panel_height=panel_height,
        z_position="distributed",
    )

    # -----------------------------------------------------------------------
    # Boundaries — enhanced side h for metal frame
    # -----------------------------------------------------------------------
    boundaries = BoundaryConditions(
        top=SurfaceBoundary(),
        bottom=SurfaceBoundary(),
        side=SurfaceBoundary(convection_h=25.0),
    )

    # -----------------------------------------------------------------------
    # Materials — only those referenced by the layer stack
    # -----------------------------------------------------------------------
    materials = _filter_materials(layers)

    return {
        "layers": layers,
        "materials": materials,
        "led_arrays": [led_array],
        "boundaries": boundaries,
        "edge_frame": edge_frame,
    }


def generate_eled_zones(
    panel_width: float,
    panel_height: float,
    frame_width_left: float,
    pcb_width_left: float,
    air_gap_left: float,
    frame_width_right: float,
    pcb_width_right: float,
    air_gap_right: float,
    edge_config: str = "left_right",
) -> list:
    """Return MaterialZone list for ELED LGP cross-section.

    Physical arrangement (near-edge to far-edge):
    [frame | PCB+LED | air gap | LGP bulk | air gap | PCB+LED | frame]

    For ``left_right``: zones run along x (left-to-right).  "left"/"right"
    spinbox values map to the left and right panel edges.

    For ``bottom`` or ``top``: zones run along y.  "left" spinbox values
    map to the bottom edge and "right" values to the top edge (``bottom``),
    or vice-versa (``top``).

    Parameters are in SI metres. Zones with width <= 0 are omitted.

    Raises ValueError if the sum of edge zone widths exceeds the relevant
    panel dimension.
    """
    from thermal_sim.models.material_zone import MaterialZone

    # Choose the axis that is perpendicular to the LED edge.
    # "left_right" -> zones along x, span full height.
    # "bottom"/"top" -> zones along y, span full width.
    horizontal = edge_config in ("left_right", "all")
    span_dim = panel_width if horizontal else panel_height  # extent along zone axis
    cross_dim = panel_height if horizontal else panel_width  # extent perpendicular

    # For "bottom": "left" spinbox = bottom edge, "right" = top edge.
    # For "top": "left" spinbox = top edge, "right" = bottom edge.
    if edge_config == "top":
        near_frame, near_pcb, near_air = frame_width_right, pcb_width_right, air_gap_right
        far_frame, far_pcb, far_air = frame_width_left, pcb_width_left, air_gap_left
    else:
        near_frame, near_pcb, near_air = frame_width_left, pcb_width_left, air_gap_left
        far_frame, far_pcb, far_air = frame_width_right, pcb_width_right, air_gap_right

    total_edge = near_frame + near_pcb + near_air + far_frame + far_pcb + far_air
    lgp_bulk_width = span_dim - total_edge
    if lgp_bulk_width <= 0:
        raise ValueError(
            f"ELED zone widths ({total_edge:.4f} m) "
            f"exceed panel {'width' if horizontal else 'height'} ({span_dim:.4f} m). "
            f"Reduce zone widths."
        )

    zones = []
    pos = 0.0
    for material, w in [
        ("Steel",    near_frame),
        ("FR4",      near_pcb),
        ("Air Gap",  near_air),
        ("PMMA",     lgp_bulk_width),
        ("Air Gap",  far_air),
        ("FR4",      far_pcb),
        ("Steel",    far_frame),
    ]:
        if w > 0:
            if horizontal:
                zones.append(MaterialZone(
                    material=material, x=pos, y=0.0,
                    width=w, height=cross_dim,
                ))
            else:
                zones.append(MaterialZone(
                    material=material, x=0.0, y=pos,
                    width=cross_dim, height=w,
                ))
        pos += w
    return zones


def generate_edge_zones(
    layer: "Layer",
    panel_width: float,
    panel_height: float,
) -> list:
    """Convert a layer's edge_layers dict to MaterialZone rectangles.

    Physical layout:
    - Bottom/top zones span the full panel width (include corners).
    - Left/right zones span only the interior height
      (panel_height - bottom_total - top_total).

    Parameters
    ----------
    layer:
        Layer whose ``edge_layers`` dict defines edge materials.
    panel_width:
        Full panel width in metres (SI).
    panel_height:
        Full panel height in metres (SI).

    Returns
    -------
    list[MaterialZone]
        Zones ordered bottom → top → left → right.
        Empty list when ``layer.edge_layers`` is empty or has no entries.

    Raises
    ------
    ValueError
        When left+right total thickness >= panel_width or
        bottom+top total thickness >= panel_height.
    """
    from thermal_sim.models.material_zone import MaterialZone

    if not layer.edge_layers:
        return []

    bottom_list = layer.edge_layers.get("bottom", [])
    top_list    = layer.edge_layers.get("top",    [])
    left_list   = layer.edge_layers.get("left",   [])
    right_list  = layer.edge_layers.get("right",  [])

    bottom_total = sum(el.thickness for el in bottom_list)
    top_total    = sum(el.thickness for el in top_list)
    left_total   = sum(el.thickness for el in left_list)
    right_total  = sum(el.thickness for el in right_list)

    if left_total + right_total >= panel_width:
        raise ValueError(
            f"Edge layer left+right total thickness ({left_total + right_total:.6f} m) "
            f"must be less than panel_width ({panel_width:.6f} m)."
        )
    if bottom_total + top_total >= panel_height:
        raise ValueError(
            f"Edge layer bottom+top total thickness ({bottom_total + top_total:.6f} m) "
            f"must be less than panel_height ({panel_height:.6f} m)."
        )

    zones: list = []

    # Bottom zones: full-width strips stacked from y=0 upward.
    y = 0.0
    for el in bottom_list:
        zones.append(MaterialZone(
            material=el.material,
            x=panel_width / 2.0,
            y=y + el.thickness / 2.0,
            width=panel_width,
            height=el.thickness,
        ))
        y += el.thickness

    # Top zones: full-width strips stacked from y=panel_height downward.
    y = panel_height
    for el in top_list:
        zones.append(MaterialZone(
            material=el.material,
            x=panel_width / 2.0,
            y=y - el.thickness / 2.0,
            width=panel_width,
            height=el.thickness,
        ))
        y -= el.thickness

    # Interior height for left/right zones (excludes corners covered by bottom/top).
    interior_height = panel_height - bottom_total - top_total
    interior_y_center = bottom_total + interior_height / 2.0

    # Left zones: interior-height strips from x=0 rightward.
    x = 0.0
    for el in left_list:
        zones.append(MaterialZone(
            material=el.material,
            x=x + el.thickness / 2.0,
            y=interior_y_center,
            width=el.thickness,
            height=interior_height,
        ))
        x += el.thickness

    # Right zones: interior-height strips from x=panel_width leftward.
    x = panel_width
    for el in right_list:
        zones.append(MaterialZone(
            material=el.material,
            x=x - el.thickness / 2.0,
            y=interior_y_center,
            width=el.thickness,
            height=interior_height,
        ))
        x -= el.thickness

    return zones


# Materials required for ELED cross-section zones.
# All are present in the builtin materials library.
ELED_ZONE_MATERIALS = {"Steel", "FR4", "Air Gap", "PMMA"}


def _filter_materials(layers: list[Layer]) -> dict:
    """Return only the builtin materials referenced by the given layer list.

    Also includes materials referenced by layer.edge_layers entries so that
    ELED perimeter materials (Steel, Air Gap, FR4) are included automatically.
    """
    library = load_builtin_library()
    used_names: set[str] = {layer.material for layer in layers}
    for layer in layers:
        for edge_layers_list in getattr(layer, "edge_layers", {}).values():
            for el in edge_layers_list:
                used_names.add(el.material)
    return {name: mat for name, mat in library.items() if name in used_names}
