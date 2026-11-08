"""Deterministic first-improvement 2-opt on a closed Euclidean route."""
from __future__ import annotations

from time import perf_counter
from typing import Sequence
from ..distance import distance_matrix, route_distance
from ..models import Dataset, OptimizationResult
from ..validation import validate_route
from .nearest_neighbor import nearest_neighbor


def two_opt(dataset: Dataset, initial_route: Sequence[int] | None = None) -> OptimizationResult:
    """Improve NN by default; a supplied route is labeled separately from pure GA."""
    started = perf_counter()
    matrix = distance_matrix(dataset)
    from_nn = initial_route is None
    route = nearest_neighbor(dataset).route if from_nn else list(initial_route)
    validate_route(route, dataset)
    distance = route_distance(route, matrix)
    evaluations = 1
    history = [{"iteration": 0, "best_distance": distance, "route": route.copy()}]
    iteration = 0
    while True:
        improved = False
        for first in range(1, len(route) - 2):
            for last in range(first + 1, len(route) - 1):
                # Each candidate is evaluated as a complete tour so its count
                # is directly interpretable alongside GA and random search.
                candidate = route[:first] + list(reversed(route[first:last + 1])) + route[last + 1:]
                candidate_distance = route_distance(candidate, matrix)
                evaluations += 1
                if candidate_distance < distance - 1e-12:
                    route, distance = candidate, candidate_distance
                    improved = True
                    iteration += 1
                    history.append({"iteration": iteration, "best_distance": distance, "route": route.copy()})
                    break
            if improved:
                break
        if not improved:
            break
    validate_route(route, dataset)
    name = "Nearest Neighbor + 2-opt" if from_nn else "2-opt (supplied route)"
    return OptimizationResult(name, route, distance, perf_counter() - started, evaluations,
                              parameters={"initialization": "nearest_neighbor" if from_nn else "supplied_route", "strategy": "first_improvement"}, history=history)
