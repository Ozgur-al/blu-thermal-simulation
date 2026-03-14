"""Heat source data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

ShapeType = Literal["full", "rectangle", "circle"]
LedFootprintType = Literal["rectangle", "circle"]


@dataclass
class PowerBreakpoint:
    """A (time, power) breakpoint for a piecewise-linear power profile."""

    time_s: float
    power_w: float

    def to_dict(self) -> dict:
        return {"time_s": self.time_s, "power_w": self.power_w}

    @classmethod
    def from_dict(cls, data: dict) -> "PowerBreakpoint":
        return cls(time_s=float(data["time_s"]), power_w=float(data["power_w"]))


@dataclass
class HeatSource:
    """Localized or full-area power source."""

    name: str
    layer: str
    power_w: float
    shape: ShapeType = "rectangle"
    x: float = 0.0
    y: float = 0.0
    width: float | None = None
    height: float | None = None
    radius: float | None = None
    power_profile: list[PowerBreakpoint] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Heat source name must not be empty.")
        if not self.layer.strip():
            raise ValueError("Heat source layer must not be empty.")
        if self.power_w < 0.0:
            raise ValueError("Heat source power must be >= 0.")
        if self.shape not in ("full", "rectangle", "circle"):
            raise ValueError(f"Unsupported heat source shape: {self.shape}")
        if self.shape == "rectangle":
            if self.width is None or self.height is None:
                raise ValueError("Rectangle source needs width and height.")
            if self.width <= 0.0 or self.height <= 0.0:
                raise ValueError("Rectangle width/height must be > 0.")
        if self.shape == "circle":
            if self.radius is None or self.radius <= 0.0:
                raise ValueError("Circle source needs radius > 0.")
        if self.power_profile is not None and len(self.power_profile) > 0:
            if self.power_profile[0].time_s != 0.0:
                raise ValueError("First power profile breakpoint must have time_s=0.")

    def power_at_time(self, t: float) -> float:
        """Return power (W) at time t, using profile if present (loops)."""
        if not self.power_profile or len(self.power_profile) < 2:
            return self.power_w
        profile_end = self.power_profile[-1].time_s
        if profile_end <= 0.0:
            return self.power_w
        t_wrapped = t % profile_end
        times = [bp.time_s for bp in self.power_profile]
        powers = [bp.power_w for bp in self.power_profile]
        return float(np.interp(t_wrapped, times, powers))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer": self.layer,
            "power_w": self.power_w,
            "shape": self.shape,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
            "power_profile": (
                [bp.to_dict() for bp in self.power_profile]
                if self.power_profile is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HeatSource":
        raw_profile = data.get("power_profile")
        profile = (
            [PowerBreakpoint.from_dict(bp) for bp in raw_profile]
            if raw_profile is not None
            else None
        )
        return cls(
            name=data["name"],
            layer=data["layer"],
            power_w=float(data["power_w"]),
            shape=data.get("shape", "rectangle"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            width=None if data.get("width") is None else float(data["width"]),
            height=None if data.get("height") is None else float(data["height"]),
            radius=None if data.get("radius") is None else float(data["radius"]),
            power_profile=profile,
        )


@dataclass
class LEDArray:
    """Template describing an LED array that expands to many heat sources."""

    name: str
    layer: str
    center_x: float
    center_y: float
    count_x: int
    count_y: int
    pitch_x: float
    pitch_y: float
    power_per_led_w: float
    footprint_shape: LedFootprintType = "rectangle"
    led_width: float | None = None
    led_height: float | None = None
    led_radius: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("LED array name must not be empty.")
        if not self.layer.strip():
            raise ValueError("LED array layer must not be empty.")
        if self.count_x < 1 or self.count_y < 1:
            raise ValueError("LED array counts must be >= 1.")
        if self.pitch_x < 0.0 or self.pitch_y < 0.0:
            raise ValueError("LED array pitch must be >= 0.")
        if self.count_x > 1 and self.pitch_x <= 0.0:
            raise ValueError("pitch_x must be > 0 when count_x > 1.")
        if self.count_y > 1 and self.pitch_y <= 0.0:
            raise ValueError("pitch_y must be > 0 when count_y > 1.")
        if self.power_per_led_w < 0.0:
            raise ValueError("power_per_led_w must be >= 0.")
        if self.footprint_shape not in ("rectangle", "circle"):
            raise ValueError(f"Unsupported footprint shape: {self.footprint_shape}")
        if self.footprint_shape == "rectangle":
            if self.led_width is None or self.led_height is None:
                raise ValueError("Rectangle LED footprint needs led_width and led_height.")
            if self.led_width <= 0.0 or self.led_height <= 0.0:
                raise ValueError("led_width and led_height must be > 0.")
        if self.footprint_shape == "circle":
            if self.led_radius is None or self.led_radius <= 0.0:
                raise ValueError("Circle LED footprint needs led_radius > 0.")

    @property
    def total_power_w(self) -> float:
        return self.count_x * self.count_y * self.power_per_led_w

    def expand(self) -> list[HeatSource]:
        """Expand array template into one source per LED."""
        sources: list[HeatSource] = []
        x0 = self.center_x - 0.5 * (self.count_x - 1) * self.pitch_x
        y0 = self.center_y - 0.5 * (self.count_y - 1) * self.pitch_y
        for iy in range(self.count_y):
            for ix in range(self.count_x):
                x = x0 + ix * self.pitch_x
                y = y0 + iy * self.pitch_y
                sources.append(
                    HeatSource(
                        name=f"{self.name}_r{iy + 1}_c{ix + 1}",
                        layer=self.layer,
                        power_w=self.power_per_led_w,
                        shape=self.footprint_shape,
                        x=x,
                        y=y,
                        width=self.led_width if self.footprint_shape == "rectangle" else None,
                        height=self.led_height if self.footprint_shape == "rectangle" else None,
                        radius=self.led_radius if self.footprint_shape == "circle" else None,
                    )
                )
        return sources

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer": self.layer,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "count_x": self.count_x,
            "count_y": self.count_y,
            "pitch_x": self.pitch_x,
            "pitch_y": self.pitch_y,
            "power_per_led_w": self.power_per_led_w,
            "footprint_shape": self.footprint_shape,
            "led_width": self.led_width,
            "led_height": self.led_height,
            "led_radius": self.led_radius,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LEDArray":
        return cls(
            name=data["name"],
            layer=data["layer"],
            center_x=float(data["center_x"]),
            center_y=float(data["center_y"]),
            count_x=int(data["count_x"]),
            count_y=int(data["count_y"]),
            pitch_x=float(data["pitch_x"]),
            pitch_y=float(data["pitch_y"]),
            power_per_led_w=float(data["power_per_led_w"]),
            footprint_shape=data.get("footprint_shape", "rectangle"),
            led_width=None if data.get("led_width") is None else float(data["led_width"]),
            led_height=None if data.get("led_height") is None else float(data["led_height"]),
            led_radius=None if data.get("led_radius") is None else float(data["led_radius"]),
        )
