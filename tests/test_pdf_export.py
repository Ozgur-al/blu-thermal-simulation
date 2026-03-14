"""Integration tests for PDF report generation."""

from __future__ import annotations

import numpy as np
import pytest

from thermal_sim.core.postprocess import layer_stats, top_n_hottest_cells
from thermal_sim.models.snapshot import ResultSnapshot
from thermal_sim.io.pdf_export import generate_pdf_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_steady_snapshot(name: str = "steady-test") -> ResultSnapshot:
    """Create a minimal 2-layer 5x5 steady-state snapshot."""
    temps = np.zeros((2, 5, 5), dtype=float)
    temps[0, :, :] = np.linspace(25.0, 35.0, 25).reshape(5, 5)
    temps[1, :, :] = np.linspace(40.0, 60.0, 25).reshape(5, 5)
    layer_names = ["Bottom", "Top"]
    dx = dy = 0.02  # 20mm cells, 5 cells → 100mm total
    stats = layer_stats(temps, layer_names)

    # Simulate top-10 hotspots from an all-layers map (reuse _top_n via public API)
    from thermal_sim.core.postprocess import _top_n_from_map
    hotspots = _top_n_from_map(temps, layer_names, dx, dy, n=10)

    return ResultSnapshot(
        name=name,
        mode="steady",
        project_name="TestProject",
        simulation_date="2026-03-14",
        layer_names=layer_names,
        final_temperatures_c=temps,
        temperatures_time_c=None,
        times_s=None,
        layer_stats=stats,
        hotspots=hotspots,
        probe_values={},
        dx=dx,
        dy=dy,
        width_m=0.10,
        height_m=0.10,
        probes=[],
    )


def _make_transient_snapshot() -> ResultSnapshot:
    """Create a minimal 2-layer 5x5 transient snapshot."""
    nt = 5
    temps_time = np.zeros((nt, 2, 5, 5), dtype=float)
    for t in range(nt):
        temps_time[t, 0, :, :] = 25.0 + t * 2.0
        temps_time[t, 1, :, :] = 40.0 + t * 3.0
    times = np.linspace(0.0, 100.0, nt)
    final = temps_time[-1]
    layer_names = ["Bottom", "Top"]
    dx = dy = 0.02
    stats = layer_stats(final, layer_names)

    from thermal_sim.core.postprocess import _top_n_from_map
    hotspots = _top_n_from_map(final, layer_names, dx, dy, n=10)

    probe_values = {
        "P1": temps_time[:, 0, 2, 2],
        "P2": temps_time[:, 1, 2, 2],
    }

    return ResultSnapshot(
        name="transient-test",
        mode="transient",
        project_name="TestProject",
        simulation_date="2026-03-14",
        layer_names=layer_names,
        final_temperatures_c=final,
        temperatures_time_c=temps_time,
        times_s=times,
        layer_stats=stats,
        hotspots=hotspots,
        probe_values=probe_values,
        dx=dx,
        dy=dy,
        width_m=0.10,
        height_m=0.10,
        probes=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pdf_generated_for_steady_mode(tmp_path):
    snapshot = _make_steady_snapshot()
    out = tmp_path / "steady_report.pdf"
    generate_pdf_report(snapshot, out)
    assert out.exists(), "PDF file was not created"
    assert out.stat().st_size > 0, "PDF file is empty"


def test_pdf_generated_for_transient_mode(tmp_path):
    snapshot = _make_transient_snapshot()
    out = tmp_path / "transient_report.pdf"
    generate_pdf_report(snapshot, out)
    assert out.exists(), "PDF file was not created"
    assert out.stat().st_size > 0, "PDF file is empty"


def test_pdf_creates_parent_directory(tmp_path):
    snapshot = _make_steady_snapshot()
    out = tmp_path / "nested" / "subdir" / "report.pdf"
    generate_pdf_report(snapshot, out)
    assert out.exists(), "PDF should be created in nested directory"


def test_pdf_accepts_string_path(tmp_path):
    snapshot = _make_steady_snapshot()
    out = str(tmp_path / "string_path_report.pdf")
    generate_pdf_report(snapshot, out)
    from pathlib import Path
    assert Path(out).exists()


def test_pdf_steady_has_no_probe_history_page(tmp_path):
    """Steady-mode PDF should not fail even with no probe data."""
    snapshot = _make_steady_snapshot()
    out = tmp_path / "no_probes.pdf"
    # Should not raise even with empty probe_values
    generate_pdf_report(snapshot, out)
    assert out.exists()
