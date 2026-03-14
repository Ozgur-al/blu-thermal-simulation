"""Sweep run and aggregate result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SweepRunResult:
    """Result of a single parametric sweep run.

    Attributes:
        parameter_value: The sweep parameter value used in this run.
        layer_stats: Per-layer stats list. Each dict contains keys:
            ``layer``, ``t_max_c``, ``t_avg_c``, ``t_min_c``, ``delta_t_c``.
    """

    parameter_value: float
    layer_stats: list[dict]

    def to_dict(self) -> dict:
        return {
            "parameter_value": self.parameter_value,
            "layer_stats": list(self.layer_stats),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SweepRunResult":
        return cls(
            parameter_value=float(data["parameter_value"]),
            layer_stats=list(data["layer_stats"]),
        )


@dataclass
class SweepResult:
    """Aggregate result of a completed parametric sweep.

    Attributes:
        config: The SweepConfig that produced this result.
        runs: Ordered list of per-run results, one per sweep value.
    """

    config: "SweepConfig"  # noqa: F821  (forward ref resolved at runtime)
    runs: list[SweepRunResult]

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SweepResult":
        from thermal_sim.core.sweep_engine import SweepConfig  # avoid circular at module level

        return cls(
            config=SweepConfig.from_dict(data["config"]),
            runs=[SweepRunResult.from_dict(r) for r in data["runs"]],
        )
