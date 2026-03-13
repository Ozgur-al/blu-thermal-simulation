"""Built-in material presets for display module studies."""

from __future__ import annotations

from thermal_sim.models.material import Material


def default_materials() -> dict[str, Material]:
    """Return a practical starter material library."""
    materials = [
        Material("Glass", k_in_plane=1.05, k_through=1.05, density=2500.0, specific_heat=840.0, emissivity=0.92),
        Material("OCA", k_in_plane=0.25, k_through=0.25, density=980.0, specific_heat=1800.0, emissivity=0.95),
        Material("PMMA", k_in_plane=0.20, k_through=0.20, density=1180.0, specific_heat=1470.0, emissivity=0.94),
        Material("PC", k_in_plane=0.20, k_through=0.20, density=1210.0, specific_heat=1250.0, emissivity=0.94),
        Material("Aluminum", k_in_plane=205.0, k_through=205.0, density=2700.0, specific_heat=897.0, emissivity=0.10),
        Material("Steel", k_in_plane=16.0, k_through=16.0, density=7850.0, specific_heat=490.0, emissivity=0.60),
        Material("FR4", k_in_plane=0.35, k_through=0.30, density=1900.0, specific_heat=1100.0, emissivity=0.90),
        Material("Copper", k_in_plane=390.0, k_through=390.0, density=8960.0, specific_heat=385.0, emissivity=0.20),
        Material(
            "Thermal Pad",
            k_in_plane=3.0,
            k_through=3.0,
            density=2200.0,
            specific_heat=1200.0,
            emissivity=0.90,
        ),
        Material(
            "Graphite Sheet",
            k_in_plane=400.0,
            k_through=5.0,
            density=1800.0,
            specific_heat=710.0,
            emissivity=0.80,
        ),
    ]
    return {item.name: item for item in materials}
