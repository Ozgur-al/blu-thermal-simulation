"""Plotting helpers for thermal simulation results."""

from __future__ import annotations

from pathlib import Path

import numpy as np

PROBE_COLORS = ["#ffc107", "#ff7043", "#66bb6a", "#42a5f5", "#ab47bc"]


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
        extent=[0.0, width_m * 1000.0, 0.0, height_m * 1000.0],
        aspect="auto",
        cmap="inferno",
    )
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("Temperature [C]")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
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
    zones: list | None = None,              # list[MaterialZone] | None — zone overlays
):
    """Render annotated temperature map onto an existing axes.

    Draws the heatmap with optional crosshair hotspot annotations, probe markers,
    and dashed zone boundary overlays.
    Used by both the GUI canvas and PDF export.
    Coordinates are converted from metres to millimetres for display.
    """
    w_mm = width_m * 1000.0
    h_mm = height_m * 1000.0
    extent = [0.0, w_mm, 0.0, h_mm]
    im = ax.imshow(temperature_map_c, origin="lower", extent=extent, aspect="auto", cmap="inferno")
    ax.set_title(title)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_xlim(0, w_mm)
    ax.set_ylim(0, h_mm)

    # Hotspot crosshairs
    if hotspots:
        for rank, hotspot in enumerate(hotspots, start=1):
            x, y = hotspot["x_m"] * 1000.0, hotspot["y_m"] * 1000.0
            alpha = 0.85 if (selected_hotspot_rank and rank == selected_hotspot_rank) else 0.55
            linewidth = 1.2 if (selected_hotspot_rank and rank == selected_hotspot_rank) else 0.7
            color = "yellow" if (selected_hotspot_rank and rank == selected_hotspot_rank) else "white"
            ax.axvline(x=x, color=color, linewidth=linewidth, alpha=alpha, linestyle="--")
            ax.axhline(y=y, color=color, linewidth=linewidth, alpha=alpha, linestyle="--")
            ax.annotate(
                f"#{rank}\n{hotspot['temperature_c']:.1f}\u00b0C",
                xy=(x, y),
                xytext=(x + 0.02 * w_mm, y + 0.02 * h_mm),
                fontsize=7,
                color=color,
                fontweight="bold",
                ha="left",
                va="bottom",
            )

    # Probe markers (diamond, distinct from crosshairs)
    if probes:
        for probe in probes:
            px, py = probe.x * 1000.0, probe.y * 1000.0
            ax.plot(px, py, marker="D", markersize=5, color="cyan",
                    markeredgewidth=0.8, markeredgecolor="black", zorder=5)
            ax.text(px, py + 0.015 * h_mm, probe.name,
                    fontsize=6, color="cyan", ha="center", va="bottom")

    # Zone overlays: dashed white rectangles with material labels
    if zones:
        from matplotlib.patches import Rectangle
        for zone in zones:
            x_mm = zone.x * 1000.0
            y_mm = zone.y * 1000.0
            w_zone_mm = zone.width * 1000.0
            h_zone_mm = zone.height * 1000.0
            rect = Rectangle(
                (x_mm, y_mm), w_zone_mm, h_zone_mm,
                linewidth=1.2,
                edgecolor="white",
                linestyle="--",
                facecolor="none",
                zorder=6,
            )
            ax.add_patch(rect)
            ax.text(
                x_mm + 0.5, y_mm + 0.5,
                zone.material,
                fontsize=6, color="white",
                va="bottom", ha="left",
                zorder=7,
            )

    return im  # Return for colorbar attachment if caller needs it


def plot_validation_comparison(
    title: str,
    analytical: dict[str, float],
    numerical: dict[str, float],
    output_path: Path | str,
) -> None:
    """Save a grouped bar chart comparing analytical vs numerical node temperatures.

    Each bar group contains one analytical bar (blue) and one numerical bar (orange).
    A percentage error annotation appears above each pair.

    Args:
        title: Figure title.
        analytical: Mapping of node label to analytical temperature (C).
        numerical: Mapping of node label to numerical temperature (C).
        output_path: Path for the saved PNG file.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    labels = list(analytical.keys())
    ana_vals = [analytical[k] for k in labels]
    num_vals = [numerical[k] for k in labels]

    x = range(len(labels))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    bars_a = ax.bar(
        [i - bar_width / 2 for i in x], ana_vals, bar_width,
        label="Analytical", color="steelblue", alpha=0.85,
    )
    bars_n = ax.bar(
        [i + bar_width / 2 for i in x], num_vals, bar_width,
        label="Numerical", color="darkorange", alpha=0.85,
    )

    # Annotate each pair with percentage error
    for i, (av, nv) in enumerate(zip(ana_vals, num_vals)):
        if abs(av) > 1e-12:
            pct_err = 100.0 * abs(nv - av) / abs(av)
        else:
            pct_err = 0.0
        max_bar = max(abs(av), abs(nv))
        ax.text(
            i, max_bar + 0.2, f"{pct_err:.4f}%",
            ha="center", va="bottom", fontsize=8, color="dimgray",
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Temperature [C]")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_validation_transient_comparison(
    title: str,
    times_s_analytical: np.ndarray,
    temps_analytical: np.ndarray,
    times_s_numerical: np.ndarray,
    temps_numerical: np.ndarray,
    output_path: Path | str,
) -> None:
    """Save a line plot comparing analytical vs numerical transient temperatures.

    Analytical result is shown as a dashed line; numerical as solid with markers.

    Args:
        title: Figure title.
        times_s_analytical: Time vector for the analytical solution.
        temps_analytical: Temperature array corresponding to ``times_s_analytical``.
        times_s_numerical: Time vector from the solver output.
        temps_numerical: Temperature array from the solver output.
        output_path: Path for the saved PNG file.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=150)
    ax.plot(
        times_s_analytical, temps_analytical,
        linestyle="--", color="steelblue", linewidth=1.5, label="Analytical",
    )
    ax.plot(
        times_s_numerical, temps_numerical,
        linestyle="-", color="darkorange", linewidth=1.2,
        marker="o", markersize=3, markevery=max(1, len(times_s_numerical) // 40),
        label="Numerical",
    )
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [C]")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
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
    for i, (name, values) in enumerate(probe_history_c.items()):
        color = PROBE_COLORS[i % len(PROBE_COLORS)]
        ax.plot(times_s, values, label=name, color=color)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [C]")
    ax.set_title(title)
    if probe_history_c:
        ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
