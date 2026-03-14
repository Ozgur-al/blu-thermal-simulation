"""Stateless table-to-model and model-to-table conversion helpers.

TableDataParser contains no reference to MainWindow — it operates on plain
QTableWidget and boundary-widget-dict arguments so it can be used and tested
without a running MainWindow instance.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource, LEDArray
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig
from thermal_sim.models.probe import Probe


class TableDataParser:
    """Stateless helpers for converting between Qt table widgets and model objects.

    All methods are either static or class methods — no instance state is required.
    """

    # ------------------------------------------------------------------
    # Static widget helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_text(table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _cell_float(
        table: QTableWidget,
        row: int,
        col: int,
        default: float | None = None,
    ) -> float:
        text = TableDataParser._cell_text(table, row, col)
        if text == "":
            if default is None:
                header = table.horizontalHeaderItem(col)
                col_name = header.text() if header else f"column {col + 1}"
                raise ValueError(f"Row {row + 1}, '{col_name}' requires a numeric value")
            return default
        return float(text)

    @staticmethod
    def _cell_optional_float(table: QTableWidget, row: int, col: int) -> float | None:
        text = TableDataParser._cell_text(table, row, col)
        return None if text == "" else float(text)

    @staticmethod
    def _new_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        if len(headers) <= 6:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setDefaultSectionSize(100)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    @staticmethod
    def _add_table_row(table: QTableWidget, values: list[str] | None = None) -> None:
        row = table.rowCount()
        table.insertRow(row)
        values = values or []
        for col in range(table.columnCount()):
            table.setItem(row, col, QTableWidgetItem(values[col] if col < len(values) else ""))

    @staticmethod
    def _set_table_rows(table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(0)
        for row in rows:
            TableDataParser._add_table_row(table, row)

    @staticmethod
    def _double_spin(
        minimum: float,
        maximum: float,
        value: float,
        decimals: int = 6,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        return spin

    # ------------------------------------------------------------------
    # Parse methods — table widget → model objects
    # ------------------------------------------------------------------

    @staticmethod
    def parse_materials_table(table: QTableWidget) -> dict[str, Material]:
        """Parse a materials QTableWidget and return dict[name, Material]."""
        materials: dict[str, Material] = {}
        for row in range(table.rowCount()):
            name = TableDataParser._cell_text(table, row, 0)
            if not name:
                continue
            materials[name] = Material(
                name=name,
                k_in_plane=TableDataParser._cell_float(table, row, 1),
                k_through=TableDataParser._cell_float(table, row, 2),
                density=TableDataParser._cell_float(table, row, 3),
                specific_heat=TableDataParser._cell_float(table, row, 4),
                emissivity=TableDataParser._cell_float(table, row, 5),
            )
        return materials

    @staticmethod
    def parse_layers_table(table: QTableWidget) -> list[Layer]:
        """Parse a layers QTableWidget and return list[Layer]."""
        layers: list[Layer] = []
        for row in range(table.rowCount()):
            name = TableDataParser._cell_text(table, row, 0)
            if not name:
                continue
            layers.append(
                Layer(
                    name=name,
                    material=TableDataParser._cell_text(table, row, 1),
                    thickness=TableDataParser._cell_float(table, row, 2),
                    interface_resistance_to_next=TableDataParser._cell_float(
                        table, row, 3, default=0.0
                    ),
                )
            )
        return layers

    @staticmethod
    def parse_sources_table(table: QTableWidget) -> list[HeatSource]:
        """Parse a heat sources QTableWidget and return list[HeatSource]."""
        heat_sources: list[HeatSource] = []
        for row in range(table.rowCount()):
            name = TableDataParser._cell_text(table, row, 0)
            if not name:
                continue
            heat_sources.append(
                HeatSource(
                    name=name,
                    layer=TableDataParser._cell_text(table, row, 1),
                    power_w=TableDataParser._cell_float(table, row, 2),
                    shape=TableDataParser._cell_text(table, row, 3) or "rectangle",
                    x=TableDataParser._cell_float(table, row, 4, default=0.0),
                    y=TableDataParser._cell_float(table, row, 5, default=0.0),
                    width=TableDataParser._cell_optional_float(table, row, 6),
                    height=TableDataParser._cell_optional_float(table, row, 7),
                    radius=TableDataParser._cell_optional_float(table, row, 8),
                )
            )
        return heat_sources

    @staticmethod
    def parse_led_arrays_table(table: QTableWidget) -> list[LEDArray]:
        """Parse an LED arrays QTableWidget and return list[LEDArray]."""
        led_arrays: list[LEDArray] = []
        for row in range(table.rowCount()):
            name = TableDataParser._cell_text(table, row, 0)
            if not name:
                continue
            led_arrays.append(
                LEDArray(
                    name=name,
                    layer=TableDataParser._cell_text(table, row, 1),
                    center_x=TableDataParser._cell_float(table, row, 2),
                    center_y=TableDataParser._cell_float(table, row, 3),
                    count_x=int(TableDataParser._cell_float(table, row, 4)),
                    count_y=int(TableDataParser._cell_float(table, row, 5)),
                    pitch_x=TableDataParser._cell_float(table, row, 6),
                    pitch_y=TableDataParser._cell_float(table, row, 7),
                    power_per_led_w=TableDataParser._cell_float(table, row, 8),
                    footprint_shape=TableDataParser._cell_text(table, row, 9) or "rectangle",
                    led_width=TableDataParser._cell_optional_float(table, row, 10),
                    led_height=TableDataParser._cell_optional_float(table, row, 11),
                    led_radius=TableDataParser._cell_optional_float(table, row, 12),
                )
            )
        return led_arrays

    @staticmethod
    def parse_probes_table(table: QTableWidget) -> list[Probe]:
        """Parse a probes QTableWidget and return list[Probe]."""
        probes: list[Probe] = []
        for row in range(table.rowCount()):
            name = TableDataParser._cell_text(table, row, 0)
            if not name:
                continue
            probes.append(
                Probe(
                    name=name,
                    layer=TableDataParser._cell_text(table, row, 1),
                    x=TableDataParser._cell_float(table, row, 2),
                    y=TableDataParser._cell_float(table, row, 3),
                )
            )
        return probes

    @staticmethod
    def read_boundary_widgets(widgets: dict) -> SurfaceBoundary:
        """Read boundary condition values from a widget dict."""
        emiss_txt = widgets["emiss"].text().strip()
        emiss = None if emiss_txt == "" else float(emiss_txt)
        return SurfaceBoundary(
            ambient_c=widgets["ambient"].value(),
            convection_h=widgets["h"].value(),
            include_radiation=widgets["rad"].isChecked(),
            emissivity_override=emiss,
        )

    @staticmethod
    def set_boundary_widgets(widgets: dict, boundary: SurfaceBoundary) -> None:
        """Populate boundary widget dict from a SurfaceBoundary model object."""
        widgets["ambient"].setValue(boundary.ambient_c)
        widgets["h"].setValue(boundary.convection_h)
        widgets["rad"].setChecked(boundary.include_radiation)
        widgets["emiss"].setText(
            "" if boundary.emissivity_override is None else f"{boundary.emissivity_override:g}"
        )

    # ------------------------------------------------------------------
    # Compound methods
    # ------------------------------------------------------------------

    @staticmethod
    def build_project_from_tables(
        tables_dict: dict,
        spinboxes_dict: dict,
        boundary_widgets_dict: dict,
    ) -> DisplayProject:
        """Build a DisplayProject from the complete set of UI widget collections.

        Args:
            tables_dict: Keys — "materials", "layers", "sources", "led_arrays", "probes"
            spinboxes_dict: Keys — "name", "width", "height", "nx", "ny",
                            "initial_temp", "dt", "total_time", "output_interval"
            boundary_widgets_dict: Keys — "top", "bottom", "side" (each is a widget dict)
        """
        materials = TableDataParser.parse_materials_table(tables_dict["materials"])
        layers = TableDataParser.parse_layers_table(tables_dict["layers"])
        heat_sources = TableDataParser.parse_sources_table(tables_dict["sources"])
        led_arrays = TableDataParser.parse_led_arrays_table(tables_dict["led_arrays"])
        probes = TableDataParser.parse_probes_table(tables_dict["probes"])

        boundaries = BoundaryConditions(
            top=TableDataParser.read_boundary_widgets(boundary_widgets_dict["top"]),
            bottom=TableDataParser.read_boundary_widgets(boundary_widgets_dict["bottom"]),
            side=TableDataParser.read_boundary_widgets(boundary_widgets_dict["side"]),
        )

        sb = spinboxes_dict
        return DisplayProject(
            name=sb["name"].text().strip() or "Untitled Project",
            width=sb["width"].value(),
            height=sb["height"].value(),
            layers=layers,
            materials=materials,
            heat_sources=heat_sources,
            led_arrays=led_arrays,
            boundaries=boundaries,
            mesh=MeshConfig(nx=sb["nx"].value(), ny=sb["ny"].value()),
            transient=TransientConfig(
                time_step_s=sb["dt"].value(),
                total_time_s=sb["total_time"].value(),
                output_interval_s=sb["output_interval"].value(),
                method="implicit_euler",
            ),
            initial_temperature_c=sb["initial_temp"].value(),
            probes=probes,
        )

    @staticmethod
    def validate_tables(tables_dict: dict) -> list[str]:
        """Validate table widget contents and return a list of error strings.

        Mirrors the logic from the original MainWindow._validate_project().
        """
        errors: list[str] = []

        materials_table = tables_dict["materials"]
        layers_table = tables_dict["layers"]
        sources_table = tables_dict["sources"]
        led_arrays_table = tables_dict["led_arrays"]
        probes_table = tables_dict["probes"]

        mat_names: set[str] = set()
        for row in range(materials_table.rowCount()):
            name = TableDataParser._cell_text(materials_table, row, 0)
            if name:
                mat_names.add(name)
        if not mat_names:
            errors.append("No materials defined.")

        layer_names: list[str] = []
        for row in range(layers_table.rowCount()):
            name = TableDataParser._cell_text(layers_table, row, 0)
            if not name:
                continue
            layer_names.append(name)
            mat = TableDataParser._cell_text(layers_table, row, 1)
            if mat and mat not in mat_names:
                errors.append(f"Layer '{name}' references unknown material '{mat}'.")
            thick = TableDataParser._cell_text(layers_table, row, 2)
            if thick:
                try:
                    if float(thick) <= 0:
                        errors.append(f"Layer '{name}' thickness must be positive.")
                except ValueError:
                    errors.append(f"Layer '{name}' has invalid thickness '{thick}'.")
        if not layer_names:
            errors.append("No layers defined.")

        layer_set = set(layer_names)
        for row in range(sources_table.rowCount()):
            name = TableDataParser._cell_text(sources_table, row, 0)
            layer = TableDataParser._cell_text(sources_table, row, 1)
            if name and layer and layer not in layer_set:
                errors.append(f"Heat source '{name}' references unknown layer '{layer}'.")

        for row in range(led_arrays_table.rowCount()):
            name = TableDataParser._cell_text(led_arrays_table, row, 0)
            layer = TableDataParser._cell_text(led_arrays_table, row, 1)
            if name and layer and layer not in layer_set:
                errors.append(f"LED array '{name}' references unknown layer '{layer}'.")

        for row in range(probes_table.rowCount()):
            name = TableDataParser._cell_text(probes_table, row, 0)
            layer = TableDataParser._cell_text(probes_table, row, 1)
            if name and layer and layer not in layer_set:
                errors.append(f"Probe '{name}' references unknown layer '{layer}'.")

        return errors

    @staticmethod
    def populate_tables_from_project(project, tables_dict: dict) -> None:
        """Write a DisplayProject's data into table widgets.

        This is the inverse of build_project_from_tables — it takes a
        DisplayProject and populates the tables_dict widgets from its data.

        Args:
            project:     A DisplayProject instance.
            tables_dict: Keys — "materials", "layers", "sources", "led_arrays", "probes"
        """
        mat_rows = [
            [
                mat.name,
                f"{mat.k_in_plane:g}",
                f"{mat.k_through:g}",
                f"{mat.density:g}",
                f"{mat.specific_heat:g}",
                f"{mat.emissivity:g}",
            ]
            for mat in project.materials.values()
        ]
        TableDataParser._set_table_rows(tables_dict["materials"], mat_rows)

        layer_rows = [
            [
                layer.name,
                layer.material,
                f"{layer.thickness:g}",
                f"{layer.interface_resistance_to_next:g}",
            ]
            for layer in project.layers
        ]
        TableDataParser._set_table_rows(tables_dict["layers"], layer_rows)

        source_rows = [
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
            for source in project.heat_sources
        ]
        TableDataParser._set_table_rows(tables_dict["sources"], source_rows)

        led_rows = [
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
            for array in project.led_arrays
        ]
        TableDataParser._set_table_rows(tables_dict["led_arrays"], led_rows)

        probe_rows = [
            [probe.name, probe.layer, f"{probe.x:g}", f"{probe.y:g}"]
            for probe in project.probes
        ]
        TableDataParser._set_table_rows(tables_dict["probes"], probe_rows)

    @staticmethod
    def remove_selected_row(parent: QWidget, table: QTableWidget) -> None:
        """Remove the currently selected row after a confirmation dialog.

        Args:
            parent: Parent widget for the QMessageBox dialog.
            table: The table to remove a row from.
        """
        row = table.currentRow()
        if row < 0:
            return
        name = TableDataParser._cell_text(table, row, 0) or f"row {row + 1}"
        reply = QMessageBox.question(
            parent,
            "Remove entry",
            f"Remove '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            table.removeRow(row)
