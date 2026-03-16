"""StackGeneratorWizard — multi-page dialog for parametric display stack generation.

Uses a custom QDialog + QStackedWidget (NOT QWizard) because the live 3D preview
panel on the right requires a persistent side widget that QWizard cannot support.

Pages:
  0 — Architecture (ELED / DLED)
  1 — Panel Dimensions
  2 — LED Configuration (ELED or DLED sub-page)
  3 — Layer Thicknesses + Optical Films
  4 — Boundary Conditions
  5 — Mesh Configuration

All user-facing inputs are in mm. Conversion to SI metres happens when collecting
params to pass to generate_eled() / generate_dled().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from thermal_sim.models.voxel_project import VoxelProject

logger = logging.getLogger(__name__)

_MM = 1e-3


def _mm(m: float) -> float:
    """Convert metres to millimetres."""
    return m / _MM


def _m(mm: float) -> float:
    """Convert millimetres to metres."""
    return mm * _MM


# ---------------------------------------------------------------------------
# Preset h-values for boundary condition combos
# ---------------------------------------------------------------------------

_BC_PRESETS: dict[str, float] = {
    "Natural convection": 8.0,
    "Forced air": 25.0,
    "Enclosed still air": 3.0,
    "Custom": 8.0,
}

_FACE_LABELS = ["Top", "Bottom", "Front", "Back", "Left", "Right"]

# Edge labels for ELED LED config
_EDGE_LABELS = ["Left", "Right", "Top", "Bottom"]


# ===========================================================================
# Page 0 — Architecture selection
# ===========================================================================

class ArchitecturePage(QWidget):
    """Page 0: choose ELED or DLED architecture."""

    _DESCRIPTIONS = {
        "ELED (Edge-Lit)": (
            "Edge-lit display: LEDs are mounted along one or more edges of the frame, "
            "shining into a Light Guide Plate (LGP) that redirects light toward the panel."
        ),
        "DLED (Direct-Lit)": (
            "Direct-lit display: LEDs are mounted on a PCB directly behind the panel "
            "inside a cavity. Suitable for local-dimming and high-brightness designs."
        ),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        self._arch_combo = QComboBox()
        self._arch_combo.addItems(["ELED (Edge-Lit)", "DLED (Direct-Lit)"])
        self._arch_combo.currentTextChanged.connect(self._update_description)
        form.addRow("Architecture:", self._arch_combo)
        layout.addLayout(form)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: #555; font-style: italic; padding: 6px;")
        layout.addWidget(self._desc_label)
        layout.addStretch()

        self._update_description(self._arch_combo.currentText())

    def _update_description(self, text: str) -> None:
        self._desc_label.setText(self._DESCRIPTIONS.get(text, ""))

    def architecture(self) -> str:
        """Return 'ELED' or 'DLED'."""
        return "ELED" if "ELED" in self._arch_combo.currentText() else "DLED"


# ===========================================================================
# Page 1 — Panel Dimensions
# ===========================================================================

class PanelDimsPage(QWidget):
    """Page 1: panel width and depth in mm."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        group = QGroupBox("Panel Footprint")
        form = QFormLayout(group)

        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(50.0, 3000.0)
        self._width_spin.setValue(450.0)
        self._width_spin.setSuffix(" mm")
        self._width_spin.setDecimals(1)
        self._width_spin.setToolTip("Total panel width in the X direction (mm)")
        form.addRow("Panel Width:", self._width_spin)

        self._depth_spin = QDoubleSpinBox()
        self._depth_spin.setRange(50.0, 2000.0)
        self._depth_spin.setValue(300.0)
        self._depth_spin.setSuffix(" mm")
        self._depth_spin.setDecimals(1)
        self._depth_spin.setToolTip("Total panel depth in the Y direction (mm)")
        form.addRow("Panel Depth:", self._depth_spin)

        layout.addWidget(group)
        layout.addStretch()

    def panel_w_m(self) -> float:
        return _m(self._width_spin.value())

    def panel_d_m(self) -> float:
        return _m(self._depth_spin.value())


# ===========================================================================
# Page 2 — LED Configuration
# ===========================================================================

class _EledLedSubPage(QWidget):
    """Sub-page for ELED edge LED configuration."""

    _EDGE_ATTRS = ["Left", "Right", "Top", "Bottom"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Checkboxes
        cb_group = QGroupBox("Active LED Edges")
        cb_layout = QHBoxLayout(cb_group)
        self._checkboxes: dict[str, QCheckBox] = {}
        for edge in self._EDGE_ATTRS:
            cb = QCheckBox(edge)
            cb.setChecked(edge in ("Left", "Right"))
            cb.stateChanged.connect(self._refresh_table)
            self._checkboxes[edge] = cb
            cb_layout.addWidget(cb)
        cb_layout.addStretch()
        layout.addWidget(cb_group)

        # Per-edge table
        tbl_group = QGroupBox("Per-Edge LED Parameters")
        tbl_layout = QVBoxLayout(tbl_group)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Edge", "Count", "LED Width (mm)", "LED Depth (mm)",
            "LED Height (mm)", "Power/LED (W)", "Margin (mm)",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for c in range(1, 7):
            self._table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.Stretch
            )
        self._table.setMinimumHeight(120)
        tbl_layout.addWidget(self._table)
        layout.addWidget(tbl_group)

        self._refresh_table()

    def _refresh_table(self) -> None:
        """Add/remove rows based on active edge checkboxes."""
        self._table.blockSignals(True)
        # Collect current values so we don't lose user edits
        existing: dict[str, list[str]] = {}
        for row in range(self._table.rowCount()):
            edge_item = self._table.item(row, 0)
            if edge_item:
                edge = edge_item.text()
                vals = []
                for col in range(1, 7):
                    it = self._table.item(row, col)
                    vals.append(it.text() if it else "")
                existing[edge] = vals

        self._table.setRowCount(0)
        for edge in self._EDGE_ATTRS:
            if not self._checkboxes[edge].isChecked():
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            edge_item = QTableWidgetItem(edge)
            edge_item.setFlags(edge_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, edge_item)
            defaults = existing.get(edge, ["10", "0.6", "4.0", "1.4", "0.3", "12.0"])
            for col, default in enumerate(defaults, start=1):
                self._table.setItem(row, col, QTableWidgetItem(default))

        self._table.blockSignals(False)

    def active_edges(self) -> list[str]:
        return [e for e in self._EDGE_ATTRS if self._checkboxes[e].isChecked()]

    def get_edge_configs(self) -> dict[str, dict]:
        """Return {edge: {count, led_width_m, led_depth_m, led_height_m, power_per_led, margin_m}}."""
        configs: dict[str, dict] = {}
        for row in range(self._table.rowCount()):
            edge_item = self._table.item(row, 0)
            if not edge_item:
                continue
            edge = edge_item.text()

            def _float(col: int, default: float) -> float:
                it = self._table.item(row, col)
                if it is None:
                    return default
                try:
                    return float(it.text())
                except ValueError:
                    return default

            configs[edge] = {
                "count": max(1, int(_float(1, 10))),
                "led_width_m": _m(_float(2, 0.6)),
                "led_depth_m": _m(_float(3, 4.0)),
                "led_height_m": _m(_float(4, 1.4)),
                "power_per_led": _float(5, 0.3),
                "margin_m": _m(_float(6, 12.0)),
            }
        return configs


class _DledLedSubPage(QWidget):
    """Sub-page for DLED LED grid configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid_group = QGroupBox("LED Grid Layout")
        form = QFormLayout(grid_group)

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 50)
        self._rows_spin.setValue(4)
        self._rows_spin.setToolTip("Number of LED rows (Y direction)")
        form.addRow("Rows:", self._rows_spin)

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 50)
        self._cols_spin.setValue(6)
        self._cols_spin.setToolTip("Number of LED columns (X direction)")
        form.addRow("Columns:", self._cols_spin)

        self._pitch_x_spin = QDoubleSpinBox()
        self._pitch_x_spin.setRange(5.0, 500.0)
        self._pitch_x_spin.setValue(60.0)
        self._pitch_x_spin.setSuffix(" mm")
        self._pitch_x_spin.setDecimals(1)
        form.addRow("X Pitch:", self._pitch_x_spin)

        self._pitch_y_spin = QDoubleSpinBox()
        self._pitch_y_spin.setRange(5.0, 500.0)
        self._pitch_y_spin.setValue(60.0)
        self._pitch_y_spin.setSuffix(" mm")
        self._pitch_y_spin.setDecimals(1)
        form.addRow("Y Pitch:", self._pitch_y_spin)

        self._offset_x_spin = QDoubleSpinBox()
        self._offset_x_spin.setRange(0.0, 300.0)
        self._offset_x_spin.setValue(30.0)
        self._offset_x_spin.setSuffix(" mm")
        self._offset_x_spin.setDecimals(1)
        self._offset_x_spin.setToolTip("X offset of first LED from panel edge")
        form.addRow("X Offset:", self._offset_x_spin)

        self._offset_y_spin = QDoubleSpinBox()
        self._offset_y_spin.setRange(0.0, 300.0)
        self._offset_y_spin.setValue(30.0)
        self._offset_y_spin.setSuffix(" mm")
        self._offset_y_spin.setDecimals(1)
        self._offset_y_spin.setToolTip("Y offset of first LED from panel edge")
        form.addRow("Y Offset:", self._offset_y_spin)

        layout.addWidget(grid_group)

        led_group = QGroupBox("LED Package Dimensions")
        form2 = QFormLayout(led_group)

        self._led_w_spin = QDoubleSpinBox()
        self._led_w_spin.setRange(0.5, 50.0)
        self._led_w_spin.setValue(3.0)
        self._led_w_spin.setSuffix(" mm")
        self._led_w_spin.setDecimals(1)
        form2.addRow("LED Width (X):", self._led_w_spin)

        self._led_d_spin = QDoubleSpinBox()
        self._led_d_spin.setRange(0.5, 50.0)
        self._led_d_spin.setValue(3.0)
        self._led_d_spin.setSuffix(" mm")
        self._led_d_spin.setDecimals(1)
        form2.addRow("LED Depth (Y):", self._led_d_spin)

        self._led_h_spin = QDoubleSpinBox()
        self._led_h_spin.setRange(0.1, 10.0)
        self._led_h_spin.setValue(1.0)
        self._led_h_spin.setSuffix(" mm")
        self._led_h_spin.setDecimals(1)
        form2.addRow("LED Height (Z):", self._led_h_spin)

        self._power_spin = QDoubleSpinBox()
        self._power_spin.setRange(0.01, 50.0)
        self._power_spin.setValue(0.5)
        self._power_spin.setSuffix(" W")
        self._power_spin.setDecimals(3)
        form2.addRow("Power per LED:", self._power_spin)

        layout.addWidget(led_group)
        layout.addStretch()

    def get_dled_led_params(self) -> dict:
        return {
            "led_rows": self._rows_spin.value(),
            "led_cols": self._cols_spin.value(),
            "led_pitch_x": _m(self._pitch_x_spin.value()),
            "led_pitch_y": _m(self._pitch_y_spin.value()),
            "led_offset_x": _m(self._offset_x_spin.value()),
            "led_offset_y": _m(self._offset_y_spin.value()),
            "led_width": _m(self._led_w_spin.value()),
            "led_depth": _m(self._led_d_spin.value()),
            "led_height": _m(self._led_h_spin.value()),
            "led_power": self._power_spin.value(),
        }


class LEDConfigPage(QWidget):
    """Page 2: LED configuration — ELED or DLED depending on architecture selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._stack = QStackedWidget()
        self._eled_sub = _EledLedSubPage()
        self._dled_sub = _DledLedSubPage()
        self._stack.addWidget(self._eled_sub)   # index 0 = ELED
        self._stack.addWidget(self._dled_sub)   # index 1 = DLED
        layout.addWidget(self._stack)

    def set_architecture(self, arch: str) -> None:
        self._stack.setCurrentIndex(0 if arch == "ELED" else 1)

    def eled_sub(self) -> _EledLedSubPage:
        return self._eled_sub

    def dled_sub(self) -> _DledLedSubPage:
        return self._dled_sub


# ===========================================================================
# Page 3 — Layer Thicknesses + Optical Films
# ===========================================================================

def _make_material_combo(builtin_keys: list[str], default: str) -> QComboBox:
    combo = QComboBox()
    for key in sorted(builtin_keys):
        combo.addItem(key)
    idx = combo.findText(default)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    return combo


class _EledLayerSubPage(QWidget):
    """Layer thickness sub-page for ELED architecture."""

    def __init__(self, builtin_keys: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        thick_group = QGroupBox("Layer Thicknesses")
        form = QFormLayout(thick_group)

        def _dspin(default_mm: float, low: float = 0.05, high: float = 50.0) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(low, high)
            s.setValue(default_mm)
            s.setSuffix(" mm")
            s.setDecimals(2)
            return s

        self._panel_h = _dspin(1.5)
        form.addRow("Panel thickness:", self._panel_h)

        self._lgp_h = _dspin(4.0)
        form.addRow("LGP thickness:", self._lgp_h)

        self._reflector_h = _dspin(0.3)
        form.addRow("Reflector thickness:", self._reflector_h)

        self._frame_back_h = _dspin(1.0)
        form.addRow("Frame back plate:", self._frame_back_h)

        self._frame_wall_t = _dspin(4.0)
        form.addRow("Frame wall thickness:", self._frame_wall_t)

        self._back_cover_h = _dspin(1.0)
        form.addRow("Back cover:", self._back_cover_h)

        layout.addWidget(thick_group)

        mat_group = QGroupBox("Layer Materials")
        mat_form = QFormLayout(mat_group)

        self._panel_mat = _make_material_combo(builtin_keys, "LCD Glass")
        mat_form.addRow("Panel:", self._panel_mat)

        self._lgp_mat = _make_material_combo(builtin_keys, "PMMA / LGP")
        mat_form.addRow("LGP:", self._lgp_mat)

        self._reflector_mat = _make_material_combo(builtin_keys, "Reflector Film / PET-like Film")
        mat_form.addRow("Reflector:", self._reflector_mat)

        self._frame_mat = _make_material_combo(builtin_keys, "Aluminum, oxidized / rough")
        mat_form.addRow("Frame:", self._frame_mat)

        self._back_cover_mat = _make_material_combo(builtin_keys, "Aluminum, bare/shiny")
        mat_form.addRow("Back cover:", self._back_cover_mat)

        self._pcb_mat = _make_material_combo(builtin_keys, "PCB Effective, medium copper")
        mat_form.addRow("PCB strip:", self._pcb_mat)

        layout.addWidget(mat_group)

    def thicknesses(self) -> dict:
        return {
            "panel_h": _m(self._panel_h.value()),
            "lgp_h": _m(self._lgp_h.value()),
            "reflector_h": _m(self._reflector_h.value()),
            "frame_back_h": _m(self._frame_back_h.value()),
            "frame_wall_t": _m(self._frame_wall_t.value()),
            "back_cover_h": _m(self._back_cover_h.value()),
        }

    def materials(self) -> dict:
        return {
            "panel_material": self._panel_mat.currentText(),
            "lgp_material": self._lgp_mat.currentText(),
            "reflector_material": self._reflector_mat.currentText(),
            "frame_material": self._frame_mat.currentText(),
            "back_cover_material": self._back_cover_mat.currentText(),
            "pcb_material": self._pcb_mat.currentText(),
        }


class _DledLayerSubPage(QWidget):
    """Layer thickness sub-page for DLED architecture."""

    def __init__(self, builtin_keys: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        thick_group = QGroupBox("Layer Thicknesses")
        form = QFormLayout(thick_group)

        def _dspin(default_mm: float, low: float = 0.05, high: float = 50.0) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(low, high)
            s.setValue(default_mm)
            s.setSuffix(" mm")
            s.setDecimals(2)
            return s

        self._panel_h = _dspin(1.5)
        form.addRow("Panel thickness:", self._panel_h)

        self._diffuser_h = _dspin(2.0)
        form.addRow("Diffuser thickness:", self._diffuser_h)

        self._air_cavity_h = _dspin(10.0)
        form.addRow("Air cavity height:", self._air_cavity_h)

        self._pcb_h = _dspin(1.6)
        form.addRow("PCB thickness:", self._pcb_h)

        self._reflector_h = _dspin(0.3)
        form.addRow("Reflector thickness:", self._reflector_h)

        self._frame_back_h = _dspin(1.0)
        form.addRow("Frame back plate:", self._frame_back_h)

        self._frame_wall_t = _dspin(4.0)
        form.addRow("Frame wall thickness:", self._frame_wall_t)

        self._back_cover_h = _dspin(1.0)
        form.addRow("Back cover:", self._back_cover_h)

        layout.addWidget(thick_group)

        mat_group = QGroupBox("Layer Materials")
        mat_form = QFormLayout(mat_group)

        self._panel_mat = _make_material_combo(builtin_keys, "LCD Glass")
        mat_form.addRow("Panel:", self._panel_mat)

        self._diffuser_mat = _make_material_combo(builtin_keys, "PC")
        mat_form.addRow("Diffuser:", self._diffuser_mat)

        self._pcb_mat = _make_material_combo(builtin_keys, "PCB Effective, medium copper")
        mat_form.addRow("PCB:", self._pcb_mat)

        self._reflector_mat = _make_material_combo(builtin_keys, "Reflector Film / PET-like Film")
        mat_form.addRow("Reflector:", self._reflector_mat)

        self._frame_mat = _make_material_combo(builtin_keys, "Aluminum, oxidized / rough")
        mat_form.addRow("Frame:", self._frame_mat)

        self._back_cover_mat = _make_material_combo(builtin_keys, "Aluminum, bare/shiny")
        mat_form.addRow("Back cover:", self._back_cover_mat)

        layout.addWidget(mat_group)

    def thicknesses(self) -> dict:
        return {
            "panel_h": _m(self._panel_h.value()),
            "diffuser_h": _m(self._diffuser_h.value()),
            "air_cavity_h": _m(self._air_cavity_h.value()),
            "pcb_h": _m(self._pcb_h.value()),
            "reflector_h": _m(self._reflector_h.value()),
            "frame_back_h": _m(self._frame_back_h.value()),
            "frame_wall_t": _m(self._frame_wall_t.value()),
            "back_cover_h": _m(self._back_cover_h.value()),
        }

    def materials(self) -> dict:
        return {
            "panel_material": self._panel_mat.currentText(),
            "diffuser_material": self._diffuser_mat.currentText(),
            "pcb_material": self._pcb_mat.currentText(),
            "reflector_material": self._reflector_mat.currentText(),
            "frame_material": self._frame_mat.currentText(),
            "back_cover_material": self._back_cover_mat.currentText(),
        }


class LayerThicknessPage(QWidget):
    """Page 3: layer thicknesses, material dropdowns, and optical films."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        from thermal_sim.core.material_library import load_builtin_library
        try:
            self._builtin_keys = sorted(load_builtin_library().keys())
        except Exception:
            self._builtin_keys = []

        # ELED / DLED sub-pages via stacked widget
        self._stack = QStackedWidget()
        self._eled_sub = _EledLayerSubPage(self._builtin_keys)
        self._dled_sub = _DledLayerSubPage(self._builtin_keys)
        self._stack.addWidget(self._eled_sub)   # index 0 = ELED
        self._stack.addWidget(self._dled_sub)   # index 1 = DLED
        layout.addWidget(self._stack)

        # Optical films (shared)
        films_group = QGroupBox("Optical Films")
        films_vlayout = QVBoxLayout(films_group)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Film count:"))
        self._film_count = QSpinBox()
        self._film_count.setRange(0, 10)
        self._film_count.setValue(0)
        self._film_count.valueChanged.connect(self._refresh_films_table)
        count_row.addWidget(self._film_count)
        count_row.addStretch()
        films_vlayout.addLayout(count_row)

        self._films_table = QTableWidget(0, 3)
        self._films_table.setHorizontalHeaderLabels(["Film #", "Material", "Thickness (mm)"])
        self._films_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._films_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._films_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._films_table.setMaximumHeight(200)
        films_vlayout.addWidget(self._films_table)
        layout.addWidget(films_group)

    def set_architecture(self, arch: str) -> None:
        self._stack.setCurrentIndex(0 if arch == "ELED" else 1)

    def _refresh_films_table(self, count: int) -> None:
        """Add or remove rows to match the film count spinner."""
        self._films_table.blockSignals(True)
        current = self._films_table.rowCount()
        if count > current:
            for i in range(current, count):
                row = self._films_table.rowCount()
                self._films_table.insertRow(row)
                num_item = QTableWidgetItem(str(i + 1))
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._films_table.setItem(row, 0, num_item)
                mat_combo = _make_material_combo(self._builtin_keys, "Polarizer")
                self._films_table.setCellWidget(row, 1, mat_combo)
                thickness_item = QTableWidgetItem("0.3")
                self._films_table.setItem(row, 2, thickness_item)
        else:
            while self._films_table.rowCount() > count:
                self._films_table.removeRow(self._films_table.rowCount() - 1)
        self._films_table.blockSignals(False)

    def get_optical_films(self) -> list[dict]:
        """Return list of {material: str, thickness_m: float}."""
        films = []
        for row in range(self._films_table.rowCount()):
            mat_combo = self._films_table.cellWidget(row, 1)
            mat = mat_combo.currentText() if mat_combo else "Polarizer"
            thickness_item = self._films_table.item(row, 2)
            try:
                thickness_mm = float(thickness_item.text()) if thickness_item else 0.3
            except ValueError:
                thickness_mm = 0.3
            films.append({"material": mat, "thickness_m": _m(thickness_mm)})
        return films

    def eled_sub(self) -> _EledLayerSubPage:
        return self._eled_sub

    def dled_sub(self) -> _DledLayerSubPage:
        return self._dled_sub


# ===========================================================================
# Page 4 — Boundary Conditions
# ===========================================================================

class BoundaryConditionsPage(QWidget):
    """Page 4: per-face boundary conditions (preset or custom h), ambient temp, radiation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Ambient + radiation
        global_group = QGroupBox("Global Settings")
        global_form = QFormLayout(global_group)

        self._ambient_spin = QDoubleSpinBox()
        self._ambient_spin.setRange(-40.0, 125.0)
        self._ambient_spin.setValue(25.0)
        self._ambient_spin.setSuffix(" \u00b0C")
        self._ambient_spin.setDecimals(1)
        global_form.addRow("Ambient temperature:", self._ambient_spin)

        self._radiation_cb = QCheckBox("Include linearized radiation")
        self._radiation_cb.setChecked(True)
        global_form.addRow("", self._radiation_cb)

        layout.addWidget(global_group)

        # Per-face table
        faces_group = QGroupBox("Face Boundary Conditions")
        faces_layout = QVBoxLayout(faces_group)

        self._face_table = QTableWidget(len(_FACE_LABELS), 3)
        self._face_table.setHorizontalHeaderLabels(["Face", "Preset", "h override (W/m\u00b2K)"])
        self._face_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._face_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._face_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._face_table.verticalHeader().setVisible(False)

        self._preset_combos: list[QComboBox] = []
        self._h_spins: list[QDoubleSpinBox] = []

        for row, face in enumerate(_FACE_LABELS):
            # Face label (read-only)
            face_item = QTableWidgetItem(face)
            face_item.setFlags(face_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._face_table.setItem(row, 0, face_item)

            # Preset combo
            preset_combo = QComboBox()
            preset_combo.addItems(list(_BC_PRESETS.keys()))
            preset_combo.setCurrentText("Natural convection")
            self._face_table.setCellWidget(row, 1, preset_combo)
            self._preset_combos.append(preset_combo)

            # h override spinbox
            h_spin = QDoubleSpinBox()
            h_spin.setRange(0.1, 500.0)
            h_spin.setValue(8.0)
            h_spin.setSuffix(" W/m\u00b2K")
            h_spin.setDecimals(1)
            h_spin.setEnabled(False)
            self._face_table.setCellWidget(row, 2, h_spin)
            self._h_spins.append(h_spin)

            # Wire preset change to enable/disable h spinbox
            def _make_handler(r: int):
                def _on_preset_changed(text: str) -> None:
                    is_custom = (text == "Custom")
                    self._h_spins[r].setEnabled(is_custom)
                    if not is_custom:
                        self._h_spins[r].setValue(_BC_PRESETS[text])
                return _on_preset_changed
            preset_combo.currentTextChanged.connect(_make_handler(row))

        faces_layout.addWidget(self._face_table)
        layout.addWidget(faces_group)

    def ambient_c(self) -> float:
        return self._ambient_spin.value()

    def include_radiation(self) -> bool:
        return self._radiation_cb.isChecked()

    def get_face_bc(self, face: str) -> tuple[float, bool]:
        """Return (h, include_radiation) for the given face label."""
        idx = _FACE_LABELS.index(face)
        preset = self._preset_combos[idx].currentText()
        if preset == "Custom":
            h = self._h_spins[idx].value()
        else:
            h = _BC_PRESETS[preset]
        return (h, self._radiation_cb.isChecked())


# ===========================================================================
# Page 5 — Mesh Configuration
# ===========================================================================

class MeshConfigPage(QWidget):
    """Page 5: max cell size and cells per interval."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        group = QGroupBox("Mesh Settings")
        form = QFormLayout(group)

        self._max_cell_spin = QDoubleSpinBox()
        self._max_cell_spin.setRange(0.1, 20.0)
        self._max_cell_spin.setValue(2.0)
        self._max_cell_spin.setSuffix(" mm")
        self._max_cell_spin.setDecimals(1)
        self._max_cell_spin.setToolTip(
            "Maximum cell size. Smaller values give higher accuracy but more cells."
        )
        self._max_cell_spin.valueChanged.connect(self._update_estimate)
        form.addRow("Max Cell Size:", self._max_cell_spin)

        self._cells_per_interval_spin = QSpinBox()
        self._cells_per_interval_spin.setRange(1, 10)
        self._cells_per_interval_spin.setValue(1)
        self._cells_per_interval_spin.setToolTip(
            "Number of cells per geometric interval (thickness segment)"
        )
        form.addRow("Cells per Interval:", self._cells_per_interval_spin)

        self._estimate_label = QLabel("~-- cells")
        form.addRow("Estimated cell count:", self._estimate_label)

        layout.addWidget(group)
        layout.addStretch()

        # Wire panel dims — updated externally via update_estimate()
        self._panel_w_m: float = 0.450
        self._panel_d_m: float = 0.300

    def set_panel_dims(self, panel_w_m: float, panel_d_m: float) -> None:
        self._panel_w_m = panel_w_m
        self._panel_d_m = panel_d_m
        self._update_estimate()

    def _update_estimate(self) -> None:
        cell_m = _m(self._max_cell_spin.value())
        if cell_m > 0:
            nx = max(1, round(self._panel_w_m / cell_m))
            ny = max(1, round(self._panel_d_m / cell_m))
            nz_approx = 10  # rough estimate for layer count
            n = nx * ny * nz_approx
            self._estimate_label.setText(f"~{n:,} cells (approx)")
        else:
            self._estimate_label.setText("~-- cells")

    def max_cell_size_m(self) -> float | None:
        v = self._max_cell_spin.value()
        return _m(v) if v > 0 else None

    def cells_per_interval(self) -> int:
        return self._cells_per_interval_spin.value()


# ===========================================================================
# Main Wizard Dialog
# ===========================================================================

_PAGE_TITLES = [
    "Step 1 of 6 — Architecture",
    "Step 2 of 6 — Panel Dimensions",
    "Step 3 of 6 — LED Configuration",
    "Step 4 of 6 — Layer Thicknesses",
    "Step 5 of 6 — Boundary Conditions",
    "Step 6 of 6 — Mesh Configuration",
]


class StackGeneratorWizard(QDialog):
    """Multi-page parametric display stack generator wizard.

    Opens as a QDialog; contains:
    - Left side (60%): step indicator + QStackedWidget of pages + nav buttons
    - Right side (40%): live Voxel3DView preview (updated on page transitions)

    Call ``wizard.exec()`` and check ``wizard.generated_project()`` on Accepted.
    """

    def __init__(self, materials: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Display Stack")
        self.resize(1200, 750)
        self.setMinimumSize(900, 600)

        self._materials = materials
        self._generated_project: VoxelProject | None = None
        self._current_page: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Splitter: left panel + right 3D preview ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        outer.addWidget(splitter)

        # ---- Left panel ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        # Step indicator label
        self._step_label = QLabel()
        self._step_label.setStyleSheet("font-weight: bold; font-size: 13pt;")
        left_layout.addWidget(self._step_label)

        # Pages
        self._page_stack = QStackedWidget()
        self._arch_page = ArchitecturePage()
        self._dims_page = PanelDimsPage()
        self._led_page = LEDConfigPage()
        self._layer_page = LayerThicknessPage()
        self._bc_page = BoundaryConditionsPage()
        self._mesh_page = MeshConfigPage()

        # Wire architecture change to sub-page updates
        self._arch_page._arch_combo.currentTextChanged.connect(self._on_arch_changed)

        # Wrap each page in a scroll area for small screens
        pages = [
            self._arch_page,
            self._dims_page,
            self._led_page,
            self._layer_page,
            self._bc_page,
            self._mesh_page,
        ]
        from PySide6.QtWidgets import QScrollArea
        for page in pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(page)
            self._page_stack.addWidget(scroll)

        left_layout.addWidget(self._page_stack, stretch=1)

        # Navigation buttons
        btn_layout = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._next_btn = QPushButton("Next")
        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setDefault(True)
        self._cancel_btn = QPushButton("Cancel")

        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._generate_btn.clicked.connect(self._on_finish)
        self._cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._back_btn)
        btn_layout.addWidget(self._next_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._generate_btn)
        btn_layout.addWidget(self._cancel_btn)
        left_layout.addLayout(btn_layout)

        # ---- Right panel: live 3D preview ----
        from thermal_sim.ui.voxel_3d_view import Voxel3DView
        self._preview = Voxel3DView()

        splitter.addWidget(left_widget)
        splitter.addWidget(self._preview)
        splitter.setSizes([720, 480])

        # Initial page state
        self._refresh_page_ui()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_back(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_page_ui()
            self._update_preview()

    def _go_next(self) -> None:
        if self._current_page < len(_PAGE_TITLES) - 1:
            self._current_page += 1
            self._refresh_page_ui()
            self._update_preview()

    def _refresh_page_ui(self) -> None:
        """Update step label, button visibility, and active page."""
        self._page_stack.setCurrentIndex(self._current_page)
        self._step_label.setText(_PAGE_TITLES[self._current_page])

        last = len(_PAGE_TITLES) - 1
        self._back_btn.setVisible(self._current_page > 0)
        self._next_btn.setVisible(self._current_page < last)
        self._generate_btn.setVisible(self._current_page == last)

        # Update mesh page with current panel dimensions when on that page
        if self._current_page == 5:
            self._mesh_page.set_panel_dims(
                self._dims_page.panel_w_m(),
                self._dims_page.panel_d_m(),
            )

    def _on_arch_changed(self, text: str) -> None:
        arch = "ELED" if "ELED" in text else "DLED"
        self._led_page.set_architecture(arch)
        self._layer_page.set_architecture(arch)

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        """Generate a partial project and update the 3D preview.

        Skips preview on incomplete or invalid data — never raises.
        """
        try:
            arch = self._arch_page.architecture()
            if arch == "ELED":
                params = self._collect_eled_params()
                from thermal_sim.generators.stack_generator import generate_eled
                project = generate_eled(params)
            else:
                params = self._collect_dled_params()
                from thermal_sim.generators.stack_generator import generate_dled
                project = generate_dled(params)
            self._preview.update_structure(project)
        except Exception as exc:
            logger.debug("Preview skipped: %s", exc)

    # ------------------------------------------------------------------
    # Parameter collection
    # ------------------------------------------------------------------

    def _collect_eled_params(self):
        from thermal_sim.generators.stack_generator import EledParams, EdgeLedConfig, OpticalFilm

        dims = self._dims_page
        layers = self._layer_page.eled_sub()
        bc = self._bc_page

        thick = layers.thicknesses()
        mats = layers.materials()

        # Edge LED configs
        edge_configs = self._led_page.eled_sub().get_edge_configs()

        def _edge_cfg(edge: str) -> EdgeLedConfig | None:
            if edge not in edge_configs:
                return None
            c = edge_configs[edge]
            return EdgeLedConfig(
                count=c["count"],
                led_width=c["led_width_m"],
                led_depth=c["led_depth_m"],
                led_height=c["led_height_m"],
                power_per_led=c["power_per_led"],
                margin=c["margin_m"],
            )

        # Optical films
        raw_films = self._layer_page.get_optical_films()
        optical_films = [OpticalFilm(material=f["material"], thickness=f["thickness_m"]) for f in raw_films]

        return EledParams(
            panel_w=dims.panel_w_m(),
            panel_d=dims.panel_d_m(),
            panel_h=thick["panel_h"],
            lgp_h=thick["lgp_h"],
            reflector_h=thick["reflector_h"],
            frame_back_h=thick["frame_back_h"],
            frame_wall_t=thick["frame_wall_t"],
            back_cover_h=thick["back_cover_h"],
            optical_films=optical_films,
            led_left=_edge_cfg("Left"),
            led_right=_edge_cfg("Right"),
            led_top=_edge_cfg("Top"),
            led_bottom=_edge_cfg("Bottom"),
            panel_material=mats["panel_material"],
            lgp_material=mats["lgp_material"],
            reflector_material=mats["reflector_material"],
            frame_material=mats["frame_material"],
            back_cover_material=mats["back_cover_material"],
            pcb_material=mats["pcb_material"],
            bc_top=bc.get_face_bc("Top"),
            bc_bottom=bc.get_face_bc("Bottom"),
            bc_front=bc.get_face_bc("Front"),
            bc_back=bc.get_face_bc("Back"),
            bc_left=bc.get_face_bc("Left"),
            bc_right=bc.get_face_bc("Right"),
            ambient_c=bc.ambient_c(),
            max_cell_size=self._mesh_page.max_cell_size_m(),
            cells_per_interval=self._mesh_page.cells_per_interval(),
        )

    def _collect_dled_params(self):
        from thermal_sim.generators.stack_generator import DledParams, OpticalFilm

        dims = self._dims_page
        layers = self._layer_page.dled_sub()
        led = self._led_page.dled_sub().get_dled_led_params()
        bc = self._bc_page

        thick = layers.thicknesses()
        mats = layers.materials()

        # Optical films
        raw_films = self._layer_page.get_optical_films()
        optical_films = [OpticalFilm(material=f["material"], thickness=f["thickness_m"]) for f in raw_films]

        return DledParams(
            panel_w=dims.panel_w_m(),
            panel_d=dims.panel_d_m(),
            panel_h=thick["panel_h"],
            diffuser_h=thick["diffuser_h"],
            air_cavity_h=thick["air_cavity_h"],
            pcb_h=thick["pcb_h"],
            reflector_h=thick["reflector_h"],
            frame_back_h=thick["frame_back_h"],
            frame_wall_t=thick["frame_wall_t"],
            back_cover_h=thick["back_cover_h"],
            optical_films=optical_films,
            led_rows=led["led_rows"],
            led_cols=led["led_cols"],
            led_pitch_x=led["led_pitch_x"],
            led_pitch_y=led["led_pitch_y"],
            led_offset_x=led["led_offset_x"],
            led_offset_y=led["led_offset_y"],
            led_width=led["led_width"],
            led_depth=led["led_depth"],
            led_height=led["led_height"],
            led_power=led["led_power"],
            panel_material=mats["panel_material"],
            diffuser_material=mats["diffuser_material"],
            pcb_material=mats["pcb_material"],
            reflector_material=mats["reflector_material"],
            frame_material=mats["frame_material"],
            back_cover_material=mats["back_cover_material"],
            bc_top=bc.get_face_bc("Top"),
            bc_bottom=bc.get_face_bc("Bottom"),
            bc_front=bc.get_face_bc("Front"),
            bc_back=bc.get_face_bc("Back"),
            bc_left=bc.get_face_bc("Left"),
            bc_right=bc.get_face_bc("Right"),
            ambient_c=bc.ambient_c(),
            max_cell_size=self._mesh_page.max_cell_size_m(),
            cells_per_interval=self._mesh_page.cells_per_interval(),
        )

    # ------------------------------------------------------------------
    # Generate / Finish
    # ------------------------------------------------------------------

    def _on_finish(self) -> None:
        """Collect all params, call generator, store result, accept dialog."""
        arch = self._arch_page.architecture()
        try:
            if arch == "ELED":
                params = self._collect_eled_params()
                from thermal_sim.generators.stack_generator import generate_eled
                project = generate_eled(params)
            else:
                params = self._collect_dled_params()
                from thermal_sim.generators.stack_generator import generate_dled
                project = generate_dled(params)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Failed to generate {arch} display stack:\n\n{exc}",
            )
            return

        self._generated_project = project
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generated_project(self) -> "VoxelProject | None":
        """Return the generated VoxelProject, or None if not yet generated."""
        return self._generated_project
