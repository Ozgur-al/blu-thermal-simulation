# Codebase Concerns

**Analysis Date:** 2026-03-14

## Error Handling

**Bare exception catching in GUI:**
- Issue: Multiple bare `except Exception` clauses without specific exception type handling
- Files: `thermal_sim/ui/main_window.py` (lines 383, 602, 635, 792, 798, 810, 816)
- Impact: Suppresses all exceptions including SystemExit and KeyboardInterrupt; makes debugging difficult; could hide critical failures
- Current mitigation: Uses `# noqa: BLE001` to suppress linter warnings (acknowledges the issue)
- Fix approach: Replace with specific exception types (ValueError, RuntimeError, etc.) based on context, or create custom exception hierarchy

**Bare exception in startup project loading:**
- Issue: `_load_startup_project()` at line 383 silently catches all exceptions when loading example project
- Files: `thermal_sim/ui/main_window.py`
- Current behavior: Falls back to default materials without logging why load failed
- Improvement: Log the exception or provide user feedback about which file failed to load

## Test Coverage Gaps

**UI module untested:**
- What's not tested: All GUI components including `main_window.py` (939 lines) and `structure_preview.py` (181 lines)
- Files: `thermal_sim/ui/main_window.py`, `thermal_sim/ui/structure_preview.py`
- Risk: GUI bugs won't be caught until runtime; table parsing, data validation, visualization rendering not verified
- Recommended approach: Add pytest fixtures for PySide6 widgets if testing is needed, or document that GUI is manual-test only

**App/CLI module untested:**
- What's not tested: Command-line interface and argument parsing in `cli.py` (197 lines)
- Files: `thermal_sim/app/cli.py`
- Risk: CLI argument handling, output directory creation, plotting integration not verified
- Impact: Changes to CLI could break without detection

**I/O and export utilities untested:**
- What's not tested: CSV export functionality in `csv_export.py` (76 lines) and project JSON I/O in `project_io.py` (24 lines)
- Files: `thermal_sim/io/csv_export.py`, `thermal_sim/io/project_io.py`
- Risk: Export format changes could corrupt saved files; JSON serialization issues would only surface in production
- Priority: Medium - affects data persistence

**Visualization module untested:**
- What's not tested: Matplotlib-based plotting functions
- Files: `thermal_sim/visualization/plotting.py` (65 lines)
- Risk: Plot generation failures only discovered when users run with `--plot` flag
- Note: Plotting is optional dependency; failures are caught and reported as RuntimeError

**Postprocessing module partially tested:**
- What's not tested: `probe_temperatures()`, `probe_temperatures_over_time()`, `top_n_hottest_cells()` functions
- Files: `thermal_sim/core/postprocess.py` (110 lines)
- Risk: Probe temperature extraction with nearest-neighbor grid mapping logic not verified
- Note: Some postprocessing is tested indirectly through solver tests, but extraction logic itself is untested

## Code Quality Issues

**Overly broad exception handling with assertion:**
- Issue: Line 863 in main_window.py uses `assert` for control flow
- Files: `thermal_sim/ui/main_window.py` (line 863)
- Problem: Assertions can be disabled with Python `-O` flag; should use proper type narrowing or explicit check
- Code: `assert self.last_transient_result is not None`
- Fix: Replace with `if self.last_transient_result is None: raise RuntimeError(...)`

**GUI complexity concentration:**
- Issue: `MainWindow` class contains 939 lines mixing UI construction, event handling, data validation, and simulation coordination
- Files: `thermal_sim/ui/main_window.py`
- Impact: Hard to test, maintain, or extend; violates single responsibility principle
- Safe modification: Extract table parsing into separate TableDataParser class; extract simulation logic into controller; extract plotting into dedicated PlotManager

**Float conversion without validation in CSV export:**
- Issue: `float(temperature_map_c[...])` in line 46 of csv_export.py assumes values are finite
- Files: `thermal_sim/io/csv_export.py`
- Risk: If solver produces NaN or Inf, CSV export will write invalid data without warning
- Improvement: Add assertions or validation in solver results or explicit NaN/Inf checks in export

## Scaling and Performance Concerns

**Memory usage with large transient simulations:**
- Issue: TransientSolver stores full temperature history in memory: `states: list[np.ndarray]` (line 56 in transient.py)
- Files: `thermal_sim/solvers/transient.py`
- Current behavior: For fine mesh (e.g., 500x500 grid) with many timesteps (1000+), allocates multiple GB
- Impact: Large simulations may fail on memory-constrained systems
- Scaling path: Implement streaming output or checkpoint-based storage for very long transients

**Network builder uses dense sparse matrix operations:**
- Issue: `lil_matrix` converted to `csr_matrix` for solving (line 169 in network_builder.py)
- Files: `thermal_sim/solvers/network_builder.py`
- Current: Efficient for sparse 3D networks, but no upper bound checks on mesh resolution
- Risk: Very fine meshes (>1000x1000) could become slow or memory-bound
- Current mitigation: Implicit through reasonable default mesh (30x20) and user input validation

**Side boundary calculation scales O(n_layers * perimeter):**
- Issue: Nested loops for side boundaries in lines 125-165 of network_builder.py
- Files: `thermal_sim/solvers/network_builder.py`
- Current: No optimization; acceptable for typical stacks (5-20 layers) but could be vectorized
- Impact: Minimal for current use cases; not a blocker

## Validation Gaps

**Heat source overlap not detected:**
- Issue: No check if multiple heat sources or LEDs occupy same mesh cell
- Files: `thermal_sim/solvers/network_builder.py`
- Behavior: Power is summed (correct), but no warning that design may have overlapping thermal sources
- Current handling: Mesh density check only ensures sources hit at least one cell
- Recommendation: Add optional warning if source areas overlap

**Interface resistance validation incomplete:**
- Issue: `interface_resistance_to_next` can be set to very large values, creating numerical issues
- Files: `thermal_sim/models/layer.py`
- Risk: No upper bound validation; extremely high resistance values could cause sparse matrix singularity
- Mitigation: Model validation accepts any non-negative value; user responsible for physical reasonableness

**Probe location rounding inconsistency:**
- Issue: Probe temperature extraction uses `np.floor()` to nearest grid cell (line 78-79 in postprocess.py)
- Files: `thermal_sim/core/postprocess.py`
- Behavior: Probe at (0.15, 0.15) with dx=0.1 clips to cell (1, 1), not interpolated
- Impact: Slight inaccuracy at arbitrary probe locations; users may expect interpolation

## Dependency Risks

**PySide6 is optional but GUI requires it:**
- Risk: No graceful fallback if PySide6 missing; raises SystemExit(2)
- Files: `thermal_sim/app/gui.py` (lines 10-13, 15-19)
- Current: Clear error messages pointing to requirements.txt
- Status: Acceptable; users know to install GUI dependencies

**Matplotlib plotting is optional but silently optional:**
- Issue: Plotting requires matplotlib but failure is caught and converted to RuntimeError
- Files: `thermal_sim/visualization/plotting.py`, `thermal_sim/app/cli.py`
- Behavior: `--plot` flag fails at runtime with RuntimeError, not at argument parsing
- Improvement: Could check for matplotlib presence during argument validation

**No version pinning in requirements.txt:**
- Issue: Requirements use `>=` only, allowing any future breaking version
- Files: `requirements.txt`
- Risk: numpy 2.x or scipy 1.15 could introduce breaking changes
- Current: Project is early-phase (Phase 3 in development); acceptable
- Recommendation: Add upper version bounds once API stabilizes

## Known Behavioral Issues

**Steady-state solver has no convergence checking:**
- Issue: SteadyStateSolver directly calls `spsolve()` without checking solution validity
- Files: `thermal_sim/solvers/steady_state.py`
- Current: Sparse matrix may be singular or ill-conditioned without explicit error
- Risk: Degenerate geometries (all insulating layers, no boundary conductance) could produce invalid solutions
- Mitigation: Model validation in DisplayProject catches some degenerate cases

**Transient output sampling can skip final timestep edge case:**
- Issue: Line 64 in transient.py uses `step % sample_every == 0 or step == n_steps`
- Files: `thermal_sim/solvers/transient.py`
- Behavior: Final timestep always included but may duplicate previous sample if timing aligns poorly
- Impact: Minor; final state is captured correctly
- Note: Not a bug, but output sampling logic is slightly fragile

**CLI layer selection defaults to last layer silently:**
- Issue: `_layer_index()` in cli.py line 189 defaults to last layer without warning if plot_layer not found
- Files: `thermal_sim/app/cli.py`
- Behavior: User specifies `--plot-layer "Nonexistent"` and plots top layer instead
- Improvement: Should raise error immediately or log a warning

## Documentation Gaps

**Material library not documented:**
- Issue: No docstring explaining which materials are available or their sources
- Files: `thermal_sim/core/material_library.py`
- Impact: Users must inspect code to see available presets

**Boundary condition interpretation not clear:**
- Issue: Radiation linearization (4th order to linear) in network_builder.py not documented
- Files: `thermal_sim/solvers/network_builder.py` (lines 224-227)
- Context: `h_total += 4.0 * eps * STEFAN_BOLTZMANN * t_ref_k**3`
- Risk: Users may not realize radiation is evaluated at T_ambient, not T_surface

---

*Concerns audit: 2026-03-14*
