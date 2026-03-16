"""BlockEditorWidget — table-based editor for VoxelProject blocks, sources, boundaries, probes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from thermal_sim.models.material import Material

from thermal_sim.models.assembly_block import AssemblyBlock
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.voxel_project import (
    BoundaryGroup,
    VoxelMeshConfig,
    VoxelProject,
    VoxelProbe,
    VoxelTransientConfig,
)

logger = logging.getLogger(__name__)

_MM = 1e-3  # metres per millimetre


def _mm(m: float) -> float:
    """Convert metres to millimetres."""
    return m / _MM


def _m(mm: float) -> float:
    """Convert millimetres to metres."""
    return mm * _MM


def _float_item(value: float) -> QTableWidgetItem:
    item = QTableWidgetItem(f"{value:.4g}")
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


class BlockEditorWidget(QWidget):
    """Main editor for VoxelProject — blocks, sources, boundary groups, probes, mesh config.

    All position/size inputs are displayed in mm; stored internally as SI metres.
    Emits `project_changed` on any table edit for undo/redo integration later.
    """

    project_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._materials: dict[str, "Material"] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._build_blocks_tab()
        self._build_boundaries_tab()
        self._build_probes_tab()
        self._build_mesh_tab()

        # Populate default boundary row
        self._add_boundary_row("exposed", 25.0, 8.0, True, 0.9)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_blocks_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)

        self._blocks_table = QTableWidget(0, 9)
        self._blocks_table.setHorizontalHeaderLabels([
            "Name", "Material", "X (mm)", "Y (mm)", "Z (mm)",
            "Width (mm)", "Depth (mm)", "Height (mm)", "Power (W)",
        ])
        self._blocks_table.horizontalHeader().setToolTip(
            "Position (X,Y,Z) is the lower-left-bottom corner. Width=x, Depth=y, Height=z."
        )
        hdrs = self._blocks_table.horizontalHeader()
        hdrs.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdrs.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in range(2, 9):
            hdrs.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        # Tooltip per column
        _col_tips = [
            "Block name (must be unique)",
            "Material key from the material library",
            "X position of lower-left-bottom corner (mm)",
            "Y position of lower-left-bottom corner (mm)",
            "Z position of lower-left-bottom corner (mm)",
            "Size along x-axis (mm)",
            "Size along y-axis / depth (mm)",
            "Size along z-axis / height (mm)",
            "Heat generation power (W). 0 = passive block.",
        ]
        for col, tip in enumerate(_col_tips):
            item = self._blocks_table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tip)

        self._blocks_table.cellChanged.connect(self._on_blocks_changed)
        v.addWidget(self._blocks_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Block")
        add_btn.setToolTip("Add a new assembly block row")
        add_btn.clicked.connect(self._add_block_row_default)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.setToolTip("Remove the currently selected block row")
        rm_btn.clicked.connect(self._remove_blocks_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._tabs.addTab(w, "Blocks")

    def _build_boundaries_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)

        self._boundary_table = QTableWidget(0, 5)
        self._boundary_table.setHorizontalHeaderLabels([
            "Name", "Ambient (C)", "h_conv (W/m2K)", "Radiation", "Emissivity",
        ])
        hdrs = self._boundary_table.horizontalHeader()
        hdrs.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            hdrs.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        _col_tips = [
            "Boundary group name",
            "Ambient temperature (°C)",
            "Convection coefficient (W/m²·K)",
            "Include linearised radiation?",
            "Surface emissivity (0–1, used if radiation is enabled)",
        ]
        for col, tip in enumerate(_col_tips):
            item = self._boundary_table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tip)

        self._boundary_table.cellChanged.connect(self._on_boundaries_changed)
        v.addWidget(self._boundary_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Boundary Group")
        add_btn.clicked.connect(lambda: self._add_boundary_row("exposed", 25.0, 8.0, True, 0.9))
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove_boundaries_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._tabs.addTab(w, "Boundaries")

    def _build_probes_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)

        self._probes_table = QTableWidget(0, 4)
        self._probes_table.setHorizontalHeaderLabels([
            "Name", "X (mm)", "Y (mm)", "Z (mm)",
        ])
        hdrs = self._probes_table.horizontalHeader()
        hdrs.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 4):
            hdrs.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        _col_tips = [
            "Probe name",
            "Absolute X position (mm)",
            "Absolute Y position (mm)",
            "Absolute Z position (mm)",
        ]
        for col, tip in enumerate(_col_tips):
            item = self._probes_table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tip)

        self._probes_table.cellChanged.connect(self._on_probes_changed)
        v.addWidget(self._probes_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Probe")
        add_btn.clicked.connect(self._add_probe_row_default)
        rm_btn = QPushButton("Remove Selected")
        rm_btn.clicked.connect(self._remove_probes_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._tabs.addTab(w, "Probes")

    def _build_mesh_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(8)

        self._cells_per_interval_spin = QSpinBox()
        self._cells_per_interval_spin.setRange(1, 10)
        self._cells_per_interval_spin.setValue(1)
        self._cells_per_interval_spin.setToolTip(
            "Number of solver cells per conformal mesh interval. "
            "Higher values increase accuracy but slow the solve."
        )
        self._cells_per_interval_spin.valueChanged.connect(self.project_changed)
        form.addRow("Cells per interval:", self._cells_per_interval_spin)

        transient_group = QGroupBox("Transient Config")
        tform = QFormLayout(transient_group)

        self._transient_enabled = QCheckBox("Enable transient")
        self._transient_enabled.setToolTip("Run a time-dependent simulation instead of steady-state")
        self._transient_enabled.stateChanged.connect(self._on_transient_toggled)
        tform.addRow(self._transient_enabled)

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.1, 1e6)
        self._duration_spin.setValue(60.0)
        self._duration_spin.setSuffix(" s")
        self._duration_spin.setToolTip("Total simulation duration (seconds)")
        tform.addRow("Duration:", self._duration_spin)

        self._dt_spin = QDoubleSpinBox()
        self._dt_spin.setRange(0.001, 1000.0)
        self._dt_spin.setValue(1.0)
        self._dt_spin.setSuffix(" s")
        self._dt_spin.setToolTip("Time step size (seconds)")
        tform.addRow("Time step:", self._dt_spin)

        self._t_init_spin = QDoubleSpinBox()
        self._t_init_spin.setRange(-50.0, 300.0)
        self._t_init_spin.setValue(25.0)
        self._t_init_spin.setSuffix(" °C")
        self._t_init_spin.setToolTip("Initial temperature at t=0 (°C)")
        tform.addRow("Initial temp:", self._t_init_spin)

        self._duration_spin.setEnabled(False)
        self._dt_spin.setEnabled(False)
        self._t_init_spin.setEnabled(False)

        form.addRow(transient_group)
        self._tabs.addTab(w, "Mesh")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_transient_toggled(self, state: int) -> None:
        enabled = bool(state)
        self._duration_spin.setEnabled(enabled)
        self._dt_spin.setEnabled(enabled)
        self._t_init_spin.setEnabled(enabled)
        self.project_changed.emit()

    def _on_blocks_changed(self) -> None:
        self.project_changed.emit()

    def _on_boundaries_changed(self) -> None:
        self.project_changed.emit()

    def _on_probes_changed(self) -> None:
        self.project_changed.emit()

    def _refresh_block_combos(self) -> None:
        """Refresh dependent combos after block list changes.

        Currently a no-op — reserved for future source-block linking.
        """

    # ------------------------------------------------------------------
    # Row add helpers
    # ------------------------------------------------------------------

    def _add_block_row_default(self) -> None:
        row = self._blocks_table.rowCount()
        self._blocks_table.blockSignals(True)
        self._blocks_table.insertRow(row)
        self._blocks_table.setItem(row, 0, QTableWidgetItem(f"Block{row + 1}"))

        mat_combo = self._make_material_combo()
        self._blocks_table.setCellWidget(row, 1, mat_combo)

        for col, val in enumerate([0.0, 0.0, 0.0, 100.0, 100.0, 5.0, 0.0], start=2):
            self._blocks_table.setItem(row, col, _float_item(val))

        self._blocks_table.blockSignals(False)
        self._refresh_block_combos()
        self.project_changed.emit()

    def _remove_blocks_row(self) -> None:
        row = self._blocks_table.currentRow()
        if row >= 0:
            self._blocks_table.removeRow(row)
            self._refresh_block_combos()
            self.project_changed.emit()

    def _add_boundary_row(
        self,
        name: str = "exposed",
        ambient_c: float = 25.0,
        h_conv: float = 8.0,
        radiation: bool = True,
        emissivity: float = 0.9,
    ) -> None:
        row = self._boundary_table.rowCount()
        self._boundary_table.blockSignals(True)
        self._boundary_table.insertRow(row)
        self._boundary_table.setItem(row, 0, QTableWidgetItem(name))
        self._boundary_table.setItem(row, 1, _float_item(ambient_c))
        self._boundary_table.setItem(row, 2, _float_item(h_conv))

        chk = QCheckBox()
        chk.setChecked(radiation)
        chk.stateChanged.connect(self._on_boundaries_changed)
        self._boundary_table.setCellWidget(row, 3, chk)

        self._boundary_table.setItem(row, 4, _float_item(emissivity))
        self._boundary_table.blockSignals(False)
        self.project_changed.emit()

    def _remove_boundaries_row(self) -> None:
        row = self._boundary_table.currentRow()
        if row >= 0:
            self._boundary_table.removeRow(row)
            self.project_changed.emit()

    def _add_probe_row_default(self) -> None:
        row = self._probes_table.rowCount()
        self._probes_table.blockSignals(True)
        self._probes_table.insertRow(row)
        self._probes_table.setItem(row, 0, QTableWidgetItem(f"Probe{row + 1}"))
        for col in range(1, 4):
            self._probes_table.setItem(row, col, _float_item(0.0))
        self._probes_table.blockSignals(False)
        self.project_changed.emit()

    def _remove_probes_row(self) -> None:
        row = self._probes_table.currentRow()
        if row >= 0:
            self._probes_table.removeRow(row)
            self.project_changed.emit()

    # ------------------------------------------------------------------
    # Material combo helpers
    # ------------------------------------------------------------------

    def _make_material_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems(sorted(self._materials.keys()) if self._materials else ["(none)"])
        combo.setToolTip("Material from the material library")
        combo.currentTextChanged.connect(self._on_blocks_changed)
        return combo

    def update_material_list(self, materials: dict[str, "Material"]) -> None:
        """Refresh material combos when the material library changes."""
        self._materials = materials
        for row in range(self._blocks_table.rowCount()):
            combo = self._blocks_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(sorted(materials.keys()) if materials else ["(none)"])
                idx = combo.findText(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_project(self, materials: dict[str, "Material"] | None = None) -> VoxelProject:
        """Read all tables and construct a VoxelProject.

        Parameters
        ----------
        materials:
            Material dict to embed in the project. If None, uses the last
            material dict passed to update_material_list().
        """
        if materials is None:
            materials = self._materials

        blocks = self._read_blocks()
        boundary_groups = self._read_boundaries()
        probes = self._read_probes()
        mesh_config = VoxelMeshConfig(
            cells_per_interval=self._cells_per_interval_spin.value()
        )

        transient_config: VoxelTransientConfig | None = None
        if self._transient_enabled.isChecked():
            transient_config = VoxelTransientConfig(
                duration_s=self._duration_spin.value(),
                dt_s=self._dt_spin.value(),
                initial_temp_c=self._t_init_spin.value(),
            )

        return VoxelProject(
            name="Untitled",
            blocks=blocks,
            materials=dict(materials),
            boundary_groups=boundary_groups,
            probes=probes,
            mesh_config=mesh_config,
            transient_config=transient_config,
        )

    def validate_blocks(self) -> list[str]:
        """Check block geometry for common issues and return warning strings.

        Performs geometry checks without building the full project or running
        the solver. Operates only on block geometry (AABBs) from the table.

        Returns a list of warning strings (empty list = no issues found).
        Callers (main window, simulation controller) are responsible for
        presenting these warnings to the user.

        Checks:
        1. AABB overlap (last-defined-wins warning for overlapping blocks).
        2. Powered block without face contact with any other solid block.
        3. Air gap between powered block and any metal block.
        """
        blocks = self._read_blocks()
        warnings: list[str] = []

        _METAL_KEYWORDS = ("aluminum", "copper", "steel", "metal")

        def _aabb_overlap(a: AssemblyBlock, b: AssemblyBlock) -> bool:
            """Return True if the two AABBs overlap in all 3 axes."""
            return (
                a.x < b.x + b.width and b.x < a.x + a.width
                and a.y < b.y + b.depth and b.y < a.y + a.depth
                and a.z < b.z + b.height and b.z < a.z + a.height
            )

        def _axis_overlap(lo1: float, hi1: float, lo2: float, hi2: float) -> bool:
            """Strict overlap — intervals must share interior, not just touch."""
            return lo1 < hi2 and lo2 < hi1

        def _share_face(a: AssemblyBlock, b: AssemblyBlock) -> bool:
            """Return True if the two blocks share a face (not just edge/corner).

            Face sharing: one axis has exact boundary alignment (a_max == b_min or
            b_max == a_min) AND the remaining two axes have overlapping (not just
            touching) intervals.
            """
            # +x face of a aligns with -x face of b
            if abs((a.x + a.width) - b.x) < 1e-12:
                return (_axis_overlap(a.y, a.y + a.depth, b.y, b.y + b.depth)
                        and _axis_overlap(a.z, a.z + a.height, b.z, b.z + b.height))
            # -x face of a aligns with +x face of b
            if abs(a.x - (b.x + b.width)) < 1e-12:
                return (_axis_overlap(a.y, a.y + a.depth, b.y, b.y + b.depth)
                        and _axis_overlap(a.z, a.z + a.height, b.z, b.z + b.height))
            # +y face of a aligns with -y face of b
            if abs((a.y + a.depth) - b.y) < 1e-12:
                return (_axis_overlap(a.x, a.x + a.width, b.x, b.x + b.width)
                        and _axis_overlap(a.z, a.z + a.height, b.z, b.z + b.height))
            # -y face of a aligns with +y face of b
            if abs(a.y - (b.y + b.depth)) < 1e-12:
                return (_axis_overlap(a.x, a.x + a.width, b.x, b.x + b.width)
                        and _axis_overlap(a.z, a.z + a.height, b.z, b.z + b.height))
            # +z face of a aligns with -z face of b
            if abs((a.z + a.height) - b.z) < 1e-12:
                return (_axis_overlap(a.x, a.x + a.width, b.x, b.x + b.width)
                        and _axis_overlap(a.y, a.y + a.depth, b.y, b.y + b.depth))
            # -z face of a aligns with +z face of b
            if abs(a.z - (b.z + b.height)) < 1e-12:
                return (_axis_overlap(a.x, a.x + a.width, b.x, b.x + b.width)
                        and _axis_overlap(a.y, a.y + a.depth, b.y, b.y + b.depth))
            return False

        def _has_gap(a: AssemblyBlock, b: AssemblyBlock) -> bool:
            """Return True if blocks have space (gap) between them in any axis."""
            x_gap = (a.x + a.width < b.x - 1e-12) or (b.x + b.width < a.x - 1e-12)
            y_gap = (a.y + a.depth < b.y - 1e-12) or (b.y + b.depth < a.y - 1e-12)
            z_gap = (a.z + a.height < b.z - 1e-12) or (b.z + b.height < a.z - 1e-12)
            return x_gap or y_gap or z_gap

        # 1. Overlap warning (last-defined-wins for j > i pairs)
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                if _aabb_overlap(blocks[i], blocks[j]):
                    warnings.append(
                        f"Warning: Block '{blocks[j].name}' overlaps '{blocks[i].name}'"
                        f" — {blocks[j].name} takes priority in overlap region"
                        " (last-defined-wins rule)"
                    )

        # 2 & 3. Per-powered-block checks
        for blk in blocks:
            if blk.power_w <= 0.0:
                continue

            other_solid = [b for b in blocks if b is not blk]

            # Check 2: does this powered block share a face with any other solid block?
            has_face_contact = any(_share_face(blk, other) for other in other_solid)
            if not has_face_contact:
                warnings.append(
                    f"Warning: Powered block '{blk.name}' ({blk.power_w}W) does not"
                    " share a face with any other solid block"
                    " — heat may only dissipate to air"
                )

            # Check 3: is there a metal block close but not touching?
            for other in other_solid:
                is_metal = any(kw in other.material.lower() for kw in _METAL_KEYWORDS)
                if not is_metal:
                    continue
                if _share_face(blk, other):
                    continue  # already touching — no gap
                if _has_gap(blk, other):
                    warnings.append(
                        f"Warning: Powered block '{blk.name}' has gap between it and"
                        f" '{other.name}' — air gap may impede thermal path"
                    )

        return warnings

    def load_project(self, project: VoxelProject) -> None:
        """Populate all tables from an existing VoxelProject."""
        # Blocks
        self._blocks_table.blockSignals(True)
        self._blocks_table.setRowCount(0)
        for blk in project.blocks:
            self._load_block_row(blk)
        self._blocks_table.blockSignals(False)

        # Boundaries
        self._boundary_table.blockSignals(True)
        self._boundary_table.setRowCount(0)
        for bg in project.boundary_groups:
            self._add_boundary_row(
                name=bg.name,
                ambient_c=bg.boundary.ambient_c,
                h_conv=bg.boundary.convection_h,
                radiation=bg.boundary.include_radiation,
                emissivity=(bg.boundary.emissivity_override or 0.9),
            )
        if self._boundary_table.rowCount() == 0:
            self._add_boundary_row()
        self._boundary_table.blockSignals(False)

        # Probes
        self._probes_table.blockSignals(True)
        self._probes_table.setRowCount(0)
        for probe in project.probes:
            self._load_probe_row(probe)
        self._probes_table.blockSignals(False)

        # Mesh config
        self._cells_per_interval_spin.setValue(project.mesh_config.cells_per_interval)

        # Transient config
        if project.transient_config is not None:
            self._transient_enabled.setChecked(True)
            self._duration_spin.setValue(project.transient_config.duration_s)
            self._dt_spin.setValue(project.transient_config.dt_s)
            self._t_init_spin.setValue(project.transient_config.initial_temp_c)
        else:
            self._transient_enabled.setChecked(False)

    # ------------------------------------------------------------------
    # Private row-loading helpers
    # ------------------------------------------------------------------

    def _load_block_row(self, blk: AssemblyBlock) -> None:
        row = self._blocks_table.rowCount()
        self._blocks_table.insertRow(row)
        self._blocks_table.setItem(row, 0, QTableWidgetItem(blk.name))

        mat_combo = self._make_material_combo()
        idx = mat_combo.findText(blk.material)
        if idx < 0:
            mat_combo.addItem(blk.material)
            idx = mat_combo.findText(blk.material)
        mat_combo.setCurrentIndex(idx)
        self._blocks_table.setCellWidget(row, 1, mat_combo)

        for col, val in enumerate([
            _mm(blk.x), _mm(blk.y), _mm(blk.z),
            _mm(blk.width), _mm(blk.depth), _mm(blk.height),
            blk.power_w,
        ], start=2):
            self._blocks_table.setItem(row, col, _float_item(val))

    def _load_probe_row(self, probe: VoxelProbe) -> None:
        row = self._probes_table.rowCount()
        self._probes_table.insertRow(row)
        self._probes_table.setItem(row, 0, QTableWidgetItem(probe.name))
        self._probes_table.setItem(row, 1, _float_item(_mm(probe.x)))
        self._probes_table.setItem(row, 2, _float_item(_mm(probe.y)))
        self._probes_table.setItem(row, 3, _float_item(_mm(probe.z)))

    # ------------------------------------------------------------------
    # Private read helpers
    # ------------------------------------------------------------------

    def _read_blocks(self) -> list[AssemblyBlock]:
        blocks = []
        for row in range(self._blocks_table.rowCount()):
            name_item = self._blocks_table.item(row, 0)
            if name_item is None or not name_item.text().strip():
                continue
            name = name_item.text().strip()

            mat_combo = self._blocks_table.cellWidget(row, 1)
            material = mat_combo.currentText() if isinstance(mat_combo, QComboBox) else ""
            if not material or material == "(none)":
                material = "Air"

            def _cell(r: int, c: int, fallback: float = 0.0) -> float:
                item = self._blocks_table.item(r, c)
                if item is None:
                    return fallback
                try:
                    return float(item.text())
                except ValueError:
                    return fallback

            try:
                block = AssemblyBlock(
                    name=name,
                    material=material,
                    x=_m(_cell(row, 2)),
                    y=_m(_cell(row, 3)),
                    z=_m(_cell(row, 4)),
                    width=_m(max(_cell(row, 5, 1.0), 0.001)),
                    depth=_m(max(_cell(row, 6, 1.0), 0.001)),
                    height=_m(max(_cell(row, 7, 1.0), 0.001)),
                    power_w=max(0.0, _cell(row, 8, 0.0)),
                )
                blocks.append(block)
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping block row %d: %s", row, exc)
        return blocks

    def _read_boundaries(self) -> list[BoundaryGroup]:
        groups = []
        for row in range(self._boundary_table.rowCount()):
            name_item = self._boundary_table.item(row, 0)
            if name_item is None or not name_item.text().strip():
                continue
            name = name_item.text().strip()

            def _cell(r: int, c: int, fallback: float = 25.0) -> float:
                item = self._boundary_table.item(r, c)
                if item is None:
                    return fallback
                try:
                    return float(item.text())
                except ValueError:
                    return fallback

            ambient_c = _cell(row, 1, 25.0)
            h_conv = _cell(row, 2, 8.0)

            rad_chk = self._boundary_table.cellWidget(row, 3)
            radiation = rad_chk.isChecked() if isinstance(rad_chk, QCheckBox) else True

            emissivity = _cell(row, 4, 0.9)
            emissivity = max(0.0, min(1.0, emissivity))

            bg = BoundaryGroup(
                name=name,
                boundary=SurfaceBoundary(
                    ambient_c=ambient_c,
                    convection_h=h_conv,
                    include_radiation=radiation,
                    emissivity_override=emissivity,
                ),
            )
            groups.append(bg)
        return groups

    def _read_probes(self) -> list[VoxelProbe]:
        probes = []
        for row in range(self._probes_table.rowCount()):
            name_item = self._probes_table.item(row, 0)
            if name_item is None or not name_item.text().strip():
                continue
            name = name_item.text().strip()

            def _cell(r: int, c: int) -> float:
                item = self._probes_table.item(r, c)
                if item is None:
                    return 0.0
                try:
                    return float(item.text())
                except ValueError:
                    return 0.0

            probes.append(VoxelProbe(
                name=name,
                x=_m(_cell(row, 1)),
                y=_m(_cell(row, 2)),
                z=_m(_cell(row, 3)),
            ))
        return probes
