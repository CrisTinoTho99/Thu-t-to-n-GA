"""Integration checks for fair experiment bookkeeping and real chart data."""

import json

import pandas as pd
import pytest

from tsp.data_loader import generate_random_dataset
from tsp.evaluation.benchmark import run_benchmark, save_benchmark
from tsp.evaluation.metrics import improvement_percent, optimality_gap, results_frame
from tsp.models import GAConfig
from tsp.visualization import comparison_figure, convergence_figure, route_figure


def test_search_comparison_uses_actual_recorded_evaluation_boundaries():
    from tsp.algorithms.genetic_algorithm import genetic_algorithm
    from tsp.algorithms.random_search import random_search
    from tsp.algorithms.nearest_neighbor import nearest_neighbor
    from tsp.visualization import search_comparison_figure

    dataset = generate_random_dataset(5, seed=17)
    ga = genetic_algorithm(dataset, GAConfig(population_size=10, generations=3))
    random = random_search(dataset, evaluation_budget=ga.evaluations, seed=18)
    figure = search_comparison_figure([nearest_neighbor(dataset), ga, random])
    assert [trace.name for trace in figure.data] == [ga.algorithm, random.algorithm]
    for trace, result in zip(figure.data, (ga, random)):
        assert list(trace.x) == [row["evaluations"] for row in result.history]
        assert list(trace.y) == [row["best_distance"] for row in result.history]
        assert trace.line.shape == "hv"


def test_signed_metrics_and_zero_baseline():
    assert improvement_percent(80, 100) == pytest.approx(20)
    assert improvement_percent(120, 100) == pytest.approx(-20)
    assert optimality_gap(120, 100) == pytest.approx(20)
    assert improvement_percent(0, 0) == 0
    with pytest.raises(ValueError):
        improvement_percent(float("nan"), 1)


def test_paired_budget_seeds_and_summary():
    config = GAConfig(population_size=10, generations=5, early_stopping_patience=2)
    benchmark = run_benchmark((5,), repeats=2, base_seed=42, config=config)
    raw = benchmark.raw
    ga = raw[raw.algorithm == "Genetic Algorithm"].sort_values("repeat")
    random = raw[raw.algorithm == "Random Search"].sort_values("repeat")
    assert ga.evaluations.tolist() == random.evaluations.tolist()
    assert ga.seed.tolist() != random.seed.tolist()
    assert raw.dataset_fingerprint.nunique() == 1
    assert len(ga) == len(random) == 2
    deterministic = benchmark.summary[benchmark.summary.algorithm == "Nearest Neighbor"]
    assert deterministic.iloc[0].runs == 1
    assert deterministic.iloc[0].std_distance == 0
    again = run_benchmark((5,), repeats=2, base_seed=42, config=config)
    assert benchmark.raw.distance.tolist() == again.raw.distance.tolist()
    assert benchmark.metadata["algorithm_seeds"] == again.metadata["algorithm_seeds"]


@pytest.mark.parametrize("kwargs", [
    {"repeats": 0}, {"repeats": True}, {"customer_counts": ()},
    {"customer_counts": (5, 5)}, {"customer_counts": (0,)}, {"base_seed": -1},
])
def test_invalid_benchmark_parameters(kwargs):
    with pytest.raises(ValueError):
        run_benchmark(**kwargs)


def test_export_bundle_and_figures_use_recorded_data(tmp_path):
    benchmark = run_benchmark((3,), repeats=1,
                              config=GAConfig(population_size=6, generations=2))
    paths = save_benchmark(benchmark, tmp_path)
    bundle = json.loads((tmp_path / "raw" / "benchmark.json").read_text(encoding="utf-8"))
    assert len(bundle["runs"]) == 5  # NN, 2-opt, exact, GA, Random Search
    assert bundle["datasets"]["customers_3"]["locations"]
    assert len(pd.read_csv(paths["raw_csv"])) == 5
    assert (tmp_path / "figures" / "benchmark_mean_distance.png").stat().st_size > 1000
    dataset = benchmark.datasets["customers_3"]
    ga = next(row["result"] for row in benchmark.runs if row["algorithm"] == "Genetic Algorithm")
    route = route_figure(dataset, ga["route"])
    assert list(route.data[0].x) == [dataset.locations[i].x for i in ga["route"]]
    convergence = convergence_figure(ga["history"])
    assert list(convergence.data[1].y) == [row["best_distance"] for row in ga["history"]]
    comparison = comparison_figure(benchmark.raw)
    assert list(comparison.data[0].y) == benchmark.raw.distance.tolist()
    with pytest.raises(ValueError):
        comparison_figure(benchmark.raw, metric="invented")
