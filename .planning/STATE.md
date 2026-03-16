---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Full 3D Solver
status: in-progress
last_updated: "2026-03-16T14:52:00Z"
progress:
  total_phases: 11
  completed_phases: 10
  total_plans: 41
  completed_plans: 39
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access — one-click launch, intuitive workflow.
**Current focus:** Milestone v2.0 — Phase 11: Voxel-Based 3D Solver

## Current Position

Phase: 11 of 11 (Voxel-Based 3D Solver) — in progress
Plan: 3 of 5 (11-02 complete)
Status: in-progress
Last activity: 2026-03-16 — 11-02: voxel network builder + steady-state/transient solvers + 20 analytical validation tests

Progress: [█████████▊] 93%

## Performance Metrics

**Velocity:**
- Total plans completed: 6 (v2.0)
- Average duration: 8 min
- Total execution time: 0.60 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 07-3d-solver-core | 2 | 20 min | 10 min |
| 08-z-refinement | 3 | 20 min | 7 min |
| 09-3d-gui-and-eled-zone-preset | 2 | 15 min | 8 min |
| 10-edge-layers-and-3d-preview | 4 | 54 min | 14 min |

*Updated after each plan completion*

| Phase 11-voxel-3d-solver | 1 | 4 min | 4 min |
| Phase 11-voxel-3d-solver P02 | 1 | 6 min | 6 min |

## Accumulated Context

### Decisions

- Per-cell materials is the harder architectural change; z-refinement is trivial once per-cell works (drives Phase 7 before Phase 8)
- NodeLayout abstraction must be centralized before any z-refinement code — silently wrong otherwise
- Backward-compat regression test is the Phase 7 entry gate — write before touching any builder code
- Structured Cartesian grid only — no unstructured/tetrahedral mesh
- Vectorized NumPy conductance assembly required — no Python loops per cell in builder hot path
- DLED.json mesh: 450x300 causes UMFPACK OOM segfault in transient solve (1.08M nodes); reduced to 64x24 for regression baselines
- Layer.to_dict() omits 'zones' key entirely when zones=[] to preserve old JSON round-trip fidelity
- MaterialZone follows Material frozen dataclass pattern: __post_init__ validation + to_dict/from_dict
- [Phase 07-3d-solver-core]: NodeLayout.layer_offsets as tuple enables Phase 8 to vary nz per layer without changing call sites
- [Phase 07-3d-solver-core]: Zone rasterization reuses zone_maps cache per layer for lateral, through-thickness, and boundary conductance — one rasterization pass per layer
- [Phase 07-3d-solver-core]: Harmonic-mean test uses 0.9*dx zone width to avoid floating-point zone-boundary/cell-edge coincidence ambiguity
- [Phase 08-z-refinement]: z_position validation on HeatSource uses __post_init__ consistent with existing shape validation pattern
- [Phase 08-z-refinement]: Probe.z_position accepts str|int; from_dict converts digit strings to int for JSON round-trip fidelity
- [Phase 08-z-refinement]: Result dataclasses carry nz_per_layer/z_offsets as None until Plan 02 wires solver — None is valid backward-compat state
- [Phase 08-z-refinement]: xfail test scaffolds define exact physics expectations (concrete numbers, matrix setup) before solver implementation
- [Phase 08-z-refinement]: NodeLayout.layer_offsets updated to z_offsets[l]*n_per_layer so node() method works correctly for nz>1 layers without API changes
- [Phase 08-z-refinement]: Side BC conductance computed once per physical layer, applied per sublayer — correct because each sublayer has the same material map
- [Phase 08-z-refinement]: build_heat_source_vector recomputes z_offsets locally (does not take ThermalNetwork as argument) to keep public API unchanged
- [Phase 08-z-refinement]: CSV export writes top sublayer per physical layer (not all z-sublayers) — consistent with default visualization convention
- [Phase 08-z-refinement]: layer_stats() fallback logs a warning when z_offsets is None and total_z > n_layers — allows GUI callers to function correctly with nz=1 projects while documenting Phase 9 fix path
- [Phase 09-3d-gui-and-eled-zone-preset]: nz column uses QSpinBox as cell widget (column 4) rather than a table item; _build_project_from_ui reads cellWidget(row, 4).value() after parse_layers_table
- [Phase 09-3d-gui-and-eled-zone-preset]: _refresh_layer_choices(project, result=None) — result=None yields plain layer names; result with nz>1 yields z-sublayer entries with userData=flat_z_index
- [Phase 09-3d-gui-and-eled-zone-preset]: _plot_map uses currentData() as flat z-index; falls back to layer_names.index() when userData is None for backward compat
- [Phase 09-3d-gui-and-eled-zone-preset]: _layer_zones dict (layer_row -> list[dict]) mirrors _source_profiles pattern; stores SI metres internally, displays in mm in zone table
- [Phase 09-3d-gui-and-eled-zone-preset]: _updating_zones flag (not blockSignals) guards recursive cellChanged — blockSignals would also suppress the combo changes
- [Phase 09-3d-gui-and-eled-zone-preset]: zones= parameter on plot_temperature_map_annotated defaults to None — fully backward-compatible; ResultSnapshot.layer_zones uses getattr for older snapshots
- [Phase 09-3d-gui-and-eled-zone-preset]: Use 'Air Gap' (not 'Air') for ELED zone air material — only Air Gap exists in materials_builtin.json; matches _AIR_GAP_KEY in network_builder.py
- [Phase 09-3d-gui-and-eled-zone-preset]: generate_eled_zones() integration test uses edge_config='left_right' — only this config places LEDs in the x-axis FR4 zone columns; 'bottom' config places LEDs along y-axis and doesn't create lateral zone temperature contrast
- [Phase 10-edge-layers-and-3d-preview]: Bottom/top edge zones span full panel width to cover corners; left/right zones span interior height only
- [Phase 10-edge-layers-and-3d-preview]: Edge zones prepended before manual zones in solver so manual zones win on overlap (last-defined-wins)
- [Phase 10-edge-layers-and-3d-preview]: Layer.to_dict() omits edge_layers key when empty — consistent with existing zones omission pattern
- [Phase 10-edge-layers-and-3d-preview]: _layer_edge_layers dict (layer_row -> dict[edge, list[dict]]) mirrors _layer_zones pattern for GUI data storage
- [Phase 10-edge-layers-and-3d-preview]: _updating_edge_layers flag (not blockSignals) guards recursive cellChanged in edge table — same pattern as _updating_zones
- [Phase 10-edge-layers-and-3d-preview]: eled_template edge_layers: LED edges get Steel+Air Gap+FR4 (3mm+1mm+5mm), non-LED edges get Steel+Air Gap (3mm+1mm)
- [Phase 10-edge-layers-and-3d-preview]: _filter_materials updated to scan layer.edge_layers so ELED edge materials auto-included in template materials dict
- [Phase 10-edge-layers-and-3d-preview]: update_temperature() uses pv.ImageData per layer with cell_data scalars for temperature colormap overlay
- [Phase 10-edge-layers-and-3d-preview]: Toggle button starts disabled; enabled after first solve result; switches between material-colored structure and temperature overlay
- [Phase 10-edge-layers-and-3d-preview]: generate_edge_zones() called inside try/except in build_assembly_blocks() — catches ValueError (invalid dims) and ImportError; imported lazily inside block
- [Phase 10-edge-layers-and-3d-preview]: 2.5D model fundamentally cannot represent edge structures with independent z-thickness — edge zones inherit parent layer thickness, causing unrealistic thermal resistance for thin PCBs on thick LGPs
- [Phase 11-voxel-3d-solver]: C-order node indexing (iz*ny*nx+iy*nx+ix) kept separate from PyVista visualization — VTK callers will ravel with order='F'
- [Phase 11-voxel-3d-solver]: Cell-centre containment uses inclusive-lower/exclusive-upper bounds: cx >= block.x and cx < block.x + block.width
- [Phase 11-voxel-3d-solver]: Single BoundaryGroup applies to all 6 exposed grid-boundary faces; 1D chain test corrected to include all 6-face conductances in hand calculation
- [Phase 11-voxel-3d-solver]: VoxelThermalNetwork stores b_vector as combined BC+source term — no split needed for voxel solver

### Roadmap Evolution

- Phase 11 added: Voxel-Based 3D Solver — per-cell 3D material grid replacing 2.5D RC-network

### Pending Todos

None.

### Blockers/Concerns

- Phase 9 ELED preset: verify that Phase 6 ELED stack template exposes frame width, LED board width, and air gap width as named fields before committing to preset implementation approach (one-file inspection at Phase 9 planning start)
- CSV export format versioning: adding z-slice index to exports will break existing CSV readers — plan a format version bump before Phase 8 is declared complete

## Session Continuity

Last session: 2026-03-16
Stopped at: Completed 11-02-PLAN.md (voxel network builder + solvers + analytical validation tests)
Resume file: .planning/phases/11-voxel-3d-solver/11-02-SUMMARY.md
