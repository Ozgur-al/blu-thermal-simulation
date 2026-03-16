"""Parametric sweep engine for thermal simulation projects."""

from __future__ import annotations

import copy
import dataclasses
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thermal_sim.models.project import DisplayProject


# ---------------------------------------------------------------------------
# SweepConfig
# ---------------------------------------------------------------------------

@dataclass
class SweepConfig:
    """Configuration for a parametric sweep.

    Attributes:
        parameter: Dot-path to the project field to sweep (e.g. ``layers[0].thickness``).
        values: Ordered list of values to apply for this parameter.
        mode: Solver mode — ``"steady"`` or ``"transient"``.
    """

    parameter: str
    values: list[float]
    mode: str = "steady"

    def to_dict(self) -> dict:
        return {
            "parameter": self.parameter,
            "values": list(self.values),
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SweepConfig":
        """Parse a sweep config dict with explicit validation.

        Expected format::

            {
                "parameter": "layers[0].thickness",
                "values": [0.001, 0.002, 0.003],
                "mode": "steady"            # optional, defaults to "steady"
            }

        Raises:
            ValueError: if ``parameter`` or ``values`` keys are absent or invalid.
        """
        if "parameter" not in data:
            raise ValueError(
                "Sweep JSON is missing required key 'parameter'. "
                "Expected format: {\"parameter\": \"layers[0].thickness\", \"values\": [...], \"mode\": \"steady\"}"
            )
        if "values" not in data:
            raise ValueError(
                "Sweep JSON is missing required key 'values'. "
                "Expected format: {\"parameter\": \"layers[0].thickness\", \"values\": [...], \"mode\": \"steady\"}"
            )
        return cls(
            parameter=str(data["parameter"]),
            values=[float(v) for v in data["values"]],
            mode=str(data.get("mode", "steady")),
        )


# ---------------------------------------------------------------------------
# Parameter path application
# ---------------------------------------------------------------------------

def _apply_parameter(project: DisplayProject, path: str, value: float) -> None:
    """Apply *value* to the field indicated by *path* on *project* in-place.

    Supported path patterns:
    - ``layers[N].field``
    - ``heat_sources[N].field``
    - ``boundaries.{top|bottom|side}.field``
    - ``materials.MaterialName.field``

    Materials are ``frozen=True`` dataclasses, so a ``dataclasses.replace()``
    call is used instead of ``setattr`` and the new instance is stored back
    into ``project.materials``.

    Raises:
        ValueError: for any unrecognised root key, index out of range,
            unknown material name, or unknown field name.
    """
    segments = path.split(".")
    root = segments[0]

    # -- layers[N].field -------------------------------------------------------
    if root.startswith("layers"):
        _idx, field = _parse_indexed_root(root, segments, "layers")
        lst = project.layers
        _validate_index(lst, _idx, "layers")
        _safe_setattr(lst[_idx], field, value, f"layers[{_idx}]")
        return

    # -- heat_sources[N].field -------------------------------------------------
    if root.startswith("heat_sources"):
        _idx, field = _parse_indexed_root(root, segments, "heat_sources")
        lst = project.heat_sources
        _validate_index(lst, _idx, "heat_sources")
        _safe_setattr(lst[_idx], field, value, f"heat_sources[{_idx}]")
        return

    # -- materials.Name.field --------------------------------------------------
    if root == "materials":
        if len(segments) != 3:
            raise ValueError(
                f"Invalid material path '{path}'. "
                "Expected format: 'materials.<MaterialName>.<field>'"
            )
        mat_name = segments[1]
        field = segments[2]
        if mat_name not in project.materials:
            raise ValueError(
                f"Unknown material name '{mat_name}'. "
                f"Available materials: {list(project.materials.keys())}"
            )
        old_mat = project.materials[mat_name]
        if not hasattr(old_mat, field):
            raise ValueError(
                f"Material has no field '{field}'. "
                f"Valid fields: {[f.name for f in dataclasses.fields(old_mat)]}"
            )
        # Material is frozen — must use dataclasses.replace
        project.materials[mat_name] = dataclasses.replace(old_mat, **{field: value})
        return

    # -- boundaries.{top|bottom|side}.field -----------------------------------
    if root == "boundaries":
        if len(segments) != 3:
            raise ValueError(
                f"Invalid boundary path '{path}'. "
                "Expected format: 'boundaries.<top|bottom|side>.<field>'"
            )
        surface_name = segments[1]
        field = segments[2]
        valid_surfaces = ("top", "bottom", "side")
        if surface_name not in valid_surfaces:
            raise ValueError(
                f"Unknown boundary surface '{surface_name}'. "
                f"Valid surfaces: {valid_surfaces}"
            )
        surface = getattr(project.boundaries, surface_name)
        _safe_setattr(surface, field, value, f"boundaries.{surface_name}")
        return

    raise ValueError(
        f"Unknown root key '{root}' in parameter path '{path}'. "
        "Valid roots: layers, heat_sources, materials, boundaries"
    )


def _parse_indexed_root(root_segment: str, all_segments: list[str], key: str) -> tuple[int, str]:
    """Extract index from ``key[N]`` and the trailing field from all_segments."""
    match = re.match(r"(\w+)\[(\d+)\]", root_segment)
    if not match:
        raise ValueError(
            f"Expected indexed path like '{key}[0].field', got '{'.'.join(all_segments)}'"
        )
    idx = int(match.group(2))
    if len(all_segments) != 2:
        raise ValueError(
            f"Expected exactly one field after index in '{'.'.join(all_segments)}'"
        )
    return idx, all_segments[1]


def _validate_index(lst: list, idx: int, key: str) -> None:
    if idx < 0 or idx >= len(lst):
        raise ValueError(
            f"Index {idx} is out of range for '{key}' (length {len(lst)})"
        )


def _safe_setattr(obj: object, field: str, value: float, context: str) -> None:
    if not hasattr(obj, field):
        raise ValueError(
            f"'{context}' has no field '{field}'. "
            f"Valid fields: {[f.name for f in dataclasses.fields(obj)]}"
        )
    setattr(obj, field, value)


# ---------------------------------------------------------------------------
# SweepEngine
# ---------------------------------------------------------------------------

class SweepEngine:
    """Runs parametric sweeps over a DisplayProject.

    For each value in the sweep config, the engine:
    1. Deep-copies the base project.
    2. Applies the parameter mutation.
    3. Solves (steady or transient).
    4. Extracts per-layer summary stats (T_max, T_avg, T_min, delta_T).
    5. Discards the full temperature array — only stats are retained.
    """

    def run(
        self,
        base_project: DisplayProject,
        config: SweepConfig,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> "SweepResult":
        """Execute the sweep and return a SweepResult.

        Args:
            base_project: Project to use as the template (never modified).
            config: Sweep configuration (parameter path, values, mode).
            on_progress: Optional callback called as ``on_progress(run_number, total_runs)``
                after each completed run (1-indexed).

        Returns:
            SweepResult with one SweepRunResult per sweep value.
        """
        from thermal_sim.core.postprocess import layer_stats
        from thermal_sim.models.sweep_result import SweepResult, SweepRunResult
        from thermal_sim.solvers.steady_state import SteadyStateSolver
        from thermal_sim.solvers.transient import TransientSolver

        total = len(config.values)
        runs: list[SweepRunResult] = []

        for i, value in enumerate(config.values):
            project_copy = copy.deepcopy(base_project)
            _apply_parameter(project_copy, config.parameter, value)

            if config.mode == "transient":
                result = TransientSolver().solve(project_copy)
                temps = result.final_temperatures_c
                names = result.layer_names
            else:
                result = SteadyStateSolver().solve(project_copy)
                temps = result.temperatures_c
                names = result.layer_names

            stats = layer_stats(temps, names)
            runs.append(SweepRunResult(parameter_value=value, layer_stats=stats))

            if on_progress is not None:
                on_progress(i + 1, total)

            # Explicitly drop the full result to free memory
            del result

        return SweepResult(config=config, runs=runs)


# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------

def load_sweep_config(path: Path) -> SweepConfig:
    """Load and parse a SweepConfig from a JSON file.

    Args:
        path: Path to the sweep JSON file.

    Returns:
        Parsed SweepConfig.

    Raises:
        ValueError: if the JSON is malformed or missing required fields.
        FileNotFoundError: if the file does not exist.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return SweepConfig.from_dict(data)
