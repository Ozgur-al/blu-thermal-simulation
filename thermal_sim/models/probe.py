"""Virtual probe model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Probe:
    """Point temperature readout in a given layer."""

    name: str
    layer: str
    x: float
    y: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Probe name must not be empty.")
        if not self.layer.strip():
            raise ValueError("Probe layer must not be empty.")

    def to_dict(self) -> dict:
        return {"name": self.name, "layer": self.layer, "x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict) -> "Probe":
        return cls(name=data["name"], layer=data["layer"], x=float(data["x"]), y=float(data["y"]))
