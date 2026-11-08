"""Metrics shared by the application and experiment runner."""

from __future__ import annotations

from collections.abc import Iterable
import math

import pandas as pd

from tsp.models import OptimizationResult


def improvement_percent(distance: float, baseline: float) -> float:
    """Positive values mean a shorter tour than the baseline; retain negatives."""
    if not math.isfinite(distance) or not math.isfinite(baseline):
        raise ValueError("Distances must be finite.")
    if distance < 0 or baseline < 0:
        raise ValueError("Distances cannot be negative.")
    if baseline == 0:
        return 0.0 if distance == 0 else float("nan")
    return 100.0 * (baseline - distance) / baseline


def optimality_gap(distance: float, optimum: float) -> float:
    """Percentage above a proven optimum, undefined for a nonzero/zero pair."""
    return -improvement_percent(distance, optimum)


def results_frame(results: Iterable[OptimizationResult]) -> pd.DataFrame:
    """Present measured results, with improvement relative to nearest neighbor."""
    values = list(results)
    baseline = next(
        (r.distance for r in values if r.algorithm == "Nearest Neighbor"), None
    )
    rows = [
        {
            "algorithm": result.algorithm,
            "distance": result.distance,
            "runtime_seconds": result.runtime_seconds,
            "evaluations": result.evaluations,
            "improvement_percent": (
                improvement_percent(result.distance, baseline)
                if baseline is not None else float("nan")
            ),
            "seed": result.seed,
        }
        for result in values
    ]
    return pd.DataFrame(rows, columns=[
        "algorithm", "distance", "runtime_seconds", "evaluations",
        "improvement_percent", "seed",
    ])
