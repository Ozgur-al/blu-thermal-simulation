import math
from pathlib import Path

import numpy as np
import pytest

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource, PowerBreakpoint
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver
from thermal_sim.io.project_io import load_project
from thermal_sim.visualization.plotting import (
    plot_validation_comparison,
    plot_validation_transient_comparison,
)


def test_1d_two_layer_resistance_chain_matches_hand_calculation() -> None:
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

    # 2-node thermal network solved analytically by nodal equation.
    g_bottom = 1.0 / (t1 / (2.0 * mat1.k_through * area) + 1.0 / (h_bottom * area))
    g_top = 1.0 / (t2 / (2.0 * mat2.k_through * area) + 1.0 / (h_top * area))
    g_between = 1.0 / (
        t1 / (2.0 * mat1.k_through * area)
        + r_int / area
        + t2 / (2.0 * mat2.k_through * area)
    )

    # [g_bottom+g_between, -g_between] [T0] = [q + g_bottom*amb]
    # [-g_between, g_top+g_between]   [T1]   [g_top*amb]
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


def test_1d_three_layer_resistance_chain_matches_hand_calculation() -> None:
    """Benchmark A: 1D three-layer resistance chain (steady-state).

    Three layers stacked bottom-to-top, each with a single node (1x1 mesh).
    Heat injected at the bottom layer; convection on top and bottom surfaces.
    Two interface resistances between adjacent layers.
    Solved analytically via 3-node nodal equations and compared to solver output.
    Tolerance: rel_tol=1e-9 (exact sparse solve vs exact hand calc).
    """
    width = 0.12
    height = 0.08
    area = width * height
    amb = 23.0
    q = 1.7

    mat1 = Material("M1", 0.8, 0.8, 2000.0, 900.0, 0.9)
    mat2 = Material("M2", 10.0, 10.0, 2000.0, 900.0, 0.9)
    mat3 = Material("M3", 1.5, 1.5, 2000.0, 900.0, 0.9)

    t1 = 0.001   # bottom layer thickness
    t2 = 0.002   # middle layer thickness
    t3 = 0.0015  # top layer thickness
    r_int_12 = 4e-4  # interface resistance (m^2 K/W) between bottom and middle
    r_int_23 = 2e-4  # interface resistance between middle and top

    h_top = 12.0
    h_bottom = 4.0

    project = DisplayProject(
        name="3-layer chain",
        width=width,
        height=height,
        materials={"M1": mat1, "M2": mat2, "M3": mat3},
        layers=[
            Layer(name="Bottom", material="M1", thickness=t1, interface_resistance_to_next=r_int_12),
            Layer(name="Middle", material="M2", thickness=t2, interface_resistance_to_next=r_int_23),
            Layer(name="Top", material="M3", thickness=t3),
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

    # --- Hand calculation (3-node nodal equations) ---
    # Node 0 = Bottom, Node 1 = Middle, Node 2 = Top
    #
    # Conductances:
    #   g_bot:  bottom half-layer conduction in series with bottom convection
    #   g_01:   top half of layer0 + interface12 + bottom half of layer1 (in series)
    #   g_12:   top half of layer1 + interface23 + bottom half of layer2 (in series)
    #   g_top:  top half-layer conduction in series with top convection
    #
    # Nodal balance:
    #   Node 0: (g_bot + g_01)*T0 - g_01*T1 = Q + g_bot*T_amb
    #   Node 1: -g_01*T0 + (g_01 + g_12)*T1 - g_12*T2 = g_12*... wait — no source at node 1
    #           -g_01*T0 + (g_01 + g_12)*T1 - g_12*T2 = 0
    #   Node 2: -g_12*T1 + (g_12 + g_top)*T2 = g_top*T_amb

    g_bot = 1.0 / (t1 / (2.0 * mat1.k_through * area) + 1.0 / (h_bottom * area))
    g_top = 1.0 / (t3 / (2.0 * mat3.k_through * area) + 1.0 / (h_top * area))
    g_01 = 1.0 / (
        t1 / (2.0 * mat1.k_through * area)
        + r_int_12 / area
        + t2 / (2.0 * mat2.k_through * area)
    )
    g_12 = 1.0 / (
        t2 / (2.0 * mat2.k_through * area)
        + r_int_23 / area
        + t3 / (2.0 * mat3.k_through * area)
    )

    # Build 3x3 matrix A and RHS b
    # Row 0: (g_bot + g_01)*T0 - g_01*T1 + 0*T2 = Q + g_bot*T_amb
    # Row 1: -g_01*T0 + (g_01 + g_12)*T1 - g_12*T2 = 0
    # Row 2: 0*T0 - g_12*T1 + (g_12 + g_top)*T2 = g_top*T_amb
    A = np.array([
        [g_bot + g_01,    -g_01,           0.0         ],
        [-g_01,           g_01 + g_12,    -g_12        ],
        [0.0,            -g_12,            g_12 + g_top],
    ])
    rhs = np.array([q + g_bot * amb, 0.0, g_top * amb])
    T_expected = np.linalg.solve(A, rhs)

    t0_num = float(result.temperatures_c[0, 0, 0])  # Bottom
    t1_num = float(result.temperatures_c[1, 0, 0])  # Middle
    t2_num = float(result.temperatures_c[2, 0, 0])  # Top

    assert math.isclose(t0_num, T_expected[0], rel_tol=1e-9), (
        f"Bottom node: numerical {t0_num:.6f} C, expected {T_expected[0]:.6f} C"
    )
    assert math.isclose(t1_num, T_expected[1], rel_tol=1e-9), (
        f"Middle node: numerical {t1_num:.6f} C, expected {T_expected[1]:.6f} C"
    )
    assert math.isclose(t2_num, T_expected[2], rel_tol=1e-9), (
        f"Top node: numerical {t2_num:.6f} C, expected {T_expected[2]:.6f} C"
    )


def test_single_node_rc_with_square_wave_power_matches_analytical() -> None:
    """Benchmark B: single-node RC transient with square-wave power profile.

    A 1-layer, 1x1 mesh network is driven by a square-wave power profile that
    turns on for T_on seconds and off for T_off seconds.  Because the power
    profile is piecewise-linear the 'square wave' is approximated by using
    very fine ramp transitions (one timestep wide).  The analytical solution
    is a piecewise-exponential evaluated at the end of each half-period.

    The test evaluates temperatures only at even multiples of T_period where
    the analytical piecewise-exponential solution can be applied exactly.
    Tolerance: rel_tol=0.01 (1%).
    """
    width = 0.10
    height = 0.10
    area = width * height
    k = 10.0
    density = 2700.0
    cp = 900.0
    thickness = 0.002
    h_top = 15.0
    h_bottom = 0.0
    amb = 25.0
    q = 2.0
    T_on = 0.5    # ON duration (s)
    T_off = 0.5   # OFF duration (s)
    T_period = T_on + T_off   # 1.0 s
    total = 2.0   # 2 full cycles
    dt = 0.01     # timestep

    # Network parameters (1x1 mesh, single top-surface convection)
    # g = 1 / (thickness/(2*k*area) + 1/(h_top*area))
    g_top = 1.0 / (thickness / (2.0 * k * area) + 1.0 / (h_top * area))
    G_total = g_top  # only top convection (h_bottom=0)
    C_node = density * cp * thickness * area

    T_ss_on = amb + q / G_total
    T_ss_off = amb
    tau = C_node / G_total

    # Analytical piecewise-exponential solution evaluated at half-period ends.
    # We track temperature step by step only at t = 0.5, 1.0, 1.5, 2.0 s.
    def analytical_at_half_periods(n_periods: int) -> list[float]:
        """Return temperature at end of each half-period (ON then OFF alternating)."""
        T_curr = amb  # start at ambient
        results = []
        for cycle in range(n_periods):
            # ON phase: T(T_on) = T_ss_on + (T_curr - T_ss_on)*exp(-T_on/tau)
            T_curr = T_ss_on + (T_curr - T_ss_on) * math.exp(-T_on / tau)
            results.append(T_curr)
            # OFF phase: T(T_off) = T_ss_off + (T_curr - T_ss_off)*exp(-T_off/tau)
            T_curr = T_ss_off + (T_curr - T_ss_off) * math.exp(-T_off / tau)
            results.append(T_curr)
        return results

    expected_temps = analytical_at_half_periods(n_periods=2)
    # expected_temps[0] = T at end of first ON (t=0.5)
    # expected_temps[1] = T at end of first OFF (t=1.0)
    # expected_temps[2] = T at end of second ON (t=1.5)
    # expected_temps[3] = T at end of second OFF (t=2.0)

    # For a step-change square wave via piecewise-linear interpolation:
    # Use 4-breakpoint profile with transitions occurring within a single dt:
    #   [0, Q], [T_on - dt, Q], [T_on, 0], [T_period - dt, 0]
    # Period = T_period - dt (the profile loops at this time).
    # This makes ON phase constant Q for most of [0, T_on] and OFF constant 0.
    epsilon = dt  # transition width = 1 timestep
    profile = [
        PowerBreakpoint(0.0, q),
        PowerBreakpoint(T_on - epsilon, q),
        PowerBreakpoint(T_on, 0.0),
        PowerBreakpoint(T_period - epsilon, 0.0),
    ]
    # Profile period = T_period - epsilon (the last breakpoint time)

    mat = Material("RC", k, k, density, cp, 0.9)
    project = DisplayProject(
        name="RC square wave",
        width=width,
        height=height,
        materials={"RC": mat},
        layers=[Layer(name="L", material="RC", thickness=thickness)],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=q, shape="full", power_profile=profile)],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=amb, convection_h=h_bottom, include_radiation=False),
            side=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(
            time_step_s=dt,
            total_time_s=total,
            output_interval_s=dt,
            method="implicit_euler",
        ),
        initial_temperature_c=amb,
    )
    result = TransientSolver().solve(project)

    # Extract simulated temperatures at half-period ends (nearest sample)
    check_times = [T_on, T_period, T_on + T_period, T_period + T_period]
    for i, (t_check, t_expected) in enumerate(zip(check_times, expected_temps)):
        # Find sample index closest to t_check
        idx = int(np.argmin(np.abs(result.times_s - t_check)))
        t_sim = float(result.temperatures_time_c[idx, 0, 0, 0])
        T_rise = abs(T_ss_on - T_ss_off)
        # Allow 1% relative tolerance on temperature rise above ambient
        assert math.isclose(t_sim, t_expected, rel_tol=0.01, abs_tol=0.01 * T_rise), (
            f"At t={t_check}s (phase {'ON' if i % 2 == 0 else 'OFF'} end): "
            f"numerical {t_sim:.4f} C, expected {t_expected:.4f} C"
        )


def test_two_node_lateral_spreading_matches_hand_calculation() -> None:
    """Benchmark C: two-node lateral heat spreading (steady-state).

    A single layer with a 2x1 mesh.  Power is injected in the left cell only.
    Convection on the top surface cools both cells.  The lateral conductance
    couples the two nodes.  Solved analytically via a 2-node nodal system.
    Tolerance: rel_tol=1e-6.
    """
    width = 0.04   # m
    height = 0.02  # m
    thickness = 0.003  # m
    k = 50.0
    density = 2000.0
    cp = 900.0
    h_top = 10.0
    amb = 25.0
    q = 0.5  # W (in left cell only)

    # Mesh: 2 cells in x, 1 in y
    # Cell dimensions
    dx = width / 2      # = 0.02 m
    dy = height / 1     # = 0.02 m
    cell_area = dx * dy  # = 4e-4 m^2

    mat = Material("Spread", k, k, density, cp, 0.9)

    project = DisplayProject(
        name="2-node lateral",
        width=width,
        height=height,
        materials={"Spread": mat},
        layers=[Layer(name="L", material="Spread", thickness=thickness)],
        heat_sources=[
            HeatSource(
                name="LeftPower",
                layer="L",
                power_w=q,
                shape="rectangle",
                x=dx / 2,       # center of left cell = 0.01 m
                y=dy / 2,       # center of bottom row = 0.01 m
                width=dx - 0.001,   # slightly smaller than cell width to stay in left cell
                height=dy - 0.001,  # slightly smaller than cell height
            )
        ],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
            side=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=2, ny=1),
    )
    result = SteadyStateSolver().solve(project)

    # --- Hand calculation (2-node nodal equations) ---
    # g_top = surface conductance per cell (top convection + half-thickness conduction in series)
    g_top_per_cell = 1.0 / (thickness / (2.0 * k * cell_area) + 1.0 / (h_top * cell_area))
    # g_lat = lateral conductance between the two cells
    g_lat = k * thickness * dy / dx

    # Node 0 (left, has power Q):
    #   (g_top + g_lat)*T0 - g_lat*T1 = Q + g_top*T_amb
    # Node 1 (right, no power):
    #   -g_lat*T0 + (g_top + g_lat)*T1 = g_top*T_amb
    a = g_top_per_cell + g_lat
    b = -g_lat
    c = -g_lat
    d = g_top_per_cell + g_lat
    rhs0 = q + g_top_per_cell * amb
    rhs1 = g_top_per_cell * amb
    det = a * d - b * c
    T0_expected = (rhs0 * d - b * rhs1) / det
    T1_expected = (a * rhs1 - rhs0 * c) / det

    # result.temperatures_c[layer, iy, ix]
    t0_num = float(result.temperatures_c[0, 0, 0])   # left cell
    t1_num = float(result.temperatures_c[0, 0, 1])   # right cell

    assert math.isclose(t0_num, T0_expected, rel_tol=1e-6), (
        f"Left node: numerical {t0_num:.6f} C, expected {T0_expected:.6f} C"
    )
    assert math.isclose(t1_num, T1_expected, rel_tol=1e-6), (
        f"Right node: numerical {t1_num:.6f} C, expected {T1_expected:.6f} C"
    )


def test_constant_power_profile_matches_no_profile() -> None:
    """Benchmark D: constant power_profile must produce identical temperatures to power_profile=None.

    A constant power profile (same power_w for all time) must be backward-compatible
    with the no-profile case.  Both runs use identical physical setup; the only
    difference is whether ``power_profile`` is specified.
    Tolerance: abs_tol=0.01 C.
    """
    width = 0.10
    height = 0.10
    k = 5.0
    density = 1500.0
    cp = 800.0
    thickness = 0.002
    h_top = 10.0
    amb = 25.0
    q = 1.0
    dt = 0.05
    total_time = 2.0

    mat = Material("Mat", k, k, density, cp, 0.9)

    def _make_project(profile=None) -> DisplayProject:
        return DisplayProject(
            name="BackCompat",
            width=width,
            height=height,
            materials={"Mat": mat},
            layers=[Layer(name="L", material="Mat", thickness=thickness)],
            heat_sources=[
                HeatSource(name="Q", layer="L", power_w=q, shape="full", power_profile=profile)
            ],
            boundaries=BoundaryConditions(
                top=SurfaceBoundary(ambient_c=amb, convection_h=h_top, include_radiation=False),
                bottom=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
                side=SurfaceBoundary(ambient_c=amb, convection_h=0.0, include_radiation=False),
            ),
            mesh=MeshConfig(nx=1, ny=1),
            transient=TransientConfig(
                time_step_s=dt,
                total_time_s=total_time,
                output_interval_s=dt,
                method="implicit_euler",
            ),
            initial_temperature_c=amb,
        )

    # Run A: no profile
    result_no_profile = TransientSolver().solve(_make_project(profile=None))
    t_no = float(result_no_profile.final_temperatures_c[0, 0, 0])

    # Run B: constant profile — power stays at q for the entire simulation
    constant_profile = [PowerBreakpoint(0.0, q), PowerBreakpoint(total_time * 2, q)]
    result_with_profile = TransientSolver().solve(_make_project(profile=constant_profile))
    t_with = float(result_with_profile.final_temperatures_c[0, 0, 0])

    assert math.isclose(t_no, t_with, rel_tol=0.0, abs_tol=0.01), (
        f"No-profile temperature {t_no:.4f} C differs from constant-profile {t_with:.4f} C "
        f"by {abs(t_no - t_with):.4f} C (tolerance: 0.01 C)"
    )


# ---------------------------------------------------------------------------
# Validation plot generation utility (NOT a test — no test_ prefix)
# ---------------------------------------------------------------------------

def generate_all_validation_plots(output_dir: Path | str = Path("outputs/validation")) -> None:
    """Run all validation benchmarks and save comparison PNGs to output_dir.

    Generates:
      - benchmark_A_three_layer.png  — grouped bar chart (analytical vs numerical)
      - benchmark_B_rc_square_wave.png — transient line plot
      - benchmark_C_lateral_spreading.png — grouped bar chart
      - benchmark_D_constant_profile.png — grouped bar chart (both runs)

    Usage::

        python -c "from tests.test_validation_cases import generate_all_validation_plots; \
            from pathlib import Path; generate_all_validation_plots(Path('outputs/validation'))"
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # --- Benchmark A: 3-layer resistance chain ---
    width_a = 0.12
    height_a = 0.08
    area_a = width_a * height_a
    amb_a = 23.0
    q_a = 1.7
    mat1_a = Material("M1", 0.8, 0.8, 2000.0, 900.0, 0.9)
    mat2_a = Material("M2", 10.0, 10.0, 2000.0, 900.0, 0.9)
    mat3_a = Material("M3", 1.5, 1.5, 2000.0, 900.0, 0.9)
    t1_a, t2_a, t3_a = 0.001, 0.002, 0.0015
    r12_a, r23_a = 4e-4, 2e-4
    h_top_a, h_bot_a = 12.0, 4.0

    proj_a = DisplayProject(
        name="BenchA", width=width_a, height=height_a,
        materials={"M1": mat1_a, "M2": mat2_a, "M3": mat3_a},
        layers=[
            Layer("Bottom", "M1", t1_a, interface_resistance_to_next=r12_a),
            Layer("Middle", "M2", t2_a, interface_resistance_to_next=r23_a),
            Layer("Top", "M3", t3_a),
        ],
        heat_sources=[HeatSource("Q", "Bottom", q_a, shape="full")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(amb_a, h_top_a, False),
            bottom=SurfaceBoundary(amb_a, h_bot_a, False),
            side=SurfaceBoundary(amb_a, 0.0, False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )
    res_a = SteadyStateSolver().solve(proj_a)
    g_bot_a = 1.0 / (t1_a / (2.0 * mat1_a.k_through * area_a) + 1.0 / (h_bot_a * area_a))
    g_top_a = 1.0 / (t3_a / (2.0 * mat3_a.k_through * area_a) + 1.0 / (h_top_a * area_a))
    g01_a = 1.0 / (t1_a / (2.0 * mat1_a.k_through * area_a) + r12_a / area_a + t2_a / (2.0 * mat2_a.k_through * area_a))
    g12_a = 1.0 / (t2_a / (2.0 * mat2_a.k_through * area_a) + r23_a / area_a + t3_a / (2.0 * mat3_a.k_through * area_a))
    A_mat = np.array([[g_bot_a + g01_a, -g01_a, 0.0], [-g01_a, g01_a + g12_a, -g12_a], [0.0, -g12_a, g12_a + g_top_a]])
    rhs_a = np.array([q_a + g_bot_a * amb_a, 0.0, g_top_a * amb_a])
    T_anal_a = np.linalg.solve(A_mat, rhs_a)
    analytical_a = {"Bottom": T_anal_a[0], "Middle": T_anal_a[1], "Top": T_anal_a[2]}
    numerical_a = {
        "Bottom": float(res_a.temperatures_c[0, 0, 0]),
        "Middle": float(res_a.temperatures_c[1, 0, 0]),
        "Top": float(res_a.temperatures_c[2, 0, 0]),
    }
    plot_validation_comparison(
        "Benchmark A: 3-Layer Resistance Chain (Steady-State)",
        analytical_a, numerical_a,
        out / "benchmark_A_three_layer.png",
    )

    # --- Benchmark B: RC square-wave transient ---
    width_b, height_b = 0.10, 0.10
    area_b = width_b * height_b
    k_b, density_b, cp_b = 10.0, 2700.0, 900.0
    thickness_b = 0.002
    h_top_b = 15.0
    amb_b = 25.0
    q_b = 2.0
    T_on_b = 0.5
    T_off_b = 0.5
    T_period_b = T_on_b + T_off_b
    total_b = 2.0
    dt_b = 0.01
    g_top_b = 1.0 / (thickness_b / (2.0 * k_b * area_b) + 1.0 / (h_top_b * area_b))
    G_b = g_top_b
    C_b = density_b * cp_b * thickness_b * area_b
    tau_b = C_b / G_b
    T_ss_on_b = amb_b + q_b / G_b
    T_ss_off_b = amb_b

    epsilon_b = dt_b
    profile_b = [
        PowerBreakpoint(0.0, q_b),
        PowerBreakpoint(T_on_b - epsilon_b, q_b),
        PowerBreakpoint(T_on_b, 0.0),
        PowerBreakpoint(T_period_b - epsilon_b, 0.0),
    ]
    mat_b = Material("RC", k_b, k_b, density_b, cp_b, 0.9)
    proj_b = DisplayProject(
        name="BenchB", width=width_b, height=height_b,
        materials={"RC": mat_b},
        layers=[Layer("L", "RC", thickness_b)],
        heat_sources=[HeatSource("Q", "L", q_b, shape="full", power_profile=profile_b)],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(amb_b, h_top_b, False),
            bottom=SurfaceBoundary(amb_b, 0.0, False),
            side=SurfaceBoundary(amb_b, 0.0, False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
        transient=TransientConfig(dt_b, total_b, dt_b),
        initial_temperature_c=amb_b,
    )
    res_b = TransientSolver().solve(proj_b)
    # Build dense analytical curve
    times_anal_b = np.linspace(0.0, total_b, 500)
    T_curr_b = float(amb_b)
    t_prev_b = 0.0
    temps_anal_b = np.empty(len(times_anal_b))
    for idx_b, t_b in enumerate(times_anal_b):
        dt_seg = t_b - t_prev_b
        t_in_period = t_b % T_period_b
        T_ss = T_ss_on_b if t_in_period < T_on_b else T_ss_off_b
        T_curr_b = T_ss + (T_curr_b - T_ss) * math.exp(-dt_seg / tau_b)
        temps_anal_b[idx_b] = T_curr_b
        t_prev_b = t_b
    plot_validation_transient_comparison(
        "Benchmark B: RC Square-Wave Power (Transient)",
        times_anal_b, temps_anal_b,
        res_b.times_s,
        res_b.temperatures_time_c[:, 0, 0, 0],
        out / "benchmark_B_rc_square_wave.png",
    )

    # --- Benchmark C: 2-node lateral spreading ---
    width_c, height_c = 0.04, 0.02
    thickness_c = 0.003
    k_c = 50.0
    density_c, cp_c = 2000.0, 900.0
    h_top_c = 10.0
    amb_c = 25.0
    q_c = 0.5
    dx_c = width_c / 2
    dy_c = height_c
    cell_area_c = dx_c * dy_c
    g_top_c = 1.0 / (thickness_c / (2.0 * k_c * cell_area_c) + 1.0 / (h_top_c * cell_area_c))
    g_lat_c = k_c * thickness_c * dy_c / dx_c
    a_c = g_top_c + g_lat_c
    b_c = -g_lat_c
    det_c = a_c * a_c - b_c * b_c
    rhs0_c = q_c + g_top_c * amb_c
    rhs1_c = g_top_c * amb_c
    T0_anal_c = (rhs0_c * a_c - b_c * rhs1_c) / det_c
    T1_anal_c = (a_c * rhs1_c - rhs0_c * b_c) / det_c
    mat_c = Material("Spread", k_c, k_c, density_c, cp_c, 0.9)
    proj_c = DisplayProject(
        name="BenchC", width=width_c, height=height_c,
        materials={"Spread": mat_c},
        layers=[Layer("L", "Spread", thickness_c)],
        heat_sources=[HeatSource("Q", "L", q_c, shape="rectangle",
                                  x=dx_c / 2, y=dy_c / 2,
                                  width=dx_c - 0.001, height=dy_c - 0.001)],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(amb_c, h_top_c, False),
            bottom=SurfaceBoundary(amb_c, 0.0, False),
            side=SurfaceBoundary(amb_c, 0.0, False),
        ),
        mesh=MeshConfig(nx=2, ny=1),
    )
    res_c = SteadyStateSolver().solve(proj_c)
    analytical_c = {"Left node": T0_anal_c, "Right node": T1_anal_c}
    numerical_c = {
        "Left node": float(res_c.temperatures_c[0, 0, 0]),
        "Right node": float(res_c.temperatures_c[0, 0, 1]),
    }
    plot_validation_comparison(
        "Benchmark C: 2-Node Lateral Heat Spreading (Steady-State)",
        analytical_c, numerical_c,
        out / "benchmark_C_lateral_spreading.png",
    )

    print(f"Validation plots saved to: {out.resolve()}")
    print(f"  benchmark_A_three_layer.png")
    print(f"  benchmark_B_rc_square_wave.png")
    print(f"  benchmark_C_lateral_spreading.png")


# ---------------------------------------------------------------------------
# Z-refinement validation tests (RED targets for Plan 02)
# ---------------------------------------------------------------------------


def test_zref05_single_layer_nz5_matches_1d_analytical() -> None:
    """ZREF-05: single layer with nz=5 must match 1D analytical tridiagonal solution.

    Verifies that when a single layer is split into 5 z-sublayers the solver
    produces node temperatures that match the exact 5-node finite-difference
    solution for a slab with distributed heat generation and convection on both faces.
    """
    width = 0.10
    height = 0.10
    area = width * height  # 0.01 m^2
    thickness = 0.005      # 5 mm
    nz = 5
    dz = thickness / nz    # 0.001 m per sub-layer
    k = 2.0
    density = 1000.0
    cp = 900.0
    h_top = 10.0
    h_bot = 5.0
    T_amb = 25.0
    Q_total = 3.0          # W, distributed across layer

    mat = Material("M", k_in_plane=k, k_through=k, density=density, specific_heat=cp, emissivity=0.9)
    project = DisplayProject(
        name="ZREF05",
        width=width,
        height=height,
        materials={"M": mat},
        layers=[Layer(name="L", material="M", thickness=thickness, nz=nz)],
        heat_sources=[HeatSource(name="Q", layer="L", power_w=Q_total, shape="full", z_position="distributed")],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=T_amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=T_amb, convection_h=h_bot, include_radiation=False),
            side=SurfaceBoundary(ambient_c=T_amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )

    result = SteadyStateSolver().solve(project)

    # --- 5-node analytical solution ---
    # G_intra: conductance between adjacent interior nodes (k*area/dz)
    G_intra = k * area / dz
    # G_bot: bottom surface BC (half dz conduction + convection in series)
    G_bot = 1.0 / (dz / (2.0 * k * area) + 1.0 / (h_bot * area))
    # G_top: top surface BC (half dz conduction + convection in series)
    G_top = 1.0 / (dz / (2.0 * k * area) + 1.0 / (h_top * area))
    # Heat per node: uniform distribution
    q_node = Q_total / nz  # 0.6 W per node

    # Build 5x5 system (nodes 0=bottom, 4=top)
    A = np.zeros((nz, nz))
    rhs = np.zeros(nz)

    # Node 0 (bottom): G_bot + G_intra on diagonal, -G_intra off-diagonal
    A[0, 0] = G_bot + G_intra
    A[0, 1] = -G_intra
    rhs[0] = q_node + G_bot * T_amb

    # Interior nodes 1..3
    for i in range(1, nz - 1):
        A[i, i - 1] = -G_intra
        A[i, i] = 2.0 * G_intra
        A[i, i + 1] = -G_intra
        rhs[i] = q_node

    # Node 4 (top): G_top + G_intra on diagonal
    A[nz - 1, nz - 2] = -G_intra
    A[nz - 1, nz - 1] = G_top + G_intra
    rhs[nz - 1] = q_node + G_top * T_amb

    T_expected = np.linalg.solve(A, rhs)

    # Assertions
    assert result.temperatures_c.shape == (nz, 1, 1), (
        f"Expected shape ({nz}, 1, 1), got {result.temperatures_c.shape}"
    )
    assert result.nz_per_layer == [nz], (
        f"Expected nz_per_layer=[{nz}], got {result.nz_per_layer}"
    )
    assert result.z_offsets == [0, nz], (
        f"Expected z_offsets=[0, {nz}], got {result.z_offsets}"
    )
    for z_idx in range(nz):
        t_sim = float(result.temperatures_c[z_idx, 0, 0])
        t_anal = float(T_expected[z_idx])
        assert math.isclose(t_sim, t_anal, rel_tol=1e-9, abs_tol=1e-9), (
            f"z_idx={z_idx}: numerical {t_sim:.6f} C, expected {t_anal:.6f} C"
        )


def test_zref03_interface_resistance_applies_at_layer_boundary() -> None:
    """ZREF-03: interface resistance must apply only at true layer boundaries, not within layers.

    Two layers each with nz=3.  A nonzero interface_resistance_to_next on the
    bottom layer creates a temperature jump ONLY at the inter-layer boundary
    (between node 2 and node 3).  Within-layer node pairs have pure conduction
    links.  Verified against the 6-node tridiagonal analytical solution.
    """
    width = 0.10
    height = 0.10
    area = width * height        # 0.01 m^2
    thickness = 0.003            # 3 mm per layer
    nz = 3
    dz = thickness / nz          # 0.001 m
    k = 2.0
    density = 1000.0
    cp = 900.0
    R_interface = 0.002          # m^2*K/W
    h_top = 10.0
    h_bot = 0.0                  # adiabatic bottom
    T_amb = 25.0
    Q_total = 2.0                # W, at bottom of bottom layer

    mat = Material("M", k_in_plane=k, k_through=k, density=density, specific_heat=cp, emissivity=0.9)
    project = DisplayProject(
        name="ZREF03",
        width=width,
        height=height,
        materials={"M": mat},
        layers=[
            Layer(name="Bottom", material="M", thickness=thickness, nz=nz,
                  interface_resistance_to_next=R_interface),
            Layer(name="Top", material="M", thickness=thickness, nz=nz),
        ],
        heat_sources=[
            HeatSource(name="Q", layer="Bottom", power_w=Q_total, shape="full", z_position="bottom")
        ],
        boundaries=BoundaryConditions(
            top=SurfaceBoundary(ambient_c=T_amb, convection_h=h_top, include_radiation=False),
            bottom=SurfaceBoundary(ambient_c=T_amb, convection_h=h_bot, include_radiation=False),
            side=SurfaceBoundary(ambient_c=T_amb, convection_h=0.0, include_radiation=False),
        ),
        mesh=MeshConfig(nx=1, ny=1),
    )

    result = SteadyStateSolver().solve(project)

    # --- 6-node analytical solution ---
    # G_intra: within-layer conductance (no interface resistance)
    G_intra = k * area / dz   # = 2.0 * 0.01 / 0.001 = 20.0
    # G_inter: inter-layer conductance (includes interface resistance)
    # 1 / (dz/(2*k*A) + R_int/A + dz/(2*k*A))
    G_inter = 1.0 / (dz / (2.0 * k * area) + R_interface / area + dz / (2.0 * k * area))
    # = 1 / (0.025 + 0.2 + 0.025) = 1 / 0.25 = 4.0
    # G_top: top surface BC (half dz conduction + convection in series)
    G_top = 1.0 / (dz / (2.0 * k * area) + 1.0 / (h_top * area))
    # Bottom is adiabatic (h_bot=0): no BC link at node 0

    n_total = 2 * nz  # 6 nodes
    A = np.zeros((n_total, n_total))
    rhs = np.zeros(n_total)

    # Node 0 (bottom of layer 0, adiabatic bottom): all power here
    A[0, 0] = G_intra
    A[0, 1] = -G_intra
    rhs[0] = Q_total

    # Node 1 (interior of layer 0)
    A[1, 0] = -G_intra
    A[1, 1] = 2.0 * G_intra
    A[1, 2] = -G_intra
    rhs[1] = 0.0

    # Node 2 (top of layer 0, interface to layer 1): uses G_inter upward
    A[2, 1] = -G_intra
    A[2, 2] = G_intra + G_inter
    A[2, 3] = -G_inter
    rhs[2] = 0.0

    # Node 3 (bottom of layer 1): uses G_inter downward
    A[3, 2] = -G_inter
    A[3, 3] = G_inter + G_intra
    A[3, 4] = -G_intra
    rhs[3] = 0.0

    # Node 4 (interior of layer 1)
    A[4, 3] = -G_intra
    A[4, 4] = 2.0 * G_intra
    A[4, 5] = -G_intra
    rhs[4] = 0.0

    # Node 5 (top of layer 1, top surface BC)
    A[5, 4] = -G_intra
    A[5, 5] = G_intra + G_top
    rhs[5] = G_top * T_amb

    T_expected = np.linalg.solve(A, rhs)

    # Assertions
    assert result.temperatures_c.shape == (n_total, 1, 1), (
        f"Expected shape ({n_total}, 1, 1), got {result.temperatures_c.shape}"
    )
    assert result.nz_per_layer == [nz, nz], (
        f"Expected nz_per_layer=[{nz}, {nz}], got {result.nz_per_layer}"
    )
    assert result.z_offsets == [0, nz, 2 * nz], (
        f"Expected z_offsets=[0, {nz}, {2 * nz}], got {result.z_offsets}"
    )
    for z_idx in range(n_total):
        t_sim = float(result.temperatures_c[z_idx, 0, 0])
        t_anal = float(T_expected[z_idx])
        assert math.isclose(t_sim, t_anal, rel_tol=1e-9, abs_tol=1e-9), (
            f"z_idx={z_idx}: numerical {t_sim:.6f} C, expected {t_anal:.6f} C"
        )

    # Physics check: temperature drop at layer boundary (T[2] - T[3]) should
    # equal Q * (dz/(2*k*A) + R_int/A + dz/(2*k*A)) = 2.0 * 0.25 = 0.5 K.
    T_boundary_drop = float(T_expected[2]) - float(T_expected[3])
    expected_drop = Q_total * (dz / (2.0 * k * area) + R_interface / area + dz / (2.0 * k * area))
    assert math.isclose(T_boundary_drop, expected_drop, rel_tol=1e-9), (
        f"Boundary temperature drop {T_boundary_drop:.6f} K, expected {expected_drop:.6f} K"
    )


@pytest.mark.xfail(reason="ZREF-04: requires Plan 02 z-refinement in solver", strict=False)
def test_zref04_backward_compat_nz1_identical() -> None:
    """ZREF-04: nz=1 on all layers must produce backward-compatible result metadata.

    Loads an existing example project (steady_uniform_stack.json) which has no
    nz fields (defaults to 1).  After Plan 02 wires z-refinement, the result must
    carry nz_per_layer with all-1 values and z_offsets=[0, 1, ..., n_layers].
    """
    project_path = Path(__file__).parent.parent / "examples" / "steady_uniform_stack.json"
    project = load_project(str(project_path))
    result = SteadyStateSolver().solve(project)

    n_layers = len(project.layers)

    # nz_per_layer must be set and all-1s
    assert result.nz_per_layer is not None, "nz_per_layer should be set after Plan 02"
    assert result.nz_per_layer == [1] * n_layers, (
        f"Expected all-1 nz_per_layer, got {result.nz_per_layer}"
    )
    # z_offsets must be [0, 1, 2, ..., n_layers]
    assert result.z_offsets is not None, "z_offsets should be set after Plan 02"
    assert result.z_offsets == list(range(n_layers + 1)), (
        f"Expected z_offsets={list(range(n_layers + 1))}, got {result.z_offsets}"
    )
