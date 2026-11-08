"""Typed, serializable domain objects shared by every application layer."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from numbers import Integral
from typing import Any


@dataclass(frozen=True)
class Location:
    """A location in an abstract Euclidean coordinate system."""

    id: str
    name: str
    x: float
    y: float
    is_depot: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Location IDs must be nonempty strings.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Location names must be nonempty strings.")
        for coordinate in (self.x, self.y):
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                raise ValueError("Coordinates must be finite numbers.")
            if not math.isfinite(coordinate):
                raise ValueError("Coordinates must be finite numbers.")
        if not isinstance(self.is_depot, bool):
            raise ValueError("is_depot must be a boolean.")


@dataclass(frozen=True)
class Dataset:
    """Immutable input: a single depot and one or more customers."""

    name: str
    locations: tuple[Location, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "locations", tuple(self.locations))
        from .validation import validate_dataset
        validate_dataset(self)

    @property
    def depot_index(self) -> int:
        return next(i for i, location in enumerate(self.locations) if location.is_depot)

    @property
    def customer_indices(self) -> tuple[int, ...]:
        return tuple(i for i, location in enumerate(self.locations) if not location.is_depot)

    @property
    def n_customers(self) -> int:
        return len(self.locations) - 1

    @property
    def fingerprint(self) -> str:
        """Hash ordered input content; labels and the depot are included."""
        encoded = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_frame(self):
        """Return an editable independent pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame([asdict(location) for location in self.locations])

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "locations": [asdict(location) for location in self.locations]}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Dataset":
        return cls(name=value["name"], locations=tuple(Location(**row) for row in value["locations"]))


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}.")


def validate_seed(seed: int) -> None:
    """Validate a NumPy-compatible nonnegative integer seed."""
    _integer(seed, "seed", 0)


@dataclass(frozen=True)
class GAConfig:
    """Validated GA configuration; zero patience disables early stopping."""

    population_size: int = 100
    generations: int = 200
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    elitism_count: int = 2
    tournament_size: int = 3
    seed: int = 42
    early_stopping_patience: int = 0

    def __post_init__(self) -> None:
        _integer(self.population_size, "population_size", 2, 5000)
        _integer(self.generations, "generations", 1, 100000)
        _integer(self.elitism_count, "elitism_count", 0, self.population_size - 1)
        _integer(self.tournament_size, "tournament_size", 2, self.population_size)
        _integer(self.early_stopping_patience, "early_stopping_patience", 0)
        validate_seed(self.seed)
        for name in ("crossover_rate", "mutation_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite number between 0 and 1.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationResult:
    """A measured run. Routes contain row indices, including both depot endpoints."""

    algorithm: str
    route: list[int]
    distance: float
    runtime_seconds: float
    evaluations: int
    seed: int | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OptimizationResult":
        return cls(**value)
