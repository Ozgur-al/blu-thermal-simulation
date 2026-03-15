"""CSV export helpers."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from thermal_sim.solvers.steady_state import SteadyStateResult


def export_temperature_map(result: SteadyStateResult, output_path: str | Path) -> None:
    """Export temperatures as a long-format CSV table."""
    z_offsets = getattr(result, 'z_offsets', None)
    export_temperature_map_array(
        temperature_map_c=result.temperatures_c,
        layer_names=result.layer_names,
        dx=result.dx,
        dy=result.dy,
        output_path=output_path,
        z_offsets=z_offsets,
    )


def export_temperature_map_array(
    temperature_map_c: np.ndarray,
    layer_names: list[str],
    dx: float,
    dy: float,
    output_path: str | Path,
    z_offsets: list[int] | None = None,
) -> None:
    """Export [total_z, y, x] temperatures as a long-format CSV table.

    Exports the top sublayer per physical layer (default visualization layer).
    When z_offsets is None, falls back to assuming one z-node per layer.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    total_z, ny, nx = temperature_map_c.shape
    if z_offsets is None:
        z_offsets = list(range(len(layer_names) + 1))

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["layer", "x_m", "y_m", "temperature_c"])
        for l_idx, layer_name in enumerate(layer_names):
            z0 = z_offsets[l_idx]
            z1 = z_offsets[l_idx + 1]
            # Export top sublayer per layer (default visualization layer)
            top_z = z1 - 1
            for iy in range(ny):
                y = (iy + 0.5) * dy
                for ix in range(nx):
                    x = (ix + 0.5) * dx
                    writer.writerow([layer_name, x, y, float(temperature_map_c[top_z, iy, ix])])


def export_probe_temperatures(probe_values: dict[str, float], output_path: str | Path) -> None:
    """Export probe temperatures to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["probe", "temperature_c"])
        for name, value in probe_values.items():
            writer.writerow([name, value])


def export_sweep_results(sweep_result: object, output_path: "str | Path") -> None:
    """Export a SweepResult as a comparison CSV.

    Columns: ``parameter_value``, then ``{layer}_t_max_c`` and
    ``{layer}_t_avg_c`` for each layer in the sweep.

    Parameters
    ----------
    sweep_result:
        A ``SweepResult`` dataclass instance.
    output_path:
        Destination CSV path.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not sweep_result.runs:
        # Write an empty file with only the header
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["parameter_value"])
        return

    layer_names = [s["layer"] for s in sweep_result.runs[0].layer_stats]
    header = ["parameter_value"]
    for name in layer_names:
        header.append(f"{name}_t_max_c")
        header.append(f"{name}_t_avg_c")

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for run in sweep_result.runs:
            row = [run.parameter_value]
            for stat in run.layer_stats:
                row.append(stat["t_max_c"])
                row.append(stat["t_avg_c"])
            writer.writerow(row)


def export_probe_temperatures_vs_time(
    times_s: np.ndarray,
    probe_history_c: dict[str, np.ndarray],
    output_path: str | Path,
) -> None:
    """Export transient probe temperatures over time to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    probe_names = list(probe_history_c.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", *probe_names])
        for i, time_s in enumerate(times_s):
            row = [float(time_s)]
            for name in probe_names:
                row.append(float(probe_history_c[name][i]))
            writer.writerow(row)
