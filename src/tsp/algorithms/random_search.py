"""Uniform random permutation search with a strict full-tour evaluation budget."""
from __future__ import annotations

from time import perf_counter
import numpy as np
from ..distance import distance_matrix
from ..models import Dataset, OptimizationResult, _integer, validate_seed
from ..validation import validate_route


def random_search(dataset: Dataset, evaluation_budget: int = 10000, seed: int = 42) -> OptimizationResult:
    """Evaluate exactly budget tours; repeated permutations count as evaluations."""
    _integer(evaluation_budget, "evaluation_budget", 1)
    validate_seed(seed)
    started = perf_counter()
    rng = np.random.default_rng(seed)
    matrix = distance_matrix(dataset)
    depot = dataset.depot_index
    customers = np.asarray(dataset.customer_indices, dtype=int)
    best_distance = float("inf")
    best_route: list[int] = []
    history: list[dict] = []
    # Batches bound memory without changing the seeded permutation stream.
    for offset in range(0, evaluation_budget, 512):
        count = min(512, evaluation_budget - offset)
        permutations = np.asarray([rng.permutation(customers) for _ in range(count)])
        routes = np.column_stack((np.full(count, depot), permutations, np.full(count, depot)))
        distances = matrix[routes[:, :-1], routes[:, 1:]].sum(axis=1)
        winner = int(np.argmin(distances))
        if float(distances[winner]) < best_distance:
            best_distance = float(distances[winner])
            best_route = routes[winner].tolist()
        history.append({"evaluations": offset + count, "best_distance": best_distance,
                        "average_distance": float(np.mean(distances)), "route": best_route.copy()})
    validate_route(best_route, dataset)
    return OptimizationResult("Random Search", best_route, best_distance, perf_counter() - started,
                              evaluation_budget, seed, {"evaluation_budget": evaluation_budget}, history)
