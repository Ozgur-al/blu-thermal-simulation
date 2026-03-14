"""Tests for HeatSource power profile (PowerBreakpoint + power_at_time)."""

from __future__ import annotations

import math

import pytest

from thermal_sim.models.heat_source import HeatSource, PowerBreakpoint


# ---------------------------------------------------------------------------
# PowerBreakpoint basic tests
# ---------------------------------------------------------------------------

def test_power_breakpoint_to_dict_round_trip() -> None:
    bp = PowerBreakpoint(time_s=1.5, power_w=10.0)
    d = bp.to_dict()
    assert d == {"time_s": 1.5, "power_w": 10.0}
    bp2 = PowerBreakpoint.from_dict(d)
    assert bp2.time_s == 1.5
    assert bp2.power_w == 10.0


# ---------------------------------------------------------------------------
# power_at_time — no profile (backward compat)
# ---------------------------------------------------------------------------

def _make_rect_source(**kwargs) -> HeatSource:
    defaults = dict(
        name="src",
        layer="L1",
        power_w=5.0,
        shape="rectangle",
        width=0.01,
        height=0.01,
    )
    defaults.update(kwargs)
    return HeatSource(**defaults)


def test_no_profile_returns_constant_power_w() -> None:
    src = _make_rect_source(power_w=7.5)
    assert src.power_profile is None
    for t in [0.0, 0.5, 1.0, 100.0]:
        assert src.power_at_time(t) == pytest.approx(7.5)


def test_empty_profile_returns_power_w() -> None:
    # Empty list treated same as None
    src = _make_rect_source(power_w=3.0, power_profile=[])
    for t in [0.0, 1.0]:
        assert src.power_at_time(t) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# power_at_time — linear interpolation
# ---------------------------------------------------------------------------

def test_profile_two_points_interpolation() -> None:
    """Profile [(0,10),(1,0)] — linear ramp from 10 to 0 over 1 second.

    Note: t=1.0 wraps to t=0.0 (start of next period) → returns 10.0.
    The last point is exclusive (period boundary).
    """
    profile = [PowerBreakpoint(0.0, 10.0), PowerBreakpoint(1.0, 0.0)]
    src = _make_rect_source(power_w=10.0, power_profile=profile)
    assert src.power_at_time(0.0) == pytest.approx(10.0)
    assert src.power_at_time(0.5) == pytest.approx(5.0)
    assert src.power_at_time(0.9999) == pytest.approx(0.001, abs=1e-3)  # near end of period


# ---------------------------------------------------------------------------
# power_at_time — looping
# ---------------------------------------------------------------------------

def test_profile_loops_at_period() -> None:
    """t=1.5 must match t=0.5 (same phase in the second period)."""
    profile = [PowerBreakpoint(0.0, 10.0), PowerBreakpoint(1.0, 0.0)]
    src = _make_rect_source(power_w=10.0, power_profile=profile)
    assert src.power_at_time(1.5) == pytest.approx(5.0, rel=1e-9)


def test_profile_loops_multiple_periods() -> None:
    """t=2.5 must also match t=0.5 (third period)."""
    profile = [PowerBreakpoint(0.0, 10.0), PowerBreakpoint(1.0, 0.0)]
    src = _make_rect_source(power_w=10.0, power_profile=profile)
    assert src.power_at_time(2.5) == pytest.approx(5.0, rel=1e-9)


# ---------------------------------------------------------------------------
# power_at_time — edge cases
# ---------------------------------------------------------------------------

def test_single_breakpoint_returns_power_w() -> None:
    """Single breakpoint: profile period is zero -> fall back to power_w."""
    profile = [PowerBreakpoint(0.0, 5.0)]
    src = _make_rect_source(power_w=5.0, power_profile=profile)
    for t in [0.0, 1.0, 99.0]:
        assert src.power_at_time(t) == pytest.approx(5.0)


def test_profile_at_exact_period_start() -> None:
    """t exactly equal to profile_end wraps to 0.0 (modulo), returns start value."""
    profile = [PowerBreakpoint(0.0, 10.0), PowerBreakpoint(2.0, 0.0)]
    src = _make_rect_source(power_w=10.0, power_profile=profile)
    # t=2.0 -> t_wrapped = 2.0 % 2.0 = 0.0 -> power = 10.0
    assert src.power_at_time(2.0) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

def test_to_dict_includes_power_profile_when_present() -> None:
    profile = [PowerBreakpoint(0.0, 10.0), PowerBreakpoint(1.0, 0.0)]
    src = _make_rect_source(power_w=10.0, power_profile=profile)
    d = src.to_dict()
    assert "power_profile" in d
    assert d["power_profile"] == [{"time_s": 0.0, "power_w": 10.0}, {"time_s": 1.0, "power_w": 0.0}]


def test_to_dict_omits_power_profile_when_absent() -> None:
    src = _make_rect_source()
    d = src.to_dict()
    # Should be None or absent — both are acceptable
    assert d.get("power_profile") is None


def test_from_dict_round_trips_power_profile() -> None:
    profile = [PowerBreakpoint(0.0, 8.0), PowerBreakpoint(0.5, 4.0), PowerBreakpoint(1.0, 0.0)]
    src = _make_rect_source(power_w=8.0, power_profile=profile)
    d = src.to_dict()
    src2 = HeatSource.from_dict(d)
    assert src2.power_profile is not None
    assert len(src2.power_profile) == 3
    assert src2.power_profile[0].time_s == pytest.approx(0.0)
    assert src2.power_profile[1].power_w == pytest.approx(4.0)
    assert src2.power_profile[2].time_s == pytest.approx(1.0)


def test_from_dict_without_power_profile_gives_none() -> None:
    """Loading a legacy dict (no power_profile key) must produce power_profile=None."""
    d = {
        "name": "src",
        "layer": "L1",
        "power_w": 5.0,
        "shape": "rectangle",
        "width": 0.01,
        "height": 0.01,
    }
    src = HeatSource.from_dict(d)
    assert src.power_profile is None


def test_from_dict_with_null_power_profile_gives_none() -> None:
    """Loading a dict with power_profile: null must produce power_profile=None."""
    d = {
        "name": "src",
        "layer": "L1",
        "power_w": 5.0,
        "shape": "rectangle",
        "width": 0.01,
        "height": 0.01,
        "power_profile": None,
    }
    src = HeatSource.from_dict(d)
    assert src.power_profile is None


# ---------------------------------------------------------------------------
# Validation: first breakpoint must start at t=0
# ---------------------------------------------------------------------------

def test_profile_first_breakpoint_not_at_zero_raises() -> None:
    with pytest.raises(ValueError, match="time_s=0"):
        _make_rect_source(
            power_w=10.0,
            power_profile=[PowerBreakpoint(0.5, 10.0), PowerBreakpoint(1.0, 0.0)],
        )


# ---------------------------------------------------------------------------
# Task 2: ThermalNetwork b_vector split + transient solver power profile tests
# ---------------------------------------------------------------------------

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig
from thermal_sim.solvers.network_builder import ThermalNetwork, build_thermal_network
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver


def _single_node_project_with_profile(
    power_w: float,
    initial_c: float,
    total_time_s: float,
    time_step_s: float = 0.1,
    power_profile=None,
) -> DisplayProject:
    """Build a 1×1 single-layer project for transient power profile tests."""
    material = Material(
        name="TestMat",
        k_in_plane=2.0,
        k_through=2.0,
        density=800.0,
        specific_heat=800.0,
        emissivity=0.9,
    )
    src = HeatSource(
        name="Load",
        layer="Core",
        power_w=power_w,
        shape="full",
        power_profile=power_profile,
    )
    return DisplayProject(
        name="Profile test",
        width=0.1,
        height=0.1,
        materials={"TestMat": material},
        layers=[Layer(name="Core", material="TestMat", thickness=0.0002)],
        heat_sources=[src],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=25.0, convection_h=100.0, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=25.0, convection_h=100.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=25.0, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(
            time_step_s=time_step_s,
            total_time_s=total_time_s,
            output_interval_s=time_step_s,
            method="implicit_euler",
        ),
        initial_temperature_c=initial_c,
    )


def test_b_vector_property_backward_compatible() -> None:
    """ThermalNetwork.b_vector must equal b_boundary + b_sources."""
    import numpy as np
    project = _single_node_project_with_profile(power_w=5.0, initial_c=25.0, total_time_s=1.0)
    network = build_thermal_network(project)
    # b_vector property must equal b_boundary + b_sources
    np.testing.assert_array_almost_equal(
        network.b_vector, network.b_boundary + network.b_sources
    )


def test_steady_state_unaffected_by_b_vector_split() -> None:
    """Existing steady-state solver must still pass after b_vector split."""
    area = 0.12 * 0.08
    amb = 23.0
    q = 1.7
    mat1 = Material("L1", 0.8, 0.8, 2000.0, 900.0, 0.9)
    mat2 = Material("L2", 10.0, 10.0, 2000.0, 900.0, 0.9)
    t1 = 0.001
    t2 = 0.002
    r_int = 4e-4
    h_top = 12.0
    h_bottom = 4.0

    project = DisplayProject(
        name="1D chain",
        width=0.12,
        height=0.08,
        materials={"L1": mat1, "L2": mat2},
        layers=[
            Layer(name="Bottom", material="L1", thickness=t1, interface_resistance_to_next=r_int),
            Layer(name="Top", material="L2", thickness=t2),
        ],
        heat_sources=[HeatSource(name="Power", layer="Bottom", power_w=q, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=amb, convection_h=h_bottom, include_radiation=False),
            side=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )
    result = SteadyStateSolver().solve(project)

    g_bottom = 1.0 / (t1 / (2.0 * mat1.k_through * area) + 1.0 / (h_bottom * area))
    g_top = 1.0 / (t2 / (2.0 * mat2.k_through * area) + 1.0 / (h_top * area))
    g_between = 1.0 / (
        t1 / (2.0 * mat1.k_through * area)
        + r_int / area
        + t2 / (2.0 * mat2.k_through * area)
    )
    a = g_bottom + g_between
    b = -g_between
    c = -g_between
    d = g_top + g_between
    rhs0 = q + g_bottom * amb
    rhs1 = g_top * amb
    det = a * d - b * c
    expected_t0 = (rhs0 * d - b * rhs1) / det
    expected_t1 = (a * rhs1 - rhs0 * c) / det

    assert math.isclose(float(result.temperatures_c[0, 0, 0]), expected_t0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(float(result.temperatures_c[1, 0, 0]), expected_t1, rel_tol=1e-9, abs_tol=1e-9)


def test_constant_power_profile_matches_no_profile(
) -> None:
    """Benchmark D: single-node transient with constant power_profile must match power_profile=None."""
    # Two identical projects except one has a constant power profile
    p_no_profile = _single_node_project_with_profile(
        power_w=4.0, initial_c=25.0, total_time_s=2.0, time_step_s=0.01
    )
    # Constant profile: power stays at 4.0 for t in [0, 100] — same as no profile
    profile = [PowerBreakpoint(0.0, 4.0), PowerBreakpoint(100.0, 4.0)]
    p_with_profile = _single_node_project_with_profile(
        power_w=4.0, initial_c=25.0, total_time_s=2.0, time_step_s=0.01,
        power_profile=profile,
    )
    res_no = TransientSolver().solve(p_no_profile)
    res_with = TransientSolver().solve(p_with_profile)

    # Final temperatures must be essentially identical
    t_no = float(res_no.final_temperatures_c[0, 0, 0])
    t_with = float(res_with.final_temperatures_c[0, 0, 0])
    assert math.isclose(t_no, t_with, rel_tol=0.0, abs_tol=0.01)


def test_square_wave_profile_transient_matches_analytical() -> None:
    """Benchmark B: single-node RC transient with square-wave power profile.

    Square wave: Q=5W for T_on=1s, then Q=0 for T_off=1s (period=2s).
    Step transitions approximated with tiny epsilon gap so np.interp gives a
    near-perfect step function. dt=0.01s over 10s.
    Compare against analytical piecewise-exponential solution (1% tolerance).
    """
    import numpy as np

    width = 0.1
    height = 0.1
    area = width * height
    k = 2.0
    density = 800.0
    cp = 800.0
    thickness = 0.0002
    h_conv = 100.0
    Q = 5.0
    T_amb = 25.0
    T0 = T_amb
    dt = 0.001
    T_on = 1.0
    T_period = 2.0
    eps = 1e-9

    g_each = 1.0 / (thickness / (2.0 * k * area) + 1.0 / (h_conv * area))
    G_total = 2.0 * g_each
    C_node = density * cp * thickness * area

    T_ss_on = T_amb + Q / G_total
    T_ss_off = T_amb
    tau = C_node / G_total

    def analytical_step(t_vals: np.ndarray) -> np.ndarray:
        """Exact response to a true step square-wave."""
        T = np.empty_like(t_vals)
        T_curr = float(T0)
        t_prev = 0.0
        for i, t in enumerate(t_vals):
            dt_seg = t - t_prev
            t_mid = 0.5 * (t + t_prev)
            t_in_period = t_mid % T_period
            T_ss = T_ss_on if t_in_period < T_on else T_ss_off
            T_curr = T_ss + (T_curr - T_ss) * math.exp(-dt_seg / tau)
            T[i] = T_curr
            t_prev = t
        return T

    # Step-like square wave: Q from 0 to T_on, then 0 from T_on to T_period.
    profile = [
        PowerBreakpoint(0.0, Q),
        PowerBreakpoint(T_on, Q),
        PowerBreakpoint(T_on + eps, 0.0),
        PowerBreakpoint(T_period, 0.0),
    ]
    project = _single_node_project_with_profile(
        power_w=Q, initial_c=T0, total_time_s=10.0, time_step_s=dt,
        power_profile=profile,
    )
    result = TransientSolver().solve(project)

    t_sim = result.times_s
    T_sim = result.temperatures_time_c[:, 0, 0, 0]
    T_ref = analytical_step(t_sim[1:])

    T_rise = T_ss_on - T_amb
    tol = 0.01 * T_rise

    max_err = float(np.max(np.abs(T_sim[1:] - T_ref)))
    assert max_err < tol, (
        f"Max error {max_err:.4f} C exceeds 1% tolerance {tol:.4f} C. "
        f"Transient solver is not applying per-step power scaling."
    )
