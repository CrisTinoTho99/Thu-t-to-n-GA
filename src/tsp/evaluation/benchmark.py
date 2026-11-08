"""Seeded, paired-budget benchmarks and complete experiment exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd

from tsp.algorithms.exact_solver import exact_solver
from tsp.algorithms.genetic_algorithm import genetic_algorithm
from tsp.algorithms.nearest_neighbor import nearest_neighbor
from tsp.algorithms.random_search import random_search
from tsp.algorithms.two_opt import two_opt
from tsp.data_loader import generate_random_dataset, dataset_to_csv
from tsp.models import Dataset, GAConfig
from .metrics import improvement_percent, optimality_gap


def _json_safe(value: Any) -> Any:
    """Convert non-finite optional statistics to strict JSON nulls."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


@dataclass
class BenchmarkResult:
    """Complete benchmark data, including every route and evolution history."""

    raw: pd.DataFrame
    summary: pd.DataFrame
    datasets: dict[str, Dataset]
    runs: list[dict[str, Any]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible reproducibility bundle."""
        return _json_safe({
            "metadata": self.metadata,
            "datasets": {name: dataset.to_dict() for name, dataset in self.datasets.items()},
            "runs": self.runs,
            "summary": self.summary.to_dict(orient="records"),
        })


def run_benchmark(
    customer_counts: tuple[int, ...] = (5, 10, 20, 30),
    repeats: int = 10,
    base_seed: int = 42,
    config: GAConfig | None = None,
) -> BenchmarkResult:
    """Compare algorithms on one immutable seeded dataset per customer count.

    GA and Random Search run ``repeats`` times with independent recorded RNG
    streams. Each Random Search run receives exactly the paired GA run's actual
    number of complete-tour evaluations, including initial GA population.
    Nearest Neighbor, NN + 2-opt, and Held–Karp (<=12 customers) are measured once
    per dataset. Deterministic algorithms do not acquire fictitious repetitions.
    """
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 100:
        raise ValueError("repeats must be an integer between 1 and 100.")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or not 0 <= base_seed <= 2**32 - 1:
        raise ValueError("base_seed must be an integer in [0, 2**32 - 1].")
    if not customer_counts or len(set(customer_counts)) != len(customer_counts):
        raise ValueError("Choose distinct customer counts.")
    if any(isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 100
           for n in customer_counts):
        raise ValueError("Customer counts must be integers between 1 and 100.")
    selected_config = config if config is not None else GAConfig()
    if not isinstance(selected_config, GAConfig):
        raise ValueError("config must be a validated GAConfig.")
    datasets: dict[str, Dataset] = {}
    rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    seeds: list[dict[str, int]] = []
    for customer_count in customer_counts:
        dataset_seed = 1000 + customer_count
        key = f"customers_{customer_count}"
        dataset = generate_random_dataset(customer_count, seed=dataset_seed, name=key)
        datasets[key] = dataset
        baseline = nearest_neighbor(dataset)
        improved = two_opt(dataset)
        exact = exact_solver(dataset) if customer_count <= 12 else None
        optimum = exact.distance if exact is not None else None

        def record(result: Any, repeat: int | None, algorithm_seed: int | None) -> None:
            row = {
                "dataset": key, "dataset_seed": dataset_seed,
                "dataset_fingerprint": dataset.fingerprint,
                "customer_count": customer_count, "total_locations": customer_count + 1,
                "repeat": repeat, "algorithm": result.algorithm, "seed": algorithm_seed,
                "distance": result.distance, "runtime_seconds": result.runtime_seconds,
                "evaluations": result.evaluations,
                "improvement_percent": improvement_percent(result.distance, baseline.distance),
                "optimal_distance": optimum,
                "optimality_gap_percent": optimality_gap(result.distance, optimum)
                    if optimum is not None else None,
            }
            rows.append(row)
            runs.append({**row, "result": result.to_dict()})

        record(baseline, None, None)
        record(improved, None, None)
        if exact is not None:
            record(exact, None, None)
        for repeat in range(repeats):
            sequence = np.random.SeedSequence([base_seed, customer_count, repeat])
            ga_seed, rs_seed = [int(value) for value in sequence.generate_state(2)]
            seeds.append({"customer_count": customer_count, "repeat": repeat,
                          "ga_seed": ga_seed, "random_search_seed": rs_seed})
            ga_result = genetic_algorithm(dataset, replace(selected_config, seed=ga_seed))
            rs_result = random_search(dataset, evaluation_budget=ga_result.evaluations,
                                      seed=rs_seed)
            record(ga_result, repeat, ga_seed)
            record(rs_result, repeat, rs_seed)
    raw = pd.DataFrame(rows)
    raw["seed"] = raw["seed"].astype("Int64")
    raw["repeat"] = raw["repeat"].astype("Int64")
    summary = raw.groupby(["dataset", "customer_count", "algorithm"], sort=False).agg(
        runs=("distance", "count"),
        best_distance=("distance", "min"),
        mean_distance=("distance", "mean"),
        worst_distance=("distance", "max"),
        std_distance=("distance", lambda column: float(column.std(ddof=1))),
        mean_runtime_seconds=("runtime_seconds", "mean"),
        mean_evaluations=("evaluations", "mean"),
        mean_improvement_percent=("improvement_percent", "mean"),
        mean_optimality_gap_percent=("optimality_gap_percent", "mean"),
    ).reset_index()
    deterministic = ~summary["algorithm"].isin(["Genetic Algorithm", "Random Search"])
    summary.loc[deterministic & (summary["runs"] == 1), "std_distance"] = 0.0
    package_versions: dict[str, str] = {}
    for package in ("numpy", "pandas", "plotly", "streamlit", "matplotlib"):
        try:
            package_versions[package] = version(package)
        except PackageNotFoundError:
            package_versions[package] = "not installed"
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "processor": platform.processor(), "package_versions": package_versions,
        "base_seed": base_seed, "repeats": repeats,
        "customer_counts": list(customer_counts), "ga_config": asdict(selected_config),
        "algorithm_seeds": seeds, "dataset_seed_rule": "1000 + customer_count",
        "comparison_protocol": (
            "One fixed Euclidean dataset per size; GA and Random Search have independent "
            "recorded seeds and matched complete-tour evaluation budgets per repeat. "
            "Deterministic methods run once. Runtime is measured wall-clock time and "
            "depends on hardware, scheduling, and implementation. 2-opt evaluations "
            "count candidate tours; Held–Karp counts dynamic-programming transitions "
            "and is not an equal-budget comparison."
        ),
        "distance_units": "Euclidean coordinate units, not road distance",
        "std_definition": "Sample SD (ddof=1); zero for deterministic single runs; undefined for stochastic single runs",
        "exact_limit_customers": 12,
    }
    return BenchmarkResult(raw=raw, summary=summary, datasets=datasets,
                           runs=runs, metadata=metadata)


def save_benchmark(
    result: BenchmarkResult, output_dir: str | Path = "results"
) -> dict[str, str]:
    """Save raw JSON/CSV, aggregate CSV, inputs, HTML charts and PNG figures."""
    from tsp.visualization.comparison_plot import comparison_figure
    from tsp.visualization.convergence_plot import convergence_figure
    from tsp.visualization.route_plot import route_figure

    root = Path(output_dir)
    for subdirectory in ("raw", "final", "figures", "datasets"):
        (root / subdirectory).mkdir(parents=True, exist_ok=True)
    raw_json = root / "raw" / "benchmark.json"
    raw_csv = root / "raw" / "benchmark_runs.csv"
    summary_csv = root / "final" / "benchmark_summary.csv"
    raw_json.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2,
                                   allow_nan=False), encoding="utf-8")
    result.raw.to_csv(raw_csv, index=False)
    result.summary.to_csv(summary_csv, index=False)
    (root / "final" / "metadata.json").write_text(
        json.dumps(_json_safe(result.metadata), ensure_ascii=False, indent=2,
                   allow_nan=False), encoding="utf-8")
    for key, dataset in result.datasets.items():
        (root / "datasets" / f"{key}.csv").write_text(dataset_to_csv(dataset), encoding="utf-8")
        runs = [r for r in result.runs if r["dataset"] == key]
        ga_runs = [r for r in runs if r["algorithm"] == "Genetic Algorithm"]
        if not ga_runs:
            continue
        best = min(ga_runs, key=lambda row: row["distance"])
        route_figure(dataset, best["result"]["route"], f"Best GA · {key}").write_html(
            str(root / "figures" / f"{key}_route.html"), include_plotlyjs="directory")
        convergence_figure(best["result"]["history"]).write_html(
            str(root / "figures" / f"{key}_convergence.html"), include_plotlyjs="directory")
        mean_frame = result.summary[result.summary["dataset"] == key].rename(columns={
            "mean_distance": "distance", "mean_runtime_seconds": "runtime_seconds",
        })
        for metric in ("distance", "runtime_seconds"):
            comparison_figure(mean_frame, metric=metric).write_html(
                str(root / "figures" / f"{key}_{metric}.html"), include_plotlyjs="directory")
    _save_pngs(result, root / "figures")
    discussion = _measured_discussion(result)
    (root / "final" / "findings.md").write_text(discussion, encoding="utf-8")
    return {"raw_json": str(raw_json), "raw_csv": str(raw_csv),
            "summary_csv": str(summary_csv), "figures": str(root / "figures"),
            "findings": str(root / "final" / "findings.md")}


def _save_pngs(result: BenchmarkResult, destination: Path) -> None:
    """Use Matplotlib for portable static exports without a browser dependency."""
    cache_path = destination.resolve().parent / "tmp" / "matplotlib"
    cache_path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_path))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tsp.visualization.style import algorithm_color

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    customer_counts = sorted(result.summary["customer_count"].unique())
    for metric, title, ylabel, error_column in (
        ("mean_distance", "Measured route distance", "Euclidean coordinate units", "std_distance"),
        ("mean_runtime_seconds", "Measured execution time", "Seconds", None),
    ):
        row_count = max(1, math.ceil(len(customer_counts) / 2))
        fig, axes = plt.subplots(row_count, 2, figsize=(12, 4 * row_count), squeeze=False)
        for ax, count in zip(axes.flat, customer_counts):
            frame = result.summary[result.summary["customer_count"] == count]
            ax.bar(range(len(frame)), frame[metric],
                   yerr=frame[error_column].fillna(0) if error_column else None,
                   color=[algorithm_color(str(name)) for name in frame["algorithm"]], capsize=3)
            ax.set_xticks(range(len(frame)), frame["algorithm"], rotation=25, ha="right", fontsize=8)
            ax.set_title(f"{count} customers + 1 depot")
            ax.set_ylabel(ylabel)
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
        for ax in list(axes.flat)[len(customer_counts):]:
            ax.set_visible(False)
        fig.suptitle(title + (" · error bars: sample SD" if error_column else ""), fontsize=15)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(destination / f"benchmark_{metric}.png", dpi=180)
        plt.close(fig)
    for key, dataset in result.datasets.items():
        candidates = [r for r in result.runs if r["dataset"] == key
                      and r["algorithm"] == "Genetic Algorithm"]
        if not candidates:
            continue
        best = min(candidates, key=lambda row: row["distance"])
        route = best["result"]["route"]
        fig, (ax, convergence) = plt.subplots(1, 2, figsize=(11, 4.5))
        ax.plot([dataset.locations[i].x for i in route],
                [dataset.locations[i].y for i in route], "-o", color="#6366F1", markersize=4)
        depot = dataset.locations[dataset.depot_index]
        ax.scatter([depot.x], [depot.y], marker="D", color="#059669", s=90,
                   label="Depot", zorder=4)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title(f"{key} · best measured GA: {best['distance']:.3f}")
        ax.set_xlabel("x · coordinate units")
        ax.set_ylabel("y · coordinate units")
        ax.legend()
        history = best["result"]["history"]
        convergence.plot([r["generation"] for r in history],
                         [r["best_distance"] for r in history], color="#0891B2", label="Best so far")
        convergence.plot([r["generation"] for r in history],
                         [r["average_distance"] for r in history], color="#64748B", alpha=0.7,
                         label="Population mean")
        convergence.set_xlabel("Generation")
        convergence.set_ylabel("Distance")
        convergence.legend()
        for subplot in (ax, convergence):
            subplot.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(destination / f"{key}_route_convergence.png", dpi=180)
        plt.close(fig)


def _measured_discussion(result: BenchmarkResult) -> str:
    """Generate findings directly from recorded comparisons, including losses."""
    lines = ["# Measured benchmark findings", "",
             "These observations are generated from the saved runs. Positive improvement means a shorter route than Nearest Neighbor.", ""]
    for count in result.metadata["customer_counts"]:
        rows = result.raw[result.raw["customer_count"] == count]
        ga = rows[rows["algorithm"] == "Genetic Algorithm"]
        rs = rows[rows["algorithm"] == "Random Search"]
        nn = rows[rows["algorithm"] == "Nearest Neighbor"].iloc[0]
        paired = ga.merge(rs, on="repeat", suffixes=("_ga", "_rs"))
        worse_nn = int((ga["distance"] > nn["distance"] + 1e-9).sum())
        worse_rs = int((paired["distance_ga"] > paired["distance_rs"] + 1e-9).sum())
        lines.extend([
            f"## {count} customers + one depot", "",
            f"GA mean distance: {ga['distance'].mean():.6f}; Random Search mean: {rs['distance'].mean():.6f}; Nearest Neighbor: {nn['distance']:.6f}.",
            f"GA was worse than Nearest Neighbor in {worse_nn}/{len(ga)} runs and worse than its paired Random Search run in {worse_rs}/{len(paired)} runs.",
            f"GA mean improvement over Nearest Neighbor: {ga['improvement_percent'].mean():.3f}%. Mean GA time: {ga['runtime_seconds'].mean():.6f} s; mean Random Search time: {rs['runtime_seconds'].mean():.6f} s.",
            (f"Exact optimum: {nn['optimal_distance']:.6f}; GA mean optimality gap: {ga['optimality_gap_percent'].mean():.3f}%."
             if pd.notna(nn['optimal_distance']) else "Exact optimum was not computed because the dataset exceeds the 12-customer limit."),
            "",
        ])
        if worse_nn or worse_rs:
            lines.extend([
                "The measured losses are consistent with finite-budget stochastic search. The pure GA starts from random permutations; tournament selection and finite population diversity can converge to a local region. Nearest Neighbor exploits local geometry immediately. This experiment does not establish a single causal mechanism or universal algorithm ranking.", "",
            ])
    lines.extend([
        "## Interpretation limits", "",
        "There is one generated geometry per problem size. Repetitions measure algorithm RNG variability on that geometry, not variability across all delivery networks. Matching complete-tour evaluations does not match wall-clock time: crossover, selection, and Python overhead differ. Timings are machine-specific. Distances are Euclidean coordinate units and exclude roads, capacity, time windows, traffic, and multiple vehicles.", "",
    ])
    return "\n".join(lines)
