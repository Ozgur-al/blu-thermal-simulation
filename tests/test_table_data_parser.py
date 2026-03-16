"""Unit tests for TableDataParser — table-to-model round-trip."""
from __future__ import annotations

import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path

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
        headers = ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]"]
        # Table shows mm; model expects metres.  2 mm -> 0.002 m
        rows = [["Glass", "Borosilicate", "2", "0.0001"]]
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
        headers = ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]"]
        rows = [["PCB", "FR4", "1", ""]]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_layers_table(table)
        assert result[0].interface_resistance_to_next == pytest.approx(0.0)

    def test_multiple_layers_order_preserved(self):
        from thermal_sim.ui.table_data_parser import TableDataParser
        headers = ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]"]
        rows = [
            ["Bottom", "Al", "3", "0"],
            ["Middle", "FR4", "1", "0"],
            ["Top", "Glass", "2", "0"],
        ]
        table = _make_table(headers, rows)
        result = TableDataParser.parse_layers_table(table)
        assert [l.name for l in result] == ["Bottom", "Middle", "Top"]


class TestParseLedArraysTable:
    def test_edge_mode_rows_can_round_trip_with_preserved_metadata(self):
        from thermal_sim.ui.table_data_parser import TableDataParser

        headers = [
            "Name", "Layer", "Center x [mm]", "Center y [mm]", "Count x",
            "Count y", "Pitch x [mm]", "Pitch y [mm]", "Power per LED [W]",
            "LED footprint", "LED width [mm]", "LED height [mm]", "LED radius [mm]",
        ]
        rows = [[
            "ELED Array", "LGP", "150", "60", "36", "36", "0", "0",
            "0.3", "rectangle", "4", "1.5", "1",
        ]]
        table = _make_table(headers, rows)
        extras = {
            0: {
                "mode": "edge",
                "edge_config": "bottom",
                "edge_offset": 0.0025,
                "panel_width": 0.3,
                "panel_height": 0.12,
                "z_position": "distributed",
            }
        }

        result = TableDataParser.parse_led_arrays_table(
            table,
            led_array_extras=extras,
            panel_width=0.3,
            panel_height=0.12,
        )

        assert len(result) == 1
        arr = result[0]
        assert arr.mode == "edge"
        assert arr.edge_config == "bottom"
        assert arr.z_position == "distributed"
        assert arr.panel_width == pytest.approx(0.3)
        assert arr.panel_height == pytest.approx(0.12)
        assert len(arr.expand()) == 36


def test_main_window_build_project_preserves_edge_led_array_metadata(qapp):
    from thermal_sim.io.project_io import load_project
    from thermal_sim.ui.main_window import MainWindow

    window = MainWindow()
    project = load_project(Path("examples/ELED.json"))
    window._populate_ui_from_project(project)

    rebuilt = window._build_project_from_ui()

    assert len(rebuilt.led_arrays) == 1
    arr = rebuilt.led_arrays[0]
    assert arr.mode == "edge"
    assert arr.edge_config == "bottom"
    assert arr.z_position == "distributed"
    assert arr.panel_width == pytest.approx(rebuilt.width)
    assert arr.panel_height == pytest.approx(rebuilt.height)

    window.close()


def test_main_window_eled_edge_path_overlaps_fr4_and_air(qapp):
    script = r"""
import json
import os
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QApplication
from thermal_sim.core.geometry import Grid2D
from thermal_sim.io.project_io import load_project
from thermal_sim.models.stack_templates import generate_edge_zones
from thermal_sim.solvers.network_builder import _source_mask
from thermal_sim.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
window = MainWindow()
window._populate_ui_from_project(load_project(Path('examples/ELED.json')))
window._apply_edge_frame()
rebuilt = window._build_project_from_ui()
arr = rebuilt.led_arrays[0]
layer = next(layer for layer in rebuilt.layers if layer.name == arr.layer)
zones = generate_edge_zones(layer, rebuilt.width, rebuilt.height)
grid = Grid2D(rebuilt.width, rebuilt.height, rebuilt.mesh.nx, rebuilt.mesh.ny)
xx, yy = np.meshgrid(grid.x_centers(), grid.y_centers())
first_led = arr.expand()[0]
iy_arr, ix_arr = np.where(_source_mask(first_led, xx, yy, grid.dx, grid.dy))
overlapped_materials = set()
for iy, ix in zip(iy_arr, ix_arr):
    cx = grid.x_centers()[ix]
    cy = grid.y_centers()[iy]
    half_dx = grid.dx / 2.0
    half_dy = grid.dy / 2.0
    for zone in zones:
        sx0 = zone.x - zone.width / 2.0
        sx1 = zone.x + zone.width / 2.0
        sy0 = zone.y - zone.height / 2.0
        sy1 = zone.y + zone.height / 2.0
        if ((cx + half_dx > sx0) and (cx - half_dx < sx1) and (cy + half_dy > sy0) and (cy - half_dy < sy1)):
            overlapped_materials.add(zone.material)

payload = {
    'bottom_layers': [entry.material for entry in layer.edge_layers['bottom']],
    'back_cover_bottom_layers': [
        entry.material
        for entry in next(layer for layer in rebuilt.layers if layer.name == 'Back Cover').edge_layers['bottom']
    ],
    'target': window._eled_layer_combo.currentText(),
    'offset_mm': rebuilt.led_arrays[0].edge_offset * 1000.0,
    'materials': sorted(overlapped_materials),
}
print(json.dumps(payload), flush=True)
os._exit(0)
"""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["bottom_layers"] == ["Steel", "FR4", "Air Gap"]
    assert payload["back_cover_bottom_layers"] == ["Steel", "Air Gap"]
    assert payload["target"] == "LGP / FR4 (bottom)"
    assert payload["offset_mm"] == pytest.approx(8.0)
    assert "FR4" in payload["materials"]
    assert "Air Gap" in payload["materials"]


def test_main_window_save_reload_preserves_eled_ui_state(qapp):
    script = r"""
import json
import os
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from thermal_sim.io.project_io import load_project, save_project
from thermal_sim.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
window = MainWindow()
window._populate_ui_from_project(load_project(Path('examples/ELED.json')))
window.arch_combo.setCurrentText('ELED')
r = window.materials_table.rowCount()
window.materials_table.insertRow(r)
vals = ['MyMat', '1.1', '1.2', '1234', '567', '0.77', 'User']
for c, v in enumerate(vals):
    window.materials_table.setItem(r, c, QTableWidgetItem(v))
window._material_source['MyMat'] = 'User'
project = window._build_project_from_ui()
fd, name = tempfile.mkstemp(suffix='.json')
os.close(fd)
path = Path(name)
save_project(project, path)

window2 = MainWindow()
window2._populate_ui_from_project(load_project(path))
rebuilt = window2._build_project_from_ui()
payload = {
    'arch': window2.arch_combo.currentText(),
    'stack_index': window2._led_arrays_stack.currentIndex(),
    'eled_count': window2._eled_count.value(),
    'eled_power': window2._eled_power.value(),
    'led_mode': rebuilt.led_arrays[0].mode if rebuilt.led_arrays else None,
    'edge_config': rebuilt.led_arrays[0].edge_config if rebuilt.led_arrays else None,
    'has_mymat': any(
        (window2.materials_table.item(row, 0) and window2.materials_table.item(row, 0).text() == 'MyMat')
        for row in range(window2.materials_table.rowCount())
    ),
    'mymat_type': next(
        (
            window2.materials_table.item(row, 6).text()
            for row in range(window2.materials_table.rowCount())
            if window2.materials_table.item(row, 0) and window2.materials_table.item(row, 0).text() == 'MyMat'
        ),
        None,
    ),
}
print(json.dumps(payload), flush=True)
path.unlink(missing_ok=True)
os._exit(0)
"""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["arch"] == "ELED"
    assert payload["stack_index"] == 2
    assert payload["eled_count"] == 20
    assert payload["eled_power"] == pytest.approx(0.3)
    assert payload["led_mode"] == "edge"
    assert payload["edge_config"] == "bottom"
    assert payload["has_mymat"] is True
    assert payload["mymat_type"] == "User"


class TestValidateTables:
    def _make_empty_tables(self):
        """Return minimal table dict that validate_tables expects."""
        mat_table = _make_table(
            ["Name", "k in-plane [W/mK]", "k through [W/mK]",
             "Density [kg/m\u00b3]", "Specific heat [J/kgK]", "Emissivity"],
            []
        )
        layer_table = _make_table(
            ["Name", "Material", "Thickness [mm]", "Interface R to next [m\u00b2K/W]"],
            []
        )
        source_table = _make_table(
            ["Name", "Layer", "Power [W]", "Shape", "x [mm]", "y [mm]",
             "width [mm]", "height [mm]", "radius [mm]"],
            []
        )
        led_table = _make_table(
            ["Name", "Layer", "Center x [mm]", "Center y [mm]", "Count x",
             "Count y", "Pitch x [mm]", "Pitch y [mm]", "Power per LED [W]",
             "LED footprint", "LED width [mm]", "LED height [mm]", "LED radius [mm]"],
            []
        )
        probe_table = _make_table(["Name", "Layer", "x [mm]", "y [mm]"], [])
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
        for col, val in enumerate(["MyLayer", "FR4", "1", "0"]):
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
        for col, val in enumerate(["Base", "Al", "3", "0"]):
            tables["layers"].setItem(0, col, QTableWidgetItem(val))
        errors = TableDataParser.validate_tables(tables)
        assert errors == []
