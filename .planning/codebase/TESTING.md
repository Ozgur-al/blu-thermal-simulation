# Testing Patterns

**Analysis Date:** 2026-03-14

## Test Framework

**Runner:**
- pytest >= 8.0 (from `requirements.txt`)
- Config: No explicit `pytest.ini`, `setup.cfg`, or `pyproject.toml` found
- Default pytest discovery (tests in `tests/` directory with `test_*.py` files)

**Assertion Library:**
- pytest's built-in assertions and `pytest.approx()` for floating-point comparisons
- `math.isclose()` also used for numerical assertions

**Run Commands:**
```bash
pytest                          # Run all tests (discovered in tests/ directory)
pytest -v                       # Verbose output
pytest tests/                   # Run tests in tests/ directory
pytest tests/test_models.py     # Run specific test file
```

## Test File Organization

**Location:**
- Pattern: Separate `tests/` directory at project root
- Structure: `tests/test_*.py` files correspond to modules being tested

**Naming:**
- Test files: `test_*.py` (e.g., `test_models.py`, `test_steady_state_solver.py`)
- Test functions: `test_*` prefix (e.g., `test_material_validation_rejects_nonpositive_conductivity()`)
- Private helper functions: `_*` prefix (e.g., `_base_material()`, `_single_node_project()`)

**Structure:**
```
tests/
├── test_led_array.py              # LEDArray expansion and heating tests
├── test_models.py                 # Model validation and serialization
├── test_steady_state_solver.py     # Steady-state solver correctness
├── test_transient_solver.py        # Transient solver behavior
└── test_validation_cases.py        # Physics validation cases
```

## Test Structure

**Suite Organization:**
```python
import pytest
from thermal_sim.models.material import Material
from thermal_sim.solvers.steady_state import SteadyStateSolver


def test_material_validation_rejects_nonpositive_conductivity() -> None:
    """Test function with descriptive name."""
    with pytest.raises(ValueError):
        Material(
            name="Bad",
            k_in_plane=0.0,  # Invalid: must be > 0
            k_through=1.0,
            density=1000.0,
            specific_heat=1000.0,
            emissivity=0.9,
        )


def test_project_roundtrip_includes_transient_settings() -> None:
    """Test serialization via to_dict() and from_dict()."""
    mat = Material(
        name="Mat",
        k_in_plane=1.0,
        k_through=1.0,
        density=1000.0,
        specific_heat=1000.0,
        emissivity=0.9,
    )
    project = DisplayProject(...)
    restored = DisplayProject.from_dict(project.to_dict())

    assert restored.transient.time_step_s == pytest.approx(0.5)
    assert restored.transient.total_time_s == pytest.approx(10.0)
```

**Patterns:**

1. **Validation Testing**: Uses `pytest.raises()` context manager
   - Example from `test_models.py` lines 9-18: Validates that invalid parameters raise `ValueError`
   - Tests both single constraint violations and composite constraints

2. **Physics Validation Testing**: Compares solver results to analytical solutions
   - Example from `test_steady_state_solver.py` line 22: 1-cell problem with analytical parallel resistance solution
   - Uses `math.isclose(simulated, expected, rel_tol=1e-9, abs_tol=1e-9)` for precise comparison
   - Example from `test_steady_state_solver.py` line 54: Validates hotspot temperature behavior

3. **Roundtrip Testing**: Verifies serialization/deserialization
   - Example from `test_models.py` lines 43-62: Projects can serialize to dict and restore from dict
   - Checks both configuration and calculated properties persist

4. **Behavioral Testing**: Verifies expected physical behavior
   - Example from `test_steady_state_solver.py` lines 57-86: Localized heat source raises center temperature
   - Simple assertion: `assert center > corner`

5. **Solver Integration Testing**: Tests complete solver workflow
   - Example from `test_led_array.py` lines 33-73: LED array expansion contributes to heating correctly
   - Creates full project, runs solver, verifies output temperature exceeds ambient

## Mocking

**Framework:** No mocking library detected in use.

**Patterns:**
- Tests construct realistic project objects rather than mocking dependencies
- Example from `test_steady_state_solver.py`: Helper function `_base_material()` creates reusable test materials
  ```python
  def _base_material(name: str, k_ip: float, k_tp: float) -> Material:
      return Material(
          name=name,
          k_in_plane=k_ip,
          k_through=k_tp,
          density=2000.0,
          specific_heat=900.0,
          emissivity=0.9,
      )
  ```

**What to Mock:**
- Mocking not used; tests rely on actual object construction
- File I/O tested through real JSON serialization (no mocked file systems)

**What NOT to Mock:**
- Solver algorithms (tests verify actual numerical results)
- Material properties (tests use realistic values or helpers)
- Grid/mesh generation (tests use real geometry objects)

## Fixtures and Factories

**Test Data:**
- Helper functions create reusable test objects
- Example from `test_steady_state_solver.py` line 11: `_base_material()` factory
- Example from `test_transient_solver.py` line 12: `_single_node_project()` factory
  ```python
  def _single_node_project(power_w: float, initial_c: float, total_time_s: float) -> DisplayProject:
      material = Material(...)
      return DisplayProject(
          name="Transient single-node",
          width=0.1,
          height=0.1,
          materials={"NodeMat": material},
          layers=[Layer(name="Core", material="NodeMat", thickness=0.0002)],
          # ... build full project
      )
  ```

**Location:**
- Test file scoped: Factories defined at module level in test files
- No shared `conftest.py` or fixture files detected
- Factories are simple functions that return configured objects

## Coverage

**Requirements:** Not enforced (no coverage configuration found).

**View Coverage:**
No coverage command defined in repository.

## Test Types

**Unit Tests:**
- **Scope**: Individual class validation (e.g., `Material`, `Layer`, `MeshConfig`)
- **Approach**: Direct instantiation, validate `__post_init__` constraints
- **Files**: `test_models.py`
- **Example from `test_models.py` line 9**: Test invalid conductivity raises `ValueError`

**Integration Tests:**
- **Scope**: Solver workflows with complete projects
- **Approach**: Build realistic projects, run solvers, verify output structure and ranges
- **Files**: `test_steady_state_solver.py`, `test_transient_solver.py`, `test_led_array.py`
- **Example from `test_steady_state_solver.py` line 22**: One-cell solver against analytical solution

**Physics Validation Tests:**
- **Scope**: Verify solver accuracy against hand calculations and known physics
- **Approach**: Compute expected values analytically, compare to solver output
- **Files**: `test_steady_state_solver.py`, `test_transient_solver.py`, `test_validation_cases.py`
- **Example from `test_validation_cases.py` line 11**: 1D two-layer thermal resistance chain vs hand calculation
  - Solves 2x2 nodal equation analytically, compares both node temperatures to solver output

**E2E Tests:**
- Not structured as separate test class
- Some integration tests approach E2E (e.g., full project roundtrip in `test_models.py`)

## Common Patterns

**Numeric Comparison:**
```python
# Using pytest.approx()
assert restored.transient.time_step_s == pytest.approx(0.5)

# Using math.isclose()
assert math.isclose(simulated, expected, rel_tol=1e-9, abs_tol=1e-9)

# Simple comparisons for temperature relationships
assert center > corner
assert float(high_result.temperatures_c.max()) > float(low_result.temperatures_c.max())
```

**Exception Testing:**
```python
def test_material_validation_rejects_nonpositive_conductivity() -> None:
    with pytest.raises(ValueError):
        Material(
            name="Bad",
            k_in_plane=0.0,  # Triggers validation error
            k_through=1.0,
            density=1000.0,
            specific_heat=1000.0,
            emissivity=0.9,
        )
```

**Array/Matrix Testing:**
```python
def test_localized_hotspot_raises_center_temperature() -> None:
    result = SteadyStateSolver().solve(project)
    center = float(result.temperatures_c[0, 10, 10])
    corner = float(result.temperatures_c[0, 0, 0])
    assert center > corner
```

**Async Testing:**
Not applicable (no async operations in codebase).

**Error Testing:**
```python
# Test that invalid references are caught
def test_project_validation_detects_missing_material_reference() -> None:
    materials = {"Glass": Material(...)}
    with pytest.raises(ValueError):
        DisplayProject(
            name="Invalid",
            width=0.1,
            height=0.1,
            layers=[Layer(name="Layer1", material="Missing", thickness=1e-3)],  # Bad reference
            materials=materials,
            heat_sources=[HeatSource(name="HS", layer="Layer1", power_w=1.0, shape="full")],
        )
```

---

*Testing analysis: 2026-03-14*
