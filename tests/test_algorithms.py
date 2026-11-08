"""Independent optimum checks and stochastic algorithm invariants."""

from itertools import permutations

import numpy as np
import pytest

from tsp.algorithms.exact_solver import exact_solver
from tsp.algorithms.genetic_algorithm import genetic_algorithm, inversion_mutation, order_crossover
from tsp.algorithms.nearest_neighbor import nearest_neighbor
from tsp.algorithms.random_search import random_search
from tsp.algorithms.two_opt import two_opt
from tsp.data_loader import generate_random_dataset
from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, GAConfig, Location
from tsp.validation import validate_route


def test_exact_square_optimum_is_four(square):
    result = exact_solver(square)
    validate_route(result.route, square)
    assert result.distance == pytest.approx(4.0)


def test_exact_solver_matches_independent_enumeration():
    dataset = generate_random_dataset(6, seed=2026)
    matrix = distance_matrix(dataset)
    depot = dataset.depot_index
    optimum = min(
        route_distance([depot, *order, depot], matrix)
        for order in permutations(dataset.customer_indices)
    )
    assert exact_solver(dataset).distance == pytest.approx(optimum)


def test_exact_solver_refuses_large_input():
    with pytest.raises(ValueError):
        exact_solver(generate_random_dataset(13))


def test_nearest_neighbor_expected_square_route(square):
    result = nearest_neighbor(square)
    assert result.route == [0, 1, 2, 3, 0]
    assert result.distance == pytest.approx(4)


@pytest.mark.parametrize("solver", [nearest_neighbor, exact_solver, two_opt])
def test_deterministic_solvers_preserve_nonzero_depot(shifted_depot, solver):
    result = solver(shifted_depot)
    validate_route(result.route, shifted_depot)
    assert result.route[0] == result.route[-1] == 2


@pytest.mark.parametrize("length", [1, 2, 3, 7, 20])
def test_order_crossover_and_inversion_preserve_permutations(length):
    rng = np.random.default_rng(101)
    parent = list(range(length))
    other = parent[::-1]
    for _ in range(40):
        child = order_crossover(parent, other, rng)
        assert sorted(child) == parent
        mutated = inversion_mutation(child, rng)
        assert sorted(mutated) == parent


def test_genetic_algorithm_elitism_keeps_best_distance_nonincreasing():
    dataset = generate_random_dataset(12, seed=11)
    result = genetic_algorithm(dataset, GAConfig(
        population_size=30, generations=25, elitism_count=2,
        mutation_rate=1.0, seed=19,
    ))
    validate_route(result.route, dataset)
    best = [row["best_distance"] for row in result.history]
    assert len(best) == 26  # initial population plus completed generations
    assert all(later <= earlier + 1e-10 for earlier, later in zip(best, best[1:]))
    assert result.distance == pytest.approx(min(best))
    for row in result.history:
        validate_route(row["route"], dataset)


def test_seed_reproduces_ga_without_promising_optimality():
    dataset = generate_random_dataset(10, seed=123)
    config = GAConfig(population_size=24, generations=15, seed=8)
    first = genetic_algorithm(dataset, config)
    second = genetic_algorithm(dataset, config)
    assert first.route == second.route
    assert first.distance == second.distance
    assert first.evaluations == second.evaluations
    assert first.history == second.history
    assert first.parameters == second.parameters


def test_ga_evaluations_reuse_elites(square):
    config = GAConfig(population_size=12, generations=7, elitism_count=2)
    result = genetic_algorithm(square, config)
    assert result.evaluations == 12 + 7 * (12 - 2)


def test_random_search_matches_requested_evaluation_budget(square):
    result = random_search(square, evaluation_budget=37, seed=7)
    assert result.evaluations == 37
    validate_route(result.route, square)
    duplicate = random_search(square, evaluation_budget=37, seed=7)
    assert result.route == duplicate.route
    assert result.distance == duplicate.distance


def test_two_opt_never_worsens_start_route():
    dataset = generate_random_dataset(15, seed=31)
    initial = nearest_neighbor(dataset)
    result = two_opt(dataset, initial_route=initial.route)
    validate_route(result.route, dataset)
    assert result.distance <= initial.distance + 1e-10


def test_early_stopping_counts_completed_stagnant_generations():
    dataset = Dataset("Coincident points", (
        Location("D", "Depot", 0, 0, True),
        Location("A", "A", 0, 0),
        Location("B", "B", 0, 0),
    ))
    result = genetic_algorithm(dataset, GAConfig(
        population_size=10, generations=100, early_stopping_patience=3,
    ))
    assert result.distance == 0
    assert [row["generation"] for row in result.history] == [0, 1, 2, 3]
    assert result.evaluations == 10 + 3 * 8
    assert np.isfinite(result.history[-1]["best_fitness"])


def test_all_solvers_handle_one_customer():
    dataset = Dataset("One customer", (
        Location("A", "A", 3, 4),
        Location("D", "Depot", 0, 0, True),
    ))
    results = [
        nearest_neighbor(dataset), exact_solver(dataset), two_opt(dataset),
        random_search(dataset, evaluation_budget=5),
        genetic_algorithm(dataset, GAConfig(population_size=6, generations=2)),
    ]
    for result in results:
        assert result.route == [1, 0, 1]
        assert result.distance == pytest.approx(10)


@pytest.mark.parametrize("changes", [
    {"population_size": 1}, {"generations": -1},
    {"crossover_rate": -0.1}, {"crossover_rate": 1.1},
    {"mutation_rate": -0.1}, {"mutation_rate": 1.1},
    {"elitism_count": -1}, {"elitism_count": 100},
    {"tournament_size": 0}, {"tournament_size": 101},
    {"early_stopping_patience": -1},
    {"seed": -1}, {"seed": True}, {"population_size": 2.5},
])
def test_invalid_ga_parameters_are_rejected(square, changes):
    with pytest.raises(ValueError):
        genetic_algorithm(square, GAConfig(**changes))


@pytest.mark.parametrize("budget", [0, -1])
def test_random_search_rejects_nonpositive_budget(square, budget):
    with pytest.raises(ValueError):
        random_search(square, evaluation_budget=budget)
