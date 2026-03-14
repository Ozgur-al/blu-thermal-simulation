"""In-memory result snapshot for comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ResultSnapshot:
    """Captures all data needed for display and comparison after a simulation run."""

    name: str                                    # User-assigned label
    mode: str                                    # "steady" or "transient"
    project_name: str
    simulation_date: str                         # ISO date string
    layer_names: list[str]
    final_temperatures_c: np.ndarray             # [n_layers, ny, nx]
    temperatures_time_c: Optional[np.ndarray]    # [nt, n_layers, ny, nx] or None
    times_s: Optional[np.ndarray]                # None for steady
    layer_stats: list[dict]                      # from layer_stats()
    hotspots: list[dict]                         # top-10 from top_n_hottest_cells()
    probe_values: dict                           # {name: float} for steady, {name: ndarray} for transient
    dx: float
    dy: float
    width_m: float
    height_m: float
    probes: list = field(default_factory=list)    # list of Probe objects for map annotations
