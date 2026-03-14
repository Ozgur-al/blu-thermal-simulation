"""Phase 3 desktop GUI for the thermal simulator."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from thermal_sim.core.material_library import default_materials
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
from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.steady_state import SteadyStateResult, SteadyStateSolver
from thermal_sim.solvers.transient import TransientResult, TransientSolver
from thermal_sim.ui.plot_manager import PlotManager
from thermal_sim.ui.simulation_controller import SimulationController
from thermal_sim.ui.structure_preview import StructurePreviewDialog
from thermal_sim.ui.table_data_parser import TableDataParser


class MainWindow(QMainWindow):
    """Main engineering window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Thermal Simulator")
        self.resize(1500, 900)
        self.setMinimumSize(800, 500)

        self.current_project_path: Path | None = None
        self.last_project: DisplayProject | None = None
        self.last_steady_result: SteadyStateResult | None = None
        self.last_transient_result: TransientResult | None = None
        self.last_probe_values: dict[str, float] = {}
        self.last_probe_history: dict[str, np.ndarray] = {}
        self._preview_windows: list[StructurePreviewDialog] = []
        self._sim_mode: str = "steady"
        self._last_run_start: float = 0.0
        self._plot_manager = PlotManager()
        self._sim_controller = SimulationController(self)

        self._build_ui()
        self._connect_controller_signals()
        self._load_startup_project()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._build_top_controls())
        left_layout.addWidget(self._build_editor_tabs())
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._build_result_tabs())
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # Three-zone status bar -----------------------------------------------
        # Left zone: current file path (or "No file")
        # Center zone: solver state label + progress bar during transient runs
        # Right zone: last run metrics (T_max, elapsed, mesh size)
        sb = self.statusBar()
        self._path_label = QLabel("No file")
        self._solver_label = QLabel("Ready")
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setTextVisible(True)
        self._run_info_label = QLabel("")
        sb.addPermanentWidget(self._path_label, stretch=2)
        sb.addPermanentWidget(self._solver_label, stretch=1)
        sb.addPermanentWidget(self._progress_bar, stretch=1)
        sb.addPermanentWidget(self._run_info_label, stretch=1)

        QShortcut(QKeySequence.StandardKey.Open, self, self._load_project_dialog)
        QShortcut(QKeySequence.StandardKey.Save, self, self._save_project_dialog)
        QShortcut(QKeySequence("Ctrl+R"), self, self._run_simulation)
        self._draw_empty_states()

    def _build_top_controls(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Row 1: simulation controls
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["steady", "transient"])
        self.mode_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.mode_combo.setToolTip("Steady-state solves for equilibrium; transient simulates over time")
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 100)
        self.top_n_spin.setValue(10)
        self.top_n_spin.setToolTip("Number of hottest cells to report")
        self.map_layer_combo = QComboBox()
        self.map_layer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.map_layer_combo.setToolTip("Layer shown in the temperature map")
        self.map_layer_combo.currentTextChanged.connect(self._refresh_map_and_profile)

        self._run_btn = QPushButton("Run Simulation")
        self._run_btn.setObjectName("runButton")
        self._run_btn.setToolTip("Run simulation (Ctrl+R)")
        self._run_btn.clicked.connect(self._run_simulation)

        row1.addWidget(QLabel("Mode"))
        row1.addWidget(self.mode_combo)
        row1.addWidget(QLabel("Top-N"))
        row1.addWidget(self.top_n_spin)
        row1.addWidget(QLabel("Layer"))
        row1.addWidget(self.map_layer_combo)
        row1.addWidget(self._run_btn)

        # Row 2: I/O and preview
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        load_btn = QPushButton("Load JSON")
        load_btn.setToolTip("Open project JSON (Ctrl+O)")
        load_btn.clicked.connect(self._load_project_dialog)
        save_btn = QPushButton("Save JSON")
        save_btn.setToolTip("Save project to JSON (Ctrl+S)")
        save_btn.clicked.connect(self._save_project_dialog)
        export_map_btn = QPushButton("Export Map CSV")
        export_map_btn.setToolTip("Export temperature map as CSV")
        export_map_btn.clicked.connect(self._export_map_csv_dialog)
        export_probe_btn = QPushButton("Export Probe CSV")
        export_probe_btn.setToolTip("Export probe data as CSV")
        export_probe_btn.clicked.connect(self._export_probe_csv_dialog)
        preview_btn = QPushButton("Structure Preview")
        preview_btn.setToolTip("Visual preview of layer stack and source layout")
        preview_btn.clicked.connect(self._open_structure_preview)

        row2.addWidget(load_btn)
        row2.addWidget(save_btn)
        row2.addWidget(export_map_btn)
        row2.addWidget(export_probe_btn)
        row2.addWidget(preview_btn)
        row2.addStretch()

        outer.addLayout(row1)
        outer.addLayout(row2)
        return panel

    def _build_editor_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._build_setup_tab(), "Project Setup")
        tabs.addTab(self._build_materials_tab(), "Materials")
        tabs.addTab(self._build_layers_tab(), "Layers")
        tabs.addTab(self._build_sources_tab(), "Heat Sources")
        tabs.addTab(self._build_led_arrays_tab(), "LED Arrays")
        tabs.addTab(self._build_boundaries_tab(), "Boundaries")
        tabs.addTab(self._build_probes_tab(), "Probes")
        return tabs

    def _build_setup_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        geo_box = QGroupBox("Geometry / Mesh")
        geo_form = QFormLayout(geo_box)
        self.project_name_edit = QLineEdit()
        self.width_spin = TableDataParser._double_spin(0.001, 5.0, 0.18)
        self.height_spin = TableDataParser._double_spin(0.001, 5.0, 0.10)
        self.nx_spin = QSpinBox()
        self.nx_spin.setRange(1, 500)
        self.nx_spin.setValue(30)
        self.ny_spin = QSpinBox()
        self.ny_spin.setRange(1, 500)
        self.ny_spin.setValue(18)
        self.initial_temp_spin = TableDataParser._double_spin(-60.0, 200.0, 25.0, decimals=2)
        geo_form.addRow("Project name", self.project_name_edit)
        geo_form.addRow("Width [m]", self.width_spin)
        geo_form.addRow("Height [m]", self.height_spin)
        geo_form.addRow("Mesh cells X", self.nx_spin)
        geo_form.addRow("Mesh cells Y", self.ny_spin)
        geo_form.addRow("Initial temp [\u00b0C]", self.initial_temp_spin)

        tr_box = QGroupBox("Transient")
        tr_form = QFormLayout(tr_box)
        self.dt_spin = TableDataParser._double_spin(1e-4, 1000.0, 0.2, decimals=4)
        self.total_time_spin = TableDataParser._double_spin(1e-3, 1e6, 120.0, decimals=2)
        self.output_interval_spin = TableDataParser._double_spin(1e-4, 1e6, 2.0, decimals=4)
        tr_form.addRow("Time step [s]", self.dt_spin)
        tr_form.addRow("Total time [s]", self.total_time_spin)
        tr_form.addRow("Output interval [s]", self.output_interval_spin)

        layout.addWidget(geo_box)
        layout.addWidget(tr_box)
        layout.addStretch()
        return tab

    def _build_table_tab(self, headers: list[str], extra_buttons: list | None = None):
        """Return (QWidget tab, QTableWidget) for a standard add/remove table tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = TableDataParser._new_table(headers)
        layout.addWidget(table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        for btn in (extra_buttons or []):
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)
        return tab, table

    def _build_materials_tab(self) -> QWidget:
        presets_btn = QPushButton("Load Presets")
        presets_btn.clicked.connect(self._load_default_materials)
        tab, self.materials_table = self._build_table_tab(
            ["Name", "k in-plane [W/mK]", "k through [W/mK]", "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"],
            extra_buttons=[presets_btn],
        )
        return tab

    def _build_layers_tab(self) -> QWidget:
        tab, self.layers_table = self._build_table_tab(
            ["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"]
        )
        return tab

    def _build_sources_tab(self) -> QWidget:
        tab, self.sources_table = self._build_table_tab(
            ["Name", "Layer", "Power [W]", "Shape", "x [m]", "y [m]", "width [m]", "height [m]", "radius [m]"]
        )
        return tab

    def _build_boundaries_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        layout = QGridLayout(inner)
        self.top_boundary_widgets = self._build_boundary_group("Top")
        self.bottom_boundary_widgets = self._build_boundary_group("Bottom")
        self.side_boundary_widgets = self._build_boundary_group("Side")
        layout.addWidget(self.top_boundary_widgets["group"], 0, 0)
        layout.addWidget(self.bottom_boundary_widgets["group"], 0, 1)
        layout.addWidget(self.side_boundary_widgets["group"], 1, 0, 1, 2)
        scroll.setWidget(inner)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    def _build_led_arrays_tab(self) -> QWidget:
        tab, self.led_arrays_table = self._build_table_tab(
            ["Name", "Layer", "Center x [m]", "Center y [m]", "Count x", "Count y",
             "Pitch x [m]", "Pitch y [m]", "Power per LED [W]",
             "LED footprint", "LED width [m]", "LED height [m]", "LED radius [m]"]
        )
        return tab

    def _build_probes_tab(self) -> QWidget:
        tab, self.probes_table = self._build_table_tab(["Name", "Layer", "x [m]", "y [m]"])
        return tab

    def _build_result_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        map_layout.addWidget(self._plot_manager.map_canvas)
        tabs.addTab(map_tab, "Temperature Map")

        profile_tab = QWidget()
        profile_layout = QVBoxLayout(profile_tab)
        controls = QHBoxLayout()
        self.profile_point_combo = QComboBox()
        self.profile_point_combo.currentTextChanged.connect(self._refresh_profile_only)
        controls.addWidget(QLabel("Profile location"))
        controls.addWidget(self.profile_point_combo)
        controls.addStretch()
        profile_layout.addLayout(controls)
        profile_layout.addWidget(self._plot_manager.profile_canvas)
        tabs.addTab(profile_tab, "Layer Profile")

        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)
        hist_layout.addWidget(self._plot_manager.history_canvas)
        tabs.addTab(hist_tab, "Probe History")

        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.stats_label = QLabel("No results yet. Click Run Simulation to start.")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.probe_table = TableDataParser._new_table(["Probe", "Temp [\u00b0C]"])
        self.hot_table = TableDataParser._new_table(["Layer", "Temp [\u00b0C]", "x [m]", "y [m]"])
        summary_layout.addWidget(self.stats_label)
        summary_layout.addWidget(self.summary_text)
        summary_layout.addWidget(QLabel("Probe Readings"))
        summary_layout.addWidget(self.probe_table)
        summary_layout.addWidget(QLabel("Hottest Cells"))
        summary_layout.addWidget(self.hot_table)
        tabs.addTab(summary_tab, "Summary")
        return tabs

    def _build_boundary_group(self, title: str) -> dict[str, QWidget]:
        group = QGroupBox(title)
        form = QFormLayout(group)
        ambient = TableDataParser._double_spin(-60.0, 200.0, 25.0, decimals=2)
        h_coeff = TableDataParser._double_spin(0.0, 5000.0, 8.0, decimals=3)
        include_rad = QCheckBox()
        include_rad.setChecked(True)
        emiss = QLineEdit()
        emiss.setPlaceholderText("Leave blank to use layer material value")
        emiss.setValidator(QDoubleValidator(0.0, 1.0, 6, emiss))
        form.addRow("Ambient temp [\u00b0C]", ambient)
        form.addRow("h convection [W/m\u00b2K]", h_coeff)
        form.addRow("Include radiation", include_rad)
        form.addRow("Emissivity override", emiss)
        return {"group": group, "ambient": ambient, "h": h_coeff, "rad": include_rad, "emiss": emiss}

    def _draw_empty_states(self) -> None:
        for canvas, msg in [
            (self._plot_manager.map_canvas, "Temperature map will appear here\nafter running a simulation."),
            (self._plot_manager.profile_canvas, "Layer profile will appear here\nafter running a simulation."),
            (self._plot_manager.history_canvas, "Probe history will appear here\nafter running a transient simulation."),
        ]:
            ax = canvas.axes
            ax.text(
                0.5, 0.5, msg,
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#8e8e93",
            )
            ax.set_axis_off()
            canvas.draw()

    def _update_window_title(self, project_name: str = "") -> None:
        base = "Thermal Simulator"
        if project_name:
            self.setWindowTitle(f"{project_name} \u2014 {base}")
        else:
            self.setWindowTitle(base)

    def _load_startup_project(self) -> None:
        default_path = Path("examples/steady_uniform_stack.json")
        if default_path.exists():
            try:
                project = load_project(default_path)
                self._populate_ui_from_project(project)
                self.current_project_path = default_path
                self._update_path_label()
                return
            except Exception:  # noqa: BLE001
                pass
        self._load_default_materials()

    def _populate_ui_from_project(self, project: DisplayProject) -> None:
        self.project_name_edit.setText(project.name)
        self.width_spin.setValue(project.width)
        self.height_spin.setValue(project.height)
        self.nx_spin.setValue(project.mesh.nx)
        self.ny_spin.setValue(project.mesh.ny)
        self.initial_temp_spin.setValue(project.initial_temperature_c)
        self.dt_spin.setValue(project.transient.time_step_s)
        self.total_time_spin.setValue(project.transient.total_time_s)
        self.output_interval_spin.setValue(project.transient.output_interval_s)

        TableDataParser.populate_tables_from_project(project, self._tables_dict)
        TableDataParser.set_boundary_widgets(self.top_boundary_widgets, project.boundaries.top)
        TableDataParser.set_boundary_widgets(self.bottom_boundary_widgets, project.boundaries.bottom)
        TableDataParser.set_boundary_widgets(self.side_boundary_widgets, project.boundaries.side)
        self._refresh_layer_choices(project)
        self._refresh_profile_choices(project)
        self._update_window_title(project.name)

    def _load_default_materials(self) -> None:
        rows = [
            [
                mat.name,
                f"{mat.k_in_plane:g}",
                f"{mat.k_through:g}",
                f"{mat.density:g}",
                f"{mat.specific_heat:g}",
                f"{mat.emissivity:g}",
            ]
            for mat in default_materials().values()
        ]
        TableDataParser._set_table_rows(self.materials_table, rows)

    @property
    def _tables_dict(self) -> dict:
        return {
            "materials": self.materials_table,
            "layers": self.layers_table,
            "sources": self.sources_table,
            "led_arrays": self.led_arrays_table,
            "probes": self.probes_table,
        }

    @property
    def _spinboxes_dict(self) -> dict:
        return {
            "name": self.project_name_edit,
            "width": self.width_spin,
            "height": self.height_spin,
            "nx": self.nx_spin,
            "ny": self.ny_spin,
            "initial_temp": self.initial_temp_spin,
            "dt": self.dt_spin,
            "total_time": self.total_time_spin,
            "output_interval": self.output_interval_spin,
        }

    @property
    def _boundary_widgets_dict(self) -> dict:
        return {
            "top": self.top_boundary_widgets,
            "bottom": self.bottom_boundary_widgets,
            "side": self.side_boundary_widgets,
        }

    def _build_project_from_ui(self) -> DisplayProject:
        return TableDataParser.build_project_from_tables(
            self._tables_dict, self._spinboxes_dict, self._boundary_widgets_dict
        )

    def _validate_project(self) -> list[str]:
        """Delegate to TableDataParser.validate_tables()."""
        return TableDataParser.validate_tables(self._tables_dict)

    def _connect_controller_signals(self) -> None:
        """Wire SimulationController signals to MainWindow slots."""
        c = self._sim_controller
        c.run_started.connect(self._on_run_started)
        c.run_ended.connect(self._on_run_ended)
        c.progress_updated.connect(self._on_progress)
        c.run_finished.connect(self._on_sim_finished)
        c.run_error.connect(self._on_sim_error)

    def _on_run_started(self) -> None:
        """Disable Run button and show progress bar when a simulation starts."""
        self._run_btn.setEnabled(False)
        self._run_btn.setText("Running\u2026")
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._solver_label.setText("Running\u2026")

    def _on_run_ended(self) -> None:
        """Re-enable Run button and hide progress bar when a simulation ends."""
        self._run_btn.setEnabled(True)
        self._run_btn.setText("Run Simulation")
        self._progress_bar.setVisible(False)

    def _on_progress(self, percent: int, message: str) -> None:
        """Update progress bar and center label from worker progress signal."""
        self._progress_bar.setValue(percent)
        self._solver_label.setText(message)

    def _run_simulation(self) -> None:
        errors = self._validate_project()
        if errors:
            self._show_error("Validation errors", "\n".join(f"\u2022 {e}" for e in errors))
            return

        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Invalid project", self._friendly_error(exc))
            return

        self.last_project = project
        self._refresh_layer_choices(project)
        self._refresh_profile_choices(project)
        self._sim_mode = self.mode_combo.currentText()
        self._last_run_start = time.monotonic()
        self._sim_controller.start_run(project, self._sim_mode)

    def _on_sim_finished(self, result: object) -> None:
        elapsed = time.monotonic() - self._last_run_start

        # Invalidate cached map image so next plot_temperature_map rebuilds for the new geometry.
        map_canvas = self._plot_manager.map_canvas
        map_canvas._image = None
        if map_canvas._colorbar is not None:
            map_canvas._colorbar.remove()
            map_canvas._colorbar = None
        map_canvas.axes.clear()

        project = self.last_project
        top_n = self.top_n_spin.value()
        try:
            if isinstance(result, SteadyStateResult):
                self.last_steady_result = result
                self.last_transient_result = None
                self.last_probe_history = {}
                self.last_probe_values = probe_temperatures(project, result)
                stats = basic_stats(result)
                hottest = top_n_hottest_cells(result, n=top_n)
                final_map = result.temperatures_c
                layer_names = result.layer_names
                self._plot_manager.plot_probe_history(None, {})
            else:
                self.last_transient_result = result
                self.last_steady_result = None
                self.last_probe_history = probe_temperatures_over_time(project, result)
                self.last_probe_values = {
                    name: float(values[-1]) for name, values in self.last_probe_history.items()
                }
                stats = basic_stats_transient(result)
                hottest = top_n_hottest_cells_transient(result, n=top_n)
                final_map = result.final_temperatures_c
                layer_names = result.layer_names
                self._plot_manager.plot_probe_history(result.times_s, self.last_probe_history)
        except Exception as exc:  # noqa: BLE001
            self._show_error("Post-processing failed", self._friendly_error(exc))
            return

        self._plot_map(final_map, layer_names)
        self._plot_profile(final_map, layer_names)
        self._plot_manager.refresh_summary(
            self.stats_label, self.hot_table, self.summary_text,
            stats.min_c, stats.avg_c, stats.max_c, final_map, layer_names, hottest,
        )
        self._plot_manager.fill_probe_table(self.probe_table, self.last_probe_values)

        # Update three-zone status bar with run metrics.
        n_layers = len(layer_names)
        self._solver_label.setText(f"Complete ({self._sim_mode})")
        self._run_info_label.setText(
            f"T_max: {stats.max_c:.1f} C | {elapsed:.1f}s"
            f" | {project.mesh.nx}x{project.mesh.ny}x{n_layers}"
        )

    def _on_sim_error(self, message: str) -> None:
        self._solver_label.setText("Error")
        self._show_error("Simulation failed", message)

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        msg = str(exc)
        if isinstance(exc, ValueError):
            return f"Invalid value \u2014 {msg}"
        if isinstance(exc, KeyError):
            return f"Referenced item not found: {msg}"
        return msg

    def _plot_map(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        """Thin dispatcher — reads widget state and delegates to PlotManager."""
        self._plot_manager.plot_temperature_map(
            final_map_c, layer_names,
            layer_name=self.map_layer_combo.currentText(),
            width_m=self.width_spin.value(),
            height_m=self.height_spin.value(),
        )

    def _plot_profile(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        """Thin dispatcher — reads widget state and delegates to PlotManager."""
        x_m, y_m = self._selected_profile_point()
        self._plot_manager.plot_layer_profile(
            final_map_c, layer_names, x_m, y_m,
            width_m=self.width_spin.value(),
            height_m=self.height_spin.value(),
        )

    def _refresh_map_and_profile(self) -> None:
        if self.last_steady_result is not None:
            self._plot_map(self.last_steady_result.temperatures_c, self.last_steady_result.layer_names)
            self._plot_profile(self.last_steady_result.temperatures_c, self.last_steady_result.layer_names)
        elif self.last_transient_result is not None:
            self._plot_map(self.last_transient_result.final_temperatures_c, self.last_transient_result.layer_names)
            self._plot_profile(self.last_transient_result.final_temperatures_c, self.last_transient_result.layer_names)

    def _refresh_profile_only(self) -> None:
        if self.last_steady_result is not None:
            self._plot_profile(self.last_steady_result.temperatures_c, self.last_steady_result.layer_names)
        elif self.last_transient_result is not None:
            self._plot_profile(self.last_transient_result.final_temperatures_c, self.last_transient_result.layer_names)

    def _selected_profile_point(self) -> tuple[float, float]:
        label = self.profile_point_combo.currentText()
        if self.last_project is None or label == "Center":
            return self.width_spin.value() / 2.0, self.height_spin.value() / 2.0
        for probe in self.last_project.probes:
            if probe.name == label:
                return probe.x, probe.y
        return self.width_spin.value() / 2.0, self.height_spin.value() / 2.0

    def _refresh_layer_choices(self, project: DisplayProject) -> None:
        current = self.map_layer_combo.currentText()
        self.map_layer_combo.clear()
        self.map_layer_combo.addItems([layer.name for layer in project.layers])
        idx = self.map_layer_combo.findText(current)
        if idx >= 0:
            self.map_layer_combo.setCurrentIndex(idx)
        elif self.map_layer_combo.count() > 0:
            self.map_layer_combo.setCurrentIndex(self.map_layer_combo.count() - 1)

    def _refresh_profile_choices(self, project: DisplayProject) -> None:
        current = self.profile_point_combo.currentText()
        self.profile_point_combo.clear()
        self.profile_point_combo.addItem("Center")
        for probe in project.probes:
            self.profile_point_combo.addItem(probe.name)
        idx = self.profile_point_combo.findText(current)
        if idx >= 0:
            self.profile_point_combo.setCurrentIndex(idx)

    def _fill_probe_table(self, probe_values: dict[str, float]) -> None:
        self._plot_manager.fill_probe_table(self.probe_table, probe_values)

    def _update_path_label(self) -> None:
        """Update the left status bar zone with the current file path."""
        if self.current_project_path is not None:
            self._path_label.setText(str(self.current_project_path))
        else:
            self._path_label.setText("No file")

    def _load_project_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open Project", str(Path.cwd()), "JSON (*.json)")
        if not path_str:
            return
        try:
            path = Path(path_str)
            project = load_project(path)
            self._populate_ui_from_project(project)
            self.current_project_path = path
            self._update_path_label()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Load failed", str(exc))

    def _save_project_dialog(self) -> None:
        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Invalid project", str(exc))
            return
        start = self.current_project_path or Path.cwd() / "project.json"
        path_str, _ = QFileDialog.getSaveFileName(self, "Save Project", str(start), "JSON (*.json)")
        if not path_str:
            return
        try:
            path = Path(path_str)
            save_project(project, path)
            self.current_project_path = path
            self._update_window_title(project.name)
            self._update_path_label()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Save failed", str(exc))

    def _open_structure_preview(self) -> None:
        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Cannot open preview", f"Fix the project configuration first:\n{exc}")
            return

        window = StructurePreviewDialog(project, parent=self)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: self._on_preview_destroyed(window))
        self._preview_windows.append(window)
        window.show()

    def _on_preview_destroyed(self, window: StructurePreviewDialog) -> None:
        if window in self._preview_windows:
            self._preview_windows.remove(window)

    def _export_map_csv_dialog(self) -> None:
        if self.last_steady_result is None and self.last_transient_result is None:
            self._show_error("No results to export", "Run a simulation first, then export the temperature map.")
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "Export Map CSV", "temperature_map.csv", "CSV (*.csv)")
        if not path_str:
            return
        path = Path(path_str)
        if self.last_steady_result is not None:
            export_temperature_map(self.last_steady_result, path)
        else:
            assert self.last_transient_result is not None
            export_temperature_map_array(
                temperature_map_c=self.last_transient_result.final_temperatures_c,
                layer_names=self.last_transient_result.layer_names,
                dx=self.last_transient_result.dx,
                dy=self.last_transient_result.dy,
                output_path=path,
            )
        self._solver_label.setText(f"Exported {path.name}")

    def _export_probe_csv_dialog(self) -> None:
        if self.last_steady_result is None and self.last_transient_result is None:
            self._show_error("No results to export", "Run a simulation first, then export probe data.")
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "Export Probe CSV", "probe_data.csv", "CSV (*.csv)")
        if not path_str:
            return
        path = Path(path_str)
        if self.last_steady_result is not None:
            export_probe_temperatures(self.last_probe_values, path)
        else:
            assert self.last_transient_result is not None
            export_probe_temperatures_vs_time(self.last_transient_result.times_s, self.last_probe_history, path)
        self._solver_label.setText(f"Exported {path.name}")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
