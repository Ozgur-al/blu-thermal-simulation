"""VoxelProject JSON load/save helpers."""

from __future__ import annotations

import json
from pathlib import Path

from thermal_sim.models.voxel_project import VoxelProject


def load_voxel_project(path: str | Path) -> VoxelProject:
    """Load a VoxelProject from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return VoxelProject.from_dict(data)


def save_voxel_project(project: VoxelProject, path: str | Path) -> None:
    """Save a VoxelProject to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, indent=2)
