"""Built-in material presets for display module studies."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from thermal_sim.models.material import Material


def load_builtin_library() -> dict[str, Material]:
    """Load the bundled materials_builtin.json and return dict[name, Material].

    Uses importlib.resources so the file is accessible both from the source
    tree and from a PyInstaller --onedir bundle.
    """
    resource = files("thermal_sim.resources").joinpath("materials_builtin.json")
    text = resource.read_text(encoding="utf-8")
    data: dict = json.loads(text)
    return {name: Material.from_dict(entry) for name, entry in data.items()}


def load_materials_json(path: Path) -> dict[str, Material]:
    """Load an arbitrary material JSON file and return dict[name, Material].

    The JSON format must be a dict of name -> material-properties-dict,
    matching the format written by export_materials().
    """
    with open(path, encoding="utf-8") as fh:
        data: dict = json.load(fh)
    return {name: Material.from_dict(entry) for name, entry in data.items()}


def export_materials(materials: dict[str, Material], path: Path) -> None:
    """Write a materials dict to a JSON file.

    The output format is dict of name -> material-properties-dict (same as
    materials_builtin.json) so the file can be re-imported by load_materials_json().
    """
    data = {name: mat.to_dict() for name, mat in materials.items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def import_materials(
    existing: dict[str, Material],
    incoming: dict[str, Material],
    builtin_names: set[str],
) -> tuple[dict[str, Material], list[str]]:
    """Merge incoming materials into existing without mutating either input dict.

    For each incoming material:
    - If its name is not in existing AND not in builtin_names: add directly.
    - If there is a name conflict: rename to "Name_imported".  If that also
      conflicts try "Name_imported_2", "Name_imported_3", ... until a free
      slot is found.

    Returns:
        (merged_dict, rename_messages) where rename_messages is a list of
        human-readable strings describing each renaming that occurred.
    """
    merged: dict[str, Material] = dict(existing)
    rename_messages: list[str] = []

    for name, mat in incoming.items():
        if name not in merged and name not in builtin_names:
            merged[name] = mat
            continue

        # Conflict — find a free suffixed name
        candidate = f"{name}_imported"
        counter = 2
        while candidate in merged or candidate in builtin_names:
            candidate = f"{name}_imported_{counter}"
            counter += 1

        # Rebuild the material with the new name (frozen dataclass)
        import dataclasses
        renamed_mat = dataclasses.replace(mat, name=candidate)
        merged[candidate] = renamed_mat
        rename_messages.append(
            f"'{name}' renamed to '{candidate}' due to name conflict"
        )

    return merged, rename_messages


def default_materials() -> dict[str, Material]:
    """Return a practical starter material library.

    Preserved verbatim for backward compatibility — callers that depend on
    the exact set of 10 materials will continue to work unchanged.
    """
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
