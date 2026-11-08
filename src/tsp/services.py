"""Explicit optimization orchestration and portable export bundles."""
from __future__ import annotations
from datetime import datetime
from io import BytesIO
import json
import logging
from pathlib import Path
from typing import Sequence

from tsp.models import Dataset, GAConfig, OptimizationResult
from tsp.algorithms.genetic_algorithm import genetic_algorithm
from tsp.algorithms.nearest_neighbor import nearest_neighbor
from tsp.algorithms.random_search import random_search
from tsp.algorithms.exact_solver import exact_solver
from tsp.algorithms.two_opt import two_opt

LOGGER = logging.getLogger(__name__)
ALGORITHMS = ["Genetic Algorithm", "Nearest Neighbor", "Random Search", "Nearest Neighbor + 2-opt", "Exact Solver"]


def optimize(dataset: Dataset, config: GAConfig, selected: Sequence[str], random_budget: int | None = None) -> list[OptimizationResult]:
    """Run selected solvers once; callers own session-state persistence."""
    if not selected:
        raise ValueError("Select at least one algorithm.")
    unknown = set(selected) - set(ALGORITHMS)
    if unknown:
        raise ValueError(f"Unknown algorithms: {unknown}")
    output = []
    ga = None
    if "Genetic Algorithm" in selected:
        ga = genetic_algorithm(dataset, config)
        output.append(ga)
    if "Nearest Neighbor" in selected:
        output.append(nearest_neighbor(dataset))
    if "Random Search" in selected:
        budget = random_budget if random_budget is not None else (ga.evaluations if ga else config.population_size + config.generations * (config.population_size - config.elitism_count))
        output.append(random_search(dataset, evaluation_budget=budget, seed=config.seed))
    if "Nearest Neighbor + 2-opt" in selected:
        output.append(two_opt(dataset))
    if "Exact Solver" in selected:
        output.append(exact_solver(dataset))
    LOGGER.info("Completed %s solvers on dataset %s", len(output), dataset.fingerprint)
    return output


def result_bundle(dataset: Dataset, results: Sequence[OptimizationResult]) -> dict:
    """Contain all data required to replay an optimization, not just a screenshot."""
    return {"schema_version": 1, "distance_model": "Euclidean coordinate units", "dataset": dataset.to_dict(),
            "dataset_fingerprint": dataset.fingerprint, "results": [r.to_dict() for r in results]}


def bundle_json(dataset: Dataset, results: Sequence[OptimizationResult]) -> str:
    return json.dumps(result_bundle(dataset, results), ensure_ascii=False, indent=2, allow_nan=False)


def save_session(dataset: Dataset, results: Sequence[OptimizationResult], root: Path) -> Path:
    """Save a new timestamped file without replacing benchmark output."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(bundle_json(dataset, results), encoding="utf-8")
    return path


def route_png(dataset: Dataset, route: Sequence[int]) -> bytes:
    """Render a shareable static figure without a browser or Kaleido dependency."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    import numpy as np
    points = np.array([(p.x, p.y) for p in dataset.locations])
    fig, ax = plt.subplots(figsize=(9, 6), facecolor="#0b1120")
    ax.set_facecolor("#0b1120")
    line = points[list(route)]
    ax.plot(line[:, 0], line[:, 1], color="#818cf8", linewidth=2, zorder=1)
    ax.scatter(points[:, 0], points[:, 1], c="#22d3ee", s=65, edgecolors="#0b1120", zorder=2)
    depot = points[dataset.depot_index]
    ax.scatter(*depot, c="#f59e0b", marker="s", s=150, zorder=3, label="Warehouse")
    for order, idx in enumerate(route[:-1]):
        ax.annotate(str(order), points[idx], xytext=(6, 6), textcoords="offset points", color="#f8fafc", fontsize=9)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(f"{dataset.name} | Euclidean route", color="#f8fafc", pad=20)
    ax.set_xlabel("X / coordinate units", color="#94a3b8")
    ax.set_ylabel("Y / coordinate units", color="#94a3b8")
    ax.tick_params(colors="#94a3b8")
    ax.grid(color="#263248", alpha=.55)
    for spine in ax.spines.values():
        spine.set_color("#263248")
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()
