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
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
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
from thermal_sim.io.pdf_export import generate_pdf_report
from thermal_sim.models.snapshot import ResultSnapshot
from thermal_sim.ui.comparison_tab import ComparisonWidget
from thermal_sim.ui.plot_manager import MplCanvas, PlotManager
from thermal_sim.ui.results_tab import ResultsSummaryWidget
from thermal_sim.ui.simulation_controller import SimulationController
from thermal_sim.ui.table_data_parser import TableDataParser

# ---------------------------------------------------------------------------
# Legacy (Layer-based) imports — these modules were removed in Phase 11 Plan 03.
# Wrapped in try/except so the file remains importable; the old MainWindow class
# below will not function correctly at runtime without them, but VoxelMainWindow
# (added at the end of this file) is the active GUI class.
# ---------------------------------------------------------------------------
try:
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
except ImportError:
    basic_stats = basic_stats_transient = layer_stats = None  # type: ignore[assignment]
    probe_temperatures = probe_temperatures_over_time = None  # type: ignore[assignment]
    top_n_hottest_cells = top_n_hottest_cells_for_layer = top_n_hottest_cells_transient = None  # type: ignore[assignment]

try:
    from thermal_sim.visualization.plotting import plot_temperature_map_annotated
except ImportError:
    plot_temperature_map_annotated = None  # type: ignore[assignment]

try:
    from thermal_sim.io.csv_export import (
        export_probe_temperatures,
        export_probe_temperatures_vs_time,
        export_temperature_map,
        export_temperature_map_array,
    )
except ImportError:
    export_probe_temperatures = export_probe_temperatures_vs_time = None  # type: ignore[assignment]
    export_temperature_map = export_temperature_map_array = None  # type: ignore[assignment]

try:
    from thermal_sim.io.project_io import load_project, save_project
except ImportError:
    load_project = save_project = None  # type: ignore[assignment]

try:
    from thermal_sim.models.project import DisplayProject
except ImportError:
    DisplayProject = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.solvers.steady_state import SteadyStateResult, SteadyStateSolver
except ImportError:
    SteadyStateResult = SteadyStateSolver = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.solvers.transient import TransientResult, TransientSolver
except ImportError:
    TransientResult = TransientSolver = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.ui.structure_preview import StructurePreviewDialog
except ImportError:
    StructurePreviewDialog = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.ui.sweep_dialog import SweepDialog
except ImportError:
    SweepDialog = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.ui.sweep_results_widget import SweepResultsWidget
except ImportError:
    SweepResultsWidget = None  # type: ignore[assignment,misc]

try:
    from thermal_sim.models.material_zone import MaterialZone
except ImportError:
    MaterialZone = None  # type: ignore[assignment,misc]


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
        self.setWindowTitle(f"Display Thermal Simulator v{APP_VERSION}")
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

        # LED-array rows may carry mode-specific metadata not shown in the generic table.
        self._led_array_extras: dict[int, dict] = {}

        # Material zones per layer row: layer_row_index -> list[dict]
        # Each dict: {"material": str, "x": float, "y": float, "width": float, "height": float} (SI metres)
        self._layer_zones: dict[int, list] = {}
        # Guard flag to prevent recursive cellChanged during zone table population
        self._updating_zones: bool = False

        # Edge layers per layer row: layer_row_index -> dict[edge, list[dict]]
        # Each inner dict: {"material": str, "thickness": float} (SI metres)
        self._layer_edge_layers: dict[int, dict[str, list]] = {}
        # Guard flag to prevent recursive cellChanged during edge layer table population
        self._updating_edge_layers: bool = False
        # Current edge tab selection ("bottom", "top", "left", "right")
        self._current_edge: str = "bottom"

        # 3D assembly dock (lazy-created on first use)
        self._3d_dock = None
        self._3d_widget = None

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

        # Panel dimension changes update auto-computed pitch labels
        # (must be after both top_controls and editor_tabs are built)
        self.width_spin.valueChanged.connect(self._update_dled_pitch_labels)
        self.height_spin.valueChanged.connect(self._update_dled_pitch_labels)
        self.width_spin.valueChanged.connect(self._update_eled_pitch_label)
        self.height_spin.valueChanged.connect(self._update_eled_pitch_label)
        # Mesh size changes update node count in status bar
        self.nx_spin.valueChanged.connect(self._update_node_count_label)
        self.ny_spin.valueChanged.connect(self._update_node_count_label)
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
        self._node_count_label = QLabel("")
        sb.addPermanentWidget(self._path_label, stretch=2)
        sb.addPermanentWidget(self._solver_label, stretch=1)
        sb.addPermanentWidget(self._progress_bar, stretch=1)
        sb.addPermanentWidget(self._run_info_label, stretch=1)
        sb.addPermanentWidget(self._node_count_label, stretch=1)

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

        # 3D Assembly Preview toggle (lazy-created on first activation)
        self._3d_preview_action = QAction("3D &Assembly Preview", self)
        self._3d_preview_action.setCheckable(True)
        self._3d_preview_action.triggered.connect(self._toggle_3d_preview)
        view_menu.addAction(self._3d_preview_action)

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

        # Row 0: Architecture selection
        row0 = QHBoxLayout()
        row0.setSpacing(4)
        self.arch_combo = QComboBox()
        self.arch_combo.addItems(["Custom", "DLED", "ELED"])
        self.arch_combo.setToolTip(
            "Select display backlight architecture to auto-populate stack and LED configuration"
        )
        row0.addWidget(QLabel("Architecture"))
        row0.addWidget(self.arch_combo)
        row0.addStretch()
        outer.addLayout(row0)

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

        # Wire architecture combo signal (panels built in _build_led_arrays_tab)
        self.arch_combo.currentTextChanged.connect(self._on_architecture_changed)

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

        ef_box = QGroupBox("Edge Frame")
        ef_box.setToolTip(
            "Add a uniform metal frame + air gap around the perimeter of every layer"
        )
        ef_form = QFormLayout(ef_box)
        self._ef_metal_spin = TableDataParser._double_spin(0.1, 50.0, 3.0, decimals=2)
        self._ef_metal_spin.setToolTip("Steel frame thickness on each edge")
        self._ef_air_spin = TableDataParser._double_spin(0.01, 50.0, 1.0, decimals=2)
        self._ef_air_spin.setToolTip("Air gap thickness between frame and panel body")
        ef_form.addRow("Metal thickness [mm]", self._ef_metal_spin)
        ef_form.addRow("Air gap [mm]", self._ef_air_spin)
        ef_apply_btn = QPushButton("Apply to All Layers")
        ef_apply_btn.setToolTip(
            "Set these edge layers on every layer. You can then modify individual layers in the Layers tab."
        )
        ef_apply_btn.clicked.connect(self._apply_edge_frame)
        ef_form.addRow(ef_apply_btn)
        self._ef_box = ef_box

        layout.addWidget(geo_box)
        layout.addWidget(tr_box)
        layout.addWidget(ef_box)
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
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.layers_table = TableDataParser._new_table(
            ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]", "nz"]
        )
        layout.addWidget(self.layers_table)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.setToolTip("Add a new row")
        add_btn.clicked.connect(self._add_layer_row)
        rm_btn = QPushButton("Remove")
        rm_btn.setToolTip("Remove the selected row")
        rm_btn.clicked.connect(lambda: self._remove_table_row(self.layers_table))
        up_btn = QPushButton("\u25b2 Up")
        up_btn.setToolTip("Move selected layer up in the stack")
        up_btn.clicked.connect(self._move_layer_up)
        down_btn = QPushButton("\u25bc Down")
        down_btn.setToolTip("Move selected layer down in the stack")
        down_btn.clicked.connect(self._move_layer_down)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._set_header_tooltips(self.layers_table, {
            "Name": "Unique layer identifier",
            "Material": "Material name (must match a defined material)",
            "Thickness [mm]": "Layer thickness in millimeters",
            "Interface R to next [m\u00b2K/W]": "Contact resistance between this layer and the next",
            "nz": "Number of z-sublayers through thickness (z-refinement)",
        })
        self._wire_table_undo(self.layers_table)

        # Zone sub-panel (appears when a layer row is selected)
        self._zone_panel = QGroupBox("Material Zones")
        zone_layout = QVBoxLayout(self._zone_panel)

        # Zone table: Material, X start [mm], X end [mm], Y start [mm], Y end [mm]
        self._zone_table = QTableWidget(0, 5)
        self._zone_table.setHorizontalHeaderLabels(
            ["Material", "X start [mm]", "X end [mm]", "Y start [mm]", "Y end [mm]"]
        )
        self._zone_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._zone_table.verticalHeader().setVisible(False)
        self._zone_table.setAlternatingRowColors(True)
        self._zone_table.setMaximumHeight(150)
        self._zone_table.cellChanged.connect(self._on_zone_table_changed)
        zone_layout.addWidget(self._zone_table)

        zone_btn_row = QHBoxLayout()
        add_zone_btn = QPushButton("+ Add Zone")
        add_zone_btn.setToolTip("Add a rectangular material zone to this layer")
        add_zone_btn.clicked.connect(self._add_zone_row)
        rm_zone_btn = QPushButton("- Remove Zone")
        rm_zone_btn.setToolTip("Remove the selected zone")
        rm_zone_btn.clicked.connect(self._remove_zone_row)
        zone_btn_row.addWidget(add_zone_btn)
        zone_btn_row.addWidget(rm_zone_btn)
        zone_btn_row.addStretch()
        zone_layout.addLayout(zone_btn_row)

        # Zone preview canvas
        self._zone_preview_canvas = MplCanvas(width=3.5, height=2.5, dpi=80)
        self._zone_preview_canvas.setMaximumHeight(200)
        zone_layout.addWidget(self._zone_preview_canvas)

        self._zone_panel.setVisible(False)
        layout.addWidget(self._zone_panel)

        # Edge Layer sub-panel (appears when a layer row is selected)
        self._edge_layer_panel = QGroupBox("Edge Layers")
        edge_layout = QVBoxLayout(self._edge_layer_panel)

        # 4 edge tab buttons (Bottom / Top / Left / Right), exclusive
        edge_tab_row = QHBoxLayout()
        self._edge_buttons: dict[str, QPushButton] = {}
        for edge_name in ("bottom", "top", "left", "right"):
            btn = QPushButton(edge_name.capitalize())
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, e=edge_name: self._on_edge_tab_clicked(e))
            self._edge_buttons[edge_name] = btn
            edge_tab_row.addWidget(btn)
        edge_tab_row.addStretch()
        edge_layout.addLayout(edge_tab_row)
        # Default: bottom is active
        self._edge_buttons["bottom"].setChecked(True)

        # Edge table: Material, Thickness [mm]
        self._edge_table = QTableWidget(0, 2)
        self._edge_table.setHorizontalHeaderLabels(["Material", "Thickness [mm]"])
        self._edge_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._edge_table.verticalHeader().setVisible(False)
        self._edge_table.setAlternatingRowColors(True)
        self._edge_table.setMaximumHeight(130)
        self._edge_table.cellChanged.connect(self._on_edge_table_changed)
        edge_layout.addWidget(self._edge_table)

        edge_btn_row = QHBoxLayout()
        add_edge_btn = QPushButton("+ Add")
        add_edge_btn.setToolTip("Add an edge layer to this edge")
        add_edge_btn.clicked.connect(self._add_edge_layer_row)
        rm_edge_btn = QPushButton("- Remove")
        rm_edge_btn.setToolTip("Remove the selected edge layer")
        rm_edge_btn.clicked.connect(self._remove_edge_layer_row)
        self._copy_from_btn = QPushButton("Copy From \u25bc")
        self._copy_from_btn.setToolTip("Copy edge layers from another edge")
        self._copy_from_btn.clicked.connect(self._on_copy_from_clicked)
        edge_btn_row.addWidget(add_edge_btn)
        edge_btn_row.addWidget(rm_edge_btn)
        edge_btn_row.addWidget(self._copy_from_btn)
        edge_btn_row.addStretch()
        edge_layout.addLayout(edge_btn_row)

        self._edge_layer_panel.setVisible(False)
        layout.addWidget(self._edge_layer_panel)

        # Wire layer row selection to show/hide zone panel and edge panel
        self.layers_table.itemSelectionChanged.connect(self._on_layer_selected_for_zones)

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
        """Return a QStackedWidget with Custom (0), DLED (1), and ELED (2) panels."""
        self._led_arrays_stack = QStackedWidget()
        self._led_arrays_stack.addWidget(self._build_custom_led_panel())   # index 0
        self._led_arrays_stack.addWidget(self._build_dled_panel())          # index 1
        self._led_arrays_stack.addWidget(self._build_eled_panel())          # index 2
        return self._led_arrays_stack

    def _build_custom_led_panel(self) -> QWidget:
        """Build the existing custom LED arrays table panel (unchanged behaviour)."""
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

    def _build_dled_panel(self) -> QWidget:
        """Build the DLED-specific panel with grid config, edge offsets, zone dimming, and footprint."""
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        # --- Grid Configuration ---
        grid_box = QGroupBox("Grid Configuration")
        grid_form = QFormLayout(grid_box)

        self._dled_count_x = QSpinBox()
        self._dled_count_x.setRange(1, 200)
        self._dled_count_x.setValue(8)
        self._dled_count_x.setToolTip("Number of LEDs in X direction")

        self._dled_count_y = QSpinBox()
        self._dled_count_y.setRange(1, 200)
        self._dled_count_y.setValue(6)
        self._dled_count_y.setToolTip("Number of LEDs in Y direction")

        self._dled_pitch_x_label = QLabel("—")
        self._dled_pitch_x_label.setToolTip("Auto-computed spacing between LED centers in X (mm)")

        self._dled_pitch_y_label = QLabel("—")
        self._dled_pitch_y_label.setToolTip("Auto-computed spacing between LED centers in Y (mm)")

        self._dled_power = TableDataParser._double_spin(0.0, 100.0, 0.5, decimals=3)
        self._dled_power.setToolTip("Power dissipated by each individual LED (W)")

        grid_form.addRow("Count X", self._dled_count_x)
        grid_form.addRow("Count Y", self._dled_count_y)
        grid_form.addRow("Pitch X [mm]", self._dled_pitch_x_label)
        grid_form.addRow("Pitch Y [mm]", self._dled_pitch_y_label)
        grid_form.addRow("Power per LED [W]", self._dled_power)
        layout.addWidget(grid_box)

        # --- Edge Offsets ---
        offsets_box = QGroupBox("Edge Offsets [mm]")
        offsets_form = QFormLayout(offsets_box)

        self._dled_offset_top = TableDataParser._double_spin(0.0, 500.0, 10.0, decimals=2)
        self._dled_offset_top.setToolTip("Distance from top panel edge to LED active area")

        self._dled_offset_bottom = TableDataParser._double_spin(0.0, 500.0, 10.0, decimals=2)
        self._dled_offset_bottom.setToolTip("Distance from bottom panel edge to LED active area")

        self._dled_offset_left = TableDataParser._double_spin(0.0, 500.0, 18.0, decimals=2)
        self._dled_offset_left.setToolTip("Distance from left panel edge to LED active area")

        self._dled_offset_right = TableDataParser._double_spin(0.0, 500.0, 18.0, decimals=2)
        self._dled_offset_right.setToolTip("Distance from right panel edge to LED active area")

        offsets_form.addRow("Top [mm]", self._dled_offset_top)
        offsets_form.addRow("Bottom [mm]", self._dled_offset_bottom)
        offsets_form.addRow("Left [mm]", self._dled_offset_left)
        offsets_form.addRow("Right [mm]", self._dled_offset_right)
        layout.addWidget(offsets_box)

        # --- Zone Dimming ---
        zone_box = QGroupBox("Zone Dimming")
        zone_layout = QVBoxLayout(zone_box)
        zone_count_row = QFormLayout()

        self._dled_zone_count_x = QSpinBox()
        self._dled_zone_count_x.setRange(1, 20)
        self._dled_zone_count_x.setValue(1)
        self._dled_zone_count_x.setToolTip("Number of dimming zones in X direction")

        self._dled_zone_count_y = QSpinBox()
        self._dled_zone_count_y.setRange(1, 20)
        self._dled_zone_count_y.setValue(1)
        self._dled_zone_count_y.setToolTip("Number of dimming zones in Y direction")

        zone_count_row.addRow("Zone count X", self._dled_zone_count_x)
        zone_count_row.addRow("Zone count Y", self._dled_zone_count_y)
        zone_layout.addLayout(zone_count_row)

        self._dled_zone_table = QTableWidget(1, 2)
        self._dled_zone_table.setHorizontalHeaderLabels(["Zone", "Power [W]"])
        self._dled_zone_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._dled_zone_table.verticalHeader().setVisible(False)
        self._dled_zone_table.setAlternatingRowColors(True)
        self._dled_zone_table.setMaximumHeight(160)
        self._dled_zone_table.setItem(0, 0, QTableWidgetItem("Z(1,1)"))
        self._dled_zone_table.setItem(0, 1, QTableWidgetItem("0.5"))
        zone_layout.addWidget(self._dled_zone_table)
        layout.addWidget(zone_box)

        # --- LED Footprint ---
        foot_box = QGroupBox("LED Footprint")
        foot_form = QFormLayout(foot_box)

        self._dled_footprint_shape = QComboBox()
        self._dled_footprint_shape.addItems(["rectangle", "circle"])
        self._dled_footprint_shape.setToolTip("LED footprint geometry")

        self._dled_led_width = TableDataParser._double_spin(0.0, 100.0, 3.0, decimals=3)
        self._dled_led_width.setToolTip("Individual LED width (mm)")

        self._dled_led_height = TableDataParser._double_spin(0.0, 100.0, 3.0, decimals=3)
        self._dled_led_height.setToolTip("Individual LED height (mm)")

        self._dled_led_radius = TableDataParser._double_spin(0.0, 100.0, 1.5, decimals=3)
        self._dled_led_radius.setToolTip("Individual LED radius (mm, used when shape is circle)")

        foot_form.addRow("Shape", self._dled_footprint_shape)
        foot_form.addRow("Width [mm]", self._dled_led_width)
        foot_form.addRow("Height [mm]", self._dled_led_height)
        foot_form.addRow("Radius [mm]", self._dled_led_radius)
        layout.addWidget(foot_box)

        layout.addStretch()
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)

        # Connect zone count changes to rebuild table
        self._dled_zone_count_x.valueChanged.connect(self._rebuild_zone_table)
        self._dled_zone_count_y.valueChanged.connect(self._rebuild_zone_table)

        # Connect count/offset changes to update computed pitch labels
        self._dled_count_x.valueChanged.connect(self._update_dled_pitch_labels)
        self._dled_count_y.valueChanged.connect(self._update_dled_pitch_labels)
        self._dled_offset_left.valueChanged.connect(self._update_dled_pitch_labels)
        self._dled_offset_right.valueChanged.connect(self._update_dled_pitch_labels)
        self._dled_offset_top.valueChanged.connect(self._update_dled_pitch_labels)
        self._dled_offset_bottom.valueChanged.connect(self._update_dled_pitch_labels)

        return outer

    def _build_eled_panel(self) -> QWidget:
        """Build the ELED-specific panel with edge configuration, strip parameters, and footprint."""
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        # --- Edge Configuration ---
        edge_box = QGroupBox("Edge Configuration")
        edge_form = QFormLayout(edge_box)

        self._eled_layer_combo = QComboBox()
        self._eled_layer_combo.setToolTip("Target layer for ELED array placement")

        self._eled_edge_config = QComboBox()
        self._eled_edge_config.addItems(["bottom", "top", "left/right", "all"])
        self._eled_edge_config.setToolTip("Which panel edges carry LEDs")

        self._eled_count = QSpinBox()
        self._eled_count.setRange(1, 200)
        self._eled_count.setValue(20)
        self._eled_count.setToolTip("Number of LEDs along a horizontal edge (count_x) / vertical edge (count_y)")

        self._eled_pitch_label = QLabel("—")
        self._eled_pitch_label.setToolTip("Auto-computed spacing between LED centers along the edge (mm)")

        self._eled_edge_offset = TableDataParser._double_spin(0.1, 50.0, 5.0, decimals=3)
        self._eled_edge_offset.setToolTip("Distance from panel edge to LED center (mm)")

        self._eled_power = TableDataParser._double_spin(0.0, 100.0, 0.3, decimals=3)
        self._eled_power.setToolTip("Power dissipated by each individual LED (W)")

        edge_form.addRow("Layer", self._eled_layer_combo)
        edge_form.addRow("Edge", self._eled_edge_config)
        edge_form.addRow("Count along edge", self._eled_count)
        edge_form.addRow("Pitch [mm]", self._eled_pitch_label)
        edge_form.addRow("Edge offset [mm]", self._eled_edge_offset)
        edge_form.addRow("Power per LED [W]", self._eled_power)
        layout.addWidget(edge_box)

        # --- LED Footprint ---
        foot_box = QGroupBox("LED Footprint")
        foot_form = QFormLayout(foot_box)

        self._eled_footprint_shape = QComboBox()
        self._eled_footprint_shape.addItems(["rectangle", "circle"])
        self._eled_footprint_shape.setToolTip("LED footprint geometry")

        self._eled_led_width = TableDataParser._double_spin(0.0, 100.0, 2.0, decimals=3)
        self._eled_led_width.setToolTip("Individual LED width (mm)")

        self._eled_led_height = TableDataParser._double_spin(0.0, 100.0, 1.0, decimals=3)
        self._eled_led_height.setToolTip("Individual LED height (mm)")

        self._eled_led_radius = TableDataParser._double_spin(0.0, 100.0, 1.0, decimals=3)
        self._eled_led_radius.setToolTip("Individual LED radius (mm, used when shape is circle)")

        foot_form.addRow("Shape", self._eled_footprint_shape)
        foot_form.addRow("Width [mm]", self._eled_led_width)
        foot_form.addRow("Height [mm]", self._eled_led_height)
        foot_form.addRow("Radius [mm]", self._eled_led_radius)
        layout.addWidget(foot_box)

        layout.addStretch()
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)

        # Connect count/offset/edge config changes to update computed pitch label
        self._eled_count.valueChanged.connect(self._update_eled_pitch_label)
        self._eled_edge_offset.valueChanged.connect(self._update_eled_pitch_label)
        self._eled_edge_config.currentTextChanged.connect(
            lambda _: self._update_eled_pitch_label()
        )
        # When user picks an edge layer target, auto-set edge config + offset
        self._eled_layer_combo.currentTextChanged.connect(self._on_eled_layer_target_changed)

        return outer

    def _rebuild_zone_table(self) -> None:
        """Rebuild the DLED zone power table when zone counts change."""
        # Preserve existing values
        old_count = self._dled_zone_table.rowCount()
        old_powers: dict[int, str] = {}
        for r in range(old_count):
            item = self._dled_zone_table.item(r, 1)
            old_powers[r] = item.text() if item else "0.5"

        zone_count_x = self._dled_zone_count_x.value()
        zone_count_y = self._dled_zone_count_y.value()
        new_count = zone_count_x * zone_count_y

        self._dled_zone_table.blockSignals(True)
        self._dled_zone_table.setRowCount(new_count)
        for idx in range(new_count):
            col = (idx % zone_count_x) + 1
            row = (idx // zone_count_x) + 1
            label = f"Z({row},{col})"
            power_val = old_powers.get(idx, "0.5")
            self._dled_zone_table.setItem(idx, 0, QTableWidgetItem(label))
            self._dled_zone_table.setItem(idx, 1, QTableWidgetItem(power_val))
        self._dled_zone_table.blockSignals(False)

    def _update_dled_pitch_labels(self) -> None:
        """Recompute and display auto-calculated pitch for DLED grid."""
        w = self.width_spin.value()   # mm
        h = self.height_spin.value()  # mm
        ol = self._dled_offset_left.value()
        or_ = self._dled_offset_right.value()
        ot = self._dled_offset_top.value()
        ob = self._dled_offset_bottom.value()
        cx = self._dled_count_x.value()
        cy = self._dled_count_y.value()

        usable_w = w - ol - or_
        usable_h = h - ot - ob
        pitch_x = usable_w / (cx - 1) if cx > 1 else 0.0
        pitch_y = usable_h / (cy - 1) if cy > 1 else 0.0
        self._dled_pitch_x_label.setText(f"{pitch_x:.2f}")
        self._dled_pitch_y_label.setText(f"{pitch_y:.2f}")

    def _on_eled_layer_target_changed(self, target: str) -> None:
        """Auto-configure edge_config and edge_offset when an edge layer is selected.

        For example, selecting 'LGP / FR4 (bottom)' sets:
        - edge_config = 'bottom'
        - edge_offset = distance from panel edge to the FR4/air interface
        """
        _layer, material, edge = self._parse_layer_target(target)
        if material is None or edge is None:
            return  # Plain layer selected, don't change config

        # Map edge name to edge_config combo value
        edge_to_config = {"bottom": "bottom", "top": "top", "left": "left/right", "right": "left/right"}
        config_text = edge_to_config.get(edge)
        if config_text:
            idx = self._eled_edge_config.findText(config_text)
            if idx >= 0:
                self._eled_edge_config.blockSignals(True)
                self._eled_edge_config.setCurrentIndex(idx)
                self._eled_edge_config.blockSignals(False)

        # Find the parent layer row and compute a physically useful offset.
        # For FR4 edge targets we place LEDs on the FR4/air interface so the
        # footprint overlaps both materials; other materials use their center.
        parent_layer = _layer
        parent_row = None
        for row in range(self.layers_table.rowCount()):
            item = self.layers_table.item(row, 0)
            if item and item.text().strip() == parent_layer:
                parent_row = row
                break
        if parent_row is None:
            return

        edge_data = self._layer_edge_layers.get(parent_row, {}).get(edge, [])
        offset_m = 0.0
        found = False
        placement_desc = "center"
        for idx, entry in enumerate(edge_data):
            t = entry.get("thickness", 0.0)
            if entry.get("material") == material and not found:
                next_entry = edge_data[idx + 1] if idx + 1 < len(edge_data) else None
                if material == "FR4" and next_entry is not None:
                    offset_m += t
                    placement_desc = f"{material}/{next_entry.get('material', 'next')} interface"
                else:
                    offset_m += t / 2.0
                found = True
                break
            offset_m += t

        if found:
            self._eled_edge_offset.blockSignals(True)
            self._eled_edge_offset.setValue(offset_m * 1000.0)  # m -> mm
            self._eled_edge_offset.blockSignals(False)
            self._update_eled_pitch_label()
            self.statusBar().showMessage(
                f"LEDs positioned at {placement_desc}: {offset_m * 1000:.1f} mm from {edge} edge",
                4000,
            )

    def _update_eled_pitch_label(self) -> None:
        """Recompute and display auto-calculated pitch for ELED edge strip."""
        w = self.width_spin.value()   # mm
        h = self.height_spin.value()  # mm
        count = self._eled_count.value()
        offset = self._eled_edge_offset.value()

        # Pitch along the longer relevant edge dimension
        edge_cfg = self._eled_edge_config.currentText().lower().replace("/", "_")
        if edge_cfg in ("bottom", "top"):
            usable = w - 2 * offset
        elif edge_cfg == "left_right":
            usable = h - 2 * offset
        else:  # "all"
            usable = w - 2 * offset  # show horizontal pitch
        pitch = usable / (count - 1) if count > 1 else 0.0
        self._eled_pitch_label.setText(f"{pitch:.2f}")

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
        row = table.rowCount() - 1
        # Set layer target combo for sources / LED arrays tables
        if table in (self.sources_table, self.led_arrays_table):
            table.setCellWidget(row, 1, self._make_layer_target_combo())
        if table is self.led_arrays_table:
            self._led_array_extras[row] = {}
        self._undo_stack.endMacro()

    def _remove_table_row(self, table: QTableWidget) -> None:
        """Remove selected row and revalidate to clear any stale error entries."""
        if table is self.layers_table:
            removed_row = table.currentRow()
        elif table is self.led_arrays_table:
            removed_row = table.currentRow()
        else:
            removed_row = -1
        TableDataParser.remove_selected_row(self, table)
        self._revalidate_table(table)
        if table is self.led_arrays_table and removed_row >= 0:
            self._led_array_extras = self._shift_row_store_after_remove(
                self._led_array_extras, removed_row
            )
        if table is self.layers_table:
            self._update_node_count_label()
            # Shift _layer_zones keys: remove the deleted row, shift remaining keys down
            if removed_row >= 0:
                new_zones: dict[int, list] = {}
                for key, val in self._layer_zones.items():
                    if key < removed_row:
                        new_zones[key] = val
                    elif key > removed_row:
                        new_zones[key - 1] = val
                    # key == removed_row is dropped
                self._layer_zones = new_zones
                # Also shift _layer_edge_layers keys
                new_edge_layers: dict[int, dict] = {}
                for key, val in self._layer_edge_layers.items():
                    if key < removed_row:
                        new_edge_layers[key] = val
                    elif key > removed_row:
                        new_edge_layers[key - 1] = val
                self._layer_edge_layers = new_edge_layers
            # Hide zone panel and edge panel if the selected layer was removed
            self._zone_panel.setVisible(False)
            self._edge_layer_panel.setVisible(False)
            self._refresh_3d_preview()

    @staticmethod
    def _shift_row_store_after_remove(store: dict[int, dict], removed_row: int) -> dict[int, dict]:
        """Drop one row entry from a row-indexed store and shift later rows down."""
        shifted: dict[int, dict] = {}
        for key, value in store.items():
            if key < removed_row:
                shifted[key] = value
            elif key > removed_row:
                shifted[key - 1] = value
        return shifted

    @staticmethod
    def _led_array_extra_from_model(array) -> dict:
        """Capture non-table LED-array fields so non-custom arrays round-trip through the UI."""
        return {
            "mode": array.mode,
            "offset_top": array.offset_top,
            "offset_bottom": array.offset_bottom,
            "offset_left": array.offset_left,
            "offset_right": array.offset_right,
            "zone_count_x": array.zone_count_x,
            "zone_count_y": array.zone_count_y,
            "zone_powers": list(array.zone_powers),
            "edge_config": array.edge_config,
            "edge_offset": array.edge_offset,
            "panel_width": array.panel_width,
            "panel_height": array.panel_height,
            "z_position": array.z_position,
        }

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
        base = f"Display Thermal Simulator v{APP_VERSION}"
        if self.current_project_path:
            base = f"{self.current_project_path.name} - Display Thermal Simulator v{APP_VERSION}"
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

        # Edge frame controls — restore last-used values
        ef = getattr(project, "edge_frame", None)
        if ef is not None:
            self._ef_metal_spin.setValue(ef.metal_thickness * 1000.0)
            self._ef_air_spin.setValue(ef.air_gap_thickness * 1000.0)

        TableDataParser.populate_tables_from_project(project, self._tables_dict)
        TableDataParser.set_boundary_widgets(self.top_boundary_widgets, project.boundaries.top)
        TableDataParser.set_boundary_widgets(self.bottom_boundary_widgets, project.boundaries.bottom)
        TableDataParser.set_boundary_widgets(self.side_boundary_widgets, project.boundaries.side)

        # Populate nz spinboxes for each layer row (column 4)
        for row, layer in enumerate(project.layers):
            self._set_layer_nz_spinbox(row, layer.nz)

        # Populate zone data per layer from loaded project
        self._layer_zones = {}
        for row, layer in enumerate(project.layers):
            if layer.zones:
                self._layer_zones[row] = [
                    {
                        "material": z.material,
                        "x": z.x,
                        "y": z.y,
                        "width": z.width,
                        "height": z.height,
                    }
                    for z in layer.zones
                ]
        # Refresh zone panel if a layer row is currently selected
        self._zone_panel.setVisible(False)

        # Populate edge layer data per layer from loaded project
        self._layer_edge_layers = {}
        for row, layer in enumerate(project.layers):
            edge_layers = getattr(layer, "edge_layers", {})
            if edge_layers:
                self._layer_edge_layers[row] = {
                    edge: [{"material": el.material, "thickness": el.thickness} for el in els]
                    for edge, els in edge_layers.items()
                }
        self._edge_layer_panel.setVisible(False)
        self._led_array_extras = {
            row: self._led_array_extra_from_model(array)
            for row, array in enumerate(project.led_arrays)
        }
        self._restore_material_sources(project)

        self._refresh_layer_choices(project)
        self._refresh_profile_choices(project)

        # Replace Layer column text with combo boxes in sources and LED arrays tables
        for table in (self.sources_table, self.led_arrays_table):
            for row in range(table.rowCount()):
                item = table.item(row, 1)
                layer_text = item.text().strip() if item else ""
                table.setCellWidget(row, 1, self._make_layer_target_combo(layer_text))

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

        arch = self._infer_architecture(project)
        self.arch_combo.blockSignals(True)
        self.arch_combo.setCurrentText(arch)
        self.arch_combo.blockSignals(False)
        self._led_arrays_stack.setCurrentIndex({"Custom": 0, "DLED": 1, "ELED": 2}.get(arch, 0))
        self._restore_arch_panel_from_project(project, arch)

        self._undo_stack.clear()
        self._undo_stack.setClean()
        self._update_title()
        self._update_path_label()
        self._update_node_count_label()

        # Refresh 3D preview if the dock is visible
        self._refresh_3d_preview()

    def _restore_material_sources(self, project: DisplayProject) -> None:
        """Restore material source labels in the materials table."""
        builtin = load_builtin_library()
        self._material_source = {}
        for row, mat in enumerate(project.materials.values()):
            src = "User"
            builtin_mat = builtin.get(mat.name)
            if builtin_mat is not None and builtin_mat.to_dict() == mat.to_dict():
                src = "Built-in"
            self._material_source[mat.name] = src
            type_item = self.materials_table.item(row, 6)
            if type_item is not None:
                type_item.setText(src)

    @staticmethod
    def _infer_architecture(project: DisplayProject) -> str:
        """Infer the active architecture from the loaded project contents."""
        if len(project.led_arrays) == 1:
            arr = project.led_arrays[0]
            if arr.mode == "edge" and any(layer.name == "LGP" for layer in project.layers):
                return "ELED"
            if arr.mode == "grid" and any(layer.name == "LED Board" for layer in project.layers):
                return "DLED"
        return "Custom"

    def _restore_arch_panel_from_project(self, project: DisplayProject, arch: str) -> None:
        """Seed DLED/ELED controls from a loaded project without reapplying a template."""
        if not project.led_arrays:
            return
        la = project.led_arrays[0]
        if arch == "DLED":
            self._dled_count_x.blockSignals(True)
            self._dled_count_x.setValue(la.count_x)
            self._dled_count_x.blockSignals(False)
            self._dled_count_y.blockSignals(True)
            self._dled_count_y.setValue(la.count_y)
            self._dled_count_y.blockSignals(False)
            self._dled_power.blockSignals(True)
            self._dled_power.setValue(la.power_per_led_w)
            self._dled_power.blockSignals(False)
            self._dled_offset_top.setValue(la.offset_top * 1000.0)
            self._dled_offset_bottom.setValue(la.offset_bottom * 1000.0)
            self._dled_offset_left.setValue(la.offset_left * 1000.0)
            self._dled_offset_right.setValue(la.offset_right * 1000.0)
            self._dled_zone_count_x.setValue(la.zone_count_x)
            self._dled_zone_count_y.setValue(la.zone_count_y)
            self._rebuild_zone_table()
            self._update_dled_pitch_labels()
            if la.footprint_shape:
                idx = self._dled_footprint_shape.findText(la.footprint_shape)
                if idx >= 0:
                    self._dled_footprint_shape.setCurrentIndex(idx)
            if la.led_width is not None:
                self._dled_led_width.setValue(la.led_width * 1000.0)
            if la.led_height is not None:
                self._dled_led_height.setValue(la.led_height * 1000.0)
            if la.led_radius is not None:
                self._dled_led_radius.setValue(la.led_radius * 1000.0)
        elif arch == "ELED":
            edge_text = la.edge_config.replace("_", "/")
            idx = self._eled_edge_config.findText(edge_text)
            if idx < 0:
                idx = self._eled_edge_config.findText(la.edge_config)
            if idx >= 0:
                self._eled_edge_config.blockSignals(True)
                self._eled_edge_config.setCurrentIndex(idx)
                self._eled_edge_config.blockSignals(False)
            self._eled_count.blockSignals(True)
            self._eled_count.setValue(la.count_x if la.edge_config in ("bottom", "top", "all") else la.count_y)
            self._eled_count.blockSignals(False)
            self._eled_power.blockSignals(True)
            self._eled_power.setValue(la.power_per_led_w)
            self._eled_power.blockSignals(False)
            if la.footprint_shape:
                idx = self._eled_footprint_shape.findText(la.footprint_shape)
                if idx >= 0:
                    self._eled_footprint_shape.setCurrentIndex(idx)
            if la.led_width is not None:
                self._eled_led_width.setValue(la.led_width * 1000.0)
            if la.led_height is not None:
                self._eled_led_height.setValue(la.led_height * 1000.0)
            if la.led_radius is not None:
                self._eled_led_radius.setValue(la.led_radius * 1000.0)
            preferred_target = self._preferred_eled_layer_target()
            target = preferred_target if self._eled_layer_combo.findText(preferred_target) >= 0 else la.layer
            idx = self._eled_layer_combo.findText(target)
            if idx >= 0:
                self._eled_layer_combo.setCurrentIndex(idx)
            self._eled_edge_offset.blockSignals(True)
            self._eled_edge_offset.setValue(la.edge_offset * 1000.0)
            self._eled_edge_offset.blockSignals(False)
            self._update_eled_pitch_label()

    def _set_layer_nz_spinbox(self, row: int, nz: int = 1) -> None:
        """Create and install an nz QSpinBox cell widget for the given layers_table row."""
        nz_spin = QSpinBox()
        nz_spin.setRange(1, 50)
        nz_spin.setValue(nz)
        nz_spin.valueChanged.connect(self._update_node_count_label)
        self.layers_table.setCellWidget(row, 4, nz_spin)

    def _add_layer_row(self) -> None:
        """Add a new row to the layers table with a fresh nz QSpinBox (default 1)."""
        self._undo_stack.beginMacro("Add row")
        TableDataParser._add_table_row(self.layers_table)
        row = self.layers_table.rowCount() - 1
        self._set_layer_nz_spinbox(row, nz=1)
        self._layer_zones[row] = []
        self._layer_edge_layers[row] = {}
        self._undo_stack.endMacro()
        self._update_node_count_label()
        self._refresh_3d_preview()

    def _move_layer_up(self) -> None:
        """Move the selected layer row up (swap with the row above)."""
        row = self.layers_table.currentRow()
        if row <= 0:
            return
        self._swap_layer_rows(row, row - 1)
        self.layers_table.setCurrentCell(row - 1, 0)

    def _move_layer_down(self) -> None:
        """Move the selected layer row down (swap with the row below)."""
        row = self.layers_table.currentRow()
        if row < 0 or row >= self.layers_table.rowCount() - 1:
            return
        self._swap_layer_rows(row, row + 1)
        self.layers_table.setCurrentCell(row + 1, 0)

    def _swap_layer_rows(self, row_a: int, row_b: int) -> None:
        """Swap two rows in the layers table, including nz spinboxes, zones, and edge layers."""
        table = self.layers_table
        table.blockSignals(True)

        # Swap cell text for columns 0-3
        for col in range(4):
            item_a = table.item(row_a, col)
            item_b = table.item(row_b, col)
            text_a = item_a.text() if item_a else ""
            text_b = item_b.text() if item_b else ""
            table.setItem(row_a, col, QTableWidgetItem(text_b))
            table.setItem(row_b, col, QTableWidgetItem(text_a))

        # Swap nz spinbox values (column 4)
        nz_a = table.cellWidget(row_a, 4)
        nz_b = table.cellWidget(row_b, 4)
        val_a = nz_a.value() if nz_a else 1
        val_b = nz_b.value() if nz_b else 1
        if nz_a:
            nz_a.setValue(val_b)
        if nz_b:
            nz_b.setValue(val_a)

        # Swap zone data
        zones_a = self._layer_zones.get(row_a, [])
        zones_b = self._layer_zones.get(row_b, [])
        self._layer_zones[row_a] = zones_b
        self._layer_zones[row_b] = zones_a

        # Swap edge layer data
        edge_a = self._layer_edge_layers.get(row_a, {})
        edge_b = self._layer_edge_layers.get(row_b, {})
        self._layer_edge_layers[row_a] = edge_b
        self._layer_edge_layers[row_b] = edge_a

        table.blockSignals(False)
        self._refresh_3d_preview()

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
            self._led_array_extras = {}
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
        self._cancel_action.setEnabled(self._sim_mode != "steady")
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._solver_label.setText("Running\u2026")

    def _on_run_ended(self) -> None:
        """Re-enable Run action and hide progress bar when a simulation ends."""
        self._cancel_action.setEnabled(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        # Use _update_validation_status so run stays disabled when errors exist
        self._update_validation_status()

    def _on_progress(self, percent: int, message: str) -> None:
        """Update progress bar and center label from worker progress signal.

        A percent of -1 switches the bar to indeterminate (pulsing) mode,
        used for steady-state where the solve duration is unknown.
        """
        if percent < 0:
            self._progress_bar.setRange(0, 0)  # indeterminate pulsing
        else:
            self._progress_bar.setRange(0, 100)
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

        # Warn before solving when node count exceeds 300k
        node_count = sum(layer.nz for layer in project.layers) * project.mesh.nx * project.mesh.ny
        if node_count > 300_000:
            reply = QMessageBox.warning(
                self,
                "Large Model Warning",
                f"The model has {node_count:,} nodes (>300k). Large models may take significantly"
                " longer to solve.\n\nProceed anyway?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
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

        # Refresh combo with z-sublayer entries derived from result's nz metadata
        self._refresh_layer_choices(project, result=result)

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

        # Update 3D temperature overlay if dock is visible
        if self._3d_dock is not None and self._3d_dock.isVisible():
            try:
                self._3d_widget.update_temperature(project, result)
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).debug("3D temperature overlay failed: %s", exc)

    def _on_sim_error(self, message: str) -> None:
        self._solver_label.setText("Error")
        self._show_error("Simulation failed", message)

    # ------------------------------------------------------------------
    # 3D Assembly Preview
    # ------------------------------------------------------------------

    def _toggle_3d_preview(self, checked: bool) -> None:
        """Toggle the 3D assembly dock panel on/off."""
        if self._3d_dock is None:
            if not checked:
                return
            self._create_3d_dock()
            if self._3d_dock is None:
                # Failed to create (e.g. pyvista not installed)
                self._3d_preview_action.setChecked(False)
                return
            self._refresh_3d_preview()
        else:
            self._3d_dock.setVisible(checked)

    def _create_3d_dock(self) -> None:
        """Create the 3D assembly dock widget (lazy-loaded on first use)."""
        try:
            from thermal_sim.ui.assembly_3d import Assembly3DWidget
        except ImportError:
            QMessageBox.information(
                self,
                "3D Preview Unavailable",
                "Install pyvista and pyvistaqt to enable 3D preview:\n"
                "pip install pyvista pyvistaqt qtpy",
            )
            return

        self._3d_widget = Assembly3DWidget(self)
        self._3d_dock = QDockWidget("3D Assembly", self)
        self._3d_dock.setObjectName("Assembly3DDock")
        self._3d_dock.setWidget(self._3d_widget)
        self._3d_dock.visibilityChanged.connect(self._on_3d_dock_visibility_changed)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._3d_dock)
        self.tabifyDockWidget(self._plots_dock, self._3d_dock)

    def _on_3d_dock_visibility_changed(self, visible: bool) -> None:
        """Update the action check state when the dock is closed."""
        self._3d_preview_action.setChecked(visible)

    def _refresh_3d_preview(self) -> None:
        """Update the 3D view from the current project state."""
        if self._3d_dock is None or not self._3d_dock.isVisible():
            return
        try:
            project = self._build_project_from_ui()
            self._3d_widget.update_assembly(project)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).debug("3D preview refresh failed: %s", exc)

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

        # Collect layer zones for PDF/comparison overlay
        layer_zones = {
            layer.name: list(layer.zones)
            for layer in project.layers
            if layer.zones
        }

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
            layer_zones=layer_zones,
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
        combo_text = self.map_layer_combo.currentText()
        # Extract the physical layer name (strip z-suffix if present)
        layer_name = combo_text.split(" (z=")[0] if " (z=" in combo_text else combo_text

        # Use userData as flat z-index when available, else fall back to layer_names lookup
        flat_z_idx = self.map_layer_combo.currentData()
        if flat_z_idx is None:
            flat_z_idx = (
                layer_names.index(layer_name) if layer_name in layer_names else len(layer_names) - 1
            )
        if flat_z_idx < 0 or flat_z_idx >= final_map_c.shape[0]:
            flat_z_idx = final_map_c.shape[0] - 1

        width_m = self.width_spin.value() / 1000.0
        height_m = self.height_spin.value() / 1000.0
        data = final_map_c[flat_z_idx]

        # Compute per-layer hotspots (top 3) for annotation.
        result = self.last_steady_result or self.last_transient_result
        if result is not None:
            per_layer_hotspots = top_n_hottest_cells_for_layer(
                final_map_c, flat_z_idx, layer_name, result.dx, result.dy, n=3
            )
        else:
            per_layer_hotspots = None

        # Collect probes on this layer.
        layer_probes = [
            p for p in (self.last_project.probes if self.last_project else [])
            if p.layer == layer_name
        ]

        # Collect zones for the current physical layer.
        current_zones = None
        if self.last_project:
            for layer in self.last_project.layers:
                if layer.name == layer_name:
                    current_zones = layer.zones if layer.zones else None
                    break

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
            title=f"Temperature Map - {combo_text}",
            hotspots=per_layer_hotspots,
            probes=layer_probes if layer_probes else None,
            selected_hotspot_rank=self._selected_hotspot_rank,
            zones=current_zones,
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
        # For multi-nz results the combo has entries like "LayerName (z=1/5)".
        # Find the first entry whose text starts with the target layer name.
        target_idx = -1
        for i in range(self.map_layer_combo.count()):
            entry = self.map_layer_combo.itemText(i)
            base = entry.split(" (z=")[0]
            if base == layer_name:
                target_idx = i
                break
        if target_idx >= 0:
            self.map_layer_combo.setCurrentIndex(target_idx)
        else:
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

    def _refresh_layer_choices(self, project: DisplayProject, result=None) -> None:
        """Populate the map layer combo.

        When *result* is None or has all nz=1, adds one item per layer (plain name).
        When *result* has nz_per_layer with any value > 1, adds one item per z-sublayer
        using userData to carry the flat z-index into the result temperature array.
        """
        current = self.map_layer_combo.currentText()
        self.map_layer_combo.blockSignals(True)
        self.map_layer_combo.clear()

        has_nz_result = (
            result is not None
            and hasattr(result, "nz_per_layer")
            and result.nz_per_layer is not None
            and any(nz > 1 for nz in result.nz_per_layer)
        )

        if has_nz_result:
            for layer_idx, layer in enumerate(project.layers):
                nz = result.nz_per_layer[layer_idx]
                z_offset = result.z_offsets[layer_idx]
                if nz == 1:
                    self.map_layer_combo.addItem(layer.name, userData=z_offset)
                else:
                    for z in range(nz):
                        self.map_layer_combo.addItem(
                            f"{layer.name} (z={z + 1}/{nz})", userData=z_offset + z
                        )
        else:
            for layer_idx, layer in enumerate(project.layers):
                self.map_layer_combo.addItem(layer.name, userData=layer_idx)

        self.map_layer_combo.blockSignals(False)

        # Restore previous selection by text, else select last item
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

    def _update_node_count_label(self) -> None:
        """Recompute and display the total node count in the status bar."""
        total_nz = 0
        for row in range(self.layers_table.rowCount()):
            nz_spin = self.layers_table.cellWidget(row, 4)
            total_nz += nz_spin.value() if nz_spin is not None else 1
        nx = self.nx_spin.value()
        ny = self.ny_spin.value()
        count = total_nz * nx * ny
        if count > 300_000:
            self._node_count_label.setText(f"Nodes: {count:,} \u26a0")
            self._node_count_label.setStyleSheet("color: #ff6b6b;")
        else:
            self._node_count_label.setText(f"Nodes: {count:,}")
            self._node_count_label.setStyleSheet("")

    def _fill_probe_table(self, probe_values: dict[str, float]) -> None:
        self._plot_manager.fill_probe_table(self.probe_table, probe_values)

    # ------------------------------------------------------------------
    # Zone editor helpers (Layers tab)
    # ------------------------------------------------------------------

    def _on_layer_selected_for_zones(self) -> None:
        """Show/hide zone panel and edge layer panel when a layer row is selected."""
        row = self.layers_table.currentRow()
        if row < 0:
            self._zone_panel.setVisible(False)
            self._edge_layer_panel.setVisible(False)
            return
        self._zone_panel.setVisible(True)
        self._populate_zone_table(row)
        self._refresh_zone_preview(row)
        self._edge_layer_panel.setVisible(True)
        self._populate_edge_table(row, self._current_edge)

    def _populate_zone_table(self, layer_row: int) -> None:
        """Load zone data for *layer_row* into the zone sub-table (display in mm)."""
        self._updating_zones = True
        self._zone_table.blockSignals(True)
        self._zone_table.setRowCount(0)
        zones = self._layer_zones.get(layer_row, [])
        for z in zones:
            r = self._zone_table.rowCount()
            self._zone_table.insertRow(r)
            # Material combo
            mat_combo = self._make_zone_material_combo(z.get("material", ""))
            self._zone_table.setCellWidget(r, 0, mat_combo)
            # Coordinates in mm (stored as SI metres)
            x_start_mm = z["x"] * 1000.0
            x_end_mm = (z["x"] + z["width"]) * 1000.0
            y_start_mm = z["y"] * 1000.0
            y_end_mm = (z["y"] + z["height"]) * 1000.0
            for col, val in enumerate([x_start_mm, x_end_mm, y_start_mm, y_end_mm], start=1):
                self._zone_table.setItem(r, col, QTableWidgetItem(f"{val:.3f}"))
        self._zone_table.blockSignals(False)
        self._updating_zones = False

    def _make_zone_material_combo(self, current_material: str = "") -> QComboBox:
        """Create a QComboBox populated with current project material names."""
        combo = QComboBox()
        # Collect material names from materials_table
        for row in range(self.materials_table.rowCount()):
            name = TableDataParser._cell_text(self.materials_table, row, 0)
            if name:
                combo.addItem(name)
        # Select current or first
        idx = combo.findText(current_material)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        # Wire change to zone table update
        combo.currentTextChanged.connect(self._on_zone_combo_changed)
        return combo

    def _on_zone_combo_changed(self) -> None:
        """Handle material combo change in zone table — save and refresh preview."""
        if self._updating_zones:
            return
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        self._read_zone_table_into_store(layer_row)
        self._refresh_zone_preview(layer_row)

    def _on_zone_table_changed(self, row: int, col: int) -> None:  # noqa: ARG002
        """Handle coordinate cell edits in the zone table."""
        if self._updating_zones:
            return
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        self._read_zone_table_into_store(layer_row)
        self._refresh_zone_preview(layer_row)

    def _read_zone_table_into_store(self, layer_row: int) -> None:
        """Read all zone table rows and persist them into _layer_zones (SI metres)."""
        zones = []
        for r in range(self._zone_table.rowCount()):
            mat_combo = self._zone_table.cellWidget(r, 0)
            material = mat_combo.currentText() if mat_combo else ""
            try:
                x_start_mm = float((self._zone_table.item(r, 1) or QTableWidgetItem("0")).text())
                x_end_mm = float((self._zone_table.item(r, 2) or QTableWidgetItem("10")).text())
                y_start_mm = float((self._zone_table.item(r, 3) or QTableWidgetItem("0")).text())
                y_end_mm = float((self._zone_table.item(r, 4) or QTableWidgetItem("10")).text())
            except ValueError:
                continue
            x_m = x_start_mm / 1000.0
            width_m = max((x_end_mm - x_start_mm) / 1000.0, 1e-6)
            y_m = y_start_mm / 1000.0
            height_m = max((y_end_mm - y_start_mm) / 1000.0, 1e-6)
            zones.append({
                "material": material,
                "x": x_m,
                "y": y_m,
                "width": width_m,
                "height": height_m,
            })
        self._layer_zones[layer_row] = zones

    def _add_zone_row(self) -> None:
        """Insert a new zone row with default values spanning the full panel."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        # Default zone: full panel extent
        w_mm = self.width_spin.value()
        h_mm = self.height_spin.value()
        # Pick first available material
        default_mat = ""
        if self.materials_table.rowCount() > 0:
            default_mat = TableDataParser._cell_text(self.materials_table, 0, 0) or ""
        new_zone = {
            "material": default_mat,
            "x": 0.0,
            "y": 0.0,
            "width": w_mm / 1000.0,
            "height": h_mm / 1000.0,
        }
        existing = self._layer_zones.get(layer_row, [])
        existing.append(new_zone)
        self._layer_zones[layer_row] = existing
        self._populate_zone_table(layer_row)
        self._refresh_zone_preview(layer_row)

    def _remove_zone_row(self) -> None:
        """Remove the selected zone row."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        zone_row = self._zone_table.currentRow()
        if zone_row < 0:
            return
        zones = self._layer_zones.get(layer_row, [])
        if zone_row < len(zones):
            zones.pop(zone_row)
            self._layer_zones[layer_row] = zones
        self._populate_zone_table(layer_row)
        self._refresh_zone_preview(layer_row)

    def _refresh_zone_preview(self, layer_row: int) -> None:
        """Redraw the zone preview canvas showing rectangles on the layer footprint."""
        from matplotlib.patches import Rectangle as MplRectangle
        w_mm = self.width_spin.value()
        h_mm = self.height_spin.value()
        ax = self._zone_preview_canvas.axes
        ax.clear()
        # Draw layer footprint
        ax.add_patch(MplRectangle(
            (0, 0), w_mm, h_mm,
            linewidth=1.0, edgecolor="#888888", facecolor="#2a2a2a",
        ))
        # Draw zones
        zones = self._layer_zones.get(layer_row, [])
        colors = ["#4fc3f7", "#ffb74d", "#a5d6a7", "#f48fb1", "#ce93d8"]
        for i, z in enumerate(zones):
            x_mm = z["x"] * 1000.0
            y_mm = z["y"] * 1000.0
            w_zone = z["width"] * 1000.0
            h_zone = z["height"] * 1000.0
            color = colors[i % len(colors)]
            ax.add_patch(MplRectangle(
                (x_mm, y_mm), w_zone, h_zone,
                linewidth=1.2, edgecolor="white",
                linestyle="--", facecolor=color, alpha=0.35,
            ))
            ax.text(
                x_mm + 0.5, y_mm + 0.5,
                z.get("material", ""),
                fontsize=7, color="white",
                va="bottom", ha="left",
            )
        ax.set_xlim(0, max(w_mm, 1))
        ax.set_ylim(0, max(h_mm, 1))
        ax.set_xlabel("x [mm]", fontsize=7)
        ax.set_ylabel("y [mm]", fontsize=7)
        ax.set_title("Zone Preview", fontsize=8)
        ax.tick_params(labelsize=6)
        self._zone_preview_canvas.figure.tight_layout()
        self._zone_preview_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Edge layer UI helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Layer target choices (main layers + edge layers)
    # ------------------------------------------------------------------

    def _get_layer_target_choices(self) -> list[str]:
        """Return layer names including edge layer entries like 'LGP / FR4 (bottom)'."""
        choices: list[str] = []
        for row in range(self.layers_table.rowCount()):
            name_item = self.layers_table.item(row, 0)
            layer_name = name_item.text().strip() if name_item else ""
            if not layer_name:
                continue
            choices.append(layer_name)
            edge_data = self._layer_edge_layers.get(row, {})
            for edge, entries in edge_data.items():
                for entry in entries:
                    mat = entry.get("material", "")
                    if mat:
                        choice = f"{layer_name} / {mat} ({edge})"
                        if choice not in choices:
                            choices.append(choice)
        return choices

    @staticmethod
    def _resolve_layer_target(target: str) -> str:
        """Resolve 'LGP / FR4 (bottom)' to parent layer name 'LGP'."""
        if " / " in target and "(" in target:
            return target.split(" / ", 1)[0].strip()
        return target

    @staticmethod
    def _parse_layer_target(target: str):
        """Parse 'LGP / FR4 (bottom)' -> (layer, material, edge) or (layer, None, None)."""
        if " / " in target and "(" in target:
            layer_name = target.split(" / ", 1)[0].strip()
            rest = target.split(" / ", 1)[1]
            paren_idx = rest.index(" (")
            material = rest[:paren_idx]
            edge = rest[paren_idx + 2:-1]
            return layer_name, material, edge
        return target, None, None

    def _make_layer_target_combo(self, current: str = "") -> QComboBox:
        """Create a QComboBox populated with layer target choices."""
        combo = QComboBox()
        choices = self._get_layer_target_choices()
        combo.addItems(choices)
        if current:
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                # Allow freeform text if not in choices
                combo.setEditable(True)
                combo.setCurrentText(current)
        combo.setToolTip(
            "Target layer for this source. Edge layer entries (e.g. 'LGP / FR4 (bottom)') "
            "resolve to the parent layer — position your source in the edge zone region."
        )
        return combo

    def _refresh_layer_target_combos(self) -> None:
        """Update all layer target combo boxes in sources, LED arrays, and ELED panel."""
        choices = self._get_layer_target_choices()
        for table in (self.sources_table, self.led_arrays_table):
            for row in range(table.rowCount()):
                combo = table.cellWidget(row, 1)
                if combo is not None and isinstance(combo, QComboBox):
                    current = combo.currentText()
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(choices)
                    idx = combo.findText(current)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setEditable(True)
                        combo.setCurrentText(current)
                    combo.blockSignals(False)
        # Also refresh the ELED panel layer combo
        if hasattr(self, "_eled_layer_combo"):
            current = self._eled_layer_combo.currentText()
            self._eled_layer_combo.blockSignals(True)
            self._eled_layer_combo.clear()
            self._eled_layer_combo.addItems(choices)
            idx = self._eled_layer_combo.findText(current)
            if idx >= 0:
                self._eled_layer_combo.setCurrentIndex(idx)
            elif choices:
                # Default to LGP if available
                lgp_idx = self._eled_layer_combo.findText("LGP")
                if lgp_idx >= 0:
                    self._eled_layer_combo.setCurrentIndex(lgp_idx)
            self._eled_layer_combo.blockSignals(False)

    def _apply_edge_frame(self) -> None:
        """Apply edge structures to the current stack.

        For generic stacks this is a uniform Steel + Air Gap perimeter.
        For ELED stacks, the LGP layer gets a dedicated LED edge path:
        Steel -> FR4 -> Air Gap on LED-carrying edges and Steel -> Air Gap
        on the remaining edges.
        """
        mt = self._ef_metal_spin.value() / 1000.0  # mm -> m
        at = self._ef_air_spin.value() / 1000.0
        n_layers = self.layers_table.rowCount()
        if n_layers == 0:
            return

        arch = self.arch_combo.currentText()
        self._layer_edge_layers = {row: {} for row in range(n_layers)}

        if arch == "ELED":
            edge_cfg = self._eled_edge_config.currentText().lower().replace("/", "_")
            led_edges_map = {
                "bottom": {"bottom"},
                "top": {"top"},
                "left_right": {"left", "right"},
                "all": {"bottom", "top", "left", "right"},
            }
            led_edges = led_edges_map.get(edge_cfg, {"bottom"})
            frame_only = [
                {"material": "Steel", "thickness": mt},
                {"material": "Air Gap", "thickness": at},
            ]
            led_path = [
                {"material": "Steel", "thickness": mt},
                {"material": "FR4", "thickness": 0.005},
                {"material": "Air Gap", "thickness": at},
            ]
            for row in range(n_layers):
                self._layer_edge_layers[row] = {
                    edge: [dict(e) for e in frame_only]
                    for edge in ("bottom", "top", "left", "right")
                }
            lgp_row = self._find_layer_row("LGP")
            if lgp_row >= 0:
                self._layer_edge_layers[lgp_row] = {
                    edge: [dict(e) for e in (led_path if edge in led_edges else frame_only)]
                    for edge in ("bottom", "top", "left", "right")
                }
            self._ensure_material_rows(("Steel", "Air Gap", "FR4"))
        else:
            uniform = {
                edge: [
                    {"material": "Steel", "thickness": mt},
                    {"material": "Air Gap", "thickness": at},
                ]
                for edge in ("bottom", "top", "left", "right")
            }
            for row in range(n_layers):
                self._layer_edge_layers[row] = {
                    edge: [dict(e) for e in entries]
                    for edge, entries in uniform.items()
                }
            self._ensure_material_rows(("Steel", "Air Gap"))

        # Refresh edge panel if visible
        layer_row = self.layers_table.currentRow()
        if layer_row >= 0 and self._edge_layer_panel.isVisible():
            edge = self._current_edge if hasattr(self, "_current_edge") else "bottom"
            self._populate_edge_table(layer_row, edge)
        # Refresh layer target combos so edge layers appear as choices
        self._refresh_layer_target_combos()
        if arch == "ELED":
            preferred_target = self._preferred_eled_layer_target()
            if preferred_target:
                idx = self._eled_layer_combo.findText(preferred_target)
                if idx >= 0:
                    self._eled_layer_combo.setCurrentIndex(idx)
        self.statusBar().showMessage(
            f"Edge structure applied ({arch}): Steel {self._ef_metal_spin.value():.1f} mm + "
            f"Air Gap {self._ef_air_spin.value():.1f} mm",
            4000,
        )

    def _find_layer_row(self, layer_name: str) -> int:
        """Return the row index for a named layer, or -1 if not present."""
        for row in range(self.layers_table.rowCount()):
            item = self.layers_table.item(row, 0)
            if item and item.text().strip() == layer_name:
                return row
        return -1

    def _preferred_eled_layer_target(self) -> str:
        """Return the preferred ELED target entry for the current edge config."""
        edge_cfg = self._eled_edge_config.currentText().lower().replace("/", "_")
        preferred_edge = {
            "bottom": "bottom",
            "top": "top",
            "left_right": "left",
            "all": "bottom",
        }.get(edge_cfg, "bottom")
        return f"LGP / FR4 ({preferred_edge})"

    def _ensure_material_rows(self, material_names: tuple[str, ...]) -> None:
        """Add missing materials from the builtin library to the materials table."""
        from thermal_sim.core.material_library import load_builtin_library

        builtin = load_builtin_library()
        existing = set()
        for row in range(self.materials_table.rowCount()):
            item = self.materials_table.item(row, 0)
            if item:
                existing.add(item.text())
        for mat_name in material_names:
            if mat_name not in existing and mat_name in builtin:
                mat = builtin[mat_name]
                r = self.materials_table.rowCount()
                self.materials_table.insertRow(r)
                self.materials_table.setItem(r, 0, QTableWidgetItem(mat_name))
                self.materials_table.setItem(r, 1, QTableWidgetItem(str(mat.k_in_plane)))
                self.materials_table.setItem(r, 2, QTableWidgetItem(str(mat.k_through)))
                self.materials_table.setItem(r, 3, QTableWidgetItem(str(mat.density)))
                self.materials_table.setItem(r, 4, QTableWidgetItem(str(mat.specific_heat)))
                self.materials_table.setItem(r, 5, QTableWidgetItem(str(mat.emissivity)))

    def _on_edge_tab_clicked(self, edge: str) -> None:
        """Switch to the clicked edge tab and repopulate the edge table."""
        for name, btn in self._edge_buttons.items():
            btn.setChecked(name == edge)
        self._current_edge = edge
        layer_row = self.layers_table.currentRow()
        if layer_row >= 0:
            self._populate_edge_table(layer_row, edge)

    def _populate_edge_table(self, layer_row: int, edge: str) -> None:
        """Load edge layer data for *layer_row*/*edge* into the edge sub-table."""
        self._updating_edge_layers = True
        self._edge_table.blockSignals(True)
        self._edge_table.setRowCount(0)
        entries = self._layer_edge_layers.get(layer_row, {}).get(edge, [])
        for entry in entries:
            r = self._edge_table.rowCount()
            self._edge_table.insertRow(r)
            mat_combo = self._make_edge_material_combo(entry.get("material", ""))
            self._edge_table.setCellWidget(r, 0, mat_combo)
            t_mm = entry.get("thickness", 0.003) * 1000.0
            self._edge_table.setItem(r, 1, QTableWidgetItem(f"{t_mm:.3f}"))
        self._edge_table.blockSignals(False)
        self._updating_edge_layers = False

    def _make_edge_material_combo(self, current_material: str = "") -> QComboBox:
        """Create a QComboBox for edge layer material selection."""
        combo = QComboBox()
        for row in range(self.materials_table.rowCount()):
            name = TableDataParser._cell_text(self.materials_table, row, 0)
            if name:
                combo.addItem(name)
        idx = combo.findText(current_material)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(self._on_edge_combo_changed)
        return combo

    def _on_edge_combo_changed(self) -> None:
        """Handle material combo change in edge layer table."""
        if self._updating_edge_layers:
            return
        layer_row = self.layers_table.currentRow()
        if layer_row >= 0:
            self._read_edge_table_into_store(layer_row)

    def _on_edge_table_changed(self, row: int, col: int) -> None:  # noqa: ARG002
        """Handle thickness cell edits in the edge layer table."""
        if self._updating_edge_layers:
            return
        layer_row = self.layers_table.currentRow()
        if layer_row >= 0:
            self._read_edge_table_into_store(layer_row)
            self._refresh_layer_target_combos()

    def _read_edge_table_into_store(self, layer_row: int) -> None:
        """Read all edge table rows and persist them into _layer_edge_layers (SI metres)."""
        entries = []
        for r in range(self._edge_table.rowCount()):
            mat_combo = self._edge_table.cellWidget(r, 0)
            material = mat_combo.currentText() if mat_combo else "Steel"
            try:
                t_mm = float((self._edge_table.item(r, 1) or QTableWidgetItem("3.0")).text())
            except ValueError:
                t_mm = 3.0
            entries.append({"material": material, "thickness": t_mm / 1000.0})
        if layer_row not in self._layer_edge_layers:
            self._layer_edge_layers[layer_row] = {}
        self._layer_edge_layers[layer_row][self._current_edge] = entries

    def _add_edge_layer_row(self) -> None:
        """Add a new edge layer row with default Steel 3mm."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        self._updating_edge_layers = True
        r = self._edge_table.rowCount()
        self._edge_table.insertRow(r)
        mat_combo = self._make_edge_material_combo("Steel")
        self._edge_table.setCellWidget(r, 0, mat_combo)
        self._edge_table.setItem(r, 1, QTableWidgetItem("3.000"))
        self._updating_edge_layers = False
        self._read_edge_table_into_store(layer_row)

    def _remove_edge_layer_row(self) -> None:
        """Remove the selected edge layer row."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        selected = self._edge_table.currentRow()
        if selected < 0:
            return
        self._edge_table.removeRow(selected)
        self._read_edge_table_into_store(layer_row)

    def _on_copy_from_clicked(self) -> None:
        """Show a context menu to copy edge layers from another edge."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        menu = QMenu(self)
        other_edges = [e for e in ("bottom", "top", "left", "right") if e != self._current_edge]
        for edge in other_edges:
            action = menu.addAction(edge.capitalize())
            action.triggered.connect(lambda checked, src=edge: self._copy_edge_from(src))
        menu.exec(self._copy_from_btn.mapToGlobal(self._copy_from_btn.rect().bottomLeft()))

    def _copy_edge_from(self, source_edge: str) -> None:
        """Copy edge layers from source_edge to current edge."""
        layer_row = self.layers_table.currentRow()
        if layer_row < 0:
            return
        if layer_row not in self._layer_edge_layers:
            self._layer_edge_layers[layer_row] = {}
        source_entries = self._layer_edge_layers.get(layer_row, {}).get(source_edge, [])
        import copy
        self._layer_edge_layers[layer_row][self._current_edge] = copy.deepcopy(source_entries)
        self._populate_edge_table(layer_row, self._current_edge)

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
        arch = self.arch_combo.currentText()
        if arch in ("DLED", "ELED"):
            # Build project from arch-specific spinboxes; layers/materials/boundaries from tables
            project = TableDataParser.build_project_from_tables(
                self._tables_dict,
                self._spinboxes_dict,
                self._boundary_widgets_dict,
                led_array_extras=self._led_array_extras,
            )
            project.led_arrays = self._build_led_arrays_from_arch_panel()
        else:
            project = TableDataParser.build_project_from_tables(
                self._tables_dict,
                self._spinboxes_dict,
                self._boundary_widgets_dict,
                led_array_extras=self._led_array_extras,
            )
        # Read nz spinbox values from the layers table (column 4 cell widgets)
        for row, layer in enumerate(project.layers):
            nz_spin = self.layers_table.cellWidget(row, 4)
            layer.nz = nz_spin.value() if nz_spin is not None else 1
        # Attach material zones from the zone sub-panel
        for row, layer in enumerate(project.layers):
            zone_dicts = self._layer_zones.get(row, [])
            zones = []
            for z in zone_dicts:
                try:
                    zones.append(MaterialZone(
                        material=z["material"],
                        x=z["x"],
                        y=z["y"],
                        width=z["width"],
                        height=z["height"],
                    ))
                except (ValueError, KeyError):
                    continue
            layer.zones = zones
        # Attach edge layers from per-layer data (populated by Apply button or manual edits)
        from thermal_sim.models.layer import EdgeLayer
        from thermal_sim.models.project import EdgeFrame
        for row, layer in enumerate(project.layers):
            edge_data = self._layer_edge_layers.get(row, {})
            edge_layers = {}
            for edge, entries in edge_data.items():
                el_list = []
                for entry in entries:
                    try:
                        el_list.append(EdgeLayer(
                            material=entry["material"],
                            thickness=entry["thickness"],
                        ))
                    except (ValueError, KeyError):
                        continue
                if el_list:
                    edge_layers[edge] = el_list
            layer.edge_layers = edge_layers
        # Store edge_frame metadata for serialization (last-applied values)
        mt = self._ef_metal_spin.value() / 1000.0
        at = self._ef_air_spin.value() / 1000.0
        has_any = any(layer.edge_layers for layer in project.layers)
        project.edge_frame = EdgeFrame(metal_thickness=mt, air_gap_thickness=at) if has_any else None
        # Resolve edge layer references in heat sources and LED arrays
        for src in project.heat_sources:
            src.layer = self._resolve_layer_target(src.layer)
        for arr in project.led_arrays:
            arr.layer = self._resolve_layer_target(arr.layer)
            if arr.mode in ("grid", "edge"):
                arr.panel_width = project.width
                arr.panel_height = project.height
        # Attach power profiles from the profile sub-panel
        from thermal_sim.models.heat_source import PowerBreakpoint  # noqa: F401 (side-effect import for clarity)
        for row_idx, bps in self._source_profiles.items():
            if row_idx < len(project.heat_sources) and len(bps) >= 2:
                src = project.heat_sources[row_idx]
                src.power_profile = list(bps)
        return project

    def _on_architecture_changed(self, arch: str) -> None:
        """Switch LED panel and apply template when the architecture combo changes."""
        index = {"Custom": 0, "DLED": 1, "ELED": 2}.get(arch, 0)
        self._led_arrays_stack.setCurrentIndex(index)
        if arch == "Custom":
            return  # Keep existing data unchanged

        # Convert current panel dimensions from mm to metres
        w = self.width_spin.value() / 1000.0
        h = self.height_spin.value() / 1000.0

        from thermal_sim.models.stack_templates import dled_template, eled_template
        if arch == "DLED":
            template_data = dled_template(w, h)
        else:
            edge_cfg = self._eled_edge_config.currentText().lower().replace("/", "_")
            template_data = eled_template(w, h, edge_config=edge_cfg)

        self._apply_template(template_data)

    def _apply_template(self, template_data: dict) -> None:
        """Populate the full UI from a stack template dict.

        Layers, materials, and boundaries are loaded via _populate_ui_from_project.
        The active DLED/ELED panel spinboxes are then seeded from template LED array data.
        """
        from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig

        # Build a temporary project using template data + current spinbox values
        temp_project = DisplayProject(
            name=self.project_name_edit.text() or "Template",
            width=self.width_spin.value() / 1000.0,
            height=self.height_spin.value() / 1000.0,
            mesh=MeshConfig(nx=self.nx_spin.value(), ny=self.ny_spin.value()),
            transient=TransientConfig(
                time_step_s=self.dt_spin.value(),
                total_time_s=self.total_time_spin.value(),
                output_interval_s=self.output_interval_spin.value(),
            ),
            initial_temperature_c=self.initial_temp_spin.value(),
            layers=template_data["layers"],
            materials=template_data["materials"],
            heat_sources=[],
            led_arrays=template_data["led_arrays"],
            boundaries=template_data["boundaries"],
            probes=[],
            edge_frame=template_data.get("edge_frame"),
        )

        # Block signals before bulk update to prevent spurious undo commands
        editable_tables = [
            self.materials_table,
            self.layers_table,
            self.sources_table,
            self.led_arrays_table,
            self.probes_table,
        ]
        for table in editable_tables:
            table.blockSignals(True)

        # Block arch_combo so _populate_ui_from_project's reset to Custom is bypassed here
        self.arch_combo.blockSignals(True)
        arch_was = self.arch_combo.currentText()

        self._populate_ui_from_project(temp_project)

        # Restore arch selection (populate resets it to Custom)
        self.arch_combo.blockSignals(True)
        self.arch_combo.setCurrentText(arch_was)
        self.arch_combo.blockSignals(False)

        for table in editable_tables:
            table.blockSignals(False)

        # Seed the active arch panel spinboxes from the template LED array
        led_arrays = template_data.get("led_arrays", [])
        if led_arrays:
            la = led_arrays[0]
            if arch_was == "DLED":
                self._dled_count_x.blockSignals(True)
                self._dled_count_x.setValue(la.count_x)
                self._dled_count_x.blockSignals(False)

                self._dled_count_y.blockSignals(True)
                self._dled_count_y.setValue(la.count_y)
                self._dled_count_y.blockSignals(False)

                # Pitch labels updated after all spinboxes are set
                self._update_dled_pitch_labels()

                self._dled_power.blockSignals(True)
                self._dled_power.setValue(la.power_per_led_w)
                self._dled_power.blockSignals(False)

                self._dled_offset_top.blockSignals(True)
                self._dled_offset_top.setValue(la.offset_top * 1000.0)
                self._dled_offset_top.blockSignals(False)

                self._dled_offset_bottom.blockSignals(True)
                self._dled_offset_bottom.setValue(la.offset_bottom * 1000.0)
                self._dled_offset_bottom.blockSignals(False)

                self._dled_offset_left.blockSignals(True)
                self._dled_offset_left.setValue(la.offset_left * 1000.0)
                self._dled_offset_left.blockSignals(False)

                self._dled_offset_right.blockSignals(True)
                self._dled_offset_right.setValue(la.offset_right * 1000.0)
                self._dled_offset_right.blockSignals(False)

                self._dled_zone_count_x.blockSignals(True)
                self._dled_zone_count_x.setValue(la.zone_count_x)
                self._dled_zone_count_x.blockSignals(False)

                self._dled_zone_count_y.blockSignals(True)
                self._dled_zone_count_y.setValue(la.zone_count_y)
                self._dled_zone_count_y.blockSignals(False)

                self._rebuild_zone_table()

                if la.footprint_shape:
                    idx = self._dled_footprint_shape.findText(la.footprint_shape)
                    if idx >= 0:
                        self._dled_footprint_shape.setCurrentIndex(idx)
                if la.led_width is not None:
                    self._dled_led_width.setValue(la.led_width * 1000.0)
                if la.led_height is not None:
                    self._dled_led_height.setValue(la.led_height * 1000.0)
                if la.led_radius is not None:
                    self._dled_led_radius.setValue(la.led_radius * 1000.0)

            elif arch_was == "ELED":
                edge_text = la.edge_config.replace("_", "/")
                idx = self._eled_edge_config.findText(edge_text)
                if idx < 0:
                    idx = self._eled_edge_config.findText(la.edge_config)
                if idx >= 0:
                    self._eled_edge_config.blockSignals(True)
                    self._eled_edge_config.setCurrentIndex(idx)
                    self._eled_edge_config.blockSignals(False)

                self._eled_count.blockSignals(True)
                self._eled_count.setValue(la.count_x)
                self._eled_count.blockSignals(False)

                # Pitch label updated after all spinboxes are set
                self._update_eled_pitch_label()

                self._eled_edge_offset.blockSignals(True)
                self._eled_edge_offset.setValue(la.edge_offset * 1000.0)
                self._eled_edge_offset.blockSignals(False)

                self._eled_power.blockSignals(True)
                self._eled_power.setValue(la.power_per_led_w)
                self._eled_power.blockSignals(False)

                if la.footprint_shape:
                    idx = self._eled_footprint_shape.findText(la.footprint_shape)
                    if idx >= 0:
                        self._eled_footprint_shape.setCurrentIndex(idx)
                if la.led_width is not None:
                    self._eled_led_width.setValue(la.led_width * 1000.0)
                if la.led_height is not None:
                    self._eled_led_height.setValue(la.led_height * 1000.0)
                if la.led_radius is not None:
                    self._eled_led_radius.setValue(la.led_radius * 1000.0)

        # Restore LED stack page (populate reset it to index 0)
        index = {"Custom": 0, "DLED": 1, "ELED": 2}.get(arch_was, 0)
        self._led_arrays_stack.setCurrentIndex(index)

        # Clear undo stack — silent replacement per design decision
        self._undo_stack.clear()

        # Re-validate
        self._validation_errors.clear()
        for table in editable_tables:
            self._revalidate_table(table)

        # Auto-apply edge frame so layer target dropdowns include edge layer entries
        self._apply_edge_frame()

        # Refresh 3D preview with new template
        self._refresh_3d_preview()

    def _build_led_arrays_from_arch_panel(self) -> list:
        """Build LEDArray list from DLED or ELED spinbox panel values (mm -> SI)."""
        from thermal_sim.models.heat_source import LEDArray
        arch = self.arch_combo.currentText()
        w = self.width_spin.value() / 1000.0
        h = self.height_spin.value() / 1000.0

        if arch == "DLED":
            count_x = self._dled_count_x.value()
            count_y = self._dled_count_y.value()
            power = self._dled_power.value()
            offset_top = self._dled_offset_top.value() / 1000.0
            offset_bottom = self._dled_offset_bottom.value() / 1000.0
            offset_left = self._dled_offset_left.value() / 1000.0
            offset_right = self._dled_offset_right.value() / 1000.0
            zone_count_x = self._dled_zone_count_x.value()
            zone_count_y = self._dled_zone_count_y.value()

            # Read zone powers from table
            zone_powers: list[float] = []
            for r in range(self._dled_zone_table.rowCount()):
                item = self._dled_zone_table.item(r, 1)
                try:
                    zone_powers.append(float(item.text()) if item else power)
                except (ValueError, AttributeError):
                    zone_powers.append(power)

            footprint_shape = self._dled_footprint_shape.currentText()
            led_width = self._dled_led_width.value() / 1000.0
            led_height = self._dled_led_height.value() / 1000.0
            led_radius = self._dled_led_radius.value() / 1000.0

            led_array = LEDArray(
                name="DLED Array",
                layer="LED Board",
                center_x=w / 2.0,
                center_y=h / 2.0,
                count_x=count_x,
                count_y=count_y,
                pitch_x=0.0,  # auto-computed by model from panel/offsets/count
                pitch_y=0.0,
                power_per_led_w=power,
                footprint_shape=footprint_shape,
                led_width=led_width,
                led_height=led_height,
                led_radius=led_radius,
                mode="grid",
                panel_width=w,
                panel_height=h,
                offset_top=offset_top,
                offset_bottom=offset_bottom,
                offset_left=offset_left,
                offset_right=offset_right,
                zone_count_x=zone_count_x,
                zone_count_y=zone_count_y,
                zone_powers=zone_powers,
            )
            return [led_array]

        elif arch == "ELED":
            count = self._eled_count.value()
            edge_offset = self._eled_edge_offset.value() / 1000.0
            power = self._eled_power.value()
            edge_text = self._eled_edge_config.currentText()
            edge_cfg = edge_text.replace("/", "_")

            footprint_shape = self._eled_footprint_shape.currentText()
            led_width = self._eled_led_width.value() / 1000.0
            led_height = self._eled_led_height.value() / 1000.0
            led_radius = self._eled_led_radius.value() / 1000.0

            eled_layer = self._resolve_layer_target(
                self._eled_layer_combo.currentText() or "LGP"
            )
            led_array = LEDArray(
                name="ELED Array",
                layer=eled_layer,
                center_x=w / 2.0,
                center_y=h / 2.0,
                count_x=count,
                count_y=count,
                pitch_x=0.0,  # auto-computed by model
                pitch_y=0.0,
                power_per_led_w=power,
                footprint_shape=footprint_shape,
                led_width=led_width,
                led_height=led_height,
                led_radius=led_radius,
                mode="edge",
                edge_config=edge_cfg,
                edge_offset=edge_offset,
                panel_width=w,
                panel_height=h,
                z_position="distributed",  # edge LEDs face full layer thickness
            )
            return [led_array]

        return []

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


# ===========================================================================
# VoxelMainWindow — GUI for the voxel-based 3D solver
# ===========================================================================

class VoxelMainWindow(QMainWindow):
    """Main window for the voxel-based 3D thermal solver.

    Layout:
    - Left dock: Materials tab + BlockEditorWidget (blocks, sources, boundaries,
      probes, mesh config)
    - Right dock: Voxel3DView (structure preview / temperature overlay)
    - Bottom status bar with solver state and progress

    Wires block editor changes to 3D structure preview, and simulation results
    to the temperature overlay.
    """

    def __init__(self) -> None:
        super().__init__()
        from thermal_sim.core.paths import APP_VERSION
        self.setWindowTitle(f"Voxel Thermal Simulator v{APP_VERSION}")
        self.resize(1400, 800)
        self.setMinimumSize(800, 500)

        self.current_project_path: Path | None = None

        self._sim_controller = SimulationController(self)
        self._sim_mode: str = "steady"
        self._last_result: object = None

        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._connect_signals()
        self._load_startup_materials()
        self._restore_layout()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setCentralWidget(QWidget())

        # --- Left dock: editor ---
        editor_outer = QWidget()
        editor_layout = QVBoxLayout(editor_outer)
        editor_layout.setContentsMargins(2, 2, 2, 2)
        editor_layout.setSpacing(4)

        # Materials sub-tab + BlockEditorWidget in a QTabWidget
        self._editor_tabs = QTabWidget()

        # Materials tab (reuses the material library widget pattern)
        self._build_materials_tab()
        self._editor_tabs.addTab(self._materials_tab_widget, "Materials")

        # Block editor
        from thermal_sim.ui.block_editor import BlockEditorWidget
        self._block_editor = BlockEditorWidget()
        self._block_editor.project_changed.connect(self._on_project_changed)
        self._editor_tabs.addTab(self._block_editor, "Assembly")

        editor_layout.addWidget(self._editor_tabs)

        self._editor_dock = QDockWidget("Editor", self)
        self._editor_dock.setObjectName("VoxelEditorDock")
        self._editor_dock.setWidget(editor_outer)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)

        # --- Right dock: 3D view ---
        from thermal_sim.ui.voxel_3d_view import Voxel3DView
        self._voxel_3d_view = Voxel3DView()

        self._view_dock = QDockWidget("3D View", self)
        self._view_dock.setObjectName("Voxel3DDock")
        self._view_dock.setWidget(self._voxel_3d_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._view_dock)

        # --- Status bar ---
        sb = self.statusBar()
        self._path_label = QLabel("No file")
        self._solver_label = QLabel("Ready")
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setTextVisible(True)
        sb.addPermanentWidget(self._path_label, stretch=2)
        sb.addPermanentWidget(self._solver_label, stretch=1)
        sb.addPermanentWidget(self._progress_bar, stretch=1)

    def _build_materials_tab(self) -> None:
        """Build a minimal materials tab (library view + add/remove)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        from thermal_sim.core.material_library import load_builtin_library
        self._materials: dict = {}
        try:
            self._materials = load_builtin_library()
        except Exception:
            pass

        self._mat_table = QTableWidget(0, 4)
        self._mat_table.setHorizontalHeaderLabels([
            "Name", "k_in_plane (W/mK)", "k_through (W/mK)", "rho_cp (J/m3K)"
        ])
        self._mat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 4):
            self._mat_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self._mat_table.cellChanged.connect(self._on_mat_table_changed)
        layout.addWidget(self._mat_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Material")
        add_btn.clicked.connect(self._add_material_row)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove_material_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._materials_tab_widget = tab
        self._populate_mat_table()

    def _populate_mat_table(self) -> None:
        self._mat_table.blockSignals(True)
        self._mat_table.setRowCount(0)
        for name, mat in sorted(self._materials.items()):
            row = self._mat_table.rowCount()
            self._mat_table.insertRow(row)
            self._mat_table.setItem(row, 0, QTableWidgetItem(name))
            self._mat_table.setItem(row, 1, QTableWidgetItem(f"{mat.k_in_plane:.4g}"))
            self._mat_table.setItem(row, 2, QTableWidgetItem(f"{mat.k_through:.4g}"))
            self._mat_table.setItem(row, 3, QTableWidgetItem(f"{mat.rho_cp:.4g}"))
        self._mat_table.blockSignals(False)

    def _add_material_row(self) -> None:
        row = self._mat_table.rowCount()
        self._mat_table.blockSignals(True)
        self._mat_table.insertRow(row)
        self._mat_table.setItem(row, 0, QTableWidgetItem(f"Material{row + 1}"))
        self._mat_table.setItem(row, 1, QTableWidgetItem("1.0"))
        self._mat_table.setItem(row, 2, QTableWidgetItem("1.0"))
        self._mat_table.setItem(row, 3, QTableWidgetItem("1.0e6"))
        self._mat_table.blockSignals(False)
        self._sync_materials_from_table()

    def _remove_material_row(self) -> None:
        row = self._mat_table.currentRow()
        if row >= 0:
            self._mat_table.removeRow(row)
            self._sync_materials_from_table()

    def _on_mat_table_changed(self) -> None:
        self._sync_materials_from_table()

    def _sync_materials_from_table(self) -> None:
        """Read the materials table and update self._materials dict."""
        from thermal_sim.models.material import Material
        new_mats: dict = {}
        for row in range(self._mat_table.rowCount()):
            name_item = self._mat_table.item(row, 0)
            if name_item is None or not name_item.text().strip():
                continue
            name = name_item.text().strip()

            def _cell_f(r: int, c: int, fallback: float = 1.0) -> float:
                item = self._mat_table.item(r, c)
                if item is None:
                    return fallback
                try:
                    return float(item.text())
                except ValueError:
                    return fallback

            try:
                mat = Material(
                    name=name,
                    k_in_plane=max(1e-6, _cell_f(row, 1, 1.0)),
                    k_through=max(1e-6, _cell_f(row, 2, 1.0)),
                    rho_cp=max(1.0, _cell_f(row, 3, 1e6)),
                )
                new_mats[name] = mat
            except Exception:
                pass
        self._materials = new_mats
        self._block_editor.update_material_list(new_mats)

    def _build_menus(self) -> None:
        from PySide6.QtGui import QKeySequence, QAction

        file_menu = self.menuBar().addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        self._save_action = QAction("&Save Project", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_action)

        save_as_action = QAction("Save Project &As...", self)
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        run_menu = self.menuBar().addMenu("&Run")

        self._run_action = QAction("&Run Simulation", self)
        self._run_action.setShortcut("F5")
        self._run_action.triggered.connect(self._run_simulation)
        run_menu.addAction(self._run_action)

        self._cancel_action = QAction("&Cancel", self)
        self._cancel_action.setShortcut("Escape")
        self._cancel_action.setEnabled(False)
        self._cancel_action.triggered.connect(self._sim_controller.cancel)
        run_menu.addAction(self._cancel_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._editor_dock.toggleViewAction())
        view_menu.addAction(self._view_dock.toggleViewAction())
        view_menu.addSeparator()
        reset_action = QAction("Reset Layout", self)
        reset_action.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_action)

    def _build_toolbar(self) -> None:
        from PySide6.QtWidgets import QComboBox as _QCB
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel(" Mode: "))
        self.mode_combo = _QCB()
        self.mode_combo.addItems(["steady", "transient"])
        self.mode_combo.setToolTip("Steady-state or transient simulation")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self.mode_combo)
        toolbar.addSeparator()
        toolbar.addAction(self._run_action)
        toolbar.addAction(self._cancel_action)

    def _connect_signals(self) -> None:
        self._sim_controller.run_started.connect(self._on_run_started)
        self._sim_controller.run_ended.connect(self._on_run_ended)
        self._sim_controller.progress_updated.connect(self._on_progress)
        self._sim_controller.run_finished.connect(self._on_result)
        self._sim_controller.run_error.connect(self._on_error)

    # ------------------------------------------------------------------
    # Startup helpers
    # ------------------------------------------------------------------

    def _load_startup_materials(self) -> None:
        """Populate block editor with the default material library."""
        self._block_editor.update_material_list(self._materials)

    def _restore_layout(self) -> None:
        settings = QSettings("ThermalSim", "VoxelSimulator")
        state = settings.value("dock_state")
        geometry = settings.value("window_geometry")
        if state:
            self.restoreState(state)
        if geometry:
            self.restoreGeometry(geometry)

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    def _new_project(self) -> None:
        self._block_editor.load_project(
            self._block_editor.build_project(self._materials).__class__(
                name="Untitled",
                blocks=[],
                materials=dict(self._materials),
                sources=[],
                boundary_groups=[],
                probes=[],
                mesh_config=__import__(
                    "thermal_sim.models.voxel_project", fromlist=["VoxelMeshConfig"]
                ).VoxelMeshConfig(),
            )
        )
        self.current_project_path = None
        self._update_title()

    def _open_project_dialog(self) -> None:
        from thermal_sim.io.voxel_project_io import load_voxel_project
        settings = QSettings("ThermalSim", "VoxelSimulator")
        start_dir = str(settings.value("last_open_dir", "."))
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Voxel Project", start_dir, "JSON (*.json)"
        )
        if not path_str:
            return
        try:
            path = Path(path_str)
            project = load_voxel_project(path)
            # Merge project materials into library
            self._materials.update(project.materials)
            self._populate_mat_table()
            self._block_editor.update_material_list(self._materials)
            self._block_editor.load_project(project)
            self.current_project_path = path
            settings.setValue("last_open_dir", str(path.parent))
            self._update_title()
            self._update_3d_structure()
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))

    def _save_project(self) -> None:
        if self.current_project_path is None:
            self._save_project_as()
        else:
            self._write_project(self.current_project_path)

    def _save_project_as(self) -> None:
        settings = QSettings("ThermalSim", "VoxelSimulator")
        start_dir = str(settings.value("last_open_dir", "."))
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Voxel Project", start_dir, "JSON (*.json)"
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.suffix:
            path = path.with_suffix(".json")
        self._write_project(path)
        settings.setValue("last_open_dir", str(path.parent))

    def _write_project(self, path: Path) -> None:
        from thermal_sim.io.voxel_project_io import save_voxel_project
        try:
            project = self._block_editor.build_project(self._materials)
            save_voxel_project(project, path)
            self.current_project_path = path
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _on_mode_changed(self, mode: str) -> None:
        self._sim_mode = mode

    def _run_simulation(self) -> None:
        try:
            project = self._block_editor.build_project(self._materials)
        except Exception as exc:
            QMessageBox.critical(self, "Project Error", str(exc))
            return

        if not project.blocks:
            QMessageBox.warning(self, "No Blocks", "Add at least one assembly block before solving.")
            return

        # For transient mode, require transient config
        if self._sim_mode == "transient" and project.transient_config is None:
            QMessageBox.warning(
                self, "No Transient Config",
                "Enable transient in the Mesh tab to run a transient simulation."
            )
            return

        self._sim_controller.start_voxel_run(project, self._sim_mode)

    def _on_run_started(self) -> None:
        self._run_action.setEnabled(False)
        self._cancel_action.setEnabled(True)
        self._solver_label.setText("Solving...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # indeterminate

    def _on_run_ended(self) -> None:
        self._run_action.setEnabled(True)
        self._cancel_action.setEnabled(False)
        self._progress_bar.setVisible(False)

    def _on_progress(self, pct: int, msg: str) -> None:
        self._solver_label.setText(msg)
        if pct >= 0:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(pct)
        else:
            self._progress_bar.setRange(0, 0)

    def _on_result(self, result: object) -> None:
        self._last_result = result
        self._solver_label.setText("Complete")
        self._voxel_3d_view.update_temperature(result)

    def _on_error(self, message: str) -> None:
        self._solver_label.setText("Error")
        QMessageBox.critical(self, "Simulation Error", message)

    # ------------------------------------------------------------------
    # 3D view update
    # ------------------------------------------------------------------

    def _on_project_changed(self) -> None:
        """Live-update the 3D structure preview when the editor changes."""
        self._update_3d_structure()

    def _update_3d_structure(self) -> None:
        try:
            project = self._block_editor.build_project(self._materials)
            self._voxel_3d_view.update_structure(project)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug("3D structure update skipped: %s", exc)

    # ------------------------------------------------------------------
    # Title / path
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        from thermal_sim.core.paths import APP_VERSION
        base = f"Voxel Thermal Simulator v{APP_VERSION}"
        if self.current_project_path:
            base = f"{self.current_project_path.name} — {base}"
        self.setWindowTitle(base)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _reset_layout(self) -> None:
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._editor_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._view_dock)
        self._editor_dock.show()
        self._view_dock.show()

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        settings = QSettings("ThermalSim", "VoxelSimulator")
        settings.setValue("dock_state", self.saveState())
        settings.setValue("window_geometry", self.saveGeometry())
        event.accept()
