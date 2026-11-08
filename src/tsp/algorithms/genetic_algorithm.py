"""Pure permutation GA: tournament selection, OX, inversion, and elitism."""
from __future__ import annotations

from time import perf_counter
from typing import Sequence
import numpy as np

from ..distance import distance_matrix
from ..models import Dataset, GAConfig, OptimizationResult
from ..validation import validate_route

EPSILON = 1e-12


def order_crossover(parent1: Sequence[int], parent2: Sequence[int], rng: np.random.Generator) -> list[int]:
    """OX child: retain an inclusive random segment, fill cyclically from parent2."""
    first, second = list(parent1), list(parent2)
    if len(first) != len(second) or len(set(first)) != len(first) or set(first) != set(second):
        raise ValueError("OX parents must be permutations of the same unique genes.")
    if len(first) < 2:
        return first.copy()
    start, stop = sorted(int(i) for i in rng.choice(len(first), 2, replace=False))
    child: list[int | None] = [None] * len(first)
    child[start:stop + 1] = first[start:stop + 1]
    retained = set(first[start:stop + 1])
    candidates = second[stop + 1:] + second[:stop + 1]
    positions = list(range(stop + 1, len(first))) + list(range(0, start))
    for position, gene in zip(positions, (gene for gene in candidates if gene not in retained)):
        child[position] = gene
    return [int(gene) for gene in child]


def inversion_mutation(route: Sequence[int], rng: np.random.Generator) -> list[int]:
    """Return a copy with one inclusive random segment reversed."""
    mutated = list(route)
    if len(set(mutated)) != len(mutated):
        raise ValueError("Mutation requires a permutation with unique genes.")
    if len(mutated) >= 2:
        start, stop = sorted(int(i) for i in rng.choice(len(mutated), 2, replace=False))
        mutated[start:stop + 1] = reversed(mutated[start:stop + 1])
    return mutated


def genetic_algorithm(dataset: Dataset, config: GAConfig | None = None) -> OptimizationResult:
    """Minimize closed tour distance without heuristic seeding or local search.

    Crossover probability is applied once per selected parent pair. Mutation
    probability is applied independently per child. Elites keep their cached
    objective; each new child counts as one evaluation, including duplicates.
    Tournament contestants are sampled without replacement within a tournament.
    """
    started = perf_counter()
    config = config or GAConfig()
    if not isinstance(config, GAConfig):
        raise ValueError("config must be a validated GAConfig.")
    matrix = distance_matrix(dataset)
    rng = np.random.default_rng(config.seed)
    depot = dataset.depot_index
    customers = np.asarray(dataset.customer_indices, dtype=int)
    population = np.asarray([rng.permutation(customers) for _ in range(config.population_size)])

    def evaluate(chromosomes: np.ndarray) -> np.ndarray:
        closed = np.column_stack((np.full(len(chromosomes), depot), chromosomes, np.full(len(chromosomes), depot)))
        return matrix[closed[:, :-1], closed[:, 1:]].sum(axis=1)

    def closed(chromosome: Sequence[int]) -> list[int]:
        return [depot, *(int(gene) for gene in chromosome), depot]

    distances = evaluate(population)
    evaluations = len(population)
    best_index = int(np.argmin(distances))
    best_distance = float(distances[best_index])
    best_chromosome = population[best_index].copy()
    history: list[dict] = []

    def snapshot(generation: int) -> None:
        history.append({
            "generation": generation,
            "best_distance": best_distance,
            "average_distance": float(np.mean(distances)),
            "best_fitness": float(1.0 / (best_distance + EPSILON)),
            "average_fitness": float(np.mean(1.0 / (distances + EPSILON))),
            "route": closed(best_chromosome),
            "evaluations": evaluations,
        })

    snapshot(0)
    stagnant = 0
    for generation in range(1, config.generations + 1):
        ranked = np.argsort(distances, kind="stable")
        elite_indices = ranked[:config.elitism_count]
        children: list[list[int]] = []
        target = config.population_size - config.elitism_count

        def tournament() -> list[int]:
            contestants = rng.choice(config.population_size, config.tournament_size, replace=False)
            winner = contestants[int(np.argmin(distances[contestants]))]
            return population[winner].tolist()

        while len(children) < target:
            first, second = tournament(), tournament()
            if rng.random() < config.crossover_rate:
                offspring = [order_crossover(first, second, rng), order_crossover(second, first, rng)]
            else:
                offspring = [first.copy(), second.copy()]
            for child in offspring:
                if len(children) >= target:
                    break
                if rng.random() < config.mutation_rate:
                    child = inversion_mutation(child, rng)
                children.append(child)

        child_population = np.asarray(children, dtype=int)
        child_distances = evaluate(child_population)
        population = np.concatenate((population[elite_indices], child_population), axis=0)
        distances = np.concatenate((distances[elite_indices], child_distances))
        evaluations += len(children)
        candidate = int(np.argmin(distances))
        if float(distances[candidate]) < best_distance:
            best_distance = float(distances[candidate])
            best_chromosome = population[candidate].copy()
            stagnant = 0
        else:
            stagnant += 1
        snapshot(generation)
        if config.early_stopping_patience and stagnant >= config.early_stopping_patience:
            break

    route = closed(best_chromosome)
    validate_route(route, dataset)
    return OptimizationResult("Genetic Algorithm", route, best_distance, perf_counter() - started,
                              evaluations, config.seed, config.to_dict(), history)
