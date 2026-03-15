# Thermal Simulator (Display/Automotive)

## What This Is

A desktop thermal simulation tool for display module concept studies, used by hardware/thermal engineers to evaluate layer stack configurations, hotspot behavior, and thermal margins. It models RC conduction networks with convection and radiation boundaries, offering both steady-state and transient analysis. Targets internal team distribution as a professional engineering tool with a polished, Zemax-inspired interface.

## Current Milestone: v2.0 Full 3D Solver

**Goal:** Upgrade from 2.5D (uniform material per layer, one z-node per layer) to a full 3D RC-network solver with per-cell material assignment and z-refinement — enabling accurate modeling of laterally heterogeneous layers like ELED edge assemblies.

**Target features:**
- Per-cell material zones within a layer (different materials at different x,y positions in same z-plane)
- Z-refinement (multiple nodes through a layer's thickness for through-plane resolution)
- Correct ELED thermal modeling with dual heat paths (LED→FR4→metal + LED→air→LGP)
- GUI for defining material regions and z-refinement controls
- 3D visualization with z-plane slicing

## Core Value

Engineers can quickly set up a display stack, run thermal simulations, and get actionable results (maps, probe data, reports) without programming knowledge or admin access — one-click launch, intuitive workflow.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Existing in codebase as of Phase 3. -->

- ✓ Layered 2.5D RC thermal network with in-plane and through-thickness conduction — Phase 1
- ✓ Steady-state solver (sparse linear system via scipy spsolve) — Phase 1
- ✓ Transient solver (implicit Euler with LU prefactoring) — Phase 2
- ✓ Material model with anisotropic conductivity (k_in_plane, k_through) and emissivity — Phase 1
- ✓ Layer stack with interface thermal resistance between layers — Phase 1
- ✓ Heat sources: full-area, rectangle, circle shapes with power distribution — Phase 1
- ✓ LED array template that auto-expands to localized heat sources — Phase 3
- ✓ Convection + linearized radiation boundary conditions (top, bottom, side) — Phase 1
- ✓ Virtual probe points at specific (layer, x, y) positions — Phase 2
- ✓ CLI runner with steady/transient modes, CSV export, PNG plot export — Phase 2
- ✓ JSON project save/load with full round-trip serialization — Phase 1
- ✓ PySide6 desktop GUI with tabbed editor and results dashboard — Phase 3
- ✓ Embedded matplotlib visualization (temperature maps, probe history, layer profiles) — Phase 3
- ✓ Material library presets (aluminum, copper, FR4, etc.) — Phase 2
- ✓ Analytical validation test suite (1D resistance chain, RC transient, convergence) — Phase 2
- ✓ Structure preview dialog in GUI — Phase 3
- ✓ Example project files (steady uniform, localized hotspots, LED backlight) — Phase 2

### Active

<!-- Current scope: v2.0 — Full 3D solver with per-cell materials and z-refinement. -->

- [ ] Per-cell material assignment within a layer (lateral material zones)
- [ ] Z-refinement (multiple z-nodes per layer thickness)
- [ ] 3D network builder using per-cell conductivity lookups
- [ ] ELED cross-section modeling (metal | FR4+LED | air | LGP at same z-level)
- [ ] GUI material zone editor (define rectangular regions with different materials)
- [ ] GUI z-refinement controls (per-layer node count)
- [ ] 3D visualization with arbitrary z-plane slicing
- [ ] Validation tests for 3D conduction (analytical benchmarks)
- [ ] Backward compatibility (2.5D projects load and solve identically)

### Out of Scope

- CFD / fluid flow modeling — this is an RC-network approximation tool, not a CFD solver
- Temperature-dependent material properties — intentionally constant for speed and simplicity
- Contact pressure-dependent interface resistance — beyond current model fidelity
- Web-based UI — desktop PySide6 is the target platform
- Mobile app — desktop engineering tool only
- Unstructured/tetrahedral meshing — structured Cartesian grid with material zones is sufficient for display modules
- Auto-mesh refinement — user controls resolution via nx/ny/nz parameters

## Context

- Existing codebase is at Phase 3 complete (see README.md for phase history)
- Target users are hardware/thermal engineers at the same company, not programmers
- Work computers have no admin access — packaging and install must work within user-space Python
- Colleagues familiar with tools like Zemax — expect professional, intuitive engineering UIs
- All internal units are SI; display in Celsius for temperature
- Codebase map available at `.planning/codebase/` with architecture, conventions, concerns docs

## Constraints

- **Platform**: Must run on Windows without admin access — user-space Python + pip only
- **Framework**: PySide6 for GUI (already invested, team has Qt experience)
- **Backward compat**: Existing project JSON files must continue to load correctly
- **Dependencies**: Pure Python ecosystem (numpy, scipy, matplotlib, PySide6) — no compiled C extensions or external build tools
- **Usability**: One-click launch for non-programmer engineers; no terminal interaction required for GUI mode

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PySide6 over web UI | Team already invested in Qt, desktop performance matters for interactive results | — Pending |
| PDF over interactive HTML for reports | Target audience prefers formal documents for handoff/review | — Pending |
| Parametric sweeps as core feature | Engineers need to compare design variants, not just single-point runs | — Pending |
| One-click packaging priority | Non-programmer users, no admin access — adoption depends on easy install | — Pending |
| 3D solver via RC-network extension | Same G=kA/L math, just more nodes — no need for FEM/CFD complexity | — Pending |
| Per-cell materials before z-refinement | Lateral variation is the harder architectural change; z-refinement is trivial once per-cell works | — Pending |
| Structured Cartesian grid only | Display modules are rectangular stacks; unstructured mesh adds complexity without value | — Pending |

---
*Last updated: 2026-03-16 after v2.0 milestone start*
