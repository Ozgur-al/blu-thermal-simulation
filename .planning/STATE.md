---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: full-3d-solver
status: planning
last_updated: "2026-03-16"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Engineers can quickly set up a display stack, run thermal simulations, and get actionable results without programming knowledge or admin access — one-click launch, intuitive workflow.
**Current focus:** Milestone v2.0 — Full 3D Solver

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-16 — Milestone v2.0 started

## Accumulated Context

### From v1.0

- 2.5D RC-network solver works well for uniform layers
- Cell-overlap source masking enables coarse meshes with small LED footprints
- ELED template architecture is incorrect — LEDs should be on FR4 PCB adhered to metal cover, not on LGP
- The 2.5D model fundamentally can't represent lateral material variation within a layer
- Per-cell materials needed for ELED cross-section: metal | FR4+LED | air | LGP at same z-level
- Z-refinement (multiple z-nodes per layer) is straightforward once per-cell materials work
- Network builder already works cell-by-cell for heat sources — extending to per-cell materials is same pattern
- At 90x60 mesh, solver runs in <1s; 150x100 in ~5s; memory/speed fine up to ~200k nodes
- Grid mode auto-computes pitch from panel geometry — no manual pitch input needed
- spsolve (SuperLU) is single-threaded; CG didn't converge well at 1M nodes — keep direct solver, rely on reasonable mesh sizes

### Decisions

- Per-cell materials is the harder architectural change; z-refinement is trivial once per-cell works
- Structured Cartesian grid only — no unstructured/tetrahedral mesh needed for display modules
- Same G=kA/L RC-network math — not switching to FEM/CFD

### Pending Todos

None.

### Blockers/Concerns

- Per-cell material lookup changes the hot path in network_builder.py — need benchmarks to ensure no regression at typical mesh sizes
- JSON backward compat: old projects (no material zones, no z-refinement) must load and solve identically
