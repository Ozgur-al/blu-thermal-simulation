"""Layer data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Layer:
    """Single layer entry in the display stack."""

    name: str
    material: str
    thickness: float
    interface_resistance_to_next: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Layer name must not be empty.")
        if not self.material.strip():
            raise ValueError("Layer material key must not be empty.")
        if self.thickness <= 0.0:
            raise ValueError("Layer thickness must be > 0.")
        if self.interface_resistance_to_next < 0.0:
            raise ValueError("Interface resistance must be >= 0.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "material": self.material,
            "thickness": self.thickness,
            "interface_resistance_to_next": self.interface_resistance_to_next,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Layer":
        return cls(
            name=data["name"],
            material=data["material"],
            thickness=float(data["thickness"]),
            interface_resistance_to_next=float(data.get("interface_resistance_to_next", 0.0)),
        )
