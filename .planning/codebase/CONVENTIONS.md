# Coding Conventions

**Analysis Date:** 2026-03-14

## Naming Patterns

**Files:**
- Module names: `snake_case` (e.g., `steady_state.py`, `material_library.py`, `csv_export.py`)
- Package directories: `snake_case` (e.g., `thermal_sim/models/`, `thermal_sim/solvers/`, `thermal_sim/core/`)

**Functions:**
- Regular functions: `snake_case` (e.g., `build_parser()`, `load_project()`, `_run_steady()`)
- Private/internal functions: Prefix with `_` (e.g., `_base_material()`, `_single_node_project()`, `_run_transient()`)
- Test functions: `test_*` prefix with descriptive names (e.g., `test_material_validation_rejects_nonpositive_conductivity()`)
- Methods: `snake_case` (e.g., `solve()`, `to_dict()`, `from_dict()`)

**Variables:**
- Local/instance variables: `snake_case` (e.g., `temperatures_c`, `power_w`, `ambient_c`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `STEFAN_BOLTZMANN` in `thermal_sim/core/constants.py`)
- Suffixes used: `_c` for Celsius, `_w` for watts, `_s` for seconds, `_m` for meters, `_h` for hours/convection coefficient
- Array dimensions indicated: suffixes like `temperature_map_c` for arrays

**Types:**
- Type aliases: `PascalCase` using `Literal` (e.g., `ShapeType = Literal["full", "rectangle", "circle"]`)
- Dataclasses: `PascalCase` (e.g., `Material`, `Layer`, `DisplayProject`, `SteadyStateResult`)
- Classes: `PascalCase` (e.g., `SteadyStateSolver`, `TransientSolver`, `Grid2D`)

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc` or equivalent)
- Import organization uses `from __future__ import annotations` (Python 3.10+ postponed evaluation style)
- 4-space indentation (Python standard)
- Line length appears unrestricted

**Linting:**
- No explicit linting configuration file detected (no `.pylintrc`, `setup.cfg`, `pyproject.toml`)
- Code uses `# noqa: BLE001` comments in `thermal_sim/ui/main_window.py` lines 383, 602, 635, 792, 798, 810, 816
  - Indicates awareness of linting but selective suppression rather than strict enforcement

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first when present)
2. Standard library imports (e.g., `import json`, `import argparse`, `import math`, `from pathlib import Path`)
3. Third-party imports (e.g., `import numpy as np`, `from scipy.sparse.linalg import spsolve`, `from PySide6.QtWidgets import ...`)
4. Local/relative imports (e.g., `from thermal_sim.models.material import Material`)

**Example from `thermal_sim/models/material.py`:**
```python
from __future__ import annotations

from dataclasses import dataclass
```

**Example from `thermal_sim/solvers/steady_state.py`:**
```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import spsolve

from thermal_sim.models.project import DisplayProject
from thermal_sim.solvers.network_builder import build_thermal_network
```

**Path Aliases:**
No path aliases detected. Imports use full absolute paths from package root (e.g., `from thermal_sim.models.material import Material`).

## Error Handling

**Patterns:**
- **Validation in `__post_init__`**: Dataclasses use `__post_init__()` method for parameter validation (in `thermal_sim/models/material.py`, `thermal_sim/models/layer.py`, `thermal_sim/core/geometry.py`)
  ```python
  def __post_init__(self) -> None:
      if not self.name.strip():
          raise ValueError("Material name must not be empty.")
      if self.k_in_plane <= 0.0:
          raise ValueError("k_in_plane must be > 0.")
  ```

- **Raise ValueError for invalid inputs**: All validation uses `ValueError` with descriptive messages
  - Examples: `"Material name must not be empty."`, `"Grid width/height must be > 0."`, `"Unsupported heat source shape: {self.shape}"`

- **Try-except in UI/CLI**: Application layer catches broad `Exception` with `# noqa: BLE001` suppression
  - `thermal_sim/ui/main_window.py` lines 377-383, 600-602, 612-635, 786-816
  - `thermal_sim/app/gui.py` lines 9-19
  - Pattern: `try: ... except Exception as exc: # noqa: BLE001` then user-facing error display

- **Try-except in CLI**: Main entry point catches `RuntimeError`
  - `thermal_sim/app/cli.py` lines 66-73: `except RuntimeError as exc: print(...); raise SystemExit(2)`

- **Module not found handling**: Graceful degradation for optional dependencies
  - `thermal_sim/app/gui.py` lines 9-19 catch `ModuleNotFoundError` for PySide6 and UI modules

## Logging

**Framework:** No logging framework detected. Application uses `print()` statements only.

**Patterns:**
- Error reporting to stdout: `print(f"Error: {exc}")` in `thermal_sim/app/cli.py` line 72
- User-facing messages in UI caught exceptions
- No structured logging, metrics, or debug output

## Comments

**When to Comment:**
- Docstrings on all classes and public functions
- Inline comments for algorithmic clarity (rare, only in complex thermal solvers)
- No TODO/FIXME comments found in codebase

**JSDoc/TSDoc:**
- Uses Python docstrings (triple quotes)
- Format: One-line summary of class/function purpose
- Examples from codebase:
  - `"""Material data model."""`
  - `"""Thermal material properties (SI units)."""`
  - `"""Single layer entry in the display stack."""`
  - `"""2.5D thermal network solver (lateral + through-thickness conduction)."""`

**Example from `thermal_sim/models/material.py`:**
```python
@dataclass(frozen=True)
class Material:
    """Thermal material properties (SI units)."""
```

## Function Design

**Size:** Functions tend toward single responsibility.
- Solver methods like `solve()` are 5-10 lines (delegate complexity to helpers)
- Data transformation methods (`to_dict()`, `from_dict()`) are 5-15 lines
- Complex builder methods in `thermal_sim/solvers/network_builder.py` are 50-100 lines with clear internal helpers

**Parameters:**
- Use type hints for all parameters (e.g., `def solve(self, project: DisplayProject) -> SteadyStateResult:`)
- Return type hints always present (e.g., `-> None:`, `-> int:`, `-> dict:`)
- No default parameters in solver entry points; defaults in config dataclasses instead
- Example: `thermal_sim/solvers/steady_state.py` line 35: `def solve(self, project: DisplayProject) -> SteadyStateResult:`

**Return Values:**
- Return typed dataclasses for complex results (e.g., `SteadyStateResult`, `TransientResult`)
- Return `dict` from serialization methods (`to_dict()`)
- Return `None` for side-effect operations (writing files, UI updates)
- Use property methods for computed values:
  ```python
  @property
  def nx(self) -> int:
      return self.temperatures_c.shape[2]
  ```

## Module Design

**Exports:**
- No explicit `__all__` declarations found
- Modules export classes and functions they define directly
- Imports from modules use explicit class/function names (not wildcard imports)

**Barrel Files:**
- `__init__.py` files exist in all package directories but are empty or minimal
- Examples: `thermal_sim/__init__.py`, `thermal_sim/models/__init__.py` contain no re-exports
- No barrel pattern used for grouping exports

**Dataclass Pattern Dominance:**
- Data models use `@dataclass` decorator extensively (`Material`, `Layer`, `DisplayProject`, `HeatSource`, `LEDArray`, `MeshConfig`, `TransientConfig`)
- Immutable models use `@dataclass(frozen=True)` (e.g., `Material`, `Grid2D`)
- Mutable models use `@dataclass` (e.g., `Layer`, `DisplayProject`)
- All dataclasses implement `to_dict()` and `from_dict()` for serialization

---

*Convention analysis: 2026-03-14*
