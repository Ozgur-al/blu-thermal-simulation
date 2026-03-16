"""AssemblyBlock data model for the voxel-based 3D solver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssemblyBlock:
    """A named 3D rectangular solid placed in the assembly.

    Position (x, y, z) is the lower-left-bottom corner in metres.
    Dimensions (width, depth, height) are along the x, y, z axes respectively.
    ``material`` is a key into the VoxelProject.materials dict.
    """

    name: str
    material: str
    x: float
    y: float
    z: float
    width: float   # x-direction size (metres)
    depth: float   # y-direction size (metres)
    height: float  # z-direction size (metres)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("AssemblyBlock name must not be empty.")
        if not self.material.strip():
            raise ValueError("AssemblyBlock material must not be empty.")
        if self.width <= 0.0:
            raise ValueError("AssemblyBlock width must be > 0.")
        if self.depth <= 0.0:
            raise ValueError("AssemblyBlock depth must be > 0.")
        if self.height <= 0.0:
            raise ValueError("AssemblyBlock height must be > 0.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "material": self.material,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AssemblyBlock":
        return cls(
            name=data["name"],
            material=data["material"],
            x=float(data["x"]),
            y=float(data["y"]),
            z=float(data["z"]),
            width=float(data["width"]),
            depth=float(data["depth"]),
            height=float(data["height"]),
        )
