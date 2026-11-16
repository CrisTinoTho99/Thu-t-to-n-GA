"""Euclidean distance matrix and closed-tour objective."""
from __future__ import annotations

from numbers import Integral
from typing import Sequence
import numpy as np

from .models import Dataset
from .validation import validate_dataset


def distance_matrix(dataset: Dataset) -> np.ndarray:
    """Build an independent symmetric matrix in dataset row order."""
    validate_dataset(dataset)
    if dataset.is_geographic:
        raise ValueError("Geographic data requires an explicit road or approximate cost matrix.")
    coordinates = np.array([(location.x, location.y) for location in dataset.locations], dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        dx = coordinates[:, None, 0] - coordinates[None, :, 0]
        dy = coordinates[:, None, 1] - coordinates[None, :, 1]
        matrix = np.hypot(dx, dy)
    if not np.isfinite(matrix).all() or not np.isfinite(matrix.max() * len(dataset.locations)):
        raise ValueError("Coordinates are too large for finite route distances.")
    return matrix


def resolve_matrix(dataset: Dataset, matrix=None) -> np.ndarray:
    """Validate one directed cost matrix without symmetrizing or guessing units."""
    if matrix is None:
        return distance_matrix(dataset)
    validate_dataset(dataset)
    try:
        raw = np.asarray(matrix)
        if raw.dtype.kind == "b":
            raise ValueError("Boolean matrix costs are invalid.")
        resolved = np.asarray(matrix, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Cost matrix must contain finite nonnegative numbers.") from exc
    count = len(dataset.locations)
    if resolved.shape != (count, count):
        raise ValueError("Cost matrix dimensions must match dataset row order.")
    if not np.isfinite(resolved).all() or (resolved < 0).any():
        raise ValueError("Cost matrix must contain finite nonnegative numbers; unreachable pairs are not valid costs.")
    if not np.allclose(np.diag(resolved), 0, rtol=0, atol=1e-9):
        raise ValueError("Cost matrix diagonal must be zero.")
    if not np.isfinite(resolved.max() * count):
        raise ValueError("Cost matrix values are too large for finite tour costs.")
    return resolved.copy()


def route_distance(route: Sequence[int], matrix: np.ndarray) -> float:
    """Sum supplied consecutive edges; callers provide both depot endpoints."""
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Distance matrix must be square.")
    if len(route) < 2:
        raise ValueError("At least two route endpoints are required.")
    if any(isinstance(i, bool) or not isinstance(i, Integral) or not 0 <= i < len(matrix) for i in route):
        raise ValueError("Route contains an invalid index.")
    indices = np.asarray(route, dtype=int)
    value = float(matrix[indices[:-1], indices[1:]].sum())
    if not np.isfinite(value):
        raise ValueError("Route distance must be finite.")
    return value
