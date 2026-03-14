import math

import numpy as np

from thermal_sim.models.boundary import BoundaryConditions, SurfaceBoundary
from thermal_sim.models.heat_source import HeatSource, PowerBreakpoint
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.project import DisplayProject, MeshConfig, TransientConfig
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver


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
