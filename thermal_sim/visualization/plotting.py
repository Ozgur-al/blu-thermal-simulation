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


def plot_temperature_map_annotated(
    ax,
    temperature_map_c: np.ndarray,    # 2D [ny, nx] single-layer slice
    width_m: float,
    height_m: float,
    title: str,
    hotspots: list[dict] | None = None,    # per-layer hotspots with x_m, y_m, temperature_c
    probes: list | None = None,             # Probe objects with name, x, y
    selected_hotspot_rank: int | None = None,  # 1-based rank to highlight
):
    """Render annotated temperature map onto an existing axes.

    Draws the heatmap with optional crosshair hotspot annotations and probe markers.
    Used by both the GUI canvas and PDF export.
    """
    extent = [0.0, width_m, 0.0, height_m]
    im = ax.imshow(temperature_map_c, origin="lower", extent=extent, aspect="auto", cmap="inferno")
    ax.set_title(title)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_xlim(0, width_m)
    ax.set_ylim(0, height_m)

    # Hotspot crosshairs
    if hotspots:
        for rank, hotspot in enumerate(hotspots, start=1):
            x, y = hotspot["x_m"], hotspot["y_m"]
            alpha = 0.85 if (selected_hotspot_rank and rank == selected_hotspot_rank) else 0.55
            linewidth = 1.2 if (selected_hotspot_rank and rank == selected_hotspot_rank) else 0.7
            color = "yellow" if (selected_hotspot_rank and rank == selected_hotspot_rank) else "white"
            ax.axvline(x=x, color=color, linewidth=linewidth, alpha=alpha, linestyle="--")
            ax.axhline(y=y, color=color, linewidth=linewidth, alpha=alpha, linestyle="--")
            ax.annotate(
                f"#{rank}\n{hotspot['temperature_c']:.1f}\u00b0C",
                xy=(x, y),
                xytext=(x + 0.02 * width_m, y + 0.02 * height_m),
                fontsize=7,
                color=color,
                fontweight="bold",
                ha="left",
                va="bottom",
            )

    # Probe markers (diamond, distinct from crosshairs)
    if probes:
        for probe in probes:
            ax.plot(probe.x, probe.y, marker="D", markersize=5, color="cyan",
                    markeredgewidth=0.8, markeredgecolor="black", zorder=5)
            ax.text(probe.x, probe.y + 0.015 * height_m, probe.name,
                    fontsize=6, color="cyan", ha="center", va="bottom")

    return im  # Return for colorbar attachment if caller needs it


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
