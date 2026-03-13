"""Material data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """Thermal material properties (SI units)."""

    name: str
    k_in_plane: float
    k_through: float
    density: float
    specific_heat: float
    emissivity: float = 0.9

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Material name must not be empty.")
        if self.k_in_plane <= 0.0:
            raise ValueError("k_in_plane must be > 0.")
        if self.k_through <= 0.0:
            raise ValueError("k_through must be > 0.")
        if self.density <= 0.0:
            raise ValueError("density must be > 0.")
        if self.specific_heat <= 0.0:
            raise ValueError("specific_heat must be > 0.")
        if not (0.0 <= self.emissivity <= 1.0):
            raise ValueError("emissivity must be in [0, 1].")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "k_in_plane": self.k_in_plane,
            "k_through": self.k_through,
            "density": self.density,
            "specific_heat": self.specific_heat,
            "emissivity": self.emissivity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        return cls(
            name=data["name"],
            k_in_plane=float(data["k_in_plane"]),
            k_through=float(data["k_through"]),
            density=float(data["density"]),
            specific_heat=float(data["specific_heat"]),
            emissivity=float(data.get("emissivity", 0.9)),
        )
