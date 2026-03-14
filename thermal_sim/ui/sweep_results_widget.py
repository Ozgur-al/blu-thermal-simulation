"""SweepResultsWidget — displays parametric sweep results as table + plot.

Provides a comparison table (parameter value vs T_max/T_avg per layer),
a parameter-vs-metric plot with layer/metric dropdown selectors,
and Export CSV / Export PNG buttons.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from thermal_sim.ui.plot_manager import MplCanvas


class SweepResultsWidget(QWidget):
    """Widget that shows the results of a completed parametric sweep.

    Layout
    ------
    - Comparison table: columns are Parameter Value, then T_max/T_avg per layer.
    - Controls row: Layer dropdown + Metric dropdown (T_max / T_avg).
    - Parameter-vs-metric plot.
    - Export CSV and Export PNG buttons.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sweep_result = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Placeholder label shown before first sweep result
        self._placeholder = QLabel(
            "Run a parametric sweep (Run > Parametric Sweep...) to see results here."
        )
        self._placeholder.setStyleSheet("color: grey;")
        layout.addWidget(self._placeholder)

        # Comparison table (hidden until result arrives)
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._table.hide()
        layout.addWidget(self._table)

        # Controls: layer dropdown + metric dropdown
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Layer:"))
        self._layer_combo = QComboBox()
        self._layer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._layer_combo.currentTextChanged.connect(self._refresh_plot)
        controls.addWidget(self._layer_combo)

        controls.addWidget(QLabel("Metric:"))
        self._metric_combo = QComboBox()
        self._metric_combo.addItems(["T_max", "T_avg"])
        self._metric_combo.currentTextChanged.connect(self._refresh_plot)
        controls.addWidget(self._metric_combo)
        controls.addStretch()
        layout.addLayout(controls)

        # Plot canvas
        self._canvas = MplCanvas(width=5.0, height=3.0, dpi=100)
        self._canvas.hide()
        layout.addWidget(self._canvas)

        # Export buttons
        btn_row = QHBoxLayout()
        self._export_csv_btn = QPushButton("Export CSV")
        self._export_csv_btn.setEnabled(False)
        self._export_csv_btn.clicked.connect(self._export_csv)
        self._export_png_btn = QPushButton("Export PNG")
        self._export_png_btn.setEnabled(False)
        self._export_png_btn.clicked.connect(self._export_png)
        btn_row.addWidget(self._export_csv_btn)
        btn_row.addWidget(self._export_png_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_results(self, sweep_result: object) -> None:
        """Populate the table and plot from a completed SweepResult.

        Parameters
        ----------
        sweep_result:
            A ``SweepResult`` instance from the sweep engine.
        """
        self._sweep_result = sweep_result
        self._placeholder.hide()
        self._populate_table(sweep_result)
        self._populate_layer_combo(sweep_result)
        self._table.show()
        self._canvas.show()
        self._export_csv_btn.setEnabled(True)
        self._export_png_btn.setEnabled(True)
        self._refresh_plot()

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _populate_table(self, sweep_result: object) -> None:
        """Build the comparison table columns and rows."""
        if not sweep_result.runs:
            return
        layer_names = [s["layer"] for s in sweep_result.runs[0].layer_stats]
        # Columns: Parameter Value, then T_max + T_avg per layer
        cols = ["Parameter Value"]
        for name in layer_names:
            cols.append(f"{name} T_max [C]")
            cols.append(f"{name} T_avg [C]")

        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(len(sweep_result.runs))

        for row_idx, run in enumerate(sweep_result.runs):
            self._table.setItem(
                row_idx, 0, QTableWidgetItem(f"{run.parameter_value:g}")
            )
            for col_offset, stat in enumerate(run.layer_stats):
                base = 1 + col_offset * 2
                self._table.setItem(
                    row_idx, base, QTableWidgetItem(f"{stat['t_max_c']:.2f}")
                )
                self._table.setItem(
                    row_idx, base + 1, QTableWidgetItem(f"{stat['t_avg_c']:.2f}")
                )

        self._table.resizeColumnsToContents()

    def _populate_layer_combo(self, sweep_result: object) -> None:
        """Fill the layer dropdown from the first run's stats."""
        self._layer_combo.blockSignals(True)
        self._layer_combo.clear()
        if sweep_result.runs:
            for stat in sweep_result.runs[0].layer_stats:
                self._layer_combo.addItem(stat["layer"])
        self._layer_combo.blockSignals(False)

    def _refresh_plot(self) -> None:
        """Redraw the parameter-vs-metric plot based on current dropdown selections."""
        result = self._sweep_result
        if result is None or not result.runs:
            return

        layer_name = self._layer_combo.currentText()
        metric = self._metric_combo.currentText()  # "T_max" or "T_avg"
        metric_key = "t_max_c" if metric == "T_max" else "t_avg_c"

        x_vals = []
        y_vals = []
        for run in result.runs:
            x_vals.append(run.parameter_value)
            for stat in run.layer_stats:
                if stat["layer"] == layer_name:
                    y_vals.append(stat[metric_key])
                    break

        ax = self._canvas.axes
        ax.clear()
        ax.plot(x_vals, y_vals, marker="o", linewidth=1.5)
        ax.set_xlabel(f"Parameter: {result.config.parameter}")
        ax.set_ylabel(f"{metric} [\u00b0C]")
        ax.set_title(f"{metric} vs sweep parameter — {layer_name}")
        ax.grid(True, alpha=0.3)
        self._canvas.figure.tight_layout()
        self._canvas.draw_idle()

    def _export_csv(self) -> None:
        """Export sweep results table to CSV."""
        from thermal_sim.io.csv_export import export_sweep_results

        result = self._sweep_result
        if result is None:
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sweep CSV",
            "sweep_results.csv",
            "CSV (*.csv);;All Files (*)",
        )
        if not path_str:
            return
        try:
            export_sweep_results(result, Path(path_str))
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export failed", str(exc))

    def _export_png(self) -> None:
        """Save the current sweep plot to a PNG file."""
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sweep Plot",
            "sweep_plot.png",
            "PNG (*.png);;All Files (*)",
        )
        if not path_str:
            return
        try:
            self._canvas.figure.savefig(path_str, dpi=150, bbox_inches="tight")
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export failed", str(exc))
