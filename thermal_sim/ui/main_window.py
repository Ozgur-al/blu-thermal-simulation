"""Phase 3 desktop GUI for the thermal simulator."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDoubleValidator,
    QKeySequence,
    QAction,
    QUndoStack,
    QUndoCommand,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from thermal_sim.core.material_library import (
    default_materials,
    export_materials,
    import_materials,
    load_builtin_library,
    load_materials_json,
)
from thermal_sim.core.paths import APP_VERSION, get_examples_dir, get_output_dir
from thermal_sim.core.postprocess import (
    basic_stats,
    basic_stats_transient,
    layer_stats,
    probe_temperatures,
    probe_temperatures_over_time,
    top_n_hottest_cells,
    top_n_hottest_cells_for_layer,
    top_n_hottest_cells_transient,
)
from thermal_sim.visualization.plotting import plot_temperature_map_annotated
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
from thermal_sim.io.pdf_export import generate_pdf_report
from thermal_sim.models.snapshot import ResultSnapshot
from thermal_sim.ui.comparison_tab import ComparisonWidget
from thermal_sim.ui.plot_manager import MplCanvas, PlotManager
from thermal_sim.ui.results_tab import ResultsSummaryWidget
from thermal_sim.ui.simulation_controller import SimulationController
from thermal_sim.ui.structure_preview import StructurePreviewDialog
from thermal_sim.ui.sweep_dialog import SweepDialog
from thermal_sim.ui.sweep_results_widget import SweepResultsWidget
from thermal_sim.ui.table_data_parser import TableDataParser


class _CellEditCommand(QUndoCommand):
    """Undoable command for a single table cell edit."""

    def __init__(
        self,
        table,
        row: int,
        col: int,
        old_val: str,
        new_val: str,
        main_window: "MainWindow",
    ) -> None:
        header = table.horizontalHeaderItem(col)
        label = header.text() if header else f"col {col}"
        super().__init__(f"Edit {label}")
        self._table = table
        self._row = row
        self._col = col
        self._old = old_val
        self._new = new_val
        self._mw = main_window

    def undo(self) -> None:
        item = self._table.item(self._row, self._col)
        if item is not None:
            self._mw._undoing = True
            item.setText(self._old)
            self._mw._undoing = False

    def redo(self) -> None:
        item = self._table.item(self._row, self._col)
        if item is not None:
            self._mw._undoing = True
            item.setText(self._new)
            self._mw._undoing = False


class MainWindow(QMainWindow):
    """Main engineering window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Thermal Simulator v{APP_VERSION}")
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

        # Annotated map state ------------------------------------------------
        self._selected_hotspot_rank: int | None = None
        self._last_final_map: np.ndarray | None = None
        self._last_layer_names: list[str] | None = None

        # Snapshot management ------------------------------------------------
        self._snapshots: list[ResultSnapshot] = []

        # Undo/redo stack
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(100)
        self._undoing: bool = False

        # Store pre-edit values: (id(table), row, col) -> text
        self._pre_edit_values: dict[tuple[int, int, int], str] = {}

        # Inline validation errors: (id(table), row, col) -> error message
        self._validation_errors: dict[tuple[int, int, int], str] = {}

        # Material source tracking: name -> "Built-in" | "User"
        self._material_source: dict[str, str] = {}

        # Power profile breakpoints: source_row_index -> list[PowerBreakpoint]
        self._source_profiles: dict[int, list] = {}

        # Persistent output directory
        settings = QSettings("ThermalSim", "ThermalSimulator")
        self._output_dir = Path(settings.value("output_dir", str(get_output_dir())))

        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._connect_controller_signals()
        self._undo_stack.cleanChanged.connect(self._update_title)
        self._undo_stack.cleanChanged.connect(self._update_path_label)
        self._load_startup_project()
        self._restore_layout()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central widget: minimal placeholder (all content lives in docks)
        self.setCentralWidget(QWidget())

        # Dock 1: Editor (left) — contains top controls + editor tabs
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.addWidget(self._build_top_controls())
        editor_layout.addWidget(self._build_editor_tabs())
        self._editor_dock = QDockWidget("Editor", self)
        self._editor_dock.setObjectName("EditorDock")
        self._editor_dock.setWidget(editor_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)

        # Dock 2: Result Plots (top-right) — Temperature Map, Layer Profile, Probe History
        self._plots_dock = QDockWidget("Result Plots", self)
        self._plots_dock.setObjectName("PlotsDock")
        self._plots_dock.setWidget(self._build_plot_tabs())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._plots_dock)

        # Dock 3: Results Summary (bottom-right) — Summary, Results, Comparison, Sweep Results
        self._summary_dock = QDockWidget("Results Summary", self)
        self._summary_dock.setObjectName("SummaryDock")
        self._summary_dock.setWidget(self._build_summary_tabs())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._summary_dock)

        # Stack summary below plots in the right area
        self.splitDockWidget(self._plots_dock, self._summary_dock, Qt.Orientation.Vertical)

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

        self._draw_empty_states()

    def _build_menus(self) -> None:
        """Create the menu bar with File, Edit, and Run menus."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._load_project_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        self._save_action = QAction("&Save Project", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_action)

        save_as_action = QAction("Save Project &As...", self)
        save_as_action.triggered.connect(self._save_project_as_dialog)
        file_menu.addAction(save_as_action)

        # Edit menu (using QUndoStack's built-in actions)
        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = self._undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        redo_action = self._undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        # Run menu
        run_menu = self.menuBar().addMenu("&Run")

        self._run_action = QAction("&Run Simulation", self)
        self._run_action.setShortcut(QKeySequence("F5"))
        self._run_action.triggered.connect(self._run_simulation)
        run_menu.addAction(self._run_action)

        self._cancel_action = QAction("&Cancel", self)
        self._cancel_action.setShortcut(QKeySequence("Escape"))
        self._cancel_action.setEnabled(False)
        self._cancel_action.triggered.connect(self._sim_controller.cancel)
        run_menu.addAction(self._cancel_action)

        run_menu.addSeparator()

        set_output_action = QAction("Set &Output Directory...", self)
        set_output_action.triggered.connect(self._set_output_directory)
        run_menu.addAction(set_output_action)

        export_csv_action = QAction("&Export CSV", self)
        export_csv_action.triggered.connect(self._export_csv_dialog)
        run_menu.addAction(export_csv_action)

        run_menu.addSeparator()

        sweep_action = QAction("&Parametric Sweep...", self)
        sweep_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        sweep_action.triggered.connect(self._open_sweep_dialog)
        run_menu.addAction(sweep_action)

        # View menu
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._editor_dock.toggleViewAction())
        view_menu.addAction(self._plots_dock.toggleViewAction())
        view_menu.addAction(self._summary_dock.toggleViewAction())
        view_menu.addSeparator()
        reset_action = QAction("Reset Layout", self)
        reset_action.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_action)

    def _build_toolbar(self) -> None:
        """Create the main toolbar with mode dropdown and run/cancel actions."""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel(" Mode: "))
        toolbar.addWidget(self.mode_combo)
        toolbar.addSeparator()
        toolbar.addAction(self._run_action)
        toolbar.addAction(self._cancel_action)

    def _build_top_controls(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Mode combo is created here so _build_toolbar() can reference it
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["steady", "transient"])
        self.mode_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.mode_combo.setToolTip("Steady-state solves for equilibrium; transient simulates over time")

        # Row 1: view controls
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 100)
        self.top_n_spin.setValue(10)
        self.top_n_spin.setToolTip("Number of hottest cells to report")
        self.map_layer_combo = QComboBox()
        self.map_layer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.map_layer_combo.setToolTip("Layer shown in the temperature map")
        self.map_layer_combo.currentTextChanged.connect(self._refresh_map_and_profile)

        row1.addWidget(QLabel("Top-N"))
        row1.addWidget(self.top_n_spin)
        row1.addWidget(QLabel("Layer"))
        row1.addWidget(self.map_layer_combo)
        row1.addStretch()

        # Row 2: preview + snapshot/export buttons
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        preview_btn = QPushButton("Structure Preview")
        preview_btn.setToolTip("Visual preview of layer stack and source layout")
        preview_btn.clicked.connect(self._open_structure_preview)

        self._save_snapshot_btn = QPushButton("Save Snapshot")
        self._save_snapshot_btn.setToolTip("Name and store the current result in memory (max 4)")
        self._save_snapshot_btn.setEnabled(False)
        self._save_snapshot_btn.clicked.connect(self._save_snapshot)

        self._export_pdf_btn = QPushButton("Export PDF")
        self._export_pdf_btn.setToolTip("Export a multi-page PDF report for the current result")
        self._export_pdf_btn.setEnabled(False)
        self._export_pdf_btn.clicked.connect(self._export_pdf)

        row2.addWidget(preview_btn)
        row2.addWidget(self._save_snapshot_btn)
        row2.addWidget(self._export_pdf_btn)
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
        # Connect cellChanged for inline validation on all five editor tables
        for table in [
            self.materials_table, self.layers_table, self.sources_table,
            self.led_arrays_table, self.probes_table,
        ]:
            table.cellChanged.connect(lambda r, c, t=table: self._validate_cell(t, r, c))
        return tabs

    def _build_setup_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        geo_box = QGroupBox("Geometry / Mesh")
        geo_form = QFormLayout(geo_box)
        self.project_name_edit = QLineEdit()
        self.width_spin = TableDataParser._double_spin(1.0, 5000.0, 180.0, decimals=2)
        self.width_spin.setToolTip("Panel width in millimeters")
        self.height_spin = TableDataParser._double_spin(1.0, 5000.0, 100.0, decimals=2)
        self.height_spin.setToolTip("Panel height in millimeters")
        self.nx_spin = QSpinBox()
        self.nx_spin.setRange(1, 500)
        self.nx_spin.setValue(30)
        self.nx_spin.setToolTip("Number of mesh cells in X direction")
        self.ny_spin = QSpinBox()
        self.ny_spin.setRange(1, 500)
        self.ny_spin.setValue(18)
        self.ny_spin.setToolTip("Number of mesh cells in Y direction")
        self.initial_temp_spin = TableDataParser._double_spin(-60.0, 200.0, 25.0, decimals=2)
        self.initial_temp_spin.setToolTip("Starting temperature for all nodes")
        geo_form.addRow("Project name", self.project_name_edit)
        geo_form.addRow("Width [mm]", self.width_spin)
        geo_form.addRow("Height [mm]", self.height_spin)
        geo_form.addRow("Mesh cells X", self.nx_spin)
        geo_form.addRow("Mesh cells Y", self.ny_spin)
        geo_form.addRow("Initial temp [\u00b0C]", self.initial_temp_spin)

        tr_box = QGroupBox("Transient")
        tr_form = QFormLayout(tr_box)
        self.dt_spin = TableDataParser._double_spin(1e-4, 1000.0, 0.2, decimals=4)
        self.dt_spin.setToolTip("Integration time step for transient solver")
        self.total_time_spin = TableDataParser._double_spin(1e-3, 1e6, 120.0, decimals=2)
        self.total_time_spin.setToolTip("Total simulation duration")
        self.output_interval_spin = TableDataParser._double_spin(1e-4, 1e6, 2.0, decimals=4)
        self.output_interval_spin.setToolTip("Time between saved snapshots")
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
        add_btn.setToolTip("Add a new row")
        add_btn.clicked.connect(lambda: self._add_table_row_undoable(table))
        rm_btn = QPushButton("Remove")
        rm_btn.setToolTip("Remove the selected row")
        rm_btn.clicked.connect(lambda: self._remove_table_row(table))
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        for btn in (extra_buttons or []):
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)
        return tab, table

    @staticmethod
    def _set_header_tooltips(table: QTableWidget, tooltips: dict[str, str]) -> None:
        """Set tooltips on table column header items by matching header text."""
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            if item is not None and item.text() in tooltips:
                item.setToolTip(tooltips[item.text()])

    def _build_materials_tab(self) -> QWidget:
        presets_btn = QPushButton("Load Presets")
        presets_btn.setToolTip("Load built-in material presets")
        presets_btn.clicked.connect(self._load_default_materials)
        import_btn = QPushButton("Import...")
        import_btn.setToolTip("Import materials from a JSON file")
        import_btn.clicked.connect(self._import_materials_dialog)
        export_btn = QPushButton("Export...")
        export_btn.setToolTip("Export selected (or all user) materials to a JSON file")
        export_btn.clicked.connect(self._export_materials_dialog)
        tab, self.materials_table = self._build_table_tab(
            [
                "Name",
                "k in-plane [W/mK]",
                "k through [W/mK]",
                "Density [kg/m\u00b3]",
                "Specific heat [J/kgK]",
                "Emissivity",
                "Type",
            ],
            extra_buttons=[presets_btn, import_btn, export_btn],
        )
        self._set_header_tooltips(self.materials_table, {
            "Name": "Unique material identifier",
            "k in-plane [W/mK]": "Thermal conductivity in the lateral (XY) direction",
            "k through [W/mK]": "Thermal conductivity in the through-thickness (Z) direction",
            "Density [kg/m\u00b3]": "Material density",
            "Specific heat [J/kgK]": "Specific heat capacity",
            "Emissivity": "Surface emissivity (0-1) for radiation calculations",
            "Type": "User-defined or built-in preset",
        })
        self._wire_table_undo(self.materials_table)
        return tab

    def _build_layers_tab(self) -> QWidget:
        tab, self.layers_table = self._build_table_tab(
            ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]"]
        )
        self._set_header_tooltips(self.layers_table, {
            "Name": "Unique layer identifier",
            "Material": "Material name (must match a defined material)",
            "Thickness [mm]": "Layer thickness in millimeters",
            "Interface R to next [m\u00b2K/W]": "Contact resistance between this layer and the next",
        })
        self._wire_table_undo(self.layers_table)
        return tab

    def _build_sources_tab(self) -> QWidget:
        """Build the Heat Sources tab with main table + power profile sub-panel."""
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)

        # Main heat source table (same as before)
        self.sources_table = TableDataParser._new_table(
            ["Name", "Layer", "Power [W]", "Shape", "x [mm]", "y [mm]", "width [mm]", "height [mm]", "radius [mm]"]
        )
        self._set_header_tooltips(self.sources_table, {
            "Name": "Unique heat source identifier",
            "Layer": "Target layer name",
            "Power [W]": "Total power dissipated by this source",
            "Shape": "Geometry: rectangle, circle, or full",
            "x [mm]": "Source center X position",
            "y [mm]": "Source center Y position",
            "width [mm]": "Rectangle width (leave blank for circle/full)",
            "height [mm]": "Rectangle height (leave blank for circle/full)",
            "radius [mm]": "Circle radius (leave blank for rectangle/full)",
        })
        outer_layout.addWidget(self.sources_table)

        # Standard Add / Remove buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.setToolTip("Add a new row")
        add_btn.clicked.connect(lambda: self._add_table_row_undoable(self.sources_table))
        rm_btn = QPushButton("Remove")
        rm_btn.setToolTip("Remove the selected row")
        rm_btn.clicked.connect(lambda: self._remove_table_row(self.sources_table))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        outer_layout.addLayout(btn_row)

        # Power profile sub-panel (initially hidden)
        self._profile_panel = QGroupBox("Power Profile (time-varying)")
        profile_layout = QVBoxLayout(self._profile_panel)

        self._time_varying_check = QCheckBox("Time-varying power")
        self._time_varying_check.toggled.connect(self._on_time_varying_toggled)
        profile_layout.addWidget(self._time_varying_check)

        # Breakpoint table (Time [s], Power [W])
        self._bp_table = QTableWidget(0, 2)
        self._bp_table.setHorizontalHeaderLabels(["Time [s]", "Power [W]"])
        self._bp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._bp_table.verticalHeader().setVisible(False)
        self._bp_table.setAlternatingRowColors(True)
        self._bp_table.setMaximumHeight(140)
        self._bp_table.cellChanged.connect(self._on_bp_table_changed)
        profile_layout.addWidget(self._bp_table)

        bp_btn_row = QHBoxLayout()
        add_bp_btn = QPushButton("Add Breakpoint")
        add_bp_btn.setToolTip("Add a time-power breakpoint")
        add_bp_btn.clicked.connect(self._add_breakpoint_row)
        rm_bp_btn = QPushButton("Remove Breakpoint")
        rm_bp_btn.setToolTip("Remove the selected breakpoint")
        rm_bp_btn.clicked.connect(self._remove_breakpoint_row)
        bp_btn_row.addWidget(add_bp_btn)
        bp_btn_row.addWidget(rm_bp_btn)
        bp_btn_row.addStretch()
        profile_layout.addLayout(bp_btn_row)

        # Preview plot canvas
        self._profile_canvas = MplCanvas(width=4.0, height=2.2, dpi=90)
        self._profile_canvas.setMaximumHeight(170)
        profile_layout.addWidget(self._profile_canvas)

        self._profile_panel.setVisible(False)
        outer_layout.addWidget(self._profile_panel)

        # Wire undo to main table
        self._wire_table_undo(self.sources_table)

        # Wire row-selection to show/hide profile panel
        self.sources_table.itemSelectionChanged.connect(self._on_source_selection_changed)

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
            ["Name", "Layer", "Center x [mm]", "Center y [mm]", "Count x", "Count y",
             "Pitch x [mm]", "Pitch y [mm]", "Power per LED [W]",
             "LED footprint", "LED width [mm]", "LED height [mm]", "LED radius [mm]"]
        )
        self._set_header_tooltips(self.led_arrays_table, {
            "Name": "Unique LED array identifier",
            "Layer": "Target layer name",
            "Center x [mm]": "Array center X position",
            "Center y [mm]": "Array center Y position",
            "Count x": "Number of LEDs in X direction",
            "Count y": "Number of LEDs in Y direction",
            "Pitch x [mm]": "Spacing between LED centers in X",
            "Pitch y [mm]": "Spacing between LED centers in Y",
            "Power per LED [W]": "Power dissipated by each LED",
            "LED footprint": "LED shape: rectangle or circle",
            "LED width [mm]": "Individual LED width",
            "LED height [mm]": "Individual LED height",
            "LED radius [mm]": "Individual LED radius",
        })
        self._wire_table_undo(self.led_arrays_table)
        return tab

    def _build_probes_tab(self) -> QWidget:
        tab, self.probes_table = self._build_table_tab(["Name", "Layer", "x [mm]", "y [mm]"])
        self._set_header_tooltips(self.probes_table, {
            "Name": "Unique probe identifier",
            "Layer": "Target layer name",
            "x [mm]": "Probe X position",
            "y [mm]": "Probe Y position",
        })
        self._wire_table_undo(self.probes_table)
        return tab

    def _build_plot_tabs(self) -> QTabWidget:
        """Build the Result Plots dock contents: Temperature Map, Layer Profile, Probe History."""
        self._plot_tabs = QTabWidget()

        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        map_layout.addWidget(self._plot_manager.map_canvas)
        self._plot_tabs.addTab(map_tab, "Temperature Map")

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
        self._plot_tabs.addTab(profile_tab, "Layer Profile")

        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)
        hist_layout.addWidget(self._plot_manager.history_canvas)
        self._plot_tabs.addTab(hist_tab, "Probe History")

        return self._plot_tabs

    def _build_summary_tabs(self) -> QTabWidget:
        """Build the Results Summary dock contents: Summary, Results, Comparison, Sweep Results."""
        self._summary_tabs = QTabWidget()

        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.stats_label = QLabel("No results yet. Click Run Simulation to start.")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.probe_table = TableDataParser._new_table(["Probe", "Temp [\u00b0C]"])
        self.hot_table = TableDataParser._new_table(["Layer", "Temp [\u00b0C]", "x [mm]", "y [mm]"])
        summary_layout.addWidget(self.stats_label)
        summary_layout.addWidget(self.summary_text)
        summary_layout.addWidget(QLabel("Probe Readings"))
        summary_layout.addWidget(self.probe_table)
        summary_layout.addWidget(QLabel("Hottest Cells"))
        summary_layout.addWidget(self.hot_table)
        self._summary_tabs.addTab(summary_tab, "Summary")

        # Results tab: structured three-section summary widget
        self._results_widget = ResultsSummaryWidget()
        self._results_widget.hotspot_clicked.connect(self._on_hotspot_navigate)
        self._summary_tabs.addTab(self._results_widget, "Results")

        # Comparison tab: snapshot management and side-by-side analysis
        self._comparison_widget = ComparisonWidget()
        self._summary_tabs.addTab(self._comparison_widget, "Comparison")

        # Sweep Results tab: comparison table + parameter-vs-metric plot
        self._sweep_results_widget = SweepResultsWidget()
        self._summary_tabs.addTab(self._sweep_results_widget, "Sweep Results")

        return self._summary_tabs

    def _build_boundary_group(self, title: str) -> dict[str, QWidget]:
        group = QGroupBox(title)
        form = QFormLayout(group)
        ambient = TableDataParser._double_spin(-60.0, 200.0, 25.0, decimals=2)
        ambient.setToolTip("Ambient environment temperature")
        h_coeff = TableDataParser._double_spin(0.0, 5000.0, 8.0, decimals=3)
        h_coeff.setToolTip("Convective heat transfer coefficient")
        include_rad = QCheckBox()
        include_rad.setChecked(True)
        include_rad.setToolTip("Include linearized radiation heat transfer")
        emiss = QLineEdit()
        emiss.setPlaceholderText("Leave blank to use layer material value")
        emiss.setValidator(QDoubleValidator(0.0, 1.0, 6, emiss))
        emiss.setToolTip("Override surface emissivity (blank = use layer material value)")
        form.addRow("Ambient temp [\u00b0C]", ambient)
        form.addRow("h convection [W/m\u00b2K]", h_coeff)
        form.addRow("Include radiation", include_rad)
        form.addRow("Emissivity override", emiss)
        return {"group": group, "ambient": ambient, "h": h_coeff, "rad": include_rad, "emiss": emiss}

    def _reset_layout(self) -> None:
        """Restore the factory default dock arrangement."""
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)
        self._editor_dock.setFloating(False)
        self._editor_dock.show()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._plots_dock)
        self._plots_dock.setFloating(False)
        self._plots_dock.show()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._summary_dock)
        self._summary_dock.setFloating(False)
        self._summary_dock.show()
        self.splitDockWidget(self._plots_dock, self._summary_dock, Qt.Orientation.Vertical)

    def _restore_layout(self) -> None:
        """Restore dock arrangement and window geometry from QSettings."""
        settings = QSettings("ThermalSim", "ThermalSimulator")
        state = settings.value("dock_state")
        geom = settings.value("window_geometry")
        if state:
            self.restoreState(state)
        if geom:
            self.restoreGeometry(geom)

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
            canvas.draw_idle()

    # ------------------------------------------------------------------
    # Undo/redo wiring
    # ------------------------------------------------------------------

    def _wire_table_undo(self, table) -> None:
        """Connect a table widget to the undo system."""
        table.currentCellChanged.connect(
            lambda cur_row, cur_col, _prev_row, _prev_col, t=table:
                self._capture_old_value(t, cur_row, cur_col)
        )
        table.cellChanged.connect(
            lambda row, col, t=table: self._on_cell_changed(t, row, col)
        )

    def _capture_old_value(self, table, row: int, col: int) -> None:
        """Capture cell text before the user begins editing."""
        if row < 0 or col < 0:
            return
        item = table.item(row, col)
        if item is not None:
            self._pre_edit_values[(id(table), row, col)] = item.text()

    def _on_cell_changed(self, table, row: int, col: int) -> None:
        """Push an undo command when a cell's text changes."""
        if self._undoing:
            return
        item = table.item(row, col)
        if item is None:
            return
        new_val = item.text()
        old_val = self._pre_edit_values.get((id(table), row, col), "")
        if old_val == new_val:
            return
        # Update stored value
        self._pre_edit_values[(id(table), row, col)] = new_val
        cmd = _CellEditCommand(table, row, col, old_val, new_val, self)
        self._undo_stack.push(cmd)

    def _add_table_row_undoable(self, table) -> None:
        """Add a table row, wrapped in an undo macro."""
        self._undo_stack.beginMacro("Add row")
        TableDataParser._add_table_row(table)
        self._undo_stack.endMacro()

    def _remove_table_row(self, table: QTableWidget) -> None:
        """Remove selected row and revalidate to clear any stale error entries."""
        TableDataParser.remove_selected_row(self, table)
        self._revalidate_table(table)

    # ------------------------------------------------------------------
    # Inline cell validation
    # ------------------------------------------------------------------

    def _validate_cell(self, table: QTableWidget, row: int, col: int) -> None:
        """Validate a single cell and update its visual state."""
        item = table.item(row, col)
        if item is None:
            return
        error = TableDataParser.validate_cell(table, row, col)
        key = (id(table), row, col)
        if error:
            self._validation_errors[key] = error
            item.setBackground(QBrush(QColor("#8B0000")))  # dark red
            item.setForeground(QBrush(QColor("#ffcccc")))  # light pink text
            item.setToolTip(error)
        else:
            self._validation_errors.pop(key, None)
            item.setBackground(QBrush())  # default — clears to style default
            item.setForeground(QBrush())
            item.setToolTip("")
        self._update_validation_status()

    def _update_validation_status(self) -> None:
        """Update run button and status bar based on validation error count."""
        n = len(self._validation_errors)
        self._run_action.setEnabled(n == 0)
        if n > 0:
            self._solver_label.setText(f"{n} validation error{'s' if n != 1 else ''}")
        else:
            self._solver_label.setText("Ready")

    def _revalidate_table(self, table: QTableWidget) -> None:
        """Clear all errors for a table and re-validate all cells."""
        table_id = id(table)
        stale_keys = [k for k in self._validation_errors if k[0] == table_id]
        for k in stale_keys:
            del self._validation_errors[k]
        # Re-validate all cells (block signals to avoid re-entrant cellChanged)
        table.blockSignals(True)
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item is None:
                    continue
                error = TableDataParser.validate_cell(table, row, col)
                key = (table_id, row, col)
                if error:
                    self._validation_errors[key] = error
                    item.setBackground(QBrush(QColor("#8B0000")))
                    item.setForeground(QBrush(QColor("#ffcccc")))
                    item.setToolTip(error)
                else:
                    item.setBackground(QBrush())
                    item.setForeground(QBrush())
                    item.setToolTip("")
        table.blockSignals(False)
        self._update_validation_status()

    # ------------------------------------------------------------------
    # Title and path label
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        """Update window title, showing asterisk when there are unsaved changes."""
        base = f"Thermal Simulator v{APP_VERSION}"
        if self.current_project_path:
            base = f"{self.current_project_path.name} - Thermal Simulator v{APP_VERSION}"
        if not self._undo_stack.isClean():
            base = f"* {base}"
        self.setWindowTitle(base)

    def _update_path_label(self) -> None:
        """Update the left status bar zone with the current file path."""
        if self.current_project_path is not None:
            path_text = str(self.current_project_path)
        else:
            path_text = "No file"
        if not self._undo_stack.isClean():
            path_text = f"* {path_text}"
        self._path_label.setText(path_text)

    # ------------------------------------------------------------------
    # Project load/save
    # ------------------------------------------------------------------

    def _load_startup_project(self) -> None:
        default_path = get_examples_dir() / "steady_uniform_stack.json"
        if default_path.exists():
            try:
                project = load_project(default_path)
                self._populate_ui_from_project(project)
                self.current_project_path = default_path
                self._update_path_label()
                self._update_title()
                return
            except Exception:  # noqa: BLE001
                pass
        self._load_default_materials()

    def _populate_ui_from_project(self, project: DisplayProject) -> None:
        # Block signals on all editable tables to prevent spurious undo commands
        editable_tables = [
            self.materials_table,
            self.layers_table,
            self.sources_table,
            self.led_arrays_table,
            self.probes_table,
        ]
        for table in editable_tables:
            table.blockSignals(True)

        self.project_name_edit.setText(project.name)
        self.width_spin.setValue(project.width * 1000.0)
        self.height_spin.setValue(project.height * 1000.0)
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

        # Restore power profiles from loaded project
        self._source_profiles = {}
        for i, src in enumerate(project.heat_sources):
            if src.power_profile is not None and len(src.power_profile) >= 2:
                self._source_profiles[i] = list(src.power_profile)

        for table in editable_tables:
            table.blockSignals(False)

        # Clear old validation errors and re-validate all tables fresh
        self._validation_errors.clear()
        for table in editable_tables:
            self._revalidate_table(table)

        self._undo_stack.clear()
        self._undo_stack.setClean()
        self._update_title()
        self._update_path_label()

    def _load_default_materials(self) -> None:
        """Load built-in materials into the table; existing user materials are cleared."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QTableWidgetItem

        builtin = load_builtin_library()
        self._material_source = {}
        self.materials_table.blockSignals(True)
        self.materials_table.setRowCount(0)
        for mat in builtin.values():
            row = self.materials_table.rowCount()
            self.materials_table.insertRow(row)
            values = [
                mat.name,
                f"{mat.k_in_plane:g}",
                f"{mat.k_through:g}",
                f"{mat.density:g}",
                f"{mat.specific_heat:g}",
                f"{mat.emissivity:g}",
                "Built-in",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                # Built-in rows are read-only (all columns)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.materials_table.setItem(row, col, item)
            self._material_source[mat.name] = "Built-in"
        self.materials_table.blockSignals(False)

    def _add_material_row(self, mat, mat_type: str = "User") -> None:
        """Insert one material row into the materials table with appropriate flags."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QTableWidgetItem

        row = self.materials_table.rowCount()
        self.materials_table.insertRow(row)
        values = [
            mat.name,
            f"{mat.k_in_plane:g}",
            f"{mat.k_through:g}",
            f"{mat.density:g}",
            f"{mat.specific_heat:g}",
            f"{mat.emissivity:g}",
            mat_type,
        ]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            if mat_type == "Built-in":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.materials_table.setItem(row, col, item)
        self._material_source[mat.name] = mat_type

    def _import_materials_dialog(self) -> None:
        """Open a file dialog, import materials, and show rename notifications."""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import Materials",
            "",
            "JSON (*.json);;All Files (*)",
        )
        if not path_str:
            return
        try:
            incoming = load_materials_json(Path(path_str))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import Failed", f"Could not load file:\n{exc}")
            return

        builtin_names = set(load_builtin_library().keys())
        existing = TableDataParser.parse_materials_table(self.materials_table)
        merged, rename_messages = import_materials(existing, incoming, builtin_names)

        # Add only the newly imported materials (not already in table)
        self.materials_table.blockSignals(True)
        for name, mat in merged.items():
            if name not in existing:
                self._add_material_row(mat, "User")
        self.materials_table.blockSignals(False)

        self._update_title()  # reflect that project has unsaved changes
        if rename_messages:
            msg = "Some materials were renamed to avoid conflicts:\n\n" + "\n".join(rename_messages)
            QMessageBox.information(self, "Import: Name Conflicts Resolved", msg)

    def _export_materials_dialog(self) -> None:
        """Export selected materials (or all user materials) to a JSON file."""
        # Collect selected rows; if none selected, fall back to all User materials
        selected_rows = {idx.row() for idx in self.materials_table.selectedIndexes()}
        if not selected_rows:
            # Export all User materials
            selected_rows = {
                row
                for row in range(self.materials_table.rowCount())
                if TableDataParser._cell_text(self.materials_table, row, 6) == "User"
            }
        if not selected_rows:
            QMessageBox.information(self, "Export", "No user materials to export.")
            return

        # Build dict from selected rows
        to_export: dict = {}
        for row in sorted(selected_rows):
            name = TableDataParser._cell_text(self.materials_table, row, 0)
            if not name:
                continue
            try:
                from thermal_sim.models.material import Material as _Mat
                mat = _Mat(
                    name=name,
                    k_in_plane=float(TableDataParser._cell_text(self.materials_table, row, 1) or "1"),
                    k_through=float(TableDataParser._cell_text(self.materials_table, row, 2) or "1"),
                    density=float(TableDataParser._cell_text(self.materials_table, row, 3) or "1"),
                    specific_heat=float(TableDataParser._cell_text(self.materials_table, row, 4) or "1"),
                    emissivity=float(TableDataParser._cell_text(self.materials_table, row, 5) or "0.9"),
                )
                to_export[name] = mat
            except (ValueError, Exception):  # noqa: BLE001
                continue

        if not to_export:
            QMessageBox.information(self, "Export", "No valid materials to export.")
            return

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Materials",
            "materials.json",
            "JSON (*.json);;All Files (*)",
        )
        if not path_str:
            return
        try:
            export_materials(to_export, Path(path_str))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", f"Could not write file:\n{exc}")

    def _new_project(self) -> None:
        """Create a new blank project, prompting to save if there are unsaved changes."""
        if not self._maybe_save_changes():
            return
        # Build a minimal default project
        from thermal_sim.models.project import DisplayProject
        try:
            default = DisplayProject.default()
        except AttributeError:
            # Fall back to loading default materials if no .default() classmethod
            default = None
        if default is not None:
            self._populate_ui_from_project(default)
        else:
            # Reset tables manually
            editable_tables = [
                self.materials_table,
                self.layers_table,
                self.sources_table,
                self.led_arrays_table,
                self.probes_table,
            ]
            for table in editable_tables:
                table.blockSignals(True)
            for table in editable_tables:
                table.setRowCount(0)
            for table in editable_tables:
                table.blockSignals(False)
            # Clear all validation errors for the reset tables
            self._validation_errors.clear()
            self._update_validation_status()
            self._undo_stack.clear()
            self._undo_stack.setClean()
        self.current_project_path = None
        self._update_title()
        self._update_path_label()

    def _load_project_dialog(self) -> None:
        if not self._maybe_save_changes():
            return
        settings = QSettings("ThermalSim", "ThermalSimulator")
        start_dir = str(settings.value("last_open_dir", str(get_examples_dir())))
        path_str, _ = QFileDialog.getOpenFileName(self, "Open Project", start_dir, "JSON (*.json)")
        if not path_str:
            return
        try:
            path = Path(path_str)
            project = load_project(path)
            self._populate_ui_from_project(project)
            self.current_project_path = path
            settings.setValue("last_open_dir", str(path.parent))
            self._update_path_label()
            self._update_title()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Load failed", str(exc))

    def _save_project(self) -> None:
        """Save to current path; fall through to Save As if no path is set."""
        if self.current_project_path is None:
            self._save_project_as_dialog()
            return
        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Invalid project", str(exc))
            return
        try:
            save_project(project, self.current_project_path)
            self._undo_stack.setClean()
            self._update_title()
            self._update_path_label()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Save failed", str(exc))

    def _save_project_as_dialog(self) -> None:
        """Always show a Save As dialog."""
        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Invalid project", str(exc))
            return
        start = self.current_project_path or get_examples_dir() / "project.json"
        path_str, _ = QFileDialog.getSaveFileName(self, "Save Project As", str(start), "JSON (*.json)")
        if not path_str:
            return
        try:
            path = Path(path_str)
            save_project(project, path)
            self.current_project_path = path
            self._undo_stack.setClean()
            self._update_title()
            self._update_path_label()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Save failed", str(exc))

    # Keep old name as alias so any code paths from Plan 02 still work
    def _save_project_dialog(self) -> None:
        self._save_project_as_dialog()

    def _maybe_save_changes(self) -> bool:
        """Return True if it is safe to proceed, False if the user cancelled."""
        if self._undo_stack.isClean():
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_project()
            return self._undo_stack.isClean()  # False if save was itself cancelled
        if reply == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    # ------------------------------------------------------------------
    # Output directory + CSV export
    # ------------------------------------------------------------------

    def _set_output_directory(self) -> None:
        path_str = QFileDialog.getExistingDirectory(
            self, "Set Output Directory", str(self._output_dir)
        )
        if path_str:
            self._output_dir = Path(path_str)
            settings = QSettings("ThermalSim", "ThermalSimulator")
            settings.setValue("output_dir", str(self._output_dir))
            self._solver_label.setText(f"Output: {self._output_dir}")

    def _export_csv_dialog(self) -> None:
        """Export all available result CSVs to the configured output directory."""
        if self.last_steady_result is None and self.last_transient_result is None:
            self._show_error("No result", "Run a simulation first.")
            return
        output_dir = self._output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        if self.last_steady_result is not None:
            export_temperature_map(
                self.last_steady_result, output_dir / "temperature_map.csv"
            )
            if self.last_probe_values:
                export_probe_temperatures(
                    self.last_probe_values, output_dir / "probe_temperatures.csv"
                )
        else:
            result = self.last_transient_result
            assert result is not None
            export_temperature_map_array(
                result.final_temperatures_c,
                result.layer_names,
                result.dx,
                result.dy,
                output_dir / "temperature_map.csv",
            )
            if self.last_probe_history:
                export_probe_temperatures_vs_time(
                    result.times_s,
                    self.last_probe_history,
                    output_dir / "probe_temperatures_vs_time.csv",
                )
        self._solver_label.setText(f"Exported to {output_dir}")

    # Keep individual export dialogs for backward compatibility
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

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _connect_controller_signals(self) -> None:
        """Wire SimulationController signals to MainWindow slots."""
        c = self._sim_controller
        c.run_started.connect(self._on_run_started)
        c.run_ended.connect(self._on_run_ended)
        c.progress_updated.connect(self._on_progress)
        c.run_finished.connect(self._on_sim_finished)
        c.run_error.connect(self._on_sim_error)
        c.sweep_finished.connect(self._on_sweep_finished)

    def _on_run_started(self) -> None:
        """Disable Run action and show progress bar when a simulation starts."""
        self._run_action.setEnabled(False)
        self._cancel_action.setEnabled(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._solver_label.setText("Running\u2026")

    def _on_run_ended(self) -> None:
        """Re-enable Run action and hide progress bar when a simulation ends."""
        self._cancel_action.setEnabled(False)
        self._progress_bar.setVisible(False)
        # Use _update_validation_status so run stays disabled when errors exist
        self._update_validation_status()

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
                probe_times = None
                probe_hist: dict = {}
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
                probe_times = result.times_s
                probe_hist = self.last_probe_history
        except Exception as exc:  # noqa: BLE001
            self._show_error("Post-processing failed", self._friendly_error(exc))
            return

        # Store map state for re-render on hotspot navigation.
        self._last_final_map = final_map
        self._last_layer_names = layer_names

        self._plot_manager.begin_batch()
        self._plot_manager.plot_probe_history(probe_times, probe_hist)
        self._plot_map(final_map, layer_names)
        self._plot_profile(final_map, layer_names)
        self._plot_manager.end_batch()
        self._plot_manager.refresh_summary(
            self.stats_label, self.hot_table, self.summary_text,
            stats.min_c, stats.avg_c, stats.max_c, final_map, layer_names, hottest,
        )
        self._plot_manager.fill_probe_table(self.probe_table, self.last_probe_values)

        # Populate the structured Results tab and auto-activate it.
        layer_stats_data = layer_stats(final_map, layer_names)
        self._results_widget.update_data(
            layer_stats_data, hottest, self.last_probe_values, project.probes
        )
        self._summary_tabs.setCurrentWidget(self._results_widget)

        # Enable snapshot and PDF export buttons now that a result is available.
        self._save_snapshot_btn.setEnabled(True)
        self._export_pdf_btn.setEnabled(True)

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

    # ------------------------------------------------------------------
    # Parametric sweep
    # ------------------------------------------------------------------

    def _open_sweep_dialog(self) -> None:
        """Open the SweepDialog; start sweep if the user confirms."""
        try:
            project = self._build_project_from_ui()
        except Exception as exc:  # noqa: BLE001
            self._show_error("Invalid project", self._friendly_error(exc))
            return

        dlg = SweepDialog(project, parent=self)
        if dlg.exec() != SweepDialog.DialogCode.Accepted:
            return
        config = dlg.get_config()
        if config is None:
            return
        self.last_project = project
        self._sim_controller.start_sweep(project, config)

    def _on_sweep_finished(self, result: object) -> None:
        """Update the Sweep Results tab and switch to it."""
        self._sweep_results_widget.update_results(result)
        self._summary_tabs.setCurrentWidget(self._sweep_results_widget)

    # ------------------------------------------------------------------
    # Snapshot management
    # ------------------------------------------------------------------

    def _build_snapshot(self, name: str) -> ResultSnapshot:
        """Capture the current simulation result as a named snapshot."""
        project = self.last_project
        if self.last_steady_result is not None:
            result = self.last_steady_result
            final_map = result.temperatures_c
            temps_time = None
            times = None
            probe_values: dict = dict(self.last_probe_values)
        else:
            result = self.last_transient_result
            final_map = result.final_temperatures_c
            temps_time = result.temperatures_time_c.copy() if hasattr(result, "temperatures_time_c") and result.temperatures_time_c is not None else None
            times = result.times_s.copy() if result.times_s is not None else None
            probe_values = {k: v.copy() for k, v in self.last_probe_history.items()}

        stats = layer_stats(final_map, result.layer_names)
        if self.last_steady_result is not None:
            hotspots = top_n_hottest_cells(self.last_steady_result, n=10)
        else:
            hotspots = top_n_hottest_cells_transient(self.last_transient_result, n=10)

        return ResultSnapshot(
            name=name,
            mode=self._sim_mode,
            project_name=project.name,
            simulation_date=datetime.now().isoformat(timespec="seconds"),
            layer_names=list(result.layer_names),
            final_temperatures_c=final_map.copy(),
            temperatures_time_c=temps_time,
            times_s=times,
            layer_stats=stats,
            hotspots=hotspots,
            probe_values=probe_values,
            dx=result.dx,
            dy=result.dy,
            width_m=project.width,
            height_m=project.height,
            probes=list(project.probes),
        )

    def _save_snapshot(self) -> None:
        """Prompt for a name, create a snapshot, and add it to the comparison list."""
        if self.last_steady_result is None and self.last_transient_result is None:
            return
        name, ok = QInputDialog.getText(self, "Save Snapshot", "Snapshot name:")
        if not ok or not name.strip():
            return
        if len(self._snapshots) >= 4:
            self._snapshots.pop(0)  # Evict oldest
        snapshot = self._build_snapshot(name.strip())
        self._snapshots.append(snapshot)
        self._comparison_widget.set_snapshots(self._snapshots)
        self.statusBar().showMessage(
            f"Snapshot '{name.strip()}' saved ({len(self._snapshots)}/4)."
        )

    def _export_pdf(self) -> None:
        """Export a multi-page PDF report for the current simulation result."""
        if self.last_steady_result is None and self.last_transient_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF Report", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            snapshot = self._build_snapshot("export")
            generate_pdf_report(snapshot, path)
            self.statusBar().showMessage(f"PDF exported to {path}")
        except Exception as exc:  # noqa: BLE001
            self._show_error("PDF export failed", str(exc))

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        msg = str(exc)
        if isinstance(exc, ValueError):
            return f"Invalid value \u2014 {msg}"
        if isinstance(exc, KeyError):
            return f"Referenced item not found: {msg}"
        return msg

    # ------------------------------------------------------------------
    # Plotting helpers
    # ------------------------------------------------------------------

    def _plot_map(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        """Render the temperature map with annotated hotspot crosshairs and probe markers."""
        layer_name = self.map_layer_combo.currentText()
        layer_idx = (
            layer_names.index(layer_name) if layer_name in layer_names else len(layer_names) - 1
        )
        width_m = self.width_spin.value() / 1000.0
        height_m = self.height_spin.value() / 1000.0
        data = final_map_c[layer_idx]

        # Compute per-layer hotspots (top 3) for annotation.
        result = self.last_steady_result or self.last_transient_result
        if result is not None:
            per_layer_hotspots = top_n_hottest_cells_for_layer(
                final_map_c, layer_idx, layer_name, result.dx, result.dy, n=3
            )
        else:
            per_layer_hotspots = None

        # Collect probes on this layer.
        layer_probes = [
            p for p in (self.last_project.probes if self.last_project else [])
            if p.layer == layer_name
        ]

        canvas = self._plot_manager.map_canvas
        ax = canvas.axes

        # Remove old colorbar before clearing axes.
        if canvas._colorbar is not None:
            canvas._colorbar.remove()
            canvas._colorbar = None
        ax.clear()
        canvas._image = None

        im = plot_temperature_map_annotated(
            ax, data, width_m, height_m,
            title=f"Temperature Map - {layer_name}",
            hotspots=per_layer_hotspots,
            probes=layer_probes if layer_probes else None,
            selected_hotspot_rank=self._selected_hotspot_rank,
        )
        canvas._colorbar = canvas.figure.colorbar(im, ax=ax, label="Temperature [\u00b0C]")
        canvas._image = im
        canvas.figure.tight_layout()

        if not self._plot_manager._batching:
            canvas.draw_idle()

    def _on_hotspot_navigate(
        self, rank: int, layer_name: str, x_m: float, y_m: float  # noqa: ARG002
    ) -> None:
        """Navigate to a hotspot location on the temperature map.

        Switches the layer combo and re-renders the map with the selected hotspot
        highlighted, then switches to the Temperature Map tab.
        """
        self.map_layer_combo.setCurrentText(layer_name)
        self._selected_hotspot_rank = rank
        # Switch to Temperature Map tab (index 0) and ensure plots dock is visible.
        self._plot_tabs.setCurrentIndex(0)
        self._plots_dock.show()
        self._plots_dock.raise_()
        # Re-render map with the highlight.
        if self._last_final_map is not None and self._last_layer_names is not None:
            self._plot_map(self._last_final_map, self._last_layer_names)
        # Clear highlight so next manual interaction doesn't retain it.
        self._selected_hotspot_rank = None

    def _plot_profile(self, final_map_c: np.ndarray, layer_names: list[str]) -> None:
        """Thin dispatcher — reads widget state and delegates to PlotManager."""
        x_m, y_m = self._selected_profile_point()
        self._plot_manager.plot_layer_profile(
            final_map_c, layer_names, x_m, y_m,
            width_m=self.width_spin.value() / 1000.0,
            height_m=self.height_spin.value() / 1000.0,
        )

    def _refresh_map_and_profile(self) -> None:
        # Clear highlight when user manually changes layer.
        self._selected_hotspot_rank = None
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
            return self.width_spin.value() / 2000.0, self.height_spin.value() / 2000.0
        for probe in self.last_project.probes:
            if probe.name == label:
                return probe.x, probe.y
        return self.width_spin.value() / 2000.0, self.height_spin.value() / 2000.0

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

    # ------------------------------------------------------------------
    # Power profile UI helpers
    # ------------------------------------------------------------------

    def _on_source_selection_changed(self) -> None:
        """Show the profile panel when a source row is selected."""
        row = self.sources_table.currentRow()
        if row < 0:
            self._profile_panel.setVisible(False)
            return
        self._profile_panel.setVisible(True)
        # Load breakpoints for this row (if any stored)
        bps = self._source_profiles.get(row, [])
        has_profile = len(bps) >= 2
        self._time_varying_check.blockSignals(True)
        self._time_varying_check.setChecked(has_profile)
        self._time_varying_check.blockSignals(False)
        self._bp_table.setVisible(has_profile)
        self._profile_canvas.setVisible(has_profile)
        if has_profile:
            self._load_breakpoints_into_table(bps)
            self._refresh_profile_preview()

    def _on_time_varying_toggled(self, checked: bool) -> None:
        """Show/hide breakpoint table and preview based on checkbox state."""
        self._bp_table.setVisible(checked)
        self._profile_canvas.setVisible(checked)
        if checked:
            row = self.sources_table.currentRow()
            bps = self._source_profiles.get(row, [])
            if len(bps) < 2:
                # Seed with two rows: (0, current power) and (1, current power)
                from thermal_sim.models.heat_source import PowerBreakpoint
                try:
                    power = float(TableDataParser._cell_text(self.sources_table, row, 2) or "1")
                except (ValueError, Exception):
                    power = 1.0
                bps = [PowerBreakpoint(0.0, power), PowerBreakpoint(1.0, power)]
                self._source_profiles[row] = bps
            self._load_breakpoints_into_table(bps)
            self._refresh_profile_preview()
        else:
            row = self.sources_table.currentRow()
            if row >= 0:
                self._source_profiles.pop(row, None)
            self._bp_table.setRowCount(0)
            ax = self._profile_canvas.axes
            ax.clear()
            self._profile_canvas.draw_idle()

    def _load_breakpoints_into_table(self, bps: list) -> None:
        """Populate the breakpoint table from a list of PowerBreakpoint objects."""
        self._bp_table.blockSignals(True)
        self._bp_table.setRowCount(0)
        for bp in bps:
            r = self._bp_table.rowCount()
            self._bp_table.insertRow(r)
            self._bp_table.setItem(r, 0, QTableWidgetItem(f"{bp.time_s:g}"))
            self._bp_table.setItem(r, 1, QTableWidgetItem(f"{bp.power_w:g}"))
        self._bp_table.blockSignals(False)

    def _on_bp_table_changed(self) -> None:
        """Save breakpoints and refresh preview when table is edited."""
        self._save_breakpoints_from_table()
        self._refresh_profile_preview()

    def _save_breakpoints_from_table(self) -> None:
        """Read the breakpoint table into _source_profiles for the selected row."""
        from thermal_sim.models.heat_source import PowerBreakpoint
        src_row = self.sources_table.currentRow()
        if src_row < 0:
            return
        bps = []
        for r in range(self._bp_table.rowCount()):
            t_item = self._bp_table.item(r, 0)
            p_item = self._bp_table.item(r, 1)
            if t_item is None or p_item is None:
                continue
            try:
                t = float(t_item.text())
                p = float(p_item.text())
                bps.append(PowerBreakpoint(t, p))
            except ValueError:
                continue
        self._source_profiles[src_row] = bps

    def _add_breakpoint_row(self) -> None:
        """Append a new row to the breakpoint table."""
        r = self._bp_table.rowCount()
        self._bp_table.insertRow(r)
        # Default: time one unit after last, same power as last
        if r > 0:
            prev_t = self._bp_table.item(r - 1, 0)
            prev_p = self._bp_table.item(r - 1, 1)
            try:
                t_val = float(prev_t.text()) + 1.0 if prev_t else float(r)
                p_val = float(prev_p.text()) if prev_p else 0.0
            except ValueError:
                t_val, p_val = float(r), 0.0
        else:
            t_val, p_val = 0.0, 0.0
        self._bp_table.setItem(r, 0, QTableWidgetItem(f"{t_val:g}"))
        self._bp_table.setItem(r, 1, QTableWidgetItem(f"{p_val:g}"))

    def _remove_breakpoint_row(self) -> None:
        """Remove the currently selected breakpoint row."""
        row = self._bp_table.currentRow()
        if row < 0:
            return
        self._bp_table.removeRow(row)
        self._save_breakpoints_from_table()
        self._refresh_profile_preview()

    def _refresh_profile_preview(self) -> None:
        """Redraw the power-profile preview plot."""
        src_row = self.sources_table.currentRow()
        bps = self._source_profiles.get(src_row, [])
        ax = self._profile_canvas.axes
        ax.clear()
        if len(bps) >= 2:
            times = [bp.time_s for bp in bps]
            powers = [bp.power_w for bp in bps]
            ax.plot(times, powers, marker="o", linewidth=1.5)
            ax.set_xlabel("Time [s]", fontsize=8)
            ax.set_ylabel("Power [W]", fontsize=8)
            ax.set_title("Power Profile", fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=7)
        else:
            ax.text(0.5, 0.5, "Add breakpoints", ha="center", va="center",
                    transform=ax.transAxes, color="grey")
            ax.set_axis_off()
        self._profile_canvas.figure.tight_layout()
        self._profile_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Structure preview
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Project model helpers
    # ------------------------------------------------------------------

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
        project = TableDataParser.build_project_from_tables(
            self._tables_dict, self._spinboxes_dict, self._boundary_widgets_dict
        )
        # Attach power profiles from the profile sub-panel
        from thermal_sim.models.heat_source import PowerBreakpoint
        for row_idx, bps in self._source_profiles.items():
            if row_idx < len(project.heat_sources) and len(bps) >= 2:
                src = project.heat_sources[row_idx]
                src.power_profile = list(bps)
        return project

    def _validate_project(self) -> list[str]:
        """Delegate to TableDataParser.validate_tables()."""
        return TableDataParser.validate_tables(self._tables_dict)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Prompt to save unsaved changes before closing."""
        settings = QSettings("ThermalSim", "ThermalSimulator")
        settings.setValue("dock_state", self.saveState())
        settings.setValue("window_geometry", self.saveGeometry())
        if self._maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:
        """Intercept Escape to cancel a running simulation."""
        if event.key() == Qt.Key.Key_Escape and self._sim_controller.is_running:
            self._sim_controller.cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
