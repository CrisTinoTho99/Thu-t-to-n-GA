"""Validated settings shared by Euclidean and road delivery simulations."""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class SimulationConfig:
    """Coordinate units/second, service seconds and journey/demo compression.

    Road schedules use provider travel seconds rather than ``base_speed``.
    ``demo_time_scale`` compresses both travel and delivery time equally; the
    player's 0.5x--4x control is an additional, independent playback multiplier.
    """

    base_speed: float = 15.0
    service_seconds: float = 0.35
    demo_time_scale: float = 1.0

    def __post_init__(self) -> None:
        for name in ("base_speed", "service_seconds", "demo_time_scale"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number.")
            object.__setattr__(self, name, float(value))
        if self.base_speed <= 0:
            raise ValueError("base_speed must be greater than zero.")
        if self.service_seconds < 0:
            raise ValueError("service_seconds cannot be negative.")
        if self.demo_time_scale <= 0:
            raise ValueError("demo_time_scale must be greater than zero.")
