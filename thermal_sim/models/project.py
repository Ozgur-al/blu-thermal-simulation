"""Project model and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from thermal_sim.models.boundary import BoundaryConditions
from thermal_sim.models.heat_source import LEDArray, HeatSource
from thermal_sim.models.layer import Layer
from thermal_sim.models.material import Material
from thermal_sim.models.probe import Probe


@dataclass
class MeshConfig:
    """In-plane grid resolution."""

    nx: int = 30
    ny: int = 20

    def __post_init__(self) -> None:
        if self.nx < 1 or self.ny < 1:
            raise ValueError("nx and ny must be >= 1.")

    def to_dict(self) -> dict:
        return {"nx": self.nx, "ny": self.ny}

    @classmethod
    def from_dict(cls, data: dict) -> "MeshConfig":
        return cls(nx=int(data.get("nx", 30)), ny=int(data.get("ny", 20)))


@dataclass
class TransientConfig:
    """Transient simulation setup."""

    time_step_s: float = 0.1
    total_time_s: float = 120.0
    output_interval_s: float = 1.0
    method: str = "implicit_euler"

    def __post_init__(self) -> None:
        if self.time_step_s <= 0.0:
            raise ValueError("time_step_s must be > 0.")
        if self.total_time_s <= 0.0:
            raise ValueError("total_time_s must be > 0.")
        if self.output_interval_s <= 0.0:
            raise ValueError("output_interval_s must be > 0.")
        if self.method != "implicit_euler":
            raise ValueError("Only 'implicit_euler' is supported in Phase 2.")

    def to_dict(self) -> dict:
        return {
            "time_step_s": self.time_step_s,
            "total_time_s": self.total_time_s,
            "output_interval_s": self.output_interval_s,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TransientConfig":
        return cls(
            time_step_s=float(data.get("time_step_s", 0.1)),
            total_time_s=float(data.get("total_time_s", 120.0)),
            output_interval_s=float(data.get("output_interval_s", 1.0)),
            method=str(data.get("method", "implicit_euler")),
        )


@dataclass
class DisplayProject:
    """Display thermal simulation input model."""

    name: str
    width: float
    height: float
    layers: list[Layer]
    materials: dict[str, Material]
    heat_sources: list[HeatSource] = field(default_factory=list)
    led_arrays: list[LEDArray] = field(default_factory=list)
    boundaries: BoundaryConditions = field(default_factory=BoundaryConditions)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    transient: TransientConfig = field(default_factory=TransientConfig)
    initial_temperature_c: float = 25.0
    probes: list[Probe] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Project name must not be empty.")
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("Project width and height must be > 0.")
        if not self.layers:
            raise ValueError("At least one layer is required.")
        if not self.materials:
            raise ValueError("At least one material is required.")

        layer_names: set[str] = set()
        for layer in self.layers:
            if layer.name in layer_names:
                raise ValueError(f"Duplicate layer name: {layer.name}")
            layer_names.add(layer.name)
            if layer.material not in self.materials:
                raise ValueError(f"Layer '{layer.name}' references unknown material '{layer.material}'.")

        for source in self.heat_sources:
            if source.layer not in layer_names:
                raise ValueError(f"Heat source '{source.name}' references unknown layer '{source.layer}'.")

        for led_array in self.led_arrays:
            if led_array.layer not in layer_names:
                raise ValueError(f"LED array '{led_array.name}' references unknown layer '{led_array.layer}'.")

        for probe in self.probes:
            if probe.layer not in layer_names:
                raise ValueError(f"Probe '{probe.name}' references unknown layer '{probe.layer}'.")
            if not (0.0 <= probe.x <= self.width and 0.0 <= probe.y <= self.height):
                raise ValueError(f"Probe '{probe.name}' must be within panel bounds.")

    def expanded_heat_sources(self) -> list[HeatSource]:
        """Return explicit heat sources including expanded LED arrays."""
        expanded = list(self.heat_sources)
        for array in self.led_arrays:
            expanded.extend(array.expand())
        return expanded

    def layer_index(self, layer_name: str) -> int:
        for idx, layer in enumerate(self.layers):
            if layer.name == layer_name:
                return idx
        raise KeyError(f"Layer not found: {layer_name}")

    def material_for_layer(self, layer_index: int) -> Material:
        layer = self.layers[layer_index]
        return self.materials[layer.material]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "layers": [layer.to_dict() for layer in self.layers],
            "materials": {key: mat.to_dict() for key, mat in self.materials.items()},
            "heat_sources": [src.to_dict() for src in self.heat_sources],
            "led_arrays": [item.to_dict() for item in self.led_arrays],
            "boundaries": self.boundaries.to_dict(),
            "mesh": self.mesh.to_dict(),
            "transient": self.transient.to_dict(),
            "initial_temperature_c": self.initial_temperature_c,
            "probes": [probe.to_dict() for probe in self.probes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DisplayProject":
        return cls(
            name=data["name"],
            width=float(data["width"]),
            height=float(data["height"]),
            layers=[Layer.from_dict(item) for item in data["layers"]],
            materials={key: Material.from_dict(value) for key, value in data["materials"].items()},
            heat_sources=[HeatSource.from_dict(item) for item in data.get("heat_sources", [])],
            led_arrays=[LEDArray.from_dict(item) for item in data.get("led_arrays", [])],
            boundaries=BoundaryConditions.from_dict(data.get("boundaries", {})),
            mesh=MeshConfig.from_dict(data.get("mesh", {})),
            transient=TransientConfig.from_dict(data.get("transient", {})),
            initial_temperature_c=float(data.get("initial_temperature_c", 25.0)),
            probes=[Probe.from_dict(item) for item in data.get("probes", [])],
        )
