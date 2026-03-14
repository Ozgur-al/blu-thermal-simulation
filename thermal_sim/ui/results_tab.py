"""Results summary widget for the thermal simulator GUI.

Provides a structured three-section view of simulation results:
1. Per-layer temperature statistics table
2. Ranked hotspot table with click-to-navigate signal
3. Probe readings table
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ResultsSummaryWidget(QWidget):
    """Three-table results panel: layer stats, hotspot ranking, probe readings.

    Emits ``hotspot_clicked(rank, layer_name, x_m, y_m)`` when the user
    clicks a row in the hotspot table so that MainWindow can navigate to
    the corresponding temperature map location.
    """

    # rank (1-based), layer_name, x_m, y_m
    hotspot_clicked = Signal(int, str, float, float)

    def __init__(self, max_hotspots: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_hotspots = max_hotspots
        self._current_hotspots: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ---- Section 1: Per-layer statistics --------------------------------
        stats_group = QGroupBox("Layer Statistics")
        stats_vbox = QVBoxLayout(stats_group)
        stats_vbox.setContentsMargins(4, 4, 4, 4)

        self._stats_table = QTableWidget(0, 5)
        self._stats_table.setHorizontalHeaderLabels(
            ["Layer", "T_max [C]", "T_avg [C]", "T_min [C]", "DeltaT [C]"]
        )
        self._configure_table(self._stats_table, row_select=False)
        stats_vbox.addWidget(self._stats_table)
        layout.addWidget(stats_group)

        # ---- Section 2: Hotspot ranking -------------------------------------
        hot_group = QGroupBox("Top Hotspots")
        hot_vbox = QVBoxLayout(hot_group)
        hot_vbox.setContentsMargins(4, 4, 4, 4)

        self._hot_table = QTableWidget(0, 5)
        self._hot_table.setHorizontalHeaderLabels(
            ["Rank", "Layer", "X [mm]", "Y [mm]", "Temperature [C]"]
        )
        self._configure_table(self._hot_table, row_select=True)
        self._hot_table.cellClicked.connect(self._on_hotspot_cell_clicked)
        hot_vbox.addWidget(self._hot_table)
        layout.addWidget(hot_group)

        # ---- Section 3: Probe readings --------------------------------------
        probe_group = QGroupBox("Probe Readings")
        probe_vbox = QVBoxLayout(probe_group)
        probe_vbox.setContentsMargins(4, 4, 4, 4)

        self._probe_table = QTableWidget(0, 5)
        self._probe_table.setHorizontalHeaderLabels(
            ["Probe", "Layer", "X [mm]", "Y [mm]", "Temperature [C]"]
        )
        self._configure_table(self._probe_table, row_select=False)
        probe_vbox.addWidget(self._probe_table)
        layout.addWidget(probe_group)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_data(
        self,
        layer_stats_data: list[dict],
        hotspots: list[dict],
        probe_values: dict[str, float],
        probes: list,
    ) -> None:
        """Populate all three tables with new simulation results.

        Args:
            layer_stats_data: List of dicts from ``layer_stats()``, each with keys
                              ``layer``, ``t_max_c``, ``t_avg_c``, ``t_min_c``, ``delta_t_c``.
            hotspots:         List of dicts from ``top_n_hottest_cells()``, each with keys
                              ``layer``, ``x_m``, ``y_m``, ``temperature_c``.
            probe_values:     Mapping of probe name to temperature in Celsius.
            probes:           List of Probe objects (for layer and location info).
        """
        self._populate_stats_table(layer_stats_data)
        self._populate_hotspot_table(hotspots)
        self._populate_probe_table(probe_values, probes)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_table(table: QTableWidget, *, row_select: bool) -> None:
        """Apply standard read-only, alternating-row, stretch-columns settings."""
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        if row_select:
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        """Create a read-only, non-editable table cell item."""
        item = QTableWidgetItem(text)
        return item

    def _populate_stats_table(self, layer_stats_data: list[dict]) -> None:
        self._stats_table.setRowCount(len(layer_stats_data))
        for row, stat in enumerate(layer_stats_data):
            self._stats_table.setItem(row, 0, self._cell(stat["layer"]))
            self._stats_table.setItem(row, 1, self._cell(f"{stat['t_max_c']:.2f}"))
            self._stats_table.setItem(row, 2, self._cell(f"{stat['t_avg_c']:.2f}"))
            self._stats_table.setItem(row, 3, self._cell(f"{stat['t_min_c']:.2f}"))
            self._stats_table.setItem(row, 4, self._cell(f"{stat['delta_t_c']:.2f}"))

    def _populate_hotspot_table(self, hotspots: list[dict]) -> None:
        limited = hotspots[: self._max_hotspots]
        self._current_hotspots = list(limited)
        self._hot_table.setRowCount(len(limited))
        for row, hotspot in enumerate(limited):
            self._hot_table.setItem(row, 0, self._cell(str(row + 1)))
            self._hot_table.setItem(row, 1, self._cell(hotspot["layer"]))
            self._hot_table.setItem(row, 2, self._cell(f"{hotspot['x_m'] * 1000:.1f}"))
            self._hot_table.setItem(row, 3, self._cell(f"{hotspot['y_m'] * 1000:.1f}"))
            self._hot_table.setItem(row, 4, self._cell(f"{hotspot['temperature_c']:.2f}"))

    def _populate_probe_table(
        self, probe_values: dict[str, float], probes: list
    ) -> None:
        # Build a name->probe lookup for location and layer info.
        probe_map = {p.name: p for p in probes}
        rows = []
        for name, temp_c in probe_values.items():
            probe = probe_map.get(name)
            if probe is not None:
                layer = getattr(probe, "layer", "")
                x_mm = getattr(probe, "x", 0.0) * 1000.0
                y_mm = getattr(probe, "y", 0.0) * 1000.0
            else:
                layer = ""
                x_mm = 0.0
                y_mm = 0.0
            rows.append((name, layer, x_mm, y_mm, temp_c))

        self._probe_table.setRowCount(len(rows))
        for row, (name, layer, x_mm, y_mm, temp_c) in enumerate(rows):
            self._probe_table.setItem(row, 0, self._cell(name))
            self._probe_table.setItem(row, 1, self._cell(layer))
            self._probe_table.setItem(row, 2, self._cell(f"{x_mm:.1f}"))
            self._probe_table.setItem(row, 3, self._cell(f"{y_mm:.1f}"))
            self._probe_table.setItem(row, 4, self._cell(f"{temp_c:.2f}"))

    def _on_hotspot_cell_clicked(self, row: int, col: int) -> None:  # noqa: ARG002
        """Emit hotspot_clicked when the user clicks a row in the hotspot table."""
        if row < 0 or row >= len(self._current_hotspots):
            return
        hotspot = self._current_hotspots[row]
        self.hotspot_clicked.emit(
            row + 1,
            hotspot["layer"],
            hotspot["x_m"],
            hotspot["y_m"],
        )
