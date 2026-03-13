"""Plotting helpers for thermal simulation results."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def plot_temperature_map(
    temperature_map_c: np.ndarray,
    width_m: float,
    height_m: float,
    title: str,
    output_path: str | Path,
) -> None:
    """Save a 2D contour-like heatmap image."""
    import matplotlib.pyplot as plt

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    image = ax.imshow(
        temperature_map_c,
        origin="lower",
        extent=[0.0, width_m, 0.0, height_m],
        aspect="auto",
        cmap="inferno",
    )
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Temperature [C]")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_probe_history(
    times_s: np.ndarray,
    probe_history_c: dict[str, np.ndarray],
    output_path: str | Path,
    title: str = "Probe Temperature vs Time",
) -> None:
    """Save temperature-time curves for selected probe points."""
    import matplotlib.pyplot as plt

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    for name, values in probe_history_c.items():
        ax.plot(times_s, values, label=name)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [C]")
    ax.set_title(title)
    if probe_history_c:
        ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
