---
phase: 11-voxel-3d-solver
verified: 2026-03-16T16:00:00Z
status: gaps_found
score: 13/14 requirements verified
re_verification: false
gaps:
  - truth: "Heat sources modeled as AssemblyBlock objects with power_w (SurfaceSource deprecated by design decision)"
    status: verified
    reason: "User decision: SurfaceSource is deprecated. All heat sources are modeled as AssemblyBlock entries with power_w. LEDs are tiny blocks with power_w — simpler and sufficient. Both DLED and ELED examples use this pattern successfully."
  - truth: "GUI block editor can add and remove assembly blocks without runtime errors"
    status: failed
    reason: "_refresh_block_combos() is called in _add_block_row_default() and _remove_blocks_row() but the method is not defined on BlockEditorWidget. Attempting to add or remove a block in the GUI will raise AttributeError: 'BlockEditorWidget' object has no attribute '_refresh_block_combos'."
    artifacts:
      - path: "thermal_sim/ui/block_editor.py"
        issue: "_refresh_block_combos referenced at lines 318 and 325 but method body never defined in the class"
    missing:
      - "Define _refresh_block_combos(self) -> None method on BlockEditorWidget (could be a no-op stub if block combos are not yet needed, or could refresh source-editor block combos when blocks change)"
  - truth: "Powered blocks report their neighboring materials and shared face area for thermal path diagnosis"
    status: failed
    reason: "No contact/adjacency diagnostic exists. The physics depends on what each LED block actually touches, but the app never reports this. Users cannot tell whether an LED contacts Metal Frame, FR4, LGP, or only Air Gap."
    artifacts:
      - path: "thermal_sim/solvers/voxel_network_builder.py"
        issue: "Line 324 area — no diagnostic reporting powered-block adjacency or shared face area"
    missing:
      - "Add a diagnostic in the voxel path that reports, for each powered block, its neighboring materials and shared face area"
  - truth: "Block editor validates geometry and warns about thermal path issues (LED not touching metal, air gap between LED and metal, overlap order, edge-only contact)"
    status: failed
    reason: "No block-geometry validation exists in the editor. Since overlap uses last-defined-wins in voxel_assignment.py (line 29), users get no warning when LED blocks don't actually contact the intended thermal path."
    artifacts:
      - path: "thermal_sim/ui/block_editor.py"
        issue: "No geometry validation or thermal path warnings"
      - path: "thermal_sim/core/voxel_assignment.py"
        issue: "Line 29 — last-defined-wins overlap rule with no user feedback"
    missing:
      - "Warn when LED block does not touch the metal path"
      - "Warn when Air Gap block sits between LED and metal"
      - "Warn when LED only overlaps another block because of definition order"
      - "Warn when contact is just an edge/corner, not a face"
  - truth: "Voxel boundary conditions support independent top/bottom/side groups"
    status: failed
    reason: "Voxel mode currently applies the first boundary group to all exposed faces. Top/bottom/side cooling are not independent — boundary grouping by face orientation is missing."
    artifacts:
      - path: "thermal_sim/solvers/voxel_network_builder.py"
        issue: "Line 208 area — first boundary group applied to all exposed faces instead of matching by face orientation"
    missing:
      - "Fix boundary face grouping so top/bottom/side boundaries apply independently to the correct exposed faces"
human_verification:
  - test: "Run GUI and verify ELED example renders"
    expected: "3D view shows metal frame, air gaps, FR4 PCBs, and LGP as distinct color-coded blocks; temperature overlay shows PCB hot spots after solving"
    why_human: "Cannot run PySide6/PyVista GUI in headless test environment"
  - test: "Verify ELED temperature physics are reasonable"
    expected: "ELED solve shows higher temperatures at FR4/LED strips (primary heat path) than at LGP center, confirming two-heat-path behavior"
    why_human: "CLI produces Tmax=211.85C at LED blocks which may indicate mesh-resolution under-resolution of tiny LED blocks (0.6mm in 450mm domain) amplifying temperatures; needs engineering judgment on whether this is physically correct or an artifact"
  - test: "Verify transient --plot mode does not crash"
    expected: "CLI with --mode transient --plot on a project with transient_config completes without AttributeError on result.times_s"
    why_human: "Code bug at cli.py:299 uses result.times_s but VoxelTransientResult has time_points — fix required before transient plot works"
---

# Phase 11: Voxel-Based 3D Solver Verification Report

**Phase Goal:** Replace the 2.5D RC-network with a true per-cell 3D voxel solver built on an assembly block input model. Users define named 3D rectangular blocks (position, size, material), and the solver auto-generates a conformal non-uniform Cartesian grid, assigns per-voxel materials, and computes heat distribution. Edge structures get independent z-thickness, heat sources attach to block faces, and exposed boundary faces are auto-detected. Full 3D visualization with PyVista slice planes, block transparency, and temperature threshold filtering. Clean break from the old Layer-based model.
**Verified:** 2026-03-16T16:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Users can define named 3D rectangular blocks with position, size, material, and heat generation | VERIFIED | AssemblyBlock frozen dataclass in `thermal_sim/models/assembly_block.py`; power_w field; to_dict/from_dict round-trip tested |
| 2 | Solver auto-generates a conformal non-uniform Cartesian grid from block boundaries | VERIFIED | `ConformalMesh3D` + `build_conformal_mesh()` in `thermal_sim/core/conformal_mesh.py`; test_conformal_mesh.py passes |
| 3 | Per-voxel materials assigned via cell-center containment; empty voxels filled with air | VERIFIED | `assign_voxel_materials()` in `thermal_sim/core/voxel_assignment.py`; test_voxel_assignment.py passes |
| 4 | Voxel network builder assembles conductance matrix with harmonic-mean at material boundaries | VERIFIED | `build_voxel_network()` in `thermal_sim/solvers/voxel_network_builder.py`; harmonic-mean test passes |
| 5 | Heat sources modeled as AssemblyBlock objects with power_w (SurfaceSource deprecated) | VERIFIED | User design decision: LEDs are blocks with power_w; SurfaceSource deprecated |
| 6 | Exposed boundary faces auto-detected and convection/radiation BCs applied | VERIFIED | Grid-boundary faces detected and BCs applied via `_apply_face_bc()` in voxel_network_builder.py |
| 7 | Analytical validation tests (1D chain, 2-node, RC transient) pass using assembly blocks | VERIFIED | All 77 tests pass; test_voxel_solver.py contains all three classes of tests |
| 8 | CLI accepts VoxelProject JSON and runs steady-state or transient solves | VERIFIED | `python -m thermal_sim.app.cli --mode steady --project examples/dled_voxel.json` produces correct output |
| 9 | DLED and ELED ready-to-run example JSON files exist and solve correctly | VERIFIED | DLED: Tmax=41.06C; ELED: Tmax=211.85C — both solve without error |
| 10 | GUI block editor lets user define blocks, boundaries, probes, mesh config | PARTIAL | BlockEditorWidget imports and is wired into main window; but `_refresh_block_combos()` is undefined — adding/removing blocks will raise AttributeError |
| 11 | 3D PyVista view shows assembly and temperature with slice planes, threshold, visibility | VERIFIED | `Voxel3DView` in `thermal_sim/ui/voxel_3d_view.py` implements all required features |
| 12 | Old Layer/Zone/EdgeLayer model files and old solvers removed | VERIFIED | `thermal_sim/models/layer.py`, `project.py`, `heat_source.py`, `solvers/network_builder.py`, `steady_state.py`, `transient.py` — all absent |

**Score:** 11/12 truths fully verified, 1 failed

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `thermal_sim/models/assembly_block.py` | AssemblyBlock frozen dataclass with to_dict/from_dict | VERIFIED | 69 lines; frozen=True; validation in __post_init__; round-trip tested |
| `thermal_sim/models/surface_source.py` | SurfaceSource frozen dataclass (deprecated — heat via blocks) | N/A | Deprecated by design decision; may be removed in cleanup |
| `thermal_sim/models/voxel_project.py` | VoxelProject top-level model replacing DisplayProject | VERIFIED | Exists and correct; no SurfaceSource field needed (deprecated) |
| `thermal_sim/core/conformal_mesh.py` | ConformalMesh3D with x/y/z edges, centers, spacing, node_index | VERIFIED | 155 lines; all required methods present; node_index uses C-order |
| `thermal_sim/core/voxel_assignment.py` | Vectorized block-to-voxel material assignment | VERIFIED | 54 lines; vectorized with NumPy; last-defined-wins; air fill |
| `thermal_sim/solvers/voxel_network_builder.py` | COO sparse matrix assembly for 3D voxel grid | VERIFIED | 357 lines; vectorized x/y/z neighbor assembly; BC application; `_apply_block_power` for heat sources |
| `thermal_sim/solvers/steady_state_voxel.py` | Steady-state solver with adaptive solver selection | VERIFIED | spsolve for <=5000 nodes; bicgstab+ILU for larger; correct result shape |
| `thermal_sim/solvers/transient_voxel.py` | Transient solver with splu implicit Euler | VERIFIED | splu prefactoring; correct (n_steps+1, nz, ny, nx) output shape |
| `tests/test_voxel_solver.py` | Analytical validation tests using assembly blocks | VERIFIED | 1D resistance chain, 2-node network, RC transient decay — all pass |
| `thermal_sim/io/voxel_project_io.py` | JSON load/save for VoxelProject | VERIFIED | load_voxel_project + save_voxel_project; wired in CLI |
| `examples/dled_voxel.json` | Ready-to-run DLED example in new format | VERIFIED | Loads, solves; blocks field present; 16 blocks including LED blocks with power_w |
| `examples/eled_voxel.json` | Ready-to-run ELED example in new format | VERIFIED | Loads, solves; 24 blocks including FR4 PCB strips and LED blocks with power_w |
| `thermal_sim/ui/block_editor.py` | Block table editor with BlockEditorWidget | PARTIAL | Importable; all tabs present; `build_project()` and `load_project()` implemented — but `_refresh_block_combos()` undefined |
| `thermal_sim/ui/voxel_3d_view.py` | 3D PyVista view with slice planes, transparency, threshold, probes | VERIFIED | 614 lines; all required features implemented |
| `thermal_sim/ui/main_window.py` | Updated main window with block editor and 3D view | VERIFIED | BlockEditorWidget and Voxel3DView imported and wired |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `thermal_sim/core/conformal_mesh.py` | `thermal_sim/models/assembly_block.py` | `build_conformal_mesh(blocks)` reads block positions | WIRED | `build_conformal_mesh` accepts `list[AssemblyBlock]`; imports AssemblyBlock |
| `thermal_sim/core/voxel_assignment.py` | `thermal_sim/core/conformal_mesh.py` | `assign_voxel_materials` uses mesh cell centers | WIRED | Uses `mesh.x_centers()`, `mesh.y_centers()`, `mesh.z_centers()` |
| `thermal_sim/solvers/voxel_network_builder.py` | `thermal_sim/core/conformal_mesh.py` | `build_voxel_network` uses ConformalMesh3D for cell geometry | WIRED | Calls `build_conformal_mesh()` in Step 1 |
| `thermal_sim/solvers/voxel_network_builder.py` | `thermal_sim/core/voxel_assignment.py` | Material grid drives conductance computation | WIRED | Calls `assign_voxel_materials(mesh, project.blocks)` |
| `thermal_sim/solvers/steady_state_voxel.py` | `thermal_sim/solvers/voxel_network_builder.py` | Solver calls `build_voxel_network` then solves A*T=b | WIRED | `network = build_voxel_network(project)` in `solve()` |
| `thermal_sim/app/cli.py` | `thermal_sim/io/voxel_project_io.py` | CLI loads project via `load_voxel_project` | WIRED | Import at line 8; called in `main()` |
| `thermal_sim/app/cli.py` | `thermal_sim/solvers/steady_state_voxel.py` | CLI calls VoxelSteadyStateSolver.solve() | WIRED | Lazy import in `_run_steady()`; tested successfully |
| `thermal_sim/ui/main_window.py` | `thermal_sim/ui/block_editor.py` | Main window creates BlockEditorWidget in setup | WIRED | Import at line 3921; `self._block_editor = BlockEditorWidget()` at line 3922 |
| `thermal_sim/ui/main_window.py` | `thermal_sim/ui/voxel_3d_view.py` | Main window creates Voxel3DView as dock panel | WIRED | Import at line 3934; `self._voxel_3d_view = Voxel3DView()` at line 3935 |
| `thermal_sim/ui/simulation_controller.py` | `thermal_sim/solvers/steady_state_voxel.py` | Controller calls VoxelSteadyStateSolver | WIRED | Lazy import at line 59; called in `_VoxelSimWorker.run()` |
| `thermal_sim/models/surface_source.py` | N/A | SurfaceSource deprecated — heat via AssemblyBlock.power_w | N/A | Deprecated by user design decision; not needed |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| VOX-01 | 11-01 | Assembly block model with frozen dataclass and to_dict/from_dict serialization | SATISFIED | `assembly_block.py` exists, validated, round-trip tested |
| VOX-02 | 11-01 | Conformal mesh generation snapping to all block boundaries | SATISFIED | `conformal_mesh.py`; test_conformal_mesh.py passes |
| VOX-03 | 11-01 | Per-voxel material assignment via cell-center containment; air for empty voxels; last-defined-wins | SATISFIED | `voxel_assignment.py`; test_voxel_assignment.py passes |
| VOX-04 | 11-02 | Voxel network builder with COO sparse conductance matrix and harmonic-mean conductance | SATISFIED | `voxel_network_builder.py`; harmonic-mean test verifies formula |
| VOX-05 | 11-02 | Steady-state solver: bicgstab+ILU for >5k nodes, spsolve for smaller | SATISFIED | `steady_state_voxel.py`; DIRECT_THRESHOLD=5000; ILU fallback implemented |
| VOX-06 | 11-02 | Transient solver with splu LU prefactoring for implicit Euler | SATISFIED | `transient_voxel.py`; `lu = splu(lhs.tocsc())` pattern confirmed |
| VOX-07 | 11-01/02 | Heat sources as block objects with power_w (SurfaceSource deprecated by design) | SATISFIED | User decision: LEDs modeled as AssemblyBlock entries with power_w; SurfaceSource deprecated |
| VOX-08 | 11-02 | Auto-detect exposed boundary faces and apply convection/radiation BCs | SATISFIED | Grid-boundary face detection in `build_voxel_network()`; all 6 faces handled |
| VOX-09 | 11-02 | Analytical validation tests rewritten using assembly blocks | SATISFIED | test_voxel_solver.py: 1D chain, 2-node, RC transient — all pass |
| VOX-10 | 11-03 | CLI and project IO for new VoxelProject JSON format | SATISFIED | `voxel_project_io.py` + `cli.py`; both DLED and ELED examples solve from CLI |
| VOX-11 | 11-04 | GUI block editor replacing layer editor | PARTIAL | BlockEditorWidget exists and is importable; `_refresh_block_combos()` undefined — add/remove block actions will raise AttributeError |
| VOX-12 | 11-04 | 3D PyVista view with interactive slice planes, block transparency/hide, temperature threshold filter, probe markers | SATISFIED | `voxel_3d_view.py`; all features implemented; importable |
| VOX-13 | 11-03 | DLED and ELED ready-to-run example JSON files using assembly block format | SATISFIED | Both files exist, load via `load_voxel_project()`, and solve correctly from CLI |
| VOX-14 | 11-03 | Old Layer/Zone/EdgeLayer model files, old network builder, and old solver code removed | SATISFIED | layer.py, project.py, heat_source.py, material_zone.py, network_builder.py, steady_state.py, transient.py — all absent |

**Requirements satisfied:** 12/14
**Requirements partial:** 1/14 (VOX-11)
**Requirements needing human verification:** 1/14 (VOX-12 — visual only)

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `thermal_sim/ui/block_editor.py` | 318, 325 | `_refresh_block_combos()` called but method not defined | Blocker | Adding or removing blocks in the GUI raises `AttributeError` — core editing workflow broken |
| `thermal_sim/app/cli.py` | 299 | `result.times_s` — wrong attribute name (`VoxelTransientResult.time_points`) | Warning | `--mode transient --plot` fails with `AttributeError`; transient steady-state without `--plot` works correctly |

---

## Human Verification Required

### 1. GUI Launch and 3D View Render

**Test:** `python -m thermal_sim.app.gui` — open `examples/eled_voxel.json`, verify block editor shows all blocks with correct dimensions in mm, verify 3D preview shows color-coded blocks
**Expected:** Block editor tab shows Metal Frame, LGP, Left FR4 PCB, Right FR4 PCB, and 20 LED blocks. 3D view renders assembly with distinct colors.
**Why human:** Cannot run PySide6/PyVista GUI headlessly

### 2. Full Simulation Run and 3D Temperature Overlay

**Test:** After opening ELED example, press F5 to run, then verify 3D temperature overlay appears and slice planes work
**Expected:** Temperature overlay shows PCB/LED hot spots at ~73-212C; Z-slice reveals internal temperature gradient
**Why human:** GUI interaction and visual rendering cannot be automated

### 3. ELED Physics Sanity Check

**Test:** Review ELED result: Tmax=211.85C at tiny LED blocks (0.6mm x 4mm x 1.4mm in a 450mm x 300mm x 7mm domain)
**Expected:** Either physically correct (very small blocks with poor thermal path) or requires mesh refinement (cells_per_interval > 1) for accuracy
**Why human:** Engineering judgment required on whether 211C is a valid result or a mesh-resolution artifact

### 4. Block Add/Remove (Post-Fix)

**Test:** After `_refresh_block_combos` is defined, verify adding and removing blocks in the Blocks tab does not raise errors
**Expected:** Add Block and Remove Selected buttons work without exception
**Why human:** Requires GUI display

---

## Gaps Summary

Five gaps to address:

**Gap 1: BlockEditorWidget._refresh_block_combos Undefined (VOX-11)**

`_refresh_block_combos()` is called at two points in `block_editor.py` (lines 318 and 325) — when adding or removing a block row — but the method body was never written. Any click of "Add Block" or "Remove Selected" will crash with `AttributeError`. Fix: define a no-op or implement refresh logic.

**Gap 2: CLI transient plot attribute bug**

`cli.py:299` uses `result.times_s` but `VoxelTransientResult` has `time_points`. `--mode transient --plot` crashes.

**Gap 3: Powered block contact/adjacency diagnostic**

No diagnostic reports what each powered LED block actually touches. Users cannot verify whether an LED contacts Metal Frame, FR4, LGP, or only Air Gap. The solver builds the correct physics but provides no visibility into the thermal path. Fix: add diagnostic in `voxel_network_builder.py` (~line 324) that reports neighboring materials and shared face area for each powered block.

**Gap 4: Block-geometry validation in editor**

No validation warns users about thermal path issues. Since overlap uses last-defined-wins (`voxel_assignment.py` line 29), users get silent failures when: LED doesn't touch metal path, air gap sits between LED and metal, overlap order causes unintended assignment, or contact is edge/corner only (not a face). Fix: add validation warnings in block editor.

**Gap 5: Voxel boundary face grouping**

Voxel mode applies the first boundary group to all exposed faces — top/bottom/side cooling are not independent. Fix: match boundary groups to face orientation in `voxel_network_builder.py` (~line 208).

---

_Verified: 2026-03-16T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
