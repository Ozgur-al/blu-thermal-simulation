"""Boundary condition models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SurfaceBoundary:
    """Convection/radiation boundary on a surface."""

    ambient_c: float = 25.0
    convection_h: float = 8.0
    include_radiation: bool = True
    emissivity_override: float | None = None

    def __post_init__(self) -> None:
        if self.convection_h < 0.0:
            raise ValueError("convection_h must be >= 0.")
        if self.emissivity_override is not None and not (0.0 <= self.emissivity_override <= 1.0):
            raise ValueError("emissivity_override must be in [0, 1].")

    def to_dict(self) -> dict:
        return {
            "ambient_c": self.ambient_c,
            "convection_h": self.convection_h,
            "include_radiation": self.include_radiation,
            "emissivity_override": self.emissivity_override,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SurfaceBoundary":
        return cls(
            ambient_c=float(data.get("ambient_c", 25.0)),
            convection_h=float(data.get("convection_h", 8.0)),
            include_radiation=bool(data.get("include_radiation", True)),
            emissivity_override=(
                None if data.get("emissivity_override") is None else float(data["emissivity_override"])
            ),
        )


@dataclass
class BoundaryConditions:
    """External boundary set."""

    top: SurfaceBoundary = field(default_factory=SurfaceBoundary)
    bottom: SurfaceBoundary = field(default_factory=SurfaceBoundary)
    side: SurfaceBoundary = field(default_factory=lambda: SurfaceBoundary(convection_h=3.0))

    def to_dict(self) -> dict:
        return {
            "top": self.top.to_dict(),
            "bottom": self.bottom.to_dict(),
            "side": self.side.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoundaryConditions":
        return cls(
            top=SurfaceBoundary.from_dict(data.get("top", {})),
            bottom=SurfaceBoundary.from_dict(data.get("bottom", {})),
            side=SurfaceBoundary.from_dict(data.get("side", {"convection_h": 3.0})),
        )
