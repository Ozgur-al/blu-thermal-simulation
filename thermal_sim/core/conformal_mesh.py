"""ConformalMesh3D — non-uniform 3D grid snapped to assembly block boundaries."""

from __future__ import annotations

import numpy as np

from thermal_sim.models.assembly_block import AssemblyBlock

_DEDUP_TOL = 1e-12  # floating-point tolerance for edge deduplication


class ConformalMesh3D:
    """Non-uniform Cartesian grid whose edges align with all block faces.

    Edges are stored as numpy float64 arrays. Cell counts follow from the
    number of intervals: ``nx = len(x_edges) - 1``, etc.

    Node flat index uses **C-order**: ``iz * ny * nx + iy * nx + ix``.
    This is the convention expected by the voxel network builder. Visualization
    code that uses VTK/PyVista RectilinearGrid should ravel temperature arrays
    with ``order='F'`` when calling VTK APIs that expect Fortran order.
    """

    def __init__(
        self,
        x_edges: np.ndarray,
        y_edges: np.ndarray,
        z_edges: np.ndarray,
    ) -> None:
        self.x_edges = x_edges
        self.y_edges = y_edges
        self.z_edges = z_edges

    # ------------------------------------------------------------------
    # Cell count properties
    # ------------------------------------------------------------------

    @property
    def nx(self) -> int:
        return len(self.x_edges) - 1

    @property
    def ny(self) -> int:
        return len(self.y_edges) - 1

    @property
    def nz(self) -> int:
        return len(self.z_edges) - 1

    @property
    def total_cells(self) -> int:
        return self.nx * self.ny * self.nz

    # ------------------------------------------------------------------
    # Spacing accessors
    # ------------------------------------------------------------------

    def dx(self, i: int) -> float:
        """Width of x-interval i (metres)."""
        return float(self.x_edges[i + 1] - self.x_edges[i])

    def dy(self, j: int) -> float:
        """Width of y-interval j (metres)."""
        return float(self.y_edges[j + 1] - self.y_edges[j])

    def dz(self, k: int) -> float:
        """Width of z-interval k (metres)."""
        return float(self.z_edges[k + 1] - self.z_edges[k])

    # ------------------------------------------------------------------
    # Cell-center arrays
    # ------------------------------------------------------------------

    def x_centers(self) -> np.ndarray:
        """Midpoints of x-intervals as a 1-D float64 array."""
        return 0.5 * (self.x_edges[:-1] + self.x_edges[1:])

    def y_centers(self) -> np.ndarray:
        """Midpoints of y-intervals as a 1-D float64 array."""
        return 0.5 * (self.y_edges[:-1] + self.y_edges[1:])

    def z_centers(self) -> np.ndarray:
        """Midpoints of z-intervals as a 1-D float64 array."""
        return 0.5 * (self.z_edges[:-1] + self.z_edges[1:])

    # ------------------------------------------------------------------
    # Node indexing
    # ------------------------------------------------------------------

    def node_index(self, ix: int, iy: int, iz: int) -> int:
        """Flat C-order node index: ``iz * ny * nx + iy * nx + ix``."""
        return iz * self.ny * self.nx + iy * self.nx + ix


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def _collect_and_dedup(coords: list[float]) -> np.ndarray:
    """Sort a list of coordinates and remove duplicates within _DEDUP_TOL."""
    arr = np.array(sorted(set(coords)), dtype=np.float64)
    if len(arr) < 2:
        return arr
    # Remove values too close to their predecessor
    keep = np.ones(len(arr), dtype=bool)
    for i in range(1, len(arr)):
        if arr[i] - arr[i - 1] < _DEDUP_TOL:
            keep[i] = False
    return arr[keep]


def _subdivide(edges: np.ndarray, cells_per_interval: int) -> np.ndarray:
    """Subdivide each interval in ``edges`` into ``cells_per_interval`` equal cells."""
    if cells_per_interval <= 1:
        return edges
    result: list[float] = [float(edges[0])]
    for i in range(len(edges) - 1):
        lo = float(edges[i])
        hi = float(edges[i + 1])
        for j in range(1, cells_per_interval + 1):
            result.append(lo + j * (hi - lo) / cells_per_interval)
    return np.array(result, dtype=np.float64)


def build_conformal_mesh(
    blocks: list[AssemblyBlock],
    cells_per_interval: int = 1,
) -> ConformalMesh3D:
    """Build a ConformalMesh3D from a list of AssemblyBlocks.

    Collects all block boundary coordinates in x, y, and z, sorts and
    deduplicates them (within floating-point tolerance), and optionally
    subdivides each interval by ``cells_per_interval``.
    """
    x_coords: list[float] = []
    y_coords: list[float] = []
    z_coords: list[float] = []

    for blk in blocks:
        x_coords.extend([blk.x, blk.x + blk.width])
        y_coords.extend([blk.y, blk.y + blk.depth])
        z_coords.extend([blk.z, blk.z + blk.height])

    x_edges = _collect_and_dedup(x_coords)
    y_edges = _collect_and_dedup(y_coords)
    z_edges = _collect_and_dedup(z_coords)

    if cells_per_interval > 1:
        x_edges = _subdivide(x_edges, cells_per_interval)
        y_edges = _subdivide(y_edges, cells_per_interval)
        z_edges = _subdivide(z_edges, cells_per_interval)

    return ConformalMesh3D(x_edges=x_edges, y_edges=y_edges, z_edges=z_edges)
