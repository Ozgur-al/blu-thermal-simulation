"""Comparison tab widget for side-by-side analysis of saved result snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from thermal_sim.models.snapshot import ResultSnapshot
from thermal_sim.visualization.plotting import plot_temperature_map_annotated

# Try to import MplCanvas from plot_manager (canonical location post-Phase 1).
try:
    from thermal_sim.ui.plot_manager import MplCanvas
except ImportError:
    # Fallback: define a minimal canvas locally.
    class MplCanvas(FigureCanvasQTAgg):  # type: ignore[no-redef]
        """Simple matplotlib canvas that expands to fill available space."""

        def __init__(self, width: float = 5.0, height: float = 4.0, dpi: int = 100) -> None:
            self.figure = Figure(figsize=(width, height), dpi=dpi)
            self.axes = self.figure.add_subplot(111)
            super().__init__(self.figure)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )


# Line styles cycled within a snapshot for different probes.
_LINE_STYLES = ["-", "--", "-.", ":"]


class ComparisonWidget(QWidget):
    """Side-by-side comparison of up to 4 named result snapshots.

    Layout (vertical splitter with three sections):
      1. Snapshot selection bar (top)
      2. Metric comparison table (middle)
      3. Plot tabs — probe overlay and temperature maps (bottom)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snapshots: list[ResultSnapshot] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Section 1 — snapshot selection bar
        splitter.addWidget(self._build_selection_bar())

        # Section 2 — metric table
        splitter.addWidget(self._build_metric_group())

        # Section 3 — plot tabs
        splitter.addWidget(self._build_plot_tabs())

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        root.addWidget(splitter)

    def _build_selection_bar(self) -> QWidget:
        widget = QWidget()
        outer = QHBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)

        # Left: snapshot list
        left = QVBoxLayout()
        left.addWidget(QLabel("Saved snapshots (select 2–4 to compare):"))
        self._snap_list = QListWidget()
        self._snap_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._snap_list.setMaximumHeight(110)
        left.addWidget(self._snap_list)
        outer.addLayout(left, stretch=3)

        # Right: controls
        right = QVBoxLayout()
        right.setSpacing(4)

        self._compare_btn = QPushButton("Compare")
        self._compare_btn.setToolTip("Render comparison for selected snapshots")
        self._compare_btn.clicked.connect(self._on_compare_clicked)

        right.addWidget(QLabel("Map layer:"))
        self._layer_combo = QComboBox()
        self._layer_combo.setToolTip("Layer shown in the temperature map comparison")
        right.addWidget(self._layer_combo)
        right.addWidget(self._compare_btn)
        right.addStretch()

        outer.addLayout(right, stretch=1)

        return widget

    def _build_metric_group(self) -> QGroupBox:
        group = QGroupBox("Metric Comparison")
        layout = QVBoxLayout(group)

        self._metric_table = QTableWidget()
        self._metric_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._metric_table.setAlternatingRowColors(True)
        self._metric_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._metric_table.horizontalHeader().setStretchLastSection(True)
        self._metric_table.horizontalHeader().setMinimumSectionSize(80)
        self._metric_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        layout.addWidget(self._metric_table)
        return group

    def _build_plot_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        # Probe overlay tab
        probe_tab = QWidget()
        probe_layout = QVBoxLayout(probe_tab)
        self._probe_canvas = MplCanvas(width=6.0, height=4.0, dpi=100)
        probe_layout.addWidget(self._probe_canvas)
        tabs.addTab(probe_tab, "Probe Overlay")

        # Temperature maps tab
        maps_tab = QWidget()
        maps_layout = QVBoxLayout(maps_tab)
        self._maps_canvas = MplCanvas(width=8.0, height=6.0, dpi=100)
        maps_layout.addWidget(self._maps_canvas)
        tabs.addTab(maps_tab, "Temperature Maps")

        return tabs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_snapshots(self, snapshots: list[ResultSnapshot]) -> None:
        """Update the snapshot list widget with the given snapshots."""
        self._snapshots = list(snapshots)
        self._snap_list.clear()
        for snap in self._snapshots:
            self._snap_list.addItem(snap.name)

    # ------------------------------------------------------------------
    # Comparison rendering
    # ------------------------------------------------------------------

    def _on_compare_clicked(self) -> None:
        """Render comparison for the currently selected snapshots."""
        selected_indices = [
            self._snap_list.row(item)
            for item in self._snap_list.selectedItems()
        ]
        if len(selected_indices) < 2:
            QMessageBox.information(
                self,
                "Select snapshots",
                "Please select 2–4 snapshots to compare.",
            )
            return

        # Cap at 4 snapshots for comparison.
        selected_indices = selected_indices[:4]
        selected = [self._snapshots[i] for i in selected_indices]

        # Populate layer combo from first selected snapshot.
        current_layer = self._layer_combo.currentText()
        self._layer_combo.clear()
        self._layer_combo.addItems(selected[0].layer_names)
        if current_layer in selected[0].layer_names:
            self._layer_combo.setCurrentText(current_layer)

        self._populate_metric_table(selected)
        self._render_probe_overlay(selected)
        self._render_temperature_maps(selected)

    def _populate_metric_table(self, snapshots: list[ResultSnapshot]) -> None:
        """Fill the metric comparison table.

        Columns: Metric | snapshot_0 | ... | snapshot_n | Delta
        Rows: one bold separator per layer, then T_max / T_avg / T_min / DeltaT.
        """
        metric_keys = ["t_max_c", "t_avg_c", "t_min_c", "delta_t_c"]
        metric_labels = ["T_max [C]", "T_avg [C]", "T_min [C]", "DeltaT [C]"]

        first = snapshots[0]
        n_layers = len(first.layer_names)
        # 1 separator row + 4 metric rows per layer
        n_rows = n_layers * (1 + len(metric_keys))
        n_cols = 1 + len(snapshots) + 1  # Metric + snapshots + Delta

        self._metric_table.clearContents()
        self._metric_table.setRowCount(n_rows)
        self._metric_table.setColumnCount(n_cols)

        # Header labels
        headers = ["Metric"] + [s.name for s in snapshots] + ["Delta"]
        self._metric_table.setHorizontalHeaderLabels(headers)

        row = 0
        for layer_idx, layer_name in enumerate(first.layer_names):
            # Bold separator row for layer name.
            separator = QTableWidgetItem(layer_name)
            separator.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = separator.font()
            font.setBold(True)
            separator.setFont(font)
            self._metric_table.setItem(row, 0, separator)
            # Span the full width.
            self._metric_table.setSpan(row, 0, 1, n_cols)
            row += 1

            for key, label in zip(metric_keys, metric_labels):
                # Metric label
                label_item = QTableWidgetItem(label)
                self._metric_table.setItem(row, 0, label_item)

                # Values per snapshot
                first_val: float | None = None
                last_val: float | None = None
                for col_offset, snap in enumerate(snapshots, start=1):
                    # Find the stats entry for this layer.
                    val = self._get_stat(snap, layer_idx, key)
                    cell = QTableWidgetItem(f"{val:.2f}" if val is not None else "—")
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self._metric_table.setItem(row, col_offset, cell)
                    if col_offset == 1:
                        first_val = val
                    last_val = val

                # Delta column
                if first_val is not None and last_val is not None:
                    delta = last_val - first_val
                    delta_text = f"{delta:+.2f}"
                else:
                    delta_text = "—"
                delta_item = QTableWidgetItem(delta_text)
                delta_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._metric_table.setItem(row, n_cols - 1, delta_item)

                row += 1

        self._metric_table.resizeColumnsToContents()

    def _get_stat(self, snap: ResultSnapshot, layer_idx: int, key: str) -> float | None:
        """Extract a stat value from a snapshot's layer_stats list."""
        if not snap.layer_stats or layer_idx >= len(snap.layer_stats):
            return None
        return snap.layer_stats[layer_idx].get(key)

    def _render_probe_overlay(self, snapshots: list[ResultSnapshot]) -> None:
        """Overlay probe histories from multiple snapshots on one axes."""
        cmap = __import__("matplotlib").colormaps["tab10"]
        canvas = self._probe_canvas
        ax = canvas.axes
        ax.clear()

        has_data = False

        for snap_idx, snap in enumerate(snapshots):
            color = cmap(snap_idx / 10)

            if snap.mode == "transient" and snap.times_s is not None and snap.probe_values:
                # Transient: plot time series.
                for probe_idx, (probe_name, values) in enumerate(snap.probe_values.items()):
                    if not isinstance(values, np.ndarray):
                        # Scalar — plot as horizontal line.
                        ax.axhline(
                            y=float(values),
                            color=color,
                            linestyle=_LINE_STYLES[probe_idx % len(_LINE_STYLES)],
                            label=f"{snap.name} - {probe_name}",
                        )
                    else:
                        t = snap.times_s
                        if len(values) == len(t):
                            ax.plot(
                                t, values,
                                color=color,
                                linestyle=_LINE_STYLES[probe_idx % len(_LINE_STYLES)],
                                label=f"{snap.name} - {probe_name}",
                            )
                    has_data = True
            elif snap.probe_values:
                # Steady-state: horizontal lines.
                for probe_idx, (probe_name, value) in enumerate(snap.probe_values.items()):
                    scalar = float(value) if not isinstance(value, np.ndarray) else float(value[-1])
                    ax.axhline(
                        y=scalar,
                        color=color,
                        linestyle=_LINE_STYLES[probe_idx % len(_LINE_STYLES)],
                        label=f"{snap.name} - {probe_name}",
                    )
                    has_data = True

        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Temperature [C]")
        ax.set_title("Probe Temperature Overlay")
        ax.grid(True, alpha=0.25)
        if has_data:
            ax.legend(loc="best", fontsize=7)

        canvas.figure.tight_layout()
        canvas.draw_idle()

    def _render_temperature_maps(self, snapshots: list[ResultSnapshot]) -> None:
        """Render side-by-side temperature maps for the selected layer."""
        layer_name = self._layer_combo.currentText()
        canvas = self._maps_canvas

        # Clear previous figure content.
        canvas.figure.clear()

        n = len(snapshots)
        if n <= 2:
            rows, cols = 1, 2
        else:
            rows, cols = 2, 2

        axes = canvas.figure.subplots(rows, cols)
        # Ensure axes is always a flat list.
        if rows == 1 and cols == 1:
            axes_flat = [axes]
        else:
            axes_flat = list(np.array(axes).ravel())

        # Determine global vmin/vmax across all selected snapshots for this layer.
        vmin = float("inf")
        vmax = float("-inf")
        layer_slices: list[np.ndarray | None] = []
        for snap in snapshots:
            layer_idx = (
                snap.layer_names.index(layer_name)
                if layer_name in snap.layer_names
                else 0
            )
            slc = snap.final_temperatures_c[layer_idx]
            layer_slices.append(slc)
            vmin = min(vmin, float(slc.min()))
            vmax = max(vmax, float(slc.max()))

        # Plot each snapshot.
        last_im = None
        for i, (snap, slc) in enumerate(zip(snapshots, layer_slices)):
            ax = axes_flat[i]
            if slc is None:
                ax.set_visible(False)
                continue
            im = plot_temperature_map_annotated(
                ax,
                slc,
                snap.width_m,
                snap.height_m,
                title=f"{snap.name}\n{layer_name}",
                probes=snap.probes if snap.probes else None,
            )
            im.set_clim(vmin, vmax)
            last_im = im

        # Hide unused axes.
        for j in range(len(snapshots), len(axes_flat)):
            axes_flat[j].set_visible(False)

        # Shared colorbar.
        if last_im is not None:
            canvas.figure.colorbar(last_im, ax=axes_flat[:len(snapshots)], label="Temperature [C]")

        canvas.figure.tight_layout()
        canvas.draw_idle()
