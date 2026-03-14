"""Command-line entry point for thermal simulations."""

from __future__ import annotations

import argparse
from pathlib import Path

from thermal_sim.core.postprocess import (
    basic_stats,
    basic_stats_transient,
    probe_temperatures,
    probe_temperatures_over_time,
    top_n_hottest_cells,
    top_n_hottest_cells_transient,
)
from thermal_sim.io.csv_export import (
    export_probe_temperatures,
    export_probe_temperatures_vs_time,
    export_temperature_map,
    export_temperature_map_array,
)
from thermal_sim.io.project_io import load_project, save_project
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver
from thermal_sim.visualization.plotting import plot_probe_history, plot_temperature_map


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run steady-state or transient thermal simulations on a project.")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path("examples/steady_uniform_stack.json"),
        help="Path to project JSON file.",
    )
    parser.add_argument(
        "--mode",
        choices=("steady", "transient"),
        default="steady",
        help="Simulation mode: steady-state or transient.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Folder for output files.")
    parser.add_argument("--top-n", type=int, default=5, help="Number of hottest cells to print.")
    parser.add_argument("--plot", action="store_true", help="Generate PNG plots.")
    parser.add_argument(
        "--plot-layer",
        default=None,
        help="Layer name for temperature-map plot. Defaults to top layer.",
    )
    parser.add_argument(
        "--save-project-copy",
        type=Path,
        default=None,
        help="Optional path to write a normalized copy of the loaded project JSON.",
    )
    parser.add_argument(
        "--sweep",
        type=Path,
        default=None,
        help="Path to a sweep JSON file. When provided, runs a parametric sweep instead of a single simulation.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    project = load_project(args.project)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.save_project_copy is not None:
        save_project(project, args.save_project_copy)

    if args.sweep is not None:
        _run_sweep(project, args)
        return

    try:
        if args.mode == "steady":
            _run_steady(project, args.output_dir, args.top_n, args.plot, args.plot_layer)
            return
        _run_transient(project, args.output_dir, args.top_n, args.plot, args.plot_layer)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(2) from exc


def _run_sweep(project, args) -> None:
    """Load a sweep config and execute a parametric sweep, printing results to stdout."""
    import csv

    from thermal_sim.core.sweep_engine import SweepEngine, load_sweep_config

    config = load_sweep_config(args.sweep)

    def _on_progress(n: int, m: int) -> None:
        print(f"Run {n} of {m} ...")

    sweep_result = SweepEngine().run(project, config, on_progress=_on_progress)

    print(f"\nSweep complete: {config.parameter} ({config.mode})")
    print(f"{'Value':>12}  {'Layer':<20}  {'T_max [C]':>10}  {'T_avg [C]':>10}  {'T_min [C]':>10}")
    print("-" * 70)
    for run in sweep_result.runs:
        for i, stats in enumerate(run.layer_stats):
            value_col = f"{run.parameter_value:.5g}" if i == 0 else ""
            print(
                f"{value_col:>12}  {stats['layer']:<20}  "
                f"{stats['t_max_c']:>10.2f}  {stats['t_avg_c']:>10.2f}  {stats['t_min_c']:>10.2f}"
            )

    # Export CSV to output_dir
    csv_path = args.output_dir / "sweep_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["parameter_value", "layer", "t_max_c", "t_avg_c", "t_min_c", "delta_t_c"])
        for run in sweep_result.runs:
            for stats in run.layer_stats:
                writer.writerow([
                    run.parameter_value,
                    stats["layer"],
                    stats["t_max_c"],
                    stats["t_avg_c"],
                    stats["t_min_c"],
                    stats["delta_t_c"],
                ])
    print(f"\nSweep results exported to: {csv_path.resolve()}")


def _run_steady(
    project,
    output_dir: Path,
    top_n: int,
    plot: bool,
    plot_layer: str | None,
) -> None:
    result = SteadyStateSolver().solve(project)
    stats = basic_stats(result)
    probe_values = probe_temperatures(project, result)
    hottest = top_n_hottest_cells(result, n=top_n)

    export_temperature_map(result, output_dir / "temperature_map.csv")
    if probe_values:
        export_probe_temperatures(probe_values, output_dir / "probe_temperatures.csv")

    layer_idx = _layer_index(result.layer_names, plot_layer)
    if plot:
        try:
            plot_temperature_map(
                temperature_map_c=result.temperatures_c[layer_idx],
                width_m=project.width,
                height_m=project.height,
                title=f"Steady Map - {result.layer_names[layer_idx]}",
                output_path=output_dir / "temperature_map.png",
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError("Plotting requires matplotlib. Install dependencies from requirements.txt.") from exc

    print(f"Project: {project.name}")
    print("Mode: steady")
    print(f"Mesh: {project.mesh.nx} x {project.mesh.ny} x {len(project.layers)} layers")
    print(f"Tmin / Tavg / Tmax [C]: {stats.min_c:.2f} / {stats.avg_c:.2f} / {stats.max_c:.2f}")
    if probe_values:
        print("Probe temperatures [C]:")
        for probe_name, temp_c in probe_values.items():
            print(f"  - {probe_name}: {temp_c:.2f}")
    _print_hottest(hottest)
    print(f"Artifacts exported to: {output_dir.resolve()}")


def _run_transient(
    project,
    output_dir: Path,
    top_n: int,
    plot: bool,
    plot_layer: str | None,
) -> None:
    result = TransientSolver().solve(project)
    stats = basic_stats_transient(result)
    probe_history = probe_temperatures_over_time(project, result)
    hottest = top_n_hottest_cells_transient(result, n=top_n)

    export_temperature_map_array(
        temperature_map_c=result.final_temperatures_c,
        layer_names=result.layer_names,
        dx=result.dx,
        dy=result.dy,
        output_path=output_dir / "temperature_map.csv",
    )
    if probe_history:
        export_probe_temperatures_vs_time(result.times_s, probe_history, output_dir / "probe_temperatures_vs_time.csv")

    layer_idx = _layer_index(result.layer_names, plot_layer)
    if plot:
        try:
            plot_temperature_map(
                temperature_map_c=result.final_temperatures_c[layer_idx],
                width_m=project.width,
                height_m=project.height,
                title=f"Transient Final Map - {result.layer_names[layer_idx]}",
                output_path=output_dir / "temperature_map.png",
            )
            if probe_history:
                plot_probe_history(
                    times_s=result.times_s,
                    probe_history_c=probe_history,
                    output_path=output_dir / "probe_temperatures_vs_time.png",
                )
        except ModuleNotFoundError as exc:
            raise RuntimeError("Plotting requires matplotlib. Install dependencies from requirements.txt.") from exc

    print(f"Project: {project.name}")
    print("Mode: transient")
    print(f"Mesh: {project.mesh.nx} x {project.mesh.ny} x {len(project.layers)} layers")
    print(
        "Transient setup: dt={:.4f} s, total={:.2f} s, output every {:.4f} s".format(
            project.transient.time_step_s,
            project.transient.total_time_s,
            project.transient.output_interval_s,
        )
    )
    print(f"Final Tmin / Tavg / Tmax [C]: {stats.min_c:.2f} / {stats.avg_c:.2f} / {stats.max_c:.2f}")
    if probe_history:
        print("Final probe temperatures [C]:")
        for probe_name, history in probe_history.items():
            print(f"  - {probe_name}: {float(history[-1]):.2f}")
    _print_hottest(hottest)
    print(f"Artifacts exported to: {output_dir.resolve()}")


def _print_hottest(hottest: list[dict]) -> None:
    print("Top hottest cells:")
    for item in hottest:
        print(
            f"  - {item['layer']}: {item['temperature_c']:.2f} C at "
            f"({item['x_m']:.4f} m, {item['y_m']:.4f} m)"
        )


def _layer_index(layer_names: list[str], plot_layer: str | None) -> int:
    if plot_layer is None:
        return len(layer_names) - 1
    try:
        return layer_names.index(plot_layer)
    except ValueError as exc:
        valid = ", ".join(layer_names)
        raise ValueError(f"Layer '{plot_layer}' not found. Valid layers: {valid}") from exc


if __name__ == "__main__":
    main()
