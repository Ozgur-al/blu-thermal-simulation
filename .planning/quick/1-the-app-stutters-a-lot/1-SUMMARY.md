---
phase: quick-perf
plan: "01"
subsystem: performance
tags: [performance, vectorization, sparse-matrix, matplotlib, gui-responsiveness]
dependency_graph:
  requires: []
  provides: [vectorized-network-assembly, batched-canvas-rendering]
  affects: [thermal_sim/solvers/network_builder.py, thermal_sim/ui/plot_manager.py, thermal_sim/ui/main_window.py]
tech_stack:
  added: [scipy.sparse.coo_matrix]
  patterns: [COO-triplet-accumulation, batch-draw-idle]
key_files:
  created: []
  modified:
    - thermal_sim/solvers/network_builder.py
    - thermal_sim/ui/plot_manager.py
    - thermal_sim/ui/main_window.py
decisions:
  - "COO triplet accumulation with csr_matrix built in one shot replaces lil_matrix element-wise updates"
  - "end_batch() uses draw_idle() (Qt event loop) not draw() (synchronous) to avoid blocking the main thread"
  - "probe_history plot call moved outside try block to keep all three plot calls under a single batch"
metrics:
  duration: "~10 min"
  completed_date: "2026-03-14"
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 1: Fix GUI Stuttering — Performance Summary

**One-liner:** Vectorized COO-based sparse matrix assembly (replaces Python for-loops with numpy) and batched matplotlib draw_idle() rendering (replaces 3-4 synchronous draw() calls).

## What Was Done

### Task 1 — Vectorize network_builder.py sparse matrix assembly

Replaced all Python `for iy ... for ix` nested loops in `build_thermal_network` with vectorized numpy COO triplet accumulation. The assembly strategy:

- **Lateral conduction:** Generate all horizontal and vertical neighbor pairs for each layer using `np.where`-based mask arrays (`ix_all < nx-1`, `iy_all < ny-1`). Four COO entries per link appended as flat numpy arrays.
- **Through-thickness conduction:** For each layer pair, a single `np.arange(n_per_layer)` generates all node pairs in one shot.
- **Top/bottom sinks:** Diagonal entries and b_vec contributions applied via vectorized index arrays (`top_indices`, `bot_indices`).
- **Side sinks:** Left/right and bottom/top perimeter index arrays built with `np.arange` + `np.concatenate`, then applied uniformly.
- **Final assembly:** `coo_matrix((all_data, (all_rows, all_cols)), shape=...).tocsr()` — single conversion from accumulated COO triplets.

Removed `lil_matrix` import; added `coo_matrix` from `scipy.sparse`.

**Commit:** 82de670

### Task 2 — Batch matplotlib canvas rendering

Added `begin_batch()` / `end_batch()` mechanism to `PlotManager`:

- `self._batching = False` initialized in `__init__`
- `begin_batch()` sets flag; each plot method skips `canvas.draw()` while it is set
- `end_batch()` resets flag then calls `draw_idle()` on all three canvases — schedules repaints through Qt's event loop instead of blocking synchronously
- In `_on_sim_finished`, all three plot calls (`plot_probe_history`, `_plot_map`, `_plot_profile`) wrapped in a single `begin_batch()` / `end_batch()` block

**Commit:** 612f78c

## Verification

- All 28 tests pass (`py -m pytest -q tests`)
- CLI steady-state run: `Tmax 103.43 C` — matches expected results
- CLI transient run: `Tmax 64.71 C` at 180s — matches expected results
- No Python for-loops remain in network_builder.py for matrix assembly

## Deviations from Plan

### Auto-fixed Issues

None.

### Refactoring Note

The `probe_history` plot calls in `_on_sim_finished` were originally inside the `try` block (one call per steady/transient branch). To include them in the batch, they were refactored to use local variables (`probe_times`, `probe_hist`) that are set inside the try block, then the single `plot_probe_history(probe_times, probe_hist)` call is made after the try block inside the batch. This is a cleaner separation than the original and preserves the same behavior.

## Self-Check: PASSED

Files confirmed present:
- thermal_sim/solvers/network_builder.py (modified)
- thermal_sim/ui/plot_manager.py (modified)
- thermal_sim/ui/main_window.py (modified)

Commits confirmed:
- 82de670 feat(quick-perf-01): vectorize network_builder sparse matrix assembly
- 612f78c feat(quick-perf-01): batch matplotlib canvas rendering in PlotManager
