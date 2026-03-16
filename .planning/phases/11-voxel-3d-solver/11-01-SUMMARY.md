---
phase: 11-voxel-3d-solver
plan: "01"
subsystem: voxel-data-models
tags: [models, mesh, voxel, dataclass, serialization]
dependency_graph:
  requires: []
  provides:
    - AssemblyBlock frozen dataclass (thermal_sim/models/assembly_block.py)
    - SurfaceSource frozen dataclass (thermal_sim/models/surface_source.py)
    - VoxelProject top-level model (thermal_sim/models/voxel_project.py)
    - ConformalMesh3D non-uniform grid (thermal_sim/core/conformal_mesh.py)
    - assign_voxel_materials vectorized assignment (thermal_sim/core/voxel_assignment.py)
  affects: []
tech_stack:
  added: []
  patterns:
    - frozen dataclass + __post_init__ validation + to_dict/from_dict (AssemblyBlock, SurfaceSource)
    - mutable dataclass + to_dict/from_dict (VoxelProject and its sub-configs)
    - NumPy outer-product boolean mask for vectorized voxel assignment
    - C-order flat indexing: iz*ny*nx + iy*nx + ix
key_files:
  created:
    - thermal_sim/models/assembly_block.py
    - thermal_sim/models/surface_source.py
    - thermal_sim/models/voxel_project.py
    - thermal_sim/core/conformal_mesh.py
    - thermal_sim/core/voxel_assignment.py
    - tests/test_conformal_mesh.py
    - tests/test_voxel_assignment.py
  modified: []
decisions:
  - C-order node indexing (iz*ny*nx+iy*nx+ix) kept separate from PyVista visualization
    concern — VTK callers will use ravel(order='F') at render time
  - _DEDUP_TOL=1e-12 for floating-point edge deduplication in conformal mesh
  - Cell-centre containment uses inclusive-lower/exclusive-upper: cx >= block.x and cx < block.x + block.width
  - np.ix_ used for vectorized 3D sub-array assignment (avoids Python loops per cell)
  - VoxelProject uses mutable dataclass (not frozen) because it is a container with
    mutable lists; nested model classes (AssemblyBlock, SurfaceSource) remain frozen
metrics:
  duration: 4 min
  completed: "2026-03-16"
  tasks_completed: 2
  files_created: 7
  tests_added: 27
---

# Phase 11 Plan 01: Voxel Data Models and Conformal Mesh Summary

**One-liner:** AssemblyBlock/SurfaceSource/VoxelProject frozen dataclasses with to_dict/from_dict, plus ConformalMesh3D non-uniform grid and vectorized NumPy voxel-to-material assignment.

## What Was Built

Five new source files forming the foundational data layer for the voxel-based 3D solver:

1. **AssemblyBlock** (`thermal_sim/models/assembly_block.py`) — frozen dataclass defining a named 3D rectangular solid with position (x, y, z) and size (width, depth, height) in metres plus a material name reference. Validates non-empty name/material and positive dimensions.

2. **SurfaceSource** (`thermal_sim/models/surface_source.py`) — frozen dataclass placing heat power on a named block's face. Validates face membership in `{top, bottom, left, right, front, back}`, shape in `{full, rectangle, circle}`, non-negative power, and shape-specific dimension fields.

3. **VoxelProject** (`thermal_sim/models/voxel_project.py`) — top-level mutable dataclass holding blocks, materials dict, sources, boundary groups, probes, mesh config, and optional transient config. Four helper dataclasses: `VoxelProbe` (absolute 3D position), `BoundaryGroup` (named SurfaceBoundary), `VoxelMeshConfig` (cells_per_interval), `VoxelTransientConfig` (duration, dt, initial_temp).

4. **ConformalMesh3D** (`thermal_sim/core/conformal_mesh.py`) — non-uniform Cartesian grid built by `build_conformal_mesh(blocks, cells_per_interval=1)`. Collects all block boundary coordinates, deduplicates within 1e-12, and optionally subdivides intervals. Provides `nx/ny/nz`, `dx/dy/dz(i)` spacing, `x/y/z_centers()` 1-D arrays, and `node_index(ix, iy, iz)` using C-order.

5. **assign_voxel_materials** (`thermal_sim/core/voxel_assignment.py`) — vectorized NumPy function returning an `(nz, ny, nx)` object array of material name strings. Uses `np.ix_` for efficient 3D sub-array assignment; iterates blocks in definition order so last-defined wins on overlap; fills air for unoccupied cells.

## Test Coverage

Two new test files with 27 tests covering:
- AssemblyBlock/SurfaceSource/VoxelProject round-trips through to_dict/from_dict
- Validation error cases (empty name, invalid face, negative dimensions, missing shape fields)
- Conformal mesh edge collection with overlapping/touching/separated blocks
- Deduplication of coincident edges
- Cell count, center, and spacing calculations
- node_index C-order formula
- cells_per_interval subdivision
- Voxel assignment: single block fill, air gaps, last-defined-wins overlap, custom air name, shape (nz, ny, nx)

## Verification

```
py -m pytest tests/test_conformal_mesh.py tests/test_voxel_assignment.py -x -q
27 passed in 0.07s

py -m pytest -q tests/
287 passed in 26.92s
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- G:/blu-thermal-simulation/thermal_sim/models/assembly_block.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/models/surface_source.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/models/voxel_project.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/core/conformal_mesh.py — FOUND
- G:/blu-thermal-simulation/thermal_sim/core/voxel_assignment.py — FOUND
- G:/blu-thermal-simulation/tests/test_conformal_mesh.py — FOUND
- G:/blu-thermal-simulation/tests/test_voxel_assignment.py — FOUND

Commits:
- b98ad7c test(11-01): add failing tests for voxel models and conformal mesh
- 0ebb173 feat(11-01): add AssemblyBlock, SurfaceSource, and VoxelProject data models
- 844780f feat(11-01): add ConformalMesh3D and vectorized voxel material assignment
