"""MaterialZone data model for per-region material overrides within a layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialZone:
    """A rectangular region within a layer that uses a different material.

    Coordinates are absolute from the panel origin (SI units, metres).
    The zone may extend beyond the panel boundary; cells are clipped at
    rasterization time.

    Attributes:
        material: Key into the project.materials dict.
        x:        Zone center x-coordinate (m), absolute from panel origin.
        y:        Zone center y-coordinate (m), absolute from panel origin.
        width:    Zone width (m). Must be > 0.
        height:   Zone height (m). Must be > 0.
    """

    material: str
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not self.material.strip():
            raise ValueError("MaterialZone material must not be empty.")
        if self.width <= 0.0:
            raise ValueError(f"MaterialZone width must be > 0, got {self.width}.")
        if self.height <= 0.0:
            raise ValueError(f"MaterialZone height must be > 0, got {self.height}.")

    def to_dict(self) -> dict:
        return {
            "material": self.material,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialZone":
        return cls(
            material=data["material"],
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"]),
        )
