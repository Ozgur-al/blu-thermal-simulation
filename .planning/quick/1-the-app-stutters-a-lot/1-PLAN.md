---
phase: quick-perf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - thermal_sim/solvers/network_builder.py
  - thermal_sim/ui/plot_manager.py
  - thermal_sim/ui/main_window.py
autonomous: true
requirements: [PERF-01]
must_haves:
  truths:
    - "Simulation launch (network build) completes noticeably faster than before"
    - "GUI remains responsive during post-simulation plot rendering"
    - "All existing validation tests still pass with identical numerical results"
  artifacts:
    - path: "thermal_sim/solvers/network_builder.py"
      provides: "Vectorized COO-based network assembly replacing Python loops"
    - path: "thermal_sim/ui/plot_manager.py"
      provides: "Batched canvas drawing to reduce main-thread blocking"
    - path: "thermal_sim/ui/main_window.py"
      provides: "Deferred rendering after simulation completes"
  key_links:
    - from: "thermal_sim/solvers/network_builder.py"
      to: "thermal_sim/solvers/steady_state.py"
      via: "build_thermal_network returns identical ThermalNetwork"
      pattern: "build_thermal_network"
    - from: "thermal_sim/solvers/network_builder.py"
      to: "thermal_sim/solvers/transient.py"
      via: "build_thermal_network returns identical ThermalNetwork"
      pattern: "build_thermal_network"
---

<objective>
Fix GUI stuttering caused by two bottlenecks: (1) the network builder uses pure Python loops to assemble the sparse conductance matrix element-by-element via lil_matrix, which is extremely slow for even moderate meshes; (2) post-simulation matplotlib rendering does multiple synchronous tight_layout() + draw() calls on the main thread, blocking the event loop.

Purpose: The app is unusable for interactive work because both the simulation setup (matrix build) and the result display (plot rendering) freeze the UI.
Output: A responsive GUI where network assembly is 10-50x faster and plot rendering does not block the event loop.
</objective>

<execution_context>
@C:/Users/hasan/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/hasan/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@thermal_sim/solvers/network_builder.py
@thermal_sim/ui/plot_manager.py
@thermal_sim/ui/main_window.py
@thermal_sim/core/geometry.py
@tests/test_validation_cases.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Vectorize network_builder.py sparse matrix assembly</name>
  <files>thermal_sim/solvers/network_builder.py</files>
  <action>
Replace all Python `for iy ... for ix` loops in `build_thermal_network` with vectorized numpy + COO-format sparse matrix construction. The current code uses `lil_matrix` with element-wise access in 4 separate loop nests (lateral conduction, through-thickness conduction, top/bottom sinks, side sinks). This is the primary performance bottleneck.

Strategy:
1. Pre-compute all COO triplets (row, col, data) as numpy arrays using vectorized index arithmetic instead of Python loops.
2. Build the final `csr_matrix` in one shot from accumulated COO arrays using `coo_matrix((data, (row, col)), shape=...).tocsr()`.
3. Similarly vectorize the `b_vec` sink contributions.

Specific replacements:

**Lateral conduction (lines 70-81):** For each layer, generate all horizontal neighbor pairs (n, n+1 in x-direction) and vertical neighbor pairs (n, n+nx in y-direction) using `np.arange` index arrays. Compute the 4 COO entries per link (diagonal += g, off-diagonal -= g) as flat arrays.

**Through-thickness conduction (lines 83-97):** For each layer pair, the conductance `g_z` is uniform across all (ix, iy). Generate pairs `(l_idx*n_per_layer + flat_idx, (l_idx+1)*n_per_layer + flat_idx)` for `flat_idx in range(n_per_layer)` using `np.arange`.

**Top/bottom sinks (lines 99-121):** Uniform conductance across all cells in the top/bottom layer. Vectorize as `a_diag[top_indices] += g_top` and `b_vec[top_indices] += g_top * ambient`.

**Side sinks (lines 124-149):** For each layer, compute perimeter cell indices using `np.concatenate` of left/right/top/bottom edge index arrays. Apply sink conductances vectorized.

Important constraints:
- The function signature and return type (`ThermalNetwork`) must not change.
- The resulting `a_matrix`, `b_vector`, `c_vector` must be numerically identical to the current implementation (bit-for-bit for the same inputs).
- The `_apply_heat_sources` function is already vectorized and should not be changed.
- The `_surface_sink_conductance` helper is fine as-is (called once per boundary, not per cell).
- Keep `node_index` as a local function since `_apply_heat_sources` uses `node_index_fn` (but it won't be called in loops anymore for the main assembly).
- Import `coo_matrix` from `scipy.sparse` alongside existing imports.

Performance target: For a 30x18x5 mesh (2700 nodes), assembly should drop from ~200ms to ~5ms.
  </action>
  <verify>
    <automated>cd /g/blu-thermal-simulation && .venv/Scripts/python -m pytest tests/test_validation_cases.py tests/test_steady_state_solver.py tests/test_transient_solver.py -q</automated>
  </verify>
  <done>All existing solver/validation tests pass with identical numerical results. Network builder no longer contains Python for-loops for matrix assembly (only the existing _apply_heat_sources loop-free code remains).</done>
</task>

<task type="auto">
  <name>Task 2: Batch matplotlib canvas rendering to reduce main-thread blocking</name>
  <files>thermal_sim/ui/plot_manager.py, thermal_sim/ui/main_window.py</files>
  <action>
The current `_on_sim_finished` in main_window.py calls PlotManager methods that each do `figure.tight_layout()` + `canvas.draw()` individually -- that is 3-4 separate full canvas renders on the main thread, each taking 50-150ms. This causes visible stuttering after simulation results arrive.

Changes to PlotManager (`plot_manager.py`):

1. Add a `begin_batch()` / `end_batch()` mechanism to PlotManager:
   - `begin_batch()` sets a `self._batching = True` flag.
   - While batching, `plot_temperature_map`, `plot_layer_profile`, `plot_probe_history` should skip their individual `canvas.draw()` calls (still do the artist updates and tight_layout, just skip the final `draw()`).
   - `end_batch()` calls `draw_idle()` (not `draw()`) on all three canvases in one pass, then sets `_batching = False`. `draw_idle()` schedules the redraw through the Qt event loop rather than blocking synchronously.

2. Modify each plot method: at the end, replace the unconditional `self.{canvas}.draw()` with:
   ```python
   if not self._batching:
       self.{canvas}.draw()
   ```

3. Initialize `self._batching = False` in `__init__`.

Changes to MainWindow (`main_window.py`):

4. In `_on_sim_finished`, wrap the plot calls in a batch:
   ```python
   self._plot_manager.begin_batch()
   # ... existing plot calls ...
   self._plot_manager.end_batch()
   ```

5. The `_draw_empty_states` method (called once during init) is fine as-is -- 3 draws during startup is acceptable.

6. The `_refresh_map_and_profile` and `_refresh_profile_only` methods call individual plot methods outside of simulation -- these are fine unbatched since they are 1-2 draws triggered by user combo box changes.

This change reduces the synchronous blocking from 3-4 serial `draw()` calls (~300-600ms total) to a single `draw_idle()` pass that cooperates with the Qt event loop.
  </action>
  <verify>
    <automated>cd /g/blu-thermal-simulation && .venv/Scripts/python -c "from thermal_sim.ui.plot_manager import PlotManager; pm = PlotManager(); pm.begin_batch(); pm.end_batch(); print('OK')"</automated>
  </verify>
  <done>PlotManager supports begin_batch/end_batch. _on_sim_finished wraps all plot calls in a batch. Individual plot methods respect the batching flag. The app no longer freezes for 300-600ms after simulation results arrive.</done>
</task>

</tasks>

<verification>
1. All existing tests pass: `py -m pytest -q tests`
2. Run a steady-state simulation via CLI to confirm correctness: `python -m thermal_sim.app.cli --mode steady`
3. Run a transient simulation via CLI: `python -m thermal_sim.app.cli --mode transient --project examples/localized_hotspots_stack.json --output-dir outputs`
4. Launch GUI and run both steady and transient simulations -- confirm no freezing during matrix build or result display
</verification>

<success_criteria>
- All existing tests pass (zero regressions)
- network_builder.py contains no Python for-loops for matrix assembly
- PlotManager supports batched rendering via begin_batch/end_batch
- _on_sim_finished uses batched rendering
- GUI is noticeably more responsive during simulation and result display
</success_criteria>

<output>
After completion, create `.planning/quick/1-the-app-stutters-a-lot/1-SUMMARY.md`
</output>
