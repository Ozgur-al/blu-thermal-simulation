"""Layer data model."""

from __future__ import annotations

from dataclasses import dataclass, field

from thermal_sim.models.material_zone import MaterialZone


@dataclass(frozen=True)
class EdgeLayer:
    """One lateral layer slice on an edge (material + thickness in metres)."""

    material: str
    thickness: float

    def __post_init__(self) -> None:
        if not self.material.strip():
            raise ValueError("EdgeLayer material must not be empty.")
        if self.thickness <= 0.0:
            raise ValueError(f"EdgeLayer thickness must be > 0, got {self.thickness}.")

    def to_dict(self) -> dict:
        return {"material": self.material, "thickness": self.thickness}

    @classmethod
    def from_dict(cls, data: dict) -> "EdgeLayer":
        return cls(material=data["material"], thickness=float(data["thickness"]))


@dataclass
class Layer:
    """Single layer entry in the display stack."""

    name: str
    material: str
    thickness: float
    interface_resistance_to_next: float = 0.0
    zones: list[MaterialZone] = field(default_factory=list)
    nz: int = 1
    edge_layers: dict[str, list[EdgeLayer]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Layer name must not be empty.")
        if not self.material.strip():
            raise ValueError("Layer material key must not be empty.")
        if self.thickness <= 0.0:
            raise ValueError("Layer thickness must be > 0.")
        if self.interface_resistance_to_next < 0.0:
            raise ValueError("Interface resistance must be >= 0.")
        if self.nz < 1:
            raise ValueError(f"Layer '{self.name}' nz must be >= 1.")

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "material": self.material,
            "thickness": self.thickness,
            "interface_resistance_to_next": self.interface_resistance_to_next,
            "nz": self.nz,
        }
        if self.zones:
            d["zones"] = [z.to_dict() for z in self.zones]
        if self.edge_layers:
            d["edge_layers"] = {
                edge: [el.to_dict() for el in layers]
                for edge, layers in self.edge_layers.items()
            }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Layer":
        edge_layers_raw = data.get("edge_layers", {})
        edge_layers = {
            edge: [EdgeLayer.from_dict(el) for el in lst]
            for edge, lst in edge_layers_raw.items()
        }
        return cls(
            name=data["name"],
            material=data["material"],
            thickness=float(data["thickness"]),
            interface_resistance_to_next=float(data.get("interface_resistance_to_next", 0.0)),
            zones=[MaterialZone.from_dict(z) for z in data.get("zones", [])],
            nz=int(data.get("nz", 1)),
            edge_layers=edge_layers,
        )
