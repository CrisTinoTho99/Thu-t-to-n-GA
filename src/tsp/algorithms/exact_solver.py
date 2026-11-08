"""Held–Karp dynamic programming for at most 12 customers."""
from __future__ import annotations

from time import perf_counter
from ..distance import distance_matrix, route_distance
from ..models import Dataset, OptimizationResult, _integer
from ..validation import validate_route

HARD_CUSTOMER_LIMIT = 12


def exact_solver(dataset: Dataset, max_customers: int = HARD_CUSTOMER_LIMIT) -> OptimizationResult:
    """Find a provably optimal tour using O(n²2ⁿ) time and O(n2ⁿ) memory.

    evaluations is the number of DP predecessor transitions compared, including
    singleton initialization and closure. It is not a count of complete tours.
    """
    _integer(max_customers, "max_customers", 1, HARD_CUSTOMER_LIMIT)
    if dataset.n_customers > max_customers:
        raise ValueError(f"Exact solver is limited to {max_customers} customers (hard cap {HARD_CUSTOMER_LIMIT}).")
    started = perf_counter()
    matrix = distance_matrix(dataset)
    customers = dataset.customer_indices
    depot, count = dataset.depot_index, len(customers)
    costs: dict[tuple[int, int], float] = {}
    previous: dict[tuple[int, int], int] = {}
    evaluations = 0
    for end, row_index in enumerate(customers):
        costs[(1 << end, end)] = float(matrix[depot, row_index])
        previous[(1 << end, end)] = -1
        evaluations += 1
    for mask in range(1, 1 << count):
        for end in range(count):
            if not mask & (1 << end) or mask == (1 << end):
                continue
            smaller = mask ^ (1 << end)
            candidates = [candidate for candidate in range(count) if smaller & (1 << candidate)]
            winner = min(candidates, key=lambda candidate: (costs[(smaller, candidate)] + matrix[customers[candidate], customers[end]], candidate))
            evaluations += len(candidates)
            costs[(mask, end)] = float(costs[(smaller, winner)] + matrix[customers[winner], customers[end]])
            previous[(mask, end)] = winner
    mask = (1 << count) - 1
    end = min(range(count), key=lambda candidate: (costs[(mask, candidate)] + matrix[customers[candidate], depot], candidate))
    evaluations += count
    reversed_path: list[int] = []
    while end != -1:
        reversed_path.append(customers[end])
        predecessor = previous[(mask, end)]
        mask ^= 1 << end
        end = predecessor
    route = [depot, *reversed(reversed_path), depot]
    validate_route(route, dataset)
    return OptimizationResult("Exact (Held–Karp)", route, route_distance(route, matrix),
                              perf_counter() - started, evaluations,
                              parameters={"max_customers": max_customers, "evaluation_unit": "DP transitions"})
