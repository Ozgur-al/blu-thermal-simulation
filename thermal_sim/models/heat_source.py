"""Heat source data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

ShapeType = Literal["full", "rectangle", "circle"]
LedFootprintType = Literal["rectangle", "circle"]
LEDMode = Literal["grid", "edge", "custom"]
EdgeConfig = Literal["bottom", "top", "left_right", "all"]


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
    z_position: str = "top"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Heat source name must not be empty.")
        if not self.layer.strip():
            raise ValueError("Heat source layer must not be empty.")
        if self.power_w < 0.0:
            raise ValueError("Heat source power must be >= 0.")
        if self.shape not in ("full", "rectangle", "circle"):
            raise ValueError(f"Unsupported heat source shape: {self.shape}")
        if self.z_position not in ("top", "bottom", "distributed"):
            raise ValueError(
                f"Unsupported z_position: {self.z_position}. Must be 'top', 'bottom', or 'distributed'."
            )
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
            "z_position": self.z_position,
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
            z_position=data.get("z_position", "top"),
        )


@dataclass
class LEDArray:
    """Template describing an LED array that expands to many heat sources.

    Supports three expansion modes:
      - "custom" (default): legacy center_x/center_y grid placement.
      - "grid": panel-aware 2D grid with per-side edge offsets and zone-based power.
      - "edge": discrete LEDs placed along one or more panel edges.
    """

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

    # --- new fields (all default to backward-compat values) ---
    mode: LEDMode = "custom"
    offset_top: float = 0.0
    offset_bottom: float = 0.0
    offset_left: float = 0.0
    offset_right: float = 0.0
    zone_count_x: int = 1
    zone_count_y: int = 1
    zone_powers: list[float] = field(default_factory=list)
    edge_config: EdgeConfig = "bottom"
    edge_offset: float = 0.005  # 5 mm default
    panel_width: float = 0.0
    panel_height: float = 0.0
    z_position: str = "top"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("LED array name must not be empty.")
        if not self.layer.strip():
            raise ValueError("LED array layer must not be empty.")
        if self.count_x < 1 or self.count_y < 1:
            raise ValueError("LED array counts must be >= 1.")
        # Pitch validation only for custom mode (grid/edge auto-compute pitch)
        if self.mode == "custom":
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

        # Validate new fields for non-custom modes
        if self.mode == "grid":
            if self.panel_width <= 0.0 or self.panel_height <= 0.0:
                raise ValueError("panel_width and panel_height must be > 0 for mode='grid'.")
        elif self.mode == "edge":
            if self.panel_width <= 0.0 or self.panel_height <= 0.0:
                raise ValueError("panel_width and panel_height must be > 0 for mode='edge'.")
            if self.edge_config in ("bottom", "top", "all") and self.count_x < 1:
                raise ValueError("count_x >= 1 required for horizontal edges.")
            if self.edge_config in ("left_right", "all") and self.count_y < 1:
                raise ValueError("count_y >= 1 required for vertical edges.")

    @property
    def total_power_w(self) -> float:
        if self.mode == "grid":
            expected_zones = self.zone_count_x * self.zone_count_y
            if self.zone_powers and len(self.zone_powers) == expected_zones:
                # Count LEDs per zone and sum zone_power * count
                total = 0.0
                leds_per_zone_x = self.count_x / self.zone_count_x
                leds_per_zone_y = self.count_y / self.zone_count_y
                for zy in range(self.zone_count_y):
                    for zx in range(self.zone_count_x):
                        zone_idx = zy * self.zone_count_x + zx
                        # Count actual LEDs in this zone
                        ix_start = round(zx * leds_per_zone_x)
                        ix_end = round((zx + 1) * leds_per_zone_x)
                        iy_start = round(zy * leds_per_zone_y)
                        iy_end = round((zy + 1) * leds_per_zone_y)
                        n = (ix_end - ix_start) * (iy_end - iy_start)
                        total += n * self.zone_powers[zone_idx]
                return total
        elif self.mode == "edge":
            n = self._edge_led_count()
            return n * self.power_per_led_w
        # Default (custom) or fallback
        return self.count_x * self.count_y * self.power_per_led_w

    def _edge_led_count(self) -> int:
        """Return total number of LEDs for edge mode."""
        cfg = self.edge_config
        n = 0
        if cfg in ("bottom", "top"):
            n = self.count_x
        elif cfg == "left_right":
            n = self.count_y * 2
        elif cfg == "all":
            n = self.count_x * 2 + self.count_y * 2
        return n

    def expand(self) -> list[HeatSource]:
        """Expand array template into one source per LED."""
        if self.mode == "grid":
            return self._expand_grid()
        elif self.mode == "edge":
            return self._expand_edge()
        else:
            return self._expand_custom()

    def _expand_custom(self) -> list[HeatSource]:
        """Legacy expand: center_x/center_y based grid placement."""
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
                        z_position=self.z_position,
                    )
                )
        return sources

    def _expand_grid(self) -> list[HeatSource]:
        """Panel-aware 2D grid placement with edge offsets and optional zone power.

        Pitch is auto-computed from usable area and LED count so LEDs always
        fill the active area evenly.
        """
        sources: list[HeatSource] = []

        # Usable area within offsets
        x_start = self.offset_left
        x_end = self.panel_width - self.offset_right
        y_start = self.offset_bottom
        y_end = self.panel_height - self.offset_top

        usable_w = x_end - x_start
        usable_h = y_end - y_start

        # Auto-compute pitch from usable area and count
        pitch_x = usable_w / (self.count_x - 1) if self.count_x > 1 else 0.0
        pitch_y = usable_h / (self.count_y - 1) if self.count_y > 1 else 0.0

        # First LED at start of usable area (or centered for single LED)
        x0 = x_start if self.count_x > 1 else x_start + usable_w / 2.0
        y0 = y_start if self.count_y > 1 else y_start + usable_h / 2.0

        # Determine zone power lookup
        expected_zones = self.zone_count_x * self.zone_count_y
        use_zones = (
            self.zone_powers
            and len(self.zone_powers) == expected_zones
            and self.zone_count_x >= 1
            and self.zone_count_y >= 1
        )

        leds_per_zone_x = self.count_x / self.zone_count_x if use_zones else 1
        leds_per_zone_y = self.count_y / self.zone_count_y if use_zones else 1

        for iy in range(self.count_y):
            for ix in range(self.count_x):
                x = x0 + ix * pitch_x
                y = y0 + iy * pitch_y

                if use_zones:
                    zone_xi = min(int(ix / leds_per_zone_x), self.zone_count_x - 1)
                    zone_yi = min(int(iy / leds_per_zone_y), self.zone_count_y - 1)
                    zone_idx = zone_yi * self.zone_count_x + zone_xi
                    power = self.zone_powers[zone_idx]
                else:
                    power = self.power_per_led_w

                sources.append(
                    HeatSource(
                        name=f"{self.name}_r{iy + 1}_c{ix + 1}",
                        layer=self.layer,
                        power_w=power,
                        shape=self.footprint_shape,
                        x=x,
                        y=y,
                        width=self.led_width if self.footprint_shape == "rectangle" else None,
                        height=self.led_height if self.footprint_shape == "rectangle" else None,
                        radius=self.led_radius if self.footprint_shape == "circle" else None,
                        z_position=self.z_position,
                    )
                )
        return sources

    def _expand_edge(self) -> list[HeatSource]:
        """Place discrete LEDs along configured panel edges (clamped to panel bounds)."""
        sources: list[HeatSource] = []
        cfg = self.edge_config
        pw = self.panel_width
        ph = self.panel_height
        offset = self.edge_offset

        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))

        def make_led(name: str, x: float, y: float) -> HeatSource:
            return HeatSource(
                name=name,
                layer=self.layer,
                power_w=self.power_per_led_w,
                shape=self.footprint_shape,
                x=clamp(x, 0.0, pw),
                y=clamp(y, 0.0, ph),
                width=self.led_width if self.footprint_shape == "rectangle" else None,
                height=self.led_height if self.footprint_shape == "rectangle" else None,
                radius=self.led_radius if self.footprint_shape == "circle" else None,
                z_position=self.z_position,
            )

        # Horizontal edges (bottom / top): count_x LEDs spaced along x axis
        def horizontal_strip(y_pos: float, tag: str) -> list[HeatSource]:
            strip: list[HeatSource] = []
            if self.count_x == 1:
                xs = [pw / 2.0]
            else:
                x0 = offset
                x1 = pw - offset
                step = (x1 - x0) / (self.count_x - 1)
                xs = [x0 + i * step for i in range(self.count_x)]
            for i, x in enumerate(xs):
                strip.append(make_led(f"{self.name}_{tag}_{i + 1}", x, y_pos))
            return strip

        # Vertical edges (left / right): count_y LEDs spaced along y axis
        def vertical_strip(x_pos: float, tag: str) -> list[HeatSource]:
            strip: list[HeatSource] = []
            if self.count_y == 1:
                ys = [ph / 2.0]
            else:
                y0 = offset
                y1 = ph - offset
                step = (y1 - y0) / (self.count_y - 1)
                ys = [y0 + i * step for i in range(self.count_y)]
            for i, y in enumerate(ys):
                strip.append(make_led(f"{self.name}_{tag}_{i + 1}", x_pos, y))
            return strip

        if cfg in ("bottom", "all"):
            sources.extend(horizontal_strip(offset, "bot"))
        if cfg in ("top", "all"):
            sources.extend(horizontal_strip(ph - offset, "top"))
        if cfg in ("left_right", "all"):
            sources.extend(vertical_strip(offset, "left"))
            sources.extend(vertical_strip(pw - offset, "right"))

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
            # new fields
            "mode": self.mode,
            "offset_top": self.offset_top,
            "offset_bottom": self.offset_bottom,
            "offset_left": self.offset_left,
            "offset_right": self.offset_right,
            "zone_count_x": self.zone_count_x,
            "zone_count_y": self.zone_count_y,
            "zone_powers": self.zone_powers,
            "edge_config": self.edge_config,
            "edge_offset": self.edge_offset,
            "panel_width": self.panel_width,
            "panel_height": self.panel_height,
            "z_position": self.z_position,
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
            # new fields — use .get() with defaults for backward compatibility
            mode=data.get("mode", "custom"),
            offset_top=float(data.get("offset_top", 0.0)),
            offset_bottom=float(data.get("offset_bottom", 0.0)),
            offset_left=float(data.get("offset_left", 0.0)),
            offset_right=float(data.get("offset_right", 0.0)),
            zone_count_x=int(data.get("zone_count_x", 1)),
            zone_count_y=int(data.get("zone_count_y", 1)),
            zone_powers=list(data.get("zone_powers", [])),
            edge_config=data.get("edge_config", "bottom"),
            edge_offset=float(data.get("edge_offset", 0.005)),
            panel_width=float(data.get("panel_width", 0.0)),
            panel_height=float(data.get("panel_height", 0.0)),
            z_position=data.get("z_position", "top"),
        )
