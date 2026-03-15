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
    z_position: str | int = "top"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Probe name must not be empty.")
        if not self.layer.strip():
            raise ValueError("Probe layer must not be empty.")
        if isinstance(self.z_position, str) and self.z_position not in ("top", "bottom", "center"):
            raise ValueError(
                f"Unsupported z_position string: '{self.z_position}'. Must be 'top', 'bottom', or 'center'."
            )
        if isinstance(self.z_position, int) and self.z_position < 0:
            raise ValueError("Probe z_position int must be >= 0.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer": self.layer,
            "x": self.x,
            "y": self.y,
            "z_position": self.z_position,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Probe":
        raw_zp = data.get("z_position", "top")
        z_position: str | int = (
            int(raw_zp)
            if isinstance(raw_zp, int) or (isinstance(raw_zp, str) and raw_zp.isdigit())
            else raw_zp
        )
        return cls(
            name=data["name"],
            layer=data["layer"],
            x=float(data["x"]),
            y=float(data["y"]),
            z_position=z_position,
        )
