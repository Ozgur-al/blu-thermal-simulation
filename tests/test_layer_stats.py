"""Unit tests for layer_stats() and top_n_hottest_cells_for_layer()."""

from __future__ import annotations

import numpy as np
import pytest

from thermal_sim.core.postprocess import layer_stats, top_n_hottest_cells_for_layer
from thermal_sim.models.snapshot import ResultSnapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def three_layer_map():
    """3-layer 5x5 temperature map with known values.

    Layer 0: all 25.0 C (uniform)
    Layer 1: linearly ranging from 30.0 to 40.0 C
    Layer 2: all 50.0 C (uniform)
    """
    arr = np.zeros((3, 5, 5), dtype=float)
    arr[0, :, :] = 25.0
    # Layer 1: values from 30..40 across 25 cells
    arr[1, :, :] = np.linspace(30.0, 40.0, 25).reshape(5, 5)
    arr[2, :, :] = 50.0
    return arr


# ---------------------------------------------------------------------------
# layer_stats() tests
# ---------------------------------------------------------------------------

def test_layer_stats_returns_one_dict_per_layer(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    assert len(result) == 3


def test_layer_stats_has_required_keys(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    for entry in result:
        assert set(entry.keys()) >= {"layer", "t_max_c", "t_avg_c", "t_min_c", "delta_t_c"}


def test_layer_stats_layer_names(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    assert [r["layer"] for r in result] == ["A", "B", "C"]


def test_layer_stats_uniform_layer_zero_delta(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    # Layer A is uniform at 25.0
    a = result[0]
    assert a["t_max_c"] == pytest.approx(25.0)
    assert a["t_min_c"] == pytest.approx(25.0)
    assert a["t_avg_c"] == pytest.approx(25.0)
    assert a["delta_t_c"] == pytest.approx(0.0)


def test_layer_stats_nonuniform_layer_correct_values(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    b = result[1]
    assert b["t_max_c"] == pytest.approx(40.0)
    assert b["t_min_c"] == pytest.approx(30.0)
    assert b["t_avg_c"] == pytest.approx(35.0)
    assert b["delta_t_c"] == pytest.approx(10.0)


def test_layer_stats_delta_t_equals_max_minus_min(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    for entry in result:
        assert entry["delta_t_c"] == pytest.approx(entry["t_max_c"] - entry["t_min_c"])


def test_layer_stats_second_uniform_layer(three_layer_map):
    result = layer_stats(three_layer_map, ["A", "B", "C"])
    c = result[2]
    assert c["t_max_c"] == pytest.approx(50.0)
    assert c["delta_t_c"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# top_n_hottest_cells_for_layer() tests
# ---------------------------------------------------------------------------

def test_top_n_hottest_cells_returns_n_items(three_layer_map):
    result = top_n_hottest_cells_for_layer(three_layer_map, layer_idx=1, layer_name="B", dx=0.01, dy=0.01, n=3)
    assert len(result) == 3


def test_top_n_hottest_cells_all_have_correct_layer_name(three_layer_map):
    result = top_n_hottest_cells_for_layer(three_layer_map, layer_idx=1, layer_name="B", dx=0.01, dy=0.01, n=5)
    for entry in result:
        assert entry["layer"] == "B"


def test_top_n_hottest_cells_sorted_descending(three_layer_map):
    result = top_n_hottest_cells_for_layer(three_layer_map, layer_idx=1, layer_name="B", dx=0.01, dy=0.01, n=5)
    temps = [r["temperature_c"] for r in result]
    assert temps == sorted(temps, reverse=True)


def test_top_n_hottest_cells_hottest_has_max_temperature(three_layer_map):
    result = top_n_hottest_cells_for_layer(three_layer_map, layer_idx=1, layer_name="B", dx=0.01, dy=0.01, n=3)
    # The hottest cell in layer 1 should be ~40.0
    assert result[0]["temperature_c"] == pytest.approx(40.0)


def test_top_n_hottest_cells_has_coordinate_keys(three_layer_map):
    result = top_n_hottest_cells_for_layer(three_layer_map, layer_idx=2, layer_name="C", dx=0.01, dy=0.01, n=2)
    for entry in result:
        assert "x_m" in entry
        assert "y_m" in entry
        assert "temperature_c" in entry


# ---------------------------------------------------------------------------
# ResultSnapshot construction tests
# ---------------------------------------------------------------------------

def test_result_snapshot_can_be_constructed():
    snap = ResultSnapshot(
        name="test-run",
        mode="steady",
        project_name="TestProject",
        simulation_date="2026-03-14",
        layer_names=["Top", "Bottom"],
        final_temperatures_c=np.ones((2, 5, 5)) * 30.0,
        temperatures_time_c=None,
        times_s=None,
        layer_stats=[{"layer": "Top", "t_max_c": 30.0, "t_avg_c": 30.0, "t_min_c": 30.0, "delta_t_c": 0.0}],
        hotspots=[],
        probe_values={},
        dx=0.01,
        dy=0.01,
        width_m=0.05,
        height_m=0.05,
        probes=[],
    )
    assert snap.name == "test-run"
    assert snap.mode == "steady"
    assert snap.final_temperatures_c.shape == (2, 5, 5)
    assert snap.temperatures_time_c is None
    assert snap.times_s is None


def test_result_snapshot_transient_fields():
    times = np.linspace(0, 10, 5)
    temps_time = np.ones((5, 2, 5, 5)) * 30.0
    snap = ResultSnapshot(
        name="transient-run",
        mode="transient",
        project_name="TestProject",
        simulation_date="2026-03-14",
        layer_names=["Top", "Bottom"],
        final_temperatures_c=np.ones((2, 5, 5)) * 30.0,
        temperatures_time_c=temps_time,
        times_s=times,
        layer_stats=[],
        hotspots=[],
        probe_values={"P1": times},
        dx=0.01,
        dy=0.01,
        width_m=0.05,
        height_m=0.05,
    )
    assert snap.temperatures_time_c.shape == (5, 2, 5, 5)
    assert snap.times_s is not None


def test_result_snapshot_is_mutable():
    """ResultSnapshot must NOT be frozen — numpy arrays are not hashable."""
    snap = ResultSnapshot(
        name="test",
        mode="steady",
        project_name="P",
        simulation_date="2026-03-14",
        layer_names=[],
        final_temperatures_c=np.zeros((0, 0, 0)),
        temperatures_time_c=None,
        times_s=None,
        layer_stats=[],
        hotspots=[],
        probe_values={},
        dx=0.01,
        dy=0.01,
        width_m=0.05,
        height_m=0.05,
    )
    # Should be able to modify a field without raising TypeError
    snap.name = "modified"
    assert snap.name == "modified"
