"""Stack template functions for DLED and ELED display architectures.

Pure Python module — no PySide6 or GUI dependencies.
All units are SI (metres, watts, etc.).
"""

from __future__ import annotations

from thermal_sim.core.material_library import load_builtin_library
from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import LEDArray
from thermal_sim.models.layer import Layer


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

    return {
        "layers": layers,
        "materials": materials,
        "led_arrays": [led_array],
        "boundaries": boundaries,
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
    # Build layer stack (bottom-to-top) — LGP replaces LED Board
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
    }


def _filter_materials(layers: list[Layer]) -> dict:
    """Return only the builtin materials referenced by the given layer list."""
    library = load_builtin_library()
    used_names = {layer.material for layer in layers}
    return {name: mat for name, mat in library.items() if name in used_names}
