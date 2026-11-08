"""Validated physical settings for an abstract Euclidean vehicle simulation."""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class SimulationConfig:
    """Coordinate units/second and seconds/customer, before playback scaling."""

    base_speed: float = 15.0
    service_seconds: float = 0.35

    def __post_init__(self) -> None:
        for name in ("base_speed", "service_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number.")
            object.__setattr__(self, name, float(value))
        if self.base_speed <= 0:
            raise ValueError("base_speed must be greater than zero.")
        if self.service_seconds < 0:
            raise ValueError("service_seconds cannot be negative.")
