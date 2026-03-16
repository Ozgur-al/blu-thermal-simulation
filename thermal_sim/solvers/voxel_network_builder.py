"""Voxel-based 3D thermal network builder.

Converts a VoxelProject (assembly blocks + surface sources + boundary conditions)
into a sparse linear system A*T = b with thermal capacity vector C for both
steady-state and transient solvers.

Node indexing follows C-order:  flat = iz * ny * nx + iy * nx + ix
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix

from thermal_sim.core.conformal_mesh import ConformalMesh3D, build_conformal_mesh
from thermal_sim.core.constants import STEFAN_BOLTZMANN
from thermal_sim.core.voxel_assignment import assign_voxel_materials, _DEFAULT_AIR
from thermal_sim.models.material import Material
from thermal_sim.models.voxel_project import VoxelProject

logger = logging.getLogger(__name__)

# Default air material used for cells outside any defined block.
# Projects that don't define "Air Gap" explicitly will fall back to this.
_DEFAULT_AIR_MATERIAL = Material(
    name=_DEFAULT_AIR,
    k_in_plane=0.026,
    k_through=0.026,
    density=1.2,
    specific_heat=1006.0,
    emissivity=0.0,
)


@dataclass
class VoxelThermalNetwork:
    """Discrete 3D network representation of a VoxelProject."""

    a_matrix: csr_matrix    # conductance matrix (n_cells x n_cells)
    b_vector: np.ndarray    # forcing vector (n_cells,) = BC + source contributions
    c_vector: np.ndarray    # thermal capacity vector (n_cells,)
    mesh: ConformalMesh3D
    material_grid: np.ndarray  # (nz, ny, nx) material name strings


def build_voxel_network(project: VoxelProject) -> VoxelThermalNetwork:
    """Build a sparse thermal network from a VoxelProject.

    Steps:
    1. Build conformal mesh and assign materials.
    2. Build per-cell material property arrays (k_in_plane, k_through, density*cp).
    3. Assemble conductance matrix using vectorised COO triplets.
    4. Auto-detect exposed faces; apply boundary conditions.
    5. Build heat source (b_sources) vector.
    6. Build capacity vector C.
    """
    # ------------------------------------------------------------------
    # Step 1: mesh + material assignment
    # ------------------------------------------------------------------
    mesh = build_conformal_mesh(project.blocks, project.mesh_config.cells_per_interval)
    material_grid = assign_voxel_materials(mesh, project.blocks)  # (nz, ny, nx)

    nx, ny, nz = mesh.nx, mesh.ny, mesh.nz
    n_cells = mesh.total_cells

    # ------------------------------------------------------------------
    # Step 2: per-cell material property arrays
    # ------------------------------------------------------------------
    k_ip = np.empty((nz, ny, nx), dtype=float)   # in-plane (x, y)
    k_th = np.empty((nz, ny, nx), dtype=float)   # through-thickness (z)
    rho_cp = np.empty((nz, ny, nx), dtype=float) # density * specific_heat
    emissivity = np.empty((nz, ny, nx), dtype=float)

    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                mat_name = str(material_grid[iz, iy, ix])
                mat = project.materials.get(mat_name, _DEFAULT_AIR_MATERIAL)
                k_ip[iz, iy, ix] = mat.k_in_plane
                k_th[iz, iy, ix] = mat.k_through
                rho_cp[iz, iy, ix] = mat.density * mat.specific_heat
                emissivity[iz, iy, ix] = mat.emissivity

    # ------------------------------------------------------------------
    # Pre-compute cell size arrays
    # ------------------------------------------------------------------
    dx = np.array([mesh.dx(i) for i in range(nx)], dtype=float)  # (nx,)
    dy = np.array([mesh.dy(j) for j in range(ny)], dtype=float)  # (ny,)
    dz = np.array([mesh.dz(k) for k in range(nz)], dtype=float)  # (nz,)

    # Broadcast to 3D grids for vectorised computation
    # DX[iz, iy, ix] = dx[ix]
    DX = dx[np.newaxis, np.newaxis, :]   # (1, 1, nx)
    DY = dy[np.newaxis, :, np.newaxis]   # (1, ny, 1)
    DZ = dz[:, np.newaxis, np.newaxis]   # (nz, 1, 1)

    # ------------------------------------------------------------------
    # COO accumulators
    # ------------------------------------------------------------------
    coo_rows: list[np.ndarray] = []
    coo_cols: list[np.ndarray] = []
    coo_data: list[np.ndarray] = []

    b_boundary = np.zeros(n_cells, dtype=float)
    b_sources = np.zeros(n_cells, dtype=float)

    def _add_links(n1: np.ndarray, n2: np.ndarray, G: np.ndarray) -> None:
        """Add symmetric conductance links between node pairs in COO format."""
        mask = G > 0.0
        if not mask.any():
            return
        n1, n2, G = n1[mask], n2[mask], G[mask]
        # Diagonals: +G
        coo_rows.append(n1); coo_cols.append(n1); coo_data.append(G)
        coo_rows.append(n2); coo_cols.append(n2); coo_data.append(G)
        # Off-diagonals: -G
        coo_rows.append(n1); coo_cols.append(n2); coo_data.append(-G)
        coo_rows.append(n2); coo_cols.append(n1); coo_data.append(-G)

    def _node_flat(iz_arr, iy_arr, ix_arr):
        """Return flat C-order node indices from integer index arrays."""
        return (iz_arr * ny * nx + iy_arr * nx + ix_arr).ravel()

    # ------------------------------------------------------------------
    # Step 3: conductance matrix — x-direction links
    # Pairs: (iz, iy, ix) -- (iz, iy, ix+1)  for ix in [0, nx-2]
    # face area = dy[iy] * dz[iz]
    # half-distances: dx[ix]/2 on left, dx[ix+1]/2 on right
    # G = face_area / (half_left/k_left + half_right/k_right)
    # ------------------------------------------------------------------
    if nx >= 2:
        iz_idx, iy_idx, ix_idx = np.meshgrid(
            np.arange(nz), np.arange(ny), np.arange(nx - 1), indexing='ij'
        )
        iz_f = iz_idx.ravel()
        iy_f = iy_idx.ravel()
        ix_f = ix_idx.ravel()  # left cell index

        face_area_x = (DY * DZ)[iz_f, iy_f, 0]  # dy[iy] * dz[iz]
        # Compute per-pair face areas vectorised
        face_area_x = dy[iy_f] * dz[iz_f]

        half_left  = dx[ix_f]       / 2.0
        half_right = dx[ix_f + 1]   / 2.0
        k_left  = k_ip[iz_f, iy_f, ix_f]
        k_right = k_ip[iz_f, iy_f, ix_f + 1]
        denom = half_left / k_left + half_right / k_right
        G_x = np.where(denom > 0.0, face_area_x / denom, 0.0)

        n1_x = _node_flat(iz_f, iy_f, ix_f)
        n2_x = _node_flat(iz_f, iy_f, ix_f + 1)
        _add_links(n1_x, n2_x, G_x)

    # ------------------------------------------------------------------
    # y-direction links
    # Pairs: (iz, iy, ix) -- (iz, iy+1, ix)  for iy in [0, ny-2]
    # face area = dx[ix] * dz[iz]
    # ------------------------------------------------------------------
    if ny >= 2:
        iz_idx, iy_idx, ix_idx = np.meshgrid(
            np.arange(nz), np.arange(ny - 1), np.arange(nx), indexing='ij'
        )
        iz_f = iz_idx.ravel()
        iy_f = iy_idx.ravel()
        ix_f = ix_idx.ravel()

        face_area_y = dx[ix_f] * dz[iz_f]
        half_bot  = dy[iy_f]       / 2.0
        half_top  = dy[iy_f + 1]   / 2.0
        k_bot = k_ip[iz_f, iy_f, ix_f]
        k_top = k_ip[iz_f, iy_f + 1, ix_f]
        denom = half_bot / k_bot + half_top / k_top
        G_y = np.where(denom > 0.0, face_area_y / denom, 0.0)

        n1_y = _node_flat(iz_f, iy_f, ix_f)
        n2_y = _node_flat(iz_f, iy_f + 1, ix_f)
        _add_links(n1_y, n2_y, G_y)

    # ------------------------------------------------------------------
    # z-direction links
    # Pairs: (iz, iy, ix) -- (iz+1, iy, ix)  for iz in [0, nz-2]
    # face area = dx[ix] * dy[iy]
    # Uses k_through for z-direction
    # ------------------------------------------------------------------
    if nz >= 2:
        iz_idx, iy_idx, ix_idx = np.meshgrid(
            np.arange(nz - 1), np.arange(ny), np.arange(nx), indexing='ij'
        )
        iz_f = iz_idx.ravel()
        iy_f = iy_idx.ravel()
        ix_f = ix_idx.ravel()

        face_area_z = dx[ix_f] * dy[iy_f]
        half_lo = dz[iz_f]       / 2.0
        half_hi = dz[iz_f + 1]   / 2.0
        k_lo = k_th[iz_f, iy_f, ix_f]
        k_hi = k_th[iz_f + 1, iy_f, ix_f]
        denom = half_lo / k_lo + half_hi / k_hi
        G_z = np.where(denom > 0.0, face_area_z / denom, 0.0)

        n1_z = _node_flat(iz_f, iy_f, ix_f)
        n2_z = _node_flat(iz_f + 1, iy_f, ix_f)
        _add_links(n1_z, n2_z, G_z)

    # ------------------------------------------------------------------
    # Step 4: boundary conditions on exposed faces
    # ------------------------------------------------------------------
    # An exposed face is a grid-boundary face (ix=0, ix=nx-1, etc.).
    # All exposed faces are assigned to the first boundary group.
    # Future: named face -> group assignment.

    if project.boundary_groups:
        bc = project.boundary_groups[0].boundary
        amb_k = bc.ambient_c + 273.15
        h_conv = bc.convection_h
        h_rad = 0.0
        if bc.include_radiation:
            # Compute averaged emissivity over grid for radiation
            h_rad_arr = 4.0 * emissivity * STEFAN_BOLTZMANN * amb_k ** 3  # per-cell

        def _apply_face_bc(iz_arr, iy_arr, ix_arr, face_areas):
            """Apply BC to given face voxels with corresponding face areas."""
            iz_a = iz_arr.ravel()
            iy_a = iy_arr.ravel()
            ix_a = ix_arr.ravel()
            fa = face_areas.ravel()

            G_conv = h_conv * fa
            if bc.include_radiation:
                eps_arr = emissivity[iz_a, iy_a, ix_a]
                if bc.emissivity_override is not None:
                    eps_arr = np.full_like(eps_arr, bc.emissivity_override)
                h_rad_cell = 4.0 * eps_arr * STEFAN_BOLTZMANN * amb_k ** 3
                G_surf = (G_conv + h_rad_cell * fa)
            else:
                G_surf = G_conv

            nodes = _node_flat(iz_a, iy_a, ix_a)
            mask = G_surf > 0.0
            if not mask.any():
                return
            coo_rows.append(nodes[mask])
            coo_cols.append(nodes[mask])
            coo_data.append(G_surf[mask])
            b_boundary[nodes[mask]] += G_surf[mask] * bc.ambient_c

        # Bottom face: iz = 0
        iz_bot = np.zeros((ny, nx), dtype=int)
        iy_bot, ix_bot = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
        fa_bot = np.outer(dy, dx)  # (ny, nx): dy[iy]*dx[ix]
        _apply_face_bc(iz_bot, iy_bot, ix_bot, fa_bot)

        # Top face: iz = nz-1
        iz_top = np.full((ny, nx), nz - 1, dtype=int)
        iy_top, ix_top = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
        fa_top = np.outer(dy, dx)
        _apply_face_bc(iz_top, iy_top, ix_top, fa_top)

        # Front face: iy = 0
        iz_front, ix_front = np.meshgrid(np.arange(nz), np.arange(nx), indexing='ij')
        iy_front = np.zeros((nz, nx), dtype=int)
        fa_front = np.outer(dz, dx)  # (nz, nx): dz[iz]*dx[ix]
        _apply_face_bc(iz_front, iy_front, ix_front, fa_front)

        # Back face: iy = ny-1
        iz_back, ix_back = np.meshgrid(np.arange(nz), np.arange(nx), indexing='ij')
        iy_back = np.full((nz, nx), ny - 1, dtype=int)
        fa_back = np.outer(dz, dx)
        _apply_face_bc(iz_back, iy_back, ix_back, fa_back)

        # Left face: ix = 0
        iz_left, iy_left = np.meshgrid(np.arange(nz), np.arange(ny), indexing='ij')
        ix_left = np.zeros((nz, ny), dtype=int)
        fa_left = np.outer(dz, dy)  # (nz, ny): dz[iz]*dy[iy]
        _apply_face_bc(iz_left, iy_left, ix_left, fa_left)

        # Right face: ix = nx-1
        iz_right, iy_right = np.meshgrid(np.arange(nz), np.arange(ny), indexing='ij')
        ix_right = np.full((nz, ny), nx - 1, dtype=int)
        fa_right = np.outer(dz, dy)
        _apply_face_bc(iz_right, iy_right, ix_right, fa_right)

    # ------------------------------------------------------------------
    # Step 5: heat source vector
    # ------------------------------------------------------------------
    _apply_block_power(project, mesh, b_sources)

    # ------------------------------------------------------------------
    # Step 6: thermal capacity vector
    # ------------------------------------------------------------------
    c_vec = np.empty(n_cells, dtype=float)
    # volume[iz, iy, ix] = dx[ix] * dy[iy] * dz[iz]
    volumes = DX * DY * DZ  # broadcast to (nz, ny, nx)
    c_3d = rho_cp * volumes  # (nz, ny, nx)
    c_vec[:] = c_3d.ravel()  # C-order

    # ------------------------------------------------------------------
    # Assemble COO -> CSR
    # ------------------------------------------------------------------
    if coo_rows:
        all_rows = np.concatenate(coo_rows)
        all_cols = np.concatenate(coo_cols)
        all_data = np.concatenate(coo_data)
        a_mat = coo_matrix(
            (all_data, (all_rows, all_cols)), shape=(n_cells, n_cells), dtype=float
        ).tocsr()
    else:
        a_mat = csr_matrix((n_cells, n_cells), dtype=float)

    b_vec = b_boundary + b_sources

    # ------------------------------------------------------------------
    # Step 7: log powered-block contact summary (diagnostic)
    # ------------------------------------------------------------------
    _log_powered_block_contacts(project)

    return VoxelThermalNetwork(
        a_matrix=a_mat,
        b_vector=b_vec,
        c_vector=c_vec,
        mesh=mesh,
        material_grid=material_grid,
    )


def diagnose_powered_block_contacts(
    project: VoxelProject,
) -> list[dict]:
    """Report neighboring materials and shared face area for each powered block.

    Returns a list of dicts, one per powered block:
    {
        "block_name": str,
        "power_w": float,
        "neighbors": [
            {"material": str, "face_area_m2": float, "direction": str},
            ...
        ]
    }

    Direction is one of: "+x", "-x", "+y", "-y", "+z", "-z".
    Only reports contacts with non-air materials, plus a single aggregate "air" entry
    if any air contact exists.
    """
    mesh = build_conformal_mesh(project.blocks, project.mesh_config.cells_per_interval)
    material_grid = assign_voxel_materials(mesh, project.blocks)  # (nz, ny, nx)

    nx, ny, nz = mesh.nx, mesh.ny, mesh.nz
    cx = mesh.x_centers()
    cy = mesh.y_centers()
    cz = mesh.z_centers()

    dx = np.array([mesh.dx(i) for i in range(nx)], dtype=float)
    dy = np.array([mesh.dy(j) for j in range(ny)], dtype=float)
    dz = np.array([mesh.dz(k) for k in range(nz)], dtype=float)

    results = []

    for blk in project.blocks:
        if blk.power_w <= 0.0:
            continue

        # Find voxel indices inside this block (cell-centre containment)
        in_x = (cx >= blk.x) & (cx < blk.x + blk.width)
        in_y = (cy >= blk.y) & (cy < blk.y + blk.depth)
        in_z = (cz >= blk.z) & (cz < blk.z + blk.height)

        ix_blk = np.where(in_x)[0]
        iy_blk = np.where(in_y)[0]
        iz_blk = np.where(in_z)[0]

        if ix_blk.size == 0 or iy_blk.size == 0 or iz_blk.size == 0:
            results.append({
                "block_name": blk.name,
                "power_w": blk.power_w,
                "neighbors": [],
            })
            continue

        ix_min, ix_max = int(ix_blk[0]), int(ix_blk[-1])
        iy_min, iy_max = int(iy_blk[0]), int(iy_blk[-1])
        iz_min, iz_max = int(iz_blk[0]), int(iz_blk[-1])

        # Accumulate face areas per (material, direction) using a dict
        # face_contacts[direction][material] = total_face_area
        face_contacts: dict[str, dict[str, float]] = {}
        for d in ("+x", "-x", "+y", "-y", "+z", "-z"):
            face_contacts[d] = {}

        def _accumulate(direction: str, iz_arr, iy_arr, ix_arr, areas):
            """Add face areas for the given neighbor voxels."""
            iz_a = np.asarray(iz_arr).ravel()
            iy_a = np.asarray(iy_arr).ravel()
            ix_a = np.asarray(ix_arr).ravel()
            areas_a = np.asarray(areas).ravel()
            for k in range(len(iz_a)):
                iz_n, iy_n, ix_n = int(iz_a[k]), int(iy_a[k]), int(ix_a[k])
                # Clamp to valid grid range
                if iz_n < 0 or iz_n >= nz:
                    mat = _DEFAULT_AIR
                elif iy_n < 0 or iy_n >= ny:
                    mat = _DEFAULT_AIR
                elif ix_n < 0 or ix_n >= nx:
                    mat = _DEFAULT_AIR
                else:
                    mat = str(material_grid[iz_n, iy_n, ix_n])
                a = float(areas_a[k])
                face_contacts[direction][mat] = face_contacts[direction].get(mat, 0.0) + a

        # +x face: neighbor at ix_max+1, varying iy and iz inside block
        ix_p = ix_max + 1
        if ix_p < nx:
            iy_g, iz_g = np.meshgrid(iy_blk, iz_blk, indexing='ij')
            areas = np.outer(dy[iy_blk], dz[iz_blk])
            _accumulate("+x", iz_g, iy_g, np.full_like(iz_g, ix_p), areas)
        else:
            # All faces at grid boundary → air
            total_area = float(dy[iy_blk].sum() * dz[iz_blk].sum())
            face_contacts["+x"][_DEFAULT_AIR] = face_contacts["+x"].get(_DEFAULT_AIR, 0.0) + total_area

        # -x face: neighbor at ix_min-1
        ix_m = ix_min - 1
        if ix_m >= 0:
            iy_g, iz_g = np.meshgrid(iy_blk, iz_blk, indexing='ij')
            areas = np.outer(dy[iy_blk], dz[iz_blk])
            _accumulate("-x", iz_g, iy_g, np.full_like(iz_g, ix_m), areas)
        else:
            total_area = float(dy[iy_blk].sum() * dz[iz_blk].sum())
            face_contacts["-x"][_DEFAULT_AIR] = face_contacts["-x"].get(_DEFAULT_AIR, 0.0) + total_area

        # +y face: neighbor at iy_max+1
        iy_p = iy_max + 1
        if iy_p < ny:
            ix_g, iz_g = np.meshgrid(ix_blk, iz_blk, indexing='ij')
            areas = np.outer(dx[ix_blk], dz[iz_blk])
            _accumulate("+y", iz_g, np.full_like(iz_g, iy_p), ix_g, areas)
        else:
            total_area = float(dx[ix_blk].sum() * dz[iz_blk].sum())
            face_contacts["+y"][_DEFAULT_AIR] = face_contacts["+y"].get(_DEFAULT_AIR, 0.0) + total_area

        # -y face: neighbor at iy_min-1
        iy_m = iy_min - 1
        if iy_m >= 0:
            ix_g, iz_g = np.meshgrid(ix_blk, iz_blk, indexing='ij')
            areas = np.outer(dx[ix_blk], dz[iz_blk])
            _accumulate("-y", iz_g, np.full_like(iz_g, iy_m), ix_g, areas)
        else:
            total_area = float(dx[ix_blk].sum() * dz[iz_blk].sum())
            face_contacts["-y"][_DEFAULT_AIR] = face_contacts["-y"].get(_DEFAULT_AIR, 0.0) + total_area

        # +z face: neighbor at iz_max+1
        iz_p = iz_max + 1
        if iz_p < nz:
            ix_g, iy_g = np.meshgrid(ix_blk, iy_blk, indexing='ij')
            areas = np.outer(dx[ix_blk], dy[iy_blk])
            _accumulate("+z", np.full_like(ix_g, iz_p), iy_g, ix_g, areas)
        else:
            total_area = float(dx[ix_blk].sum() * dy[iy_blk].sum())
            face_contacts["+z"][_DEFAULT_AIR] = face_contacts["+z"].get(_DEFAULT_AIR, 0.0) + total_area

        # -z face: neighbor at iz_min-1
        iz_m = iz_min - 1
        if iz_m >= 0:
            ix_g, iy_g = np.meshgrid(ix_blk, iy_blk, indexing='ij')
            areas = np.outer(dx[ix_blk], dy[iy_blk])
            _accumulate("-z", np.full_like(ix_g, iz_m), iy_g, ix_g, areas)
        else:
            total_area = float(dx[ix_blk].sum() * dy[iy_blk].sum())
            face_contacts["-z"][_DEFAULT_AIR] = face_contacts["-z"].get(_DEFAULT_AIR, 0.0) + total_area

        # Flatten into neighbor list
        neighbors = []
        for direction, mat_areas in face_contacts.items():
            for mat, area in mat_areas.items():
                if area > 0.0:
                    neighbors.append({
                        "material": mat,
                        "face_area_m2": area,
                        "direction": direction,
                    })

        results.append({
            "block_name": blk.name,
            "power_w": blk.power_w,
            "neighbors": neighbors,
        })

    return results


def _log_powered_block_contacts(project: VoxelProject) -> None:
    """Log a summary line per powered block after network build."""
    if not logger.isEnabledFor(logging.INFO):
        return
    contacts = diagnose_powered_block_contacts(project)
    for entry in contacts:
        name = entry["block_name"]
        pw = entry["power_w"]
        parts = []
        for n in entry["neighbors"]:
            parts.append(f"{n['direction']} -> {n['material']} ({n['face_area_m2']:.2e} m2)")
        summary = ", ".join(parts) if parts else "no neighbors"
        logger.info("Block '%s' (%.3gW): %s", name, pw, summary)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_block_power(
    project: VoxelProject,
    mesh: ConformalMesh3D,
    b_vec: np.ndarray,
) -> None:
    """Inject volumetric heat from blocks with power_w > 0.

    Power is distributed uniformly across all voxels belonging to the block.
    Heat conducts naturally into adjacent blocks via the conductance matrix.
    """
    nx, ny, nz = mesh.nx, mesh.ny, mesh.nz
    cx = mesh.x_centers()
    cy = mesh.y_centers()
    cz = mesh.z_centers()

    for blk in project.blocks:
        if blk.power_w <= 0.0:
            continue

        in_x = (cx >= blk.x) & (cx < blk.x + blk.width)
        in_y = (cy >= blk.y) & (cy < blk.y + blk.depth)
        in_z = (cz >= blk.z) & (cz < blk.z + blk.height)

        ix_blk = np.where(in_x)[0]
        iy_blk = np.where(in_y)[0]
        iz_blk = np.where(in_z)[0]
        if ix_blk.size == 0 or iy_blk.size == 0 or iz_blk.size == 0:
            continue

        iz_g, iy_g, ix_g = np.meshgrid(iz_blk, iy_blk, ix_blk, indexing='ij')
        nodes = (iz_g * ny * nx + iy_g * nx + ix_g).ravel()
        power_per_cell = blk.power_w / nodes.size
        np.add.at(b_vec, nodes, power_per_cell)
