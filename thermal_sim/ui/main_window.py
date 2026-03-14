"""Phase 3 desktop GUI for the thermal simulator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, Qt, QThread, Signal
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
    layer_average_temperatures,
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
from thermal_sim.ui.structure_preview import StructurePreviewDialog
from thermal_sim.ui.table_data_parser import TableDataParser


class MplCanvas(FigureCanvasQTAgg):
    """Simple matplotlib canvas that expands to fill available space."""

    def __init__(self, width: float = 5.0, height: float = 4.0, dpi: int = 100) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Cached artist references for in-place updates.
        self._image = None  # imshow artist
        self._colorbar = None  # colorbar instance


class _SimWorker(QObject):
    """Runs solver in a background thread."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, project: DisplayProject, mode: str) -> None:
        super().__init__()
        self._project = project
        self._mode = mode

    def run(self) -> None:
        try:
            if self._mode == "steady":
                result = SteadyStateSolver().solve(self._project)
            else:
                result = TransientSolver().solve(self._project)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


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
        self._sim_thread: QThread | None = None
        self._sim_worker: _SimWorker | None = None
        self._sim_mode: str = "steady"

        self._build_ui()
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

        self.statusBar().showMessage("Ready")

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

    def _build_materials_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.materials_table = TableDataParser._new_table(
            ["Name", "k in-plane [W/mK]", "k through [W/mK]", "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"]
        )
        layout.addWidget(self.materials_table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(self.materials_table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, self.materials_table))
        presets_btn = QPushButton("Load Presets")
        presets_btn.clicked.connect(self._load_default_materials)
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        row.addWidget(presets_btn)
        row.addStretch()
        layout.addLayout(row)
        return tab

    def _build_layers_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.layers_table = TableDataParser._new_table(["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"])
        layout.addWidget(self.layers_table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(self.layers_table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, self.layers_table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        row.addStretch()
        layout.addLayout(row)
        return tab

    def _build_sources_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.sources_table = TableDataParser._new_table(
            ["Name", "Layer", "Power [W]", "Shape", "x [m]", "y [m]", "width [m]", "height [m]", "radius [m]"]
        )
        layout.addWidget(self.sources_table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(self.sources_table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, self.sources_table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        row.addStretch()
        layout.addLayout(row)
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
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.led_arrays_table = TableDataParser._new_table(
            [
                "Name",
                "Layer",
                "Center x [m]",
                "Center y [m]",
                "Count x",
                "Count y",
                "Pitch x [m]",
                "Pitch y [m]",
                "Power per LED [W]",
                "LED footprint",
                "LED width [m]",
                "LED height [m]",
                "LED radius [m]",
            ]
        )
        layout.addWidget(self.led_arrays_table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(self.led_arrays_table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, self.led_arrays_table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        row.addStretch()
        layout.addLayout(row)
        return tab

    def _build_probes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.probes_table = TableDataParser._new_table(["Name", "Layer", "x [m]", "y [m]"])
        layout.addWidget(self.probes_table)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(lambda: TableDataParser._add_table_row(self.probes_table))
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda: TableDataParser.remove_selected_row(self, self.probes_table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        row.addStretch()
        layout.addLayout(row)
        return tab

    def _build_result_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        self.map_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        map_layout.addWidget(self.map_canvas)
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
        self.profile_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        profile_layout.addWidget(self.profile_canvas)
        tabs.addTab(profile_tab, "Layer Profile")

        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)
        self.history_canvas = MplCanvas(width=5.0, height=4.0, dpi=100)
        hist_layout.addWidget(self.history_canvas)
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
            (self.map_canvas, "Temperature map will appear here\nafter running a simulation."),
            (self.profile_canvas, "Layer profile will appear here\nafter running a simulation."),
            (self.history_canvas, "Probe history will appear here\nafter running a transient simulation."),
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
                self.statusBar().showMessage(f"Loaded {default_path}")
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

        mat_rows = []
        for mat in project.materials.values():
            mat_rows.append(
                [
                    mat.name,
                    f"{mat.k_in_plane:g}",
                    f"{mat.k_through:g}",
                    f"{mat.density:g}",
                    f"{mat.specific_heat:g}",
                    f"{mat.emissivity:g}",
                ]
            )
        TableDataParser._set_table_rows(self.materials_table, mat_rows)

        layer_rows = []
        for layer in project.layers:
            layer_rows.append(
                [
                    layer.name,
                    layer.material,
                    f"{layer.thickness:g}",
                    f"{layer.interface_resistance_to_next:g}",
                ]
            )
        TableDataParser._set_table_rows(self.layers_table, layer_rows)

        source_rows = []
        for source in project.heat_sources:
            source_rows.append(
                [
                    source.name,
                    source.layer,
                    f"{source.power_w:g}",
                    source.shape,
                    f"{source.x:g}",
                    f"{source.y:g}",
                    "" if source.width is None else f"{source.width:g}",
                    "" if source.height is None else f"{source.height:g}",
                    "" if source.radius is None else f"{source.radius:g}",
                ]
            )
        TableDataParser._set_table_rows(self.sources_table, source_rows)

        led_array_rows = []
        for array in project.led_arrays:
            led_array_rows.append(
                [
                    array.name,
                    array.layer,
                    f"{array.center_x:g}",
                    f"{array.center_y:g}",
                    str(array.count_x),
                    str(array.count_y),
                    f"{array.pitch_x:g}",
                    f"{array.pitch_y:g}",
                    f"{array.power_per_led_w:g}",
                    array.footprint_shape,
                    "" if array.led_width is None else f"{array.led_width:g}",
                    "" if array.led_height is None else f"{array.led_height:g}",
                    "" if array.led_radius is None else f"{array.led_radius:g}",
                ]
            )
        TableDataParser._set_table_rows(self.led_arrays_table, led_array_rows)

        probe_rows = []
        for probe in project.probes:
            probe_rows.append([probe.name, probe.layer, f"{probe.x:g}", f"{probe.y:g}"])
        TableDataParser._set_table_rows(self.probes_table, probe_rows)

        TableDataParser.set_boundary_widgets(self.top_boundary_widgets, project.boundaries.top)
        TableDataParser.set_boundary_widgets(self.bottom_boundary_widgets, project.boundaries.bottom)
        TableDataParser.set_boundary_widgets(self.side_boundary_widgets, project.boundaries.side)
        self._refresh_layer_choices(project)
        self._refresh_profile_choices(project)
        self._update_window_title(project.name)

    def _load_default_materials(self) -> None:
        rows = []
        for mat in default_materials().values():
            rows.append(
                [
                    mat.name,
                    f"{mat.k_in_plane:g}",
                    f"{mat.k_through:g}",
                    f"{mat.density:g}",
                    f"{mat.specific_heat:g}",
                    f"{mat.emissivity:g}",
                ]
            )
        TableDataParser._set_table_rows(self.materials_table, rows)

    def _build_project_from_ui(self) -> DisplayProject:
        return TableDataParser.build_project_from_tables(
            tables_dict={
                "materials": self.materials_table,
                "layers": self.layers_table,
                "sources": self.sources_table,
                "led_arrays": self.led_arrays_table,
                "probes": self.probes_table,
            },
            spinboxes_dict={
                "name": self.project_name_edit,
                "width": self.width_spin,
                "height": self.height_spin,
                "nx": self.nx_spin,
                "ny": self.ny_spin,
                "initial_temp": self.initial_temp_spin,
                "dt": self.dt_spin,
                "total_time": self.total_time_spin,
                "output_interval": self.output_interval_spin,
            },
            boundary_widgets_dict={
                "top": self.top_boundary_widgets,
                "bottom": self.bottom_boundary_widgets,
                "side": self.side_boundary_widgets,
            },
        )

    def _validate_project(self) -> list[str]:
        """Delegate to TableDataParser.validate_tables()."""
        return TableDataParser.validate_tables(
            tables_dict={
                "materials": self.materials_table,
                "layers": self.layers_table,
                "sources": self.sources_table,
                "led_arrays": self.led_arrays_table,
                "probes": self.probes_table,
            }
        )

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
        self._set_running_state(True)

        self._sim_thread = QThread()
        self._sim_worker = _SimWorker(project, self._sim_mode)
        self._sim_worker.moveToThread(self._sim_thread)
        self._sim_thread.started.connect(self._sim_worker.run)
        self._sim_worker.finished.connect(self._on_sim_finished)
        self._sim_worker.error.connect(self._on_sim_error)
        self._sim_worker.finished.connect(self._sim_thread.quit)
        self._sim_worker.error.connect(self._sim_thread.quit)
        self._sim_thread.finished.connect(lambda: self._set_running_state(False))
        self._sim_thread.start()

    def _on_sim_finished(self, result: object) -> None:
        # Invalidate cached map image so next _plot_map rebuilds for the new geometry.
        self.map_canvas._image = None
        if self.map_canvas._colorbar is not None:
            self.map_canvas._colorbar.remove()
            self.map_canvas._colorbar = None
        self.map_canvas.axes.clear()

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
                self._plot_history(None, {})
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
                self._plot_history(result.times_s, self.last_probe_history)
        except Exception as exc:  # noqa: BLE001
            self._show_error("Post-processing failed", self._friendly_error(exc))
            return

        self._plot_map(final_map, layer_names)
        self._plot_profile(final_map, layer_names)
        self._refresh_summary(stats.min_c, stats.avg_c, stats.max_c, final_map, layer_names, hottest)
        self._fill_probe_table(self.last_probe_values)
        self.statusBar().showMessage(f"Simulation complete ({self._sim_mode}).")

    def _on_sim_error(self, message: str) -> None:
        self._show_error("Simulation failed", message)

    def _set_running_state(self, running: bool) -> None:
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("Running\u2026" if running else "Run Simulation")
        if running:
            self.statusBar().showMessage("Running simulation\u2026")

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        msg = str(exc)
        if isinstance(exc, ValueError):
            return f"Invalid value \u2014 {msg}"
        if isinstance(exc, KeyError):
            return f"Referenced item not found: {msg}"
        return msg

    def _refresh_summary(
        self,
        min_c: float,
        avg_c: float,
        max_c: float,
        final_map_c: np.ndarray,
        layer_names: list[str],
        hottest: list[dict],
    ) -> None:
        self.stats_label.setText(f"Tmin / Tavg / Tmax [\u00b0C]: {min_c:.2f} / {avg_c:.2f} / {max_c:.2f}")
        TableDataParser._set_table_rows(
            self.hot_table,
            [
                [h["layer"], f"{h['temperature_c']:.2f}", f"{h['x_m']:.5f}", f"{h['y_m']:.5f}"]
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
        self.summary_text.setPlainText("\n".join(lines))

    def _plot_map(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        layer_name = self.map_layer_combo.currentText()
        layer_idx = layer_names.index(layer_name) if layer_name in layer_names else len(layer_names) - 1
        data = final_map_c[layer_idx]
        extent = [0.0, self.width_spin.value(), 0.0, self.height_spin.value()]
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
            im = ax.imshow(data, origin="lower", extent=extent, aspect="auto", cmap="inferno")
            ax.set_title(f"Temperature Map - {layer_names[layer_idx]}")
            ax.set_xlabel("x [m]")
            ax.set_ylabel("y [m]")
            self.map_canvas._colorbar = self.map_canvas.figure.colorbar(
                im, ax=ax, label="Temperature [\u00b0C]"
            )
            self.map_canvas._image = im
            self.map_canvas.figure.tight_layout()

        self.map_canvas.draw()

    def _plot_profile(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        x_m, y_m = self._selected_profile_point()
        nx = final_map_c.shape[2]
        ny = final_map_c.shape[1]
        ix = max(0, min(nx - 1, int(np.floor((x_m / max(self.width_spin.value(), 1e-12)) * nx))))
        iy = max(0, min(ny - 1, int(np.floor((y_m / max(self.height_spin.value(), 1e-12)) * ny))))
        vals = final_map_c[:, iy, ix]
        ax = self.profile_canvas.axes
        ax.clear()
        ax.plot(vals, np.arange(len(layer_names)), marker="o")
        ax.set_yticks(np.arange(len(layer_names)))
        ax.set_yticklabels(layer_names)
        ax.set_xlabel("Temperature [\u00b0C]")
        ax.set_ylabel("Layer")
        ax.set_title(f"Layer Profile @ x={x_m:.4f} m, y={y_m:.4f} m")
        ax.grid(True, alpha=0.3)
        self.profile_canvas.figure.tight_layout()
        self.profile_canvas.draw()

    def _plot_history(self, times_s: np.ndarray | None, probe_history: dict[str, np.ndarray]) -> None:
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
            for name, values in probe_history.items():
                ax.plot(times_s, values, label=name)
            ax.set_xlabel("Time [s]")
            ax.set_ylabel("Temperature [\u00b0C]")
            ax.set_title("Probe Temperatures vs Time")
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best")
        self.history_canvas.figure.tight_layout()
        self.history_canvas.draw()

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
        TableDataParser._set_table_rows(self.probe_table, [[k, f"{v:.2f}"] for k, v in probe_values.items()])

    def _load_project_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open Project", str(Path.cwd()), "JSON (*.json)")
        if not path_str:
            return
        try:
            path = Path(path_str)
            project = load_project(path)
            self._populate_ui_from_project(project)
            self.current_project_path = path
            self.statusBar().showMessage(f"Loaded {path}")
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
            self.statusBar().showMessage(f"Saved {path}")
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
        self.statusBar().showMessage("Structure preview opened.")

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
        self.statusBar().showMessage(f"Exported {path}")

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
        self.statusBar().showMessage(f"Exported {path}")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
