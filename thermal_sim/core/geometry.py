"""Mesh/grid utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid2D:
    """Regular Cartesian grid over a rectangle."""

    width: float
    height: float
    nx: int
    ny: int

    def __post_init__(self) -> None:
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("Grid width/height must be > 0.")
        if self.nx < 1 or self.ny < 1:
            raise ValueError("Grid nx/ny must be >= 1.")

    @property
    def dx(self) -> float:
        return self.width / self.nx

    @property
    def dy(self) -> float:
        return self.height / self.ny

    @property
    def cell_area(self) -> float:
        return self.dx * self.dy

    def x_centers(self) -> np.ndarray:
        return (np.arange(self.nx) + 0.5) * self.dx

    def y_centers(self) -> np.ndarray:
        return (np.arange(self.ny) + 0.5) * self.dy
