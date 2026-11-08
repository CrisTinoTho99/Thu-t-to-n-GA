"""Invariant checks for Euclidean TSP input and complete tours."""
from __future__ import annotations

from numbers import Integral
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .models import Dataset

MAX_CUSTOMERS = 500


def validate_dataset(dataset: "Dataset") -> None:
    """Raise ValueError for an invalid input rather than silently repairing it."""
    from .models import Location
    if not isinstance(dataset.name, str) or not dataset.name.strip():
        raise ValueError("Dataset name is required.")
    if not 2 <= len(dataset.locations) <= MAX_CUSTOMERS + 1:
        raise ValueError(f"A dataset needs 1–{MAX_CUSTOMERS} customers and one depot.")
    if not all(isinstance(location, Location) for location in dataset.locations):
        raise ValueError("Every dataset row must be a Location.")
    if sum(location.is_depot for location in dataset.locations) != 1:
        raise ValueError("Exactly one depot is required.")
    ids = [location.id for location in dataset.locations]
    if len(set(ids)) != len(ids):
        raise ValueError("Location IDs must be unique.")


def validate_route(route: Sequence[int], dataset: "Dataset") -> None:
    """Check a closed tour visits each customer once and depot only at endpoints."""
    if len(route) != len(dataset.locations) + 1:
        raise ValueError("A route must contain every location and the return to depot.")
    if any(isinstance(index, bool) or not isinstance(index, Integral) for index in route):
        raise ValueError("Route entries must be integer location indices.")
    if route[0] != dataset.depot_index or route[-1] != dataset.depot_index:
        raise ValueError("The route must start and end at the depot.")
    if sorted(route[1:-1]) != sorted(dataset.customer_indices):
        raise ValueError("The route must visit each customer exactly once.")
