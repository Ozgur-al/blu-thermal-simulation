"""Unit tests for TableDataParser — table-to-model round-trip."""
from __future__ import annotations

import sys
import pytest

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

# Ensure a QApplication exists for widget creation.
@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


def _make_table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
    """Helper to build a populated QTableWidget."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    for row_data in rows:
        row = table.rowCount()
        table.insertRow(row)
        for col, val in enumerate(row_data):
            table.setItem(row, col, QTableWidgetItem(val))
    return table


class TestParseMaterialsTable:
    def test_single_material_round_trip(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "k in-plane [W/mK]", "k through [W/mK]",
                   "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"]
        rows = [["Copper", "400", "400", "8900", "385", "0.05"]]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_materials_table(table)
        assert "Copper" in result
        mat = result["Copper"]
        assert mat.name == "Copper"
        assert mat.k_in_plane == pytest.approx(400.0)
        assert mat.k_through == pytest.approx(400.0)
        assert mat.density == pytest.approx(8900.0)
        assert mat.specific_heat == pytest.approx(385.0)
        assert mat.emissivity == pytest.approx(0.05)

    def test_multiple_materials(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "k in-plane [W/mK]", "k through [W/mK]",
                   "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"]
        rows = [
            ["Al", "205", "205", "2700", "900", "0.1"],
            ["FR4", "0.3", "0.3", "1850", "1200", "0.9"],
        ]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_materials_table(table)
        assert len(result) == 2
        assert "Al" in result
        assert "FR4" in result

    def test_empty_rows_are_skipped(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "k in-plane [W/mK]", "k through [W/mK]",
                   "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"]
        rows = [["", "", "", "", "", ""], ["Steel", "50", "50", "7800", "490", "0.8"]]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_materials_table(table)
        assert len(result) == 1
        assert "Steel" in result


class TestParseLayersTable:
    def test_single_layer_round_trip(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"]
        rows = [["Glass", "Borosilicate", "0.002", "0.0001"]]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_layers_table(table)
        assert len(result) == 1
        layer = result[0]
        assert layer.name == "Glass"
        assert layer.material == "Borosilicate"
        assert layer.thickness == pytest.approx(0.002)
        assert layer.interface_resistance_to_next == pytest.approx(0.0001)

    def test_interface_resistance_defaults_to_zero(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"]
        rows = [["PCB", "FR4", "0.001", ""]]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_layers_table(table)
        assert result[0].interface_resistance_to_next == pytest.approx(0.0)

    def test_multiple_layers_order_preserved(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"]
        rows = [
            ["Bottom", "Al", "0.003", "0"],
            ["Middle", "FR4", "0.001", "0"],
            ["Top", "Glass", "0.002", "0"],
        ]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_layers_table(table)
        assert [l.name for l in result] == ["Bottom", "Middle", "Top"]


class TestValidateTables:
    def _make_empty_tables(self):
        """Return minimal table dict that validate_tables expects."""
        mat_table = _make_table(
            ["Name", "k in-plane [W/mK]", "k through [W/mK]",
             "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"],
            []
        )
        layer_table = _make_table(
            ["Name", "Material", "Thickness [m]", "Interface R to next [m\u00b2K/W]"],
            []
        )
        source_table = _make_table(
            ["Name", "Layer", "Power [W]", "Shape", "x [m]", "y [m]",
             "width [m]", "height [m]", "radius [m]"],
            []
        )
        led_table = _make_table(
            ["Name", "Layer", "Center x [m]", "Center y [m]", "Count x",
             "Count y", "Pitch x [m]", "Pitch y [m]", "Power per LED [W]",
             "LED footprint", "LED width [m]", "LED height [m]", "LED radius [m]"],
            []
        )
        probe_table = _make_table(["Name", "Layer", "x [m]", "y [m]"], [])
        return {
            "materials": mat_table,
            "layers": layer_table,
            "sources": source_table,
            "led_arrays": led_table,
            "probes": probe_table,
        }

    def test_catches_missing_materials(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        tables = self._make_empty_tables()
        errors = TableDataParser.validate_tables(tables)
        assert any("material" in e.lower() for e in errors)

    def test_catches_missing_layers(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        tables = self._make_empty_tables()
        # Add a material so we pass that check
        tables["materials"].insertRow(0)
        for col, val in enumerate(["Al", "205", "205", "2700", "900", "0.1"]):
            tables["materials"].setItem(0, col, QTableWidgetItem(val))
        errors = TableDataParser.validate_tables(tables)
        assert any("layer" in e.lower() for e in errors)

    def test_catches_unknown_material_reference(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        tables = self._make_empty_tables()
        # Add a material "Al"
        tables["materials"].insertRow(0)
        for col, val in enumerate(["Al", "205", "205", "2700", "900", "0.1"]):
            tables["materials"].setItem(0, col, QTableWidgetItem(val))
        # Add a layer that references "FR4" (unknown)
        tables["layers"].insertRow(0)
        for col, val in enumerate(["MyLayer", "FR4", "0.001", "0"]):
            tables["layers"].setItem(0, col, QTableWidgetItem(val))
        errors = TableDataParser.validate_tables(tables)
        assert any("unknown material" in e.lower() for e in errors)

    def test_no_errors_for_valid_config(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        tables = self._make_empty_tables()
        # Material
        tables["materials"].insertRow(0)
        for col, val in enumerate(["Al", "205", "205", "2700", "900", "0.1"]):
            tables["materials"].setItem(0, col, QTableWidgetItem(val))
        # Layer referencing "Al"
        tables["layers"].insertRow(0)
        for col, val in enumerate(["Base", "Al", "0.003", "0"]):
            tables["layers"].setItem(0, col, QTableWidgetItem(val))
        errors = TableDataParser.validate_tables(tables)
        assert errors == []
