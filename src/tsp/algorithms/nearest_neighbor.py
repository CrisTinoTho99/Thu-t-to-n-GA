"""Deterministic nearest-neighbor constructive baseline."""
from __future__ import annotations

from time import perf_counter
from ..distance import distance_matrix, route_distance
from ..models import Dataset, OptimizationResult
from ..validation import validate_route


def nearest_neighbor(dataset: Dataset) -> OptimizationResult:
    """Start at depot; break equal-distance ties by original row index."""
    started = perf_counter()
    matrix = distance_matrix(dataset)
    route = [dataset.depot_index]
    unvisited = set(dataset.customer_indices)
    while unvisited:
        next_index = min(unvisited, key=lambda index: (matrix[route[-1], index], index))
        route.append(next_index)
        unvisited.remove(next_index)
    route.append(dataset.depot_index)
    validate_route(route, dataset)
    return OptimizationResult("Nearest Neighbor", route, route_distance(route, matrix),
                              perf_counter() - started, 1, parameters={"tie_break": "row_index"})
