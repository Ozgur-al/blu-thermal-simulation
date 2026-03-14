"""PlotManager — owns all matplotlib canvases and plot update logic.

This module also defines MplCanvas, which was previously defined in main_window.py.
MainWindow imports PlotManager and delegates all matplotlib operations to it.
"""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSizePolicy

from thermal_sim.core.postprocess import layer_average_temperatures
from thermal_sim.ui.table_data_parser import TableDataParser
from thermal_sim.visualization.plotting import PROBE_COLORS


class MplCanvas(FigureCanvasQTAgg):
    """Simple matplotlib canvas that expands to fill available space."""

    def __init__(self, width: float = 5.0, height: float = 4.0, dpi: int = 100) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Cached artist references for in-place updates.
        self._image = None   # imshow artist
        self._colorbar = None  # colorbar instance
        # Debounce resize events to avoid expensive redraws on every pixel change.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._do_deferred_resize)
        self._pending_resize = None

    def resizeEvent(self, event) -> None:
        """Debounce resize to prevent expensive redraws during layout changes."""
        # Store a copy of the event — the original C++ object may be deleted
        # before the deferred timer fires.
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent
        self._pending_resize = QResizeEvent(QSize(event.size()), QSize(event.oldSize()))
        self._resize_timer.start()

    def _do_deferred_resize(self) -> None:
        """Perform the actual resize after the debounce interval."""
        if self._pending_resize is not None:
            evt = self._pending_resize
            self._pending_resize = None
            super().resizeEvent(evt)


class PlotManager:
    """Owns all three matplotlib canvases and handles plot rendering.

    Create one PlotManager per MainWindow.  Access the canvases via the public
    attributes `map_canvas`, `profile_canvas`, and `history_canvas` to embed
    them into the Qt layout.
    """

    def __init__(self) -> None:
        self.map_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        self.profile_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        self.history_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        self._batching: bool = False

    # ------------------------------------------------------------------
    # Batch rendering
    # ------------------------------------------------------------------

    def begin_batch(self) -> None:
        """Suppress individual canvas.draw() calls until end_batch() is called."""
        self._batching = True

    def end_batch(self) -> None:
        """Flush all three canvases via draw_idle() and exit batch mode.

        draw_idle() schedules the repaint through the Qt event loop rather
        than blocking the main thread synchronously.
        """
        self._batching = False
        self.map_canvas.draw_idle()
        self.profile_canvas.draw_idle()
        self.history_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Plot methods
    # ------------------------------------------------------------------

    def plot_temperature_map(
        self,
        final_map_c: np.ndarray,
        layer_names: list[str],
        layer_name: str,
        width_m: float,
        height_m: float,
    ) -> None:
        """Render (or update in-place) the temperature heat-map for one layer.

        Args:
            final_map_c: Shape (n_layers, ny, nx) temperature array.
            layer_names: Ordered list of layer names matching the first axis.
            layer_name:  Name of the layer to display.
            width_m:     Physical domain width in metres (x-axis extent).
            height_m:    Physical domain height in metres (y-axis extent).
        """
        layer_idx = (
            layer_names.index(layer_name) if layer_name in layer_names else len(layer_names) - 1
        )
        data = final_map_c[layer_idx]
        extent = [0.0, width_m * 1000.0, 0.0, height_m * 1000.0]
        ax = self.map_canvas.axes

        if self.map_canvas._image is not None:
            # Update existing image data and colorbar range in-place.
            self.map_canvas._image.set_data(data)
            self.map_canvas._image.set_extent(extent)
            self.map_canvas._image.set_clim(vmin=data.min(), vmax=data.max())
            ax.set_title(f"Temperature Map - {layer_names[layer_idx]}")
        else:
            # First plot — create image, colorbar, and layout.
            ax.clear()
            im = ax.imshow(data, origin="lower", extent=extent, aspect="equal", cmap="inferno")
            ax.set_title(f"Temperature Map - {layer_names[layer_idx]}")
            ax.set_xlabel("x [mm]")
            ax.set_ylabel("y [mm]")
            self.map_canvas._colorbar = self.map_canvas.figure.colorbar(
                im, ax=ax, label="Temperature [\u00b0C]"
            )
            self.map_canvas._image = im
            self.map_canvas.figure.tight_layout()

        if not self._batching:
            self.map_canvas.draw()

    def plot_layer_profile(
        self,
        final_map_c: np.ndarray,
        layer_names: list[str],
        x_m: float,
        y_m: float,
        width_m: float,
        height_m: float,
    ) -> None:
        """Render the through-thickness temperature profile at a given (x, y) point.

        Args:
            final_map_c: Shape (n_layers, ny, nx) temperature array.
            layer_names: Ordered list of layer names.
            x_m:        Profile point x-coordinate in metres.
            y_m:        Profile point y-coordinate in metres.
            width_m:    Physical domain width in metres.
            height_m:   Physical domain height in metres.
        """
        nx = final_map_c.shape[2]
        ny = final_map_c.shape[1]
        ix = max(0, min(nx - 1, int(np.floor((x_m / max(width_m, 1e-12)) * nx))))
        iy = max(0, min(ny - 1, int(np.floor((y_m / max(height_m, 1e-12)) * ny))))
        vals = final_map_c[:, iy, ix]
        ax = self.profile_canvas.axes
        ax.clear()
        ax.plot(vals, np.arange(len(layer_names)), marker="o")
        ax.set_yticks(np.arange(len(layer_names)))
        ax.set_yticklabels(layer_names)
        ax.set_xlabel("Temperature [\u00b0C]")
        ax.set_ylabel("Layer")
        ax.set_title(f"Layer Profile @ x={x_m * 1000:.1f} mm, y={y_m * 1000:.1f} mm")
        ax.grid(True, alpha=0.3)
        self.profile_canvas.figure.tight_layout()
        if not self._batching:
            self.profile_canvas.draw()

    def plot_probe_history(
        self,
        times_s: np.ndarray | None,
        probe_history: dict[str, np.ndarray],
    ) -> None:
        """Render probe-temperature time-series curves.

        If *times_s* is None or *probe_history* is empty, displays a placeholder message.
        """
        ax = self.history_canvas.axes
        ax.clear()
        if times_s is None or not probe_history:
            ax.text(
                0.5,
                0.5,
                "No probe history available.\nRun in transient mode with probes defined to see time-series data.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
        else:
            for i, (name, values) in enumerate(probe_history.items()):
                color = PROBE_COLORS[i % len(PROBE_COLORS)]
                ax.plot(times_s, values, label=name, color=color)
            ax.set_xlabel("Time [s]")
            ax.set_ylabel("Temperature [\u00b0C]")
            ax.set_title("Probe Temperatures vs Time")
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best")
        self.history_canvas.figure.tight_layout()
        if not self._batching:
            self.history_canvas.draw()

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def refresh_summary(
        self,
        stats_label,
        hot_table,
        summary_text,
        min_c: float,
        avg_c: float,
        max_c: float,
        final_map_c: np.ndarray,
        layer_names: list[str],
        hottest: list[dict],
        set_table_rows_fn=None,
    ) -> None:
        """Update the summary tab widgets with current result statistics.

        Args:
            stats_label:       QLabel showing Tmin/Tavg/Tmax.
            hot_table:         QTableWidget for hottest cells.
            summary_text:      QTextEdit for layer averages text.
            min_c / avg_c / max_c: Scalar temperature statistics.
            final_map_c:       Shape (n_layers, ny, nx) temperature array.
            layer_names:       Ordered list of layer names.
            hottest:           List of dicts from top_n_hottest_cells*.
            set_table_rows_fn: Optional callable(table, rows) — defaults to
                               TableDataParser._set_table_rows.
        """
        if set_table_rows_fn is None:
            set_table_rows_fn = TableDataParser._set_table_rows

        stats_label.setText(
            f"Tmin / Tavg / Tmax [\u00b0C]: {min_c:.2f} / {avg_c:.2f} / {max_c:.2f}"
        )
        set_table_rows_fn(
            hot_table,
            [
                [h["layer"], f"{h['temperature_c']:.2f}", f"{h['x_m'] * 1000:.2f}", f"{h['y_m'] * 1000:.2f}"]
                for h in hottest
            ],
        )
        averages = layer_average_temperatures(final_map_c, layer_names)
        lines = ["Layer averages:"]
        for name, temp in averages.items():
            lines.append(f"- {name}: {temp:.2f} C")
        lines.append("")
        lines.append("Layer-to-layer drops:")
        for i in range(len(layer_names) - 1):
            drop = averages[layer_names[i + 1]] - averages[layer_names[i]]
            lines.append(f"- {layer_names[i]} -> {layer_names[i + 1]}: {drop:+.2f} C")
        summary_text.setPlainText("\n".join(lines))

    def fill_probe_table(
        self,
        probe_table,
        probe_values: dict[str, float],
        set_table_rows_fn=None,
    ) -> None:
        """Populate the probe readings table with current probe values.

        Args:
            probe_table:       QTableWidget for probe readings.
            probe_values:      Dict mapping probe name to temperature.
            set_table_rows_fn: Optional callable — defaults to TableDataParser._set_table_rows.
        """
        if set_table_rows_fn is None:
            set_table_rows_fn = TableDataParser._set_table_rows

        set_table_rows_fn(probe_table, [[k, f"{v:.2f}"] for k, v in probe_values.items()])
