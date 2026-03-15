"""PDF report generation using matplotlib PdfPages."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from thermal_sim.models.snapshot import ResultSnapshot
from thermal_sim.core.postprocess import top_n_hottest_cells_for_layer
from thermal_sim.visualization.plotting import plot_temperature_map_annotated


def generate_pdf_report(snapshot: ResultSnapshot, output_path: Path | str) -> None:
    """Generate a multi-page PDF engineering report from a result snapshot."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with plt.style.context("default"):
        with PdfPages(output_path) as pdf:
            # Page 1: header + stack summary + metrics table
            fig = _make_summary_page(snapshot)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

            # Pages 2..N: temperature maps per layer (with per-layer hotspot annotations)
            for layer_idx, layer_name in enumerate(snapshot.layer_names):
                fig = _make_temperature_map_page(snapshot, layer_idx, layer_name)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

            # Page N+1: hotspot ranking table
            fig = _make_hotspot_table_page(snapshot)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

            # Page N+2: probe history (transient only)
            if snapshot.mode == "transient" and snapshot.times_s is not None:
                fig = _make_probe_history_page(snapshot)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

            # PDF metadata
            d = pdf.infodict()
            d["Title"] = f"Thermal Report - {snapshot.project_name}"
            d["Subject"] = f"{snapshot.mode} simulation"


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _make_summary_page(snapshot: ResultSnapshot):
    """Letter-sized summary page with header and per-layer stats table."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    # Header text
    ax.text(0.5, 0.95, f"Thermal Report — {snapshot.project_name}",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=14, fontweight="bold")
    ax.text(0.5, 0.91, f"Mode: {snapshot.mode.capitalize()}    Date: {snapshot.simulation_date}",
            transform=ax.transAxes, ha="center", va="top", fontsize=10, color="gray")

    if not snapshot.layer_stats:
        ax.text(0.5, 0.80, "No layer statistics available.",
                transform=ax.transAxes, ha="center", va="top", fontsize=10)
        return fig

    # Build table data
    col_labels = ["Layer", "T_max [C]", "T_avg [C]", "T_min [C]", "DeltaT [C]"]
    table_data = []
    for entry in snapshot.layer_stats:
        table_data.append([
            entry.get("layer", ""),
            f"{entry.get('t_max_c', 0.0):.2f}",
            f"{entry.get('t_avg_c', 0.0):.2f}",
            f"{entry.get('t_min_c', 0.0):.2f}",
            f"{entry.get('delta_t_c', 0.0):.2f}",
        ])

    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)

    return fig


def _make_temperature_map_page(snapshot: ResultSnapshot, layer_idx: int, layer_name: str):
    """Standard figure with annotated temperature map for a single layer."""
    fig, ax = plt.subplots(figsize=(10, 7))

    layer_slice = snapshot.final_temperatures_c[layer_idx]
    per_layer_hotspots = top_n_hottest_cells_for_layer(
        snapshot.final_temperatures_c,
        layer_idx=layer_idx,
        layer_name=layer_name,
        dx=snapshot.dx,
        dy=snapshot.dy,
        n=3,
    )

    # Look up zones for this layer (may be absent in older snapshots)
    layer_zones_map = getattr(snapshot, "layer_zones", {})
    layer_zone_list = layer_zones_map.get(layer_name) or None

    im = plot_temperature_map_annotated(
        ax,
        layer_slice,
        snapshot.width_m,
        snapshot.height_m,
        title=f"Temperature Map — {layer_name}",
        hotspots=per_layer_hotspots,
        probes=snapshot.probes if snapshot.probes else None,
        zones=layer_zone_list,
    )

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Temperature [C]")
    fig.tight_layout()

    return fig


def _make_hotspot_table_page(snapshot: ResultSnapshot):
    """Letter-sized hotspot ranking table."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    ax.text(0.5, 0.97, "Top Hotspot Ranking",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=13, fontweight="bold")

    if not snapshot.hotspots:
        ax.text(0.5, 0.90, "No hotspot data available.",
                transform=ax.transAxes, ha="center", va="top", fontsize=10)
        return fig

    col_labels = ["Rank", "Layer", "X [mm]", "Y [mm]", "Temperature [C]"]
    table_data = []
    for rank, hotspot in enumerate(snapshot.hotspots, start=1):
        table_data.append([
            str(rank),
            hotspot.get("layer", ""),
            f"{hotspot.get('x_m', 0.0) * 1000.0:.1f}",
            f"{hotspot.get('y_m', 0.0) * 1000.0:.1f}",
            f"{hotspot.get('temperature_c', 0.0):.2f}",
        ])

    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)

    return fig


def _make_probe_history_page(snapshot: ResultSnapshot):
    """Probe temperature history plot (transient mode only)."""
    fig, ax = plt.subplots(figsize=(10, 7))

    if snapshot.probe_values and snapshot.times_s is not None:
        for probe_name, values in snapshot.probe_values.items():
            ax.plot(snapshot.times_s, values, label=probe_name)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [C]")
    ax.set_title("Probe Temperature History")
    if snapshot.probe_values:
        ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    return fig
