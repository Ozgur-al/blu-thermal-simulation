"""Command-line entry point for voxel-based 3D thermal simulations."""

from __future__ import annotations

import argparse
from pathlib import Path

from thermal_sim.io.voxel_project_io import load_voxel_project, save_voxel_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run steady-state or transient 3D voxel thermal simulations."
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path("examples/dled_voxel.json"),
        help="Path to VoxelProject JSON file.",
    )
    parser.add_argument(
        "--mode",
        choices=("steady", "transient"),
        default="steady",
        help="Simulation mode: steady-state or transient.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Folder for output files.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of hottest voxels to print.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate PNG slice plots.",
    )
    parser.add_argument(
        "--plot-z",
        type=float,
        default=None,
        help="Z position (metres) for the temperature-map slice. Defaults to mid-height.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export per-voxel temperatures to CSV.",
    )
    parser.add_argument(
        "--save-project-copy",
        type=Path,
        default=None,
        help="Optional path to write a normalised copy of the loaded project JSON.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    project = load_voxel_project(args.project)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.save_project_copy is not None:
        save_voxel_project(project, args.save_project_copy)

    try:
        if args.mode == "steady":
            _run_steady(project, args)
        else:
            _run_transient(project, args)
    except ImportError as exc:
        print(f"Solver not available: {exc}")
        print("Ensure voxel solver modules are installed (Plan 02 outputs).")
        raise SystemExit(2) from exc
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(2) from exc


def _run_steady(project, args) -> None:
    try:
        from thermal_sim.solvers.steady_state_voxel import VoxelSteadyStateSolver
    except ImportError as exc:
        raise ImportError(
            "VoxelSteadyStateSolver not found. "
            "steady_state_voxel.py must be present (see Phase 11 Plan 02)."
        ) from exc

    from thermal_sim.io.csv_export import export_voxel_csv

    result = VoxelSteadyStateSolver().solve(project)
    mesh = result.mesh

    print(f"Project: {project.name}")
    print("Mode: steady")
    print(
        f"Mesh: {mesh.nx} x {mesh.ny} x {mesh.nz} voxels"
        f" ({mesh.nx * mesh.ny * mesh.nz:,} total)"
    )

    t = result.temperatures_c
    print(
        f"Tmin / Tavg / Tmax [C]: "
        f"{t.min():.2f} / {t.mean():.2f} / {t.max():.2f}"
    )

    _print_hottest_voxels(result, args.top_n)

    if args.csv:
        csv_path = args.output_dir / "temperature_voxels.csv"
        export_voxel_csv(result, mesh, csv_path)
        print(f"Voxel CSV exported to: {csv_path.resolve()}")

    if args.plot:
        _plot_slice(result, mesh, args.plot_z, args.output_dir / "temperature_map.png")

    print(f"Artifacts exported to: {args.output_dir.resolve()}")


def _run_transient(project, args) -> None:
    try:
        from thermal_sim.solvers.transient_voxel import VoxelTransientSolver
    except ImportError as exc:
        raise ImportError(
            "VoxelTransientSolver not found. "
            "transient_voxel.py must be present (see Phase 11 Plan 02)."
        ) from exc

    from thermal_sim.io.csv_export import export_voxel_csv

    result = VoxelTransientSolver().solve(project)
    mesh = result.mesh

    print(f"Project: {project.name}")
    print("Mode: transient")
    print(
        f"Mesh: {mesh.nx} x {mesh.ny} x {mesh.nz} voxels"
        f" ({mesh.nx * mesh.ny * mesh.nz:,} total)"
    )

    t_final = result.temperatures_c[-1]
    print(
        f"Final Tmin / Tavg / Tmax [C]: "
        f"{t_final.min():.2f} / {t_final.mean():.2f} / {t_final.max():.2f}"
    )

    _print_hottest_voxels_transient(result, args.top_n)

    if args.csv:
        # Export the final time step
        from dataclasses import replace
        final_result = replace(result, temperatures_c=t_final)
        csv_path = args.output_dir / "temperature_voxels_final.csv"
        export_voxel_csv(final_result, mesh, csv_path)
        print(f"Final voxel CSV exported to: {csv_path.resolve()}")

    if args.plot:
        _plot_slice_transient(result, mesh, args.plot_z, args.output_dir / "temperature_map.png")

    print(f"Artifacts exported to: {args.output_dir.resolve()}")


def _print_hottest_voxels(result, top_n: int) -> None:
    """Print top-N hottest voxels with their 3D positions."""
    import numpy as np

    mesh = result.mesh
    t = result.temperatures_c
    flat = t.ravel()
    n = min(top_n, flat.size)
    indices = np.argpartition(flat, -n)[-n:]
    indices = indices[np.argsort(flat[indices])[::-1]]

    print(f"Top {n} hottest voxels:")
    for idx in indices:
        iz = int(idx // (mesh.ny * mesh.nx))
        remainder = int(idx % (mesh.ny * mesh.nx))
        iy = int(remainder // mesh.nx)
        ix = int(remainder % mesh.nx)
        x_m = mesh.x_edges[ix] + 0.5 * (mesh.x_edges[ix + 1] - mesh.x_edges[ix])
        y_m = mesh.y_edges[iy] + 0.5 * (mesh.y_edges[iy + 1] - mesh.y_edges[iy])
        z_m = mesh.z_edges[iz] + 0.5 * (mesh.z_edges[iz + 1] - mesh.z_edges[iz])
        print(
            f"  {flat[idx]:.2f} C  at  "
            f"({x_m * 1e3:.1f} mm, {y_m * 1e3:.1f} mm, {z_m * 1e3:.2f} mm)"
        )


def _print_hottest_voxels_transient(result, top_n: int) -> None:
    """Print top-N hottest voxels in the final time-step."""
    import numpy as np

    mesh = result.mesh
    t_final = result.temperatures_c[-1]
    flat = t_final.ravel()
    n = min(top_n, flat.size)
    indices = np.argpartition(flat, -n)[-n:]
    indices = indices[np.argsort(flat[indices])[::-1]]

    print(f"Top {n} hottest voxels (final step):")
    for idx in indices:
        iz = int(idx // (mesh.ny * mesh.nx))
        remainder = int(idx % (mesh.ny * mesh.nx))
        iy = int(remainder // mesh.nx)
        ix = int(remainder % mesh.nx)
        x_m = mesh.x_edges[ix] + 0.5 * (mesh.x_edges[ix + 1] - mesh.x_edges[ix])
        y_m = mesh.y_edges[iy] + 0.5 * (mesh.y_edges[iy + 1] - mesh.y_edges[iy])
        z_m = mesh.z_edges[iz] + 0.5 * (mesh.z_edges[iz + 1] - mesh.z_edges[iz])
        print(
            f"  {flat[idx]:.2f} C  at  "
            f"({x_m * 1e3:.1f} mm, {y_m * 1e3:.1f} mm, {z_m * 1e3:.2f} mm)"
        )


def _plot_slice(result, mesh, plot_z: float | None, output_path: Path) -> None:
    """Generate a 2D x-y temperature slice PNG at the given z position."""
    import numpy as np

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Plotting requires matplotlib. Install dependencies from requirements.txt."
        ) from exc

    # Choose z index
    z_centres = 0.5 * (mesh.z_edges[:-1] + mesh.z_edges[1:])
    if plot_z is None:
        iz = len(z_centres) // 2
    else:
        iz = int(np.argmin(np.abs(z_centres - plot_z)))

    t_slice = result.temperatures_c[iz]

    fig, ax = plt.subplots(figsize=(8, 5))
    extent = [
        mesh.x_edges[0] * 1e3, mesh.x_edges[-1] * 1e3,
        mesh.y_edges[0] * 1e3, mesh.y_edges[-1] * 1e3,
    ]
    im = ax.imshow(
        t_slice,
        origin="lower",
        extent=extent,
        aspect="auto",
        cmap="hot",
    )
    plt.colorbar(im, ax=ax, label="Temperature [°C]")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title(f"Steady-state temperature — z = {z_centres[iz] * 1e3:.2f} mm")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Plot saved to: {output_path.resolve()}")


def _plot_slice_transient(result, mesh, plot_z: float | None, output_path: Path) -> None:
    """Generate a 2D x-y temperature slice PNG for the final transient step."""
    import numpy as np

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Plotting requires matplotlib. Install dependencies from requirements.txt."
        ) from exc

    z_centres = 0.5 * (mesh.z_edges[:-1] + mesh.z_edges[1:])
    if plot_z is None:
        iz = len(z_centres) // 2
    else:
        iz = int(np.argmin(np.abs(z_centres - plot_z)))

    t_slice = result.temperatures_c[-1][iz]

    fig, ax = plt.subplots(figsize=(8, 5))
    extent = [
        mesh.x_edges[0] * 1e3, mesh.x_edges[-1] * 1e3,
        mesh.y_edges[0] * 1e3, mesh.y_edges[-1] * 1e3,
    ]
    im = ax.imshow(
        t_slice,
        origin="lower",
        extent=extent,
        aspect="auto",
        cmap="hot",
    )
    plt.colorbar(im, ax=ax, label="Temperature [°C]")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title(
        f"Transient final temperature — z = {z_centres[iz] * 1e3:.2f} mm"
        f"  (t = {result.time_points[-1]:.1f} s)"
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Plot saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
