"""SweepDialog — QDialog for defining a parametric sweep.

The dialog lets the user select a parameter to sweep, define target values,
and choose between steady-state and transient solver modes.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from thermal_sim.core.sweep_engine import SweepConfig
from thermal_sim.models.project import DisplayProject


# ---------------------------------------------------------------------------
# Sweep parameter categories
# ---------------------------------------------------------------------------

# Each entry: (display label, parameter path template with {idx} or {name})
_CATEGORIES = [
    "Layer thickness",
    "Material k_in_plane",
    "Material k_through",
    "Boundary convection_h (top)",
    "Boundary convection_h (bottom)",
    "Heat source power",
]


class SweepDialog(QDialog):
    """Dialog for defining a parametric sweep.

    Parameters
    ----------
    project:
        The current project — used to populate target dropdowns with actual
        layer, material, and heat source names.
    parent:
        Optional parent widget.
    """

    def __init__(self, project: DisplayProject, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Parametric Sweep")
        self.setMinimumWidth(420)
        self._project = project
        self._config: SweepConfig | None = None

        self._build_ui()
        # Populate target dropdown for the initial category selection.
        self._on_category_changed(self._category_combo.currentText())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Category selector
        self._category_combo = QComboBox()
        self._category_combo.addItems(_CATEGORIES)
        self._category_combo.currentTextChanged.connect(self._on_category_changed)
        form.addRow("Parameter", self._category_combo)

        # Target selector (specific layer / material / boundary / source)
        self._target_combo = QComboBox()
        form.addRow("Target", self._target_combo)

        # Values entry
        self._values_edit = QLineEdit()
        self._values_edit.setPlaceholderText("e.g. 0.001, 0.002, 0.003  or  0.001:0.001:0.005")
        form.addRow("Values", self._values_edit)

        # Mode selector
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["steady", "transient"])
        form.addRow("Solver mode", self._mode_combo)

        layout.addLayout(form)

        # Hint label
        hint = QLabel(
            "Values: comma-separated (0.001, 0.002, 0.003) or range (min:step:max)"
        )
        hint.setStyleSheet("color: grey; font-size: 10px;")
        layout.addWidget(hint)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_category_changed(self, category: str) -> None:
        """Repopulate the target dropdown when the category changes."""
        self._target_combo.clear()
        project = self._project

        if category == "Layer thickness":
            for i, layer in enumerate(project.layers):
                self._target_combo.addItem(
                    layer.name, f"layers[{i}].thickness"
                )

        elif category in ("Material k_in_plane", "Material k_through"):
            field = "k_in_plane" if "k_in_plane" in category else "k_through"
            for name in project.materials:
                self._target_combo.addItem(
                    name, f"materials.{name}.{field}"
                )

        elif category == "Boundary convection_h (top)":
            self._target_combo.addItem("top", "boundaries.top.convection_h")

        elif category == "Boundary convection_h (bottom)":
            self._target_combo.addItem("bottom", "boundaries.bottom.convection_h")

        elif category == "Heat source power":
            for i, src in enumerate(project.heat_sources):
                self._target_combo.addItem(
                    src.name, f"heat_sources[{i}].power_w"
                )

    def _on_accepted(self) -> None:
        """Validate inputs; accept dialog only on success."""
        try:
            values = self._parse_values(self._values_edit.text().strip())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid values", str(exc))
            return

        if len(values) < 2:
            QMessageBox.warning(
                self,
                "Not enough values",
                "Please enter at least 2 values for the sweep.",
            )
            return

        parameter = self._target_combo.currentData()
        if parameter is None:
            QMessageBox.warning(
                self,
                "No target selected",
                "The selected category has no items to sweep.",
            )
            return

        mode = self._mode_combo.currentText()
        self._config = SweepConfig(parameter=parameter, values=values, mode=mode)
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> SweepConfig | None:
        """Return the validated SweepConfig, or None if the dialog was cancelled."""
        return self._config

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_values(text: str) -> list[float]:
        """Parse the values text field.

        Accepts two formats:
        - Comma-separated floats: ``"0.001, 0.002, 0.003"``
        - Range notation: ``"min:step:max"`` (inclusive, uses np.arange)

        Returns:
            List of float values.

        Raises:
            ValueError: if the text cannot be parsed.
        """
        if not text:
            raise ValueError("Values field must not be empty.")

        # Range notation: "min:step:max"
        if ":" in text and "," not in text:
            parts = text.split(":")
            if len(parts) != 3:
                raise ValueError(
                    "Range notation must be 'min:step:max' (e.g. 0.001:0.001:0.005)."
                )
            try:
                start, step, stop = float(parts[0]), float(parts[1]), float(parts[2])
            except ValueError:
                raise ValueError(
                    "Range notation requires numeric min, step, and max values."
                )
            if step <= 0:
                raise ValueError("Step must be positive.")
            # Include the endpoint by adding a small fraction of step.
            values = list(np.arange(start, stop + step * 0.5, step))
            return [float(v) for v in values]

        # Comma-separated list
        parts = [p.strip() for p in text.split(",")]
        values = []
        for p in parts:
            if not p:
                continue
            try:
                values.append(float(p))
            except ValueError:
                raise ValueError(f"Could not parse '{p}' as a number.")
        return values
