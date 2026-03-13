"""Project JSON import/export."""

from __future__ import annotations

import json
from pathlib import Path

from thermal_sim.models.project import DisplayProject


def save_project(project: DisplayProject, path: str | Path) -> None:
    """Save project file in JSON format."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, indent=2)


def load_project(path: str | Path) -> DisplayProject:
    """Load project file from JSON."""
    in_path = Path(path)
    with in_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return DisplayProject.from_dict(raw)
