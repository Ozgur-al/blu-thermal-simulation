"""v1.0 regression baseline tests.

These tests load each of the 4 example JSON projects, solve them with both
steady-state and transient solvers, and compare results to stored .npy baselines
at atol=1e-12. They serve as the mandatory entry gate before any changes to the
network builder or solver pipeline.

Run to regenerate baselines:
    python tests/test_regression_v1.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from thermal_sim.io.project_io import load_project
from thermal_sim.solvers.steady_state import SteadyStateSolver
from thermal_sim.solvers.transient import TransientSolver

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
BASELINES_DIR = Path(__file__).parent / "baselines"

EXAMPLES = [
    "examples/DLED.json",
    "examples/led_array_backlight.json",
    "examples/localized_hotspots_stack.json",
    "examples/steady_uniform_stack.json",
]


def _example_params():
    return [
        pytest.param(path, id=Path(path).stem)
        for path in EXAMPLES
    ]


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("example_path", _example_params())
def test_regression_steady_state_matches_v1_baseline(example_path: str) -> None:
    """Steady-state temperatures match stored v1.0 baseline at atol=1e-12."""
    stem = Path(example_path).stem
    baseline_path = BASELINES_DIR / f"{stem}_steady.npy"
    assert baseline_path.exists(), (
        f"Baseline file not found: {baseline_path}\n"
        f"Run `python tests/test_regression_v1.py` to generate baselines."
    )

    project = load_project(REPO_ROOT / example_path)
    result = SteadyStateSolver().solve(project)
    baseline = np.load(baseline_path)

    np.testing.assert_allclose(
        result.temperatures_c,
        baseline,
        atol=1e-12,
        rtol=0,
        err_msg=f"Steady-state regression FAILED for {example_path}",
    )


@pytest.mark.parametrize("example_path", _example_params())
def test_regression_transient_final_matches_v1_baseline(example_path: str) -> None:
    """Transient final-timestep temperatures match stored v1.0 baseline at atol=1e-12."""
    stem = Path(example_path).stem
    baseline_path = BASELINES_DIR / f"{stem}_transient.npy"
    assert baseline_path.exists(), (
        f"Baseline file not found: {baseline_path}\n"
        f"Run `python tests/test_regression_v1.py` to generate baselines."
    )

    project = load_project(REPO_ROOT / example_path)
    result = TransientSolver().solve(project)
    baseline = np.load(baseline_path)

    np.testing.assert_allclose(
        result.temperatures_time_c[-1],
        baseline,
        atol=1e-12,
        rtol=0,
        err_msg=f"Transient regression FAILED for {example_path}",
    )


# ---------------------------------------------------------------------------
# Baseline capture (run as script, not as pytest)
# ---------------------------------------------------------------------------


def _capture_baselines() -> None:
    """Generate and save .npy baseline files for all example projects."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    steady_solver = SteadyStateSolver()
    transient_solver = TransientSolver()

    for example_path in EXAMPLES:
        full_path = REPO_ROOT / example_path
        stem = Path(example_path).stem
        print(f"\nCapturing baselines for: {example_path}")

        project = load_project(full_path)

        # Steady-state
        steady_result = steady_solver.solve(project)
        steady_path = BASELINES_DIR / f"{stem}_steady.npy"
        np.save(steady_path, steady_result.temperatures_c)
        print(f"  Saved: {steady_path.name}  shape={steady_result.temperatures_c.shape}")

        # Transient — save only the final timestep to keep files small
        transient_result = transient_solver.solve(project)
        final_frame = transient_result.temperatures_time_c[-1]
        transient_path = BASELINES_DIR / f"{stem}_transient.npy"
        np.save(transient_path, final_frame)
        print(f"  Saved: {transient_path.name}  shape={final_frame.shape}")

    print(f"\nDone. {len(EXAMPLES) * 2} baseline files written to {BASELINES_DIR}.")


if __name__ == "__main__":
    _capture_baselines()
