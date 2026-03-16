"""SurfaceSource data model for LED-on-face heat placement."""

from __future__ import annotations

from dataclasses import dataclass

_VALID_FACES = frozenset(("top", "bottom", "left", "right", "front", "back"))
_VALID_SHAPES = frozenset(("full", "rectangle", "circle"))


@dataclass(frozen=True)
class SurfaceSource:
    """Heat source placed on a named block's face.

    ``block`` references an AssemblyBlock by name.
    ``face`` is one of "top", "bottom", "left", "right", "front", "back".
    ``x``, ``y`` are local coordinates within the face (metres from the face corner).
    For rectangle shape: ``width`` and ``height`` are required.
    For circle shape: ``radius`` is required.
    """

    name: str
    block: str
    face: str
    power_w: float
    shape: str = "full"
    x: float = 0.0
    y: float = 0.0
    width: float | None = None
    height: float | None = None
    radius: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("SurfaceSource name must not be empty.")
        if not self.block.strip():
            raise ValueError("SurfaceSource block must not be empty.")
        if self.face not in _VALID_FACES:
            raise ValueError(
                f"SurfaceSource face must be one of {sorted(_VALID_FACES)}, got: {self.face!r}"
            )
        if self.power_w < 0.0:
            raise ValueError("SurfaceSource power_w must be >= 0.")
        if self.shape not in _VALID_SHAPES:
            raise ValueError(
                f"SurfaceSource shape must be one of {sorted(_VALID_SHAPES)}, got: {self.shape!r}"
            )
        if self.shape == "rectangle":
            if self.width is None or self.height is None:
                raise ValueError("Rectangle SurfaceSource requires width and height.")
            if self.width <= 0.0 or self.height <= 0.0:
                raise ValueError("Rectangle SurfaceSource width and height must be > 0.")
        if self.shape == "circle":
            if self.radius is None or self.radius <= 0.0:
                raise ValueError("Circle SurfaceSource requires radius > 0.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "block": self.block,
            "face": self.face,
            "power_w": self.power_w,
            "shape": self.shape,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SurfaceSource":
        return cls(
            name=data["name"],
            block=data["block"],
            face=data["face"],
            power_w=float(data["power_w"]),
            shape=data.get("shape", "full"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            width=None if data.get("width") is None else float(data["width"]),
            height=None if data.get("height") is None else float(data["height"]),
            radius=None if data.get("radius") is None else float(data["radius"]),
        )
