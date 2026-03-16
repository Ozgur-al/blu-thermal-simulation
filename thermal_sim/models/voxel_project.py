"""VoxelProject top-level model for the voxel-based 3D solver."""

from __future__ import annotations

from dataclasses import dataclass, field

from thermal_sim.models.assembly_block import AssemblyBlock
from thermal_sim.models.boundary import SurfaceBoundary
from thermal_sim.models.material import Material
from thermal_sim.models.surface_source import SurfaceSource


@dataclass
class VoxelProbe:
    """Virtual thermistor at an absolute 3D position (metres)."""

    name: str
    x: float
    y: float
    z: float

    def to_dict(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelProbe":
        return cls(
            name=data["name"],
            x=float(data["x"]),
            y=float(data["y"]),
            z=float(data["z"]),
        )


@dataclass
class BoundaryGroup:
    """Named boundary condition group applied to a set of exposed faces.

    Actual face assignment is performed by the solver at build time; the group
    here just carries the thermal boundary condition parameters.
    """

    name: str
    boundary: SurfaceBoundary

    def to_dict(self) -> dict:
        return {"name": self.name, "boundary": self.boundary.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "BoundaryGroup":
        return cls(
            name=data["name"],
            boundary=SurfaceBoundary.from_dict(data["boundary"]),
        )


@dataclass
class VoxelMeshConfig:
    """Mesh generation parameters."""

    cells_per_interval: int = 1  # subdivision count per conformal interval

    def to_dict(self) -> dict:
        return {"cells_per_interval": self.cells_per_interval}

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelMeshConfig":
        return cls(cells_per_interval=int(data.get("cells_per_interval", 1)))


@dataclass
class VoxelTransientConfig:
    """Transient simulation parameters."""

    duration_s: float = 60.0
    dt_s: float = 1.0
    initial_temp_c: float = 25.0

    def to_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "dt_s": self.dt_s,
            "initial_temp_c": self.initial_temp_c,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelTransientConfig":
        return cls(
            duration_s=float(data.get("duration_s", 60.0)),
            dt_s=float(data.get("dt_s", 1.0)),
            initial_temp_c=float(data.get("initial_temp_c", 25.0)),
        )


@dataclass
class VoxelProject:
    """Top-level voxel project model replacing DisplayProject.

    Holds all inputs for a voxel-based 3D thermal simulation:
    assembly blocks, materials dict, surface heat sources, boundary groups,
    virtual probes, mesh config, and optional transient config.
    """

    name: str
    blocks: list[AssemblyBlock]
    materials: dict[str, Material]
    sources: list[SurfaceSource]
    boundary_groups: list[BoundaryGroup]
    probes: list[VoxelProbe]
    mesh_config: VoxelMeshConfig
    transient_config: VoxelTransientConfig | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "blocks": [b.to_dict() for b in self.blocks],
            "materials": {k: v.to_dict() for k, v in self.materials.items()},
            "sources": [s.to_dict() for s in self.sources],
            "boundary_groups": [bg.to_dict() for bg in self.boundary_groups],
            "probes": [p.to_dict() for p in self.probes],
            "mesh_config": self.mesh_config.to_dict(),
            "transient_config": (
                self.transient_config.to_dict() if self.transient_config is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelProject":
        return cls(
            name=data["name"],
            blocks=[AssemblyBlock.from_dict(b) for b in data.get("blocks", [])],
            materials={k: Material.from_dict(v) for k, v in data.get("materials", {}).items()},
            sources=[SurfaceSource.from_dict(s) for s in data.get("sources", [])],
            boundary_groups=[
                BoundaryGroup.from_dict(bg) for bg in data.get("boundary_groups", [])
            ],
            probes=[VoxelProbe.from_dict(p) for p in data.get("probes", [])],
            mesh_config=VoxelMeshConfig.from_dict(data.get("mesh_config", {})),
            transient_config=(
                VoxelTransientConfig.from_dict(data["transient_config"])
                if data.get("transient_config") is not None
                else None
            ),
        )
