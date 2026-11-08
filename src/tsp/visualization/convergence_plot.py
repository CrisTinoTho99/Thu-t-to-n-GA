"""Convergence plots from stored GA history."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import plotly.graph_objects as go

from .style import style_figure


def search_comparison_figure(results: Sequence[Any], dark: bool = True) -> go.Figure:
    """Compare recorded GA/Random Search progress at actual objective budgets.

    Steps retain the last recorded best distance until the next stored sample.
    In particular, Random Search's batch-boundary history does not imply a known
    improvement time inside an unrecorded batch.
    """
    from .style import algorithm_color

    figure = go.Figure()
    for result in results:
        if result.algorithm not in {"Genetic Algorithm", "Random Search"}:
            continue
        history = [row for row in result.history
                   if "evaluations" in row and "best_distance" in row]
        if not history:
            continue
        figure.add_trace(go.Scatter(
            x=[row["evaluations"] for row in history],
            y=[row["best_distance"] for row in history],
            name=result.algorithm, mode="lines+markers",
            marker=dict(size=4),
            line=dict(color=algorithm_color(result.algorithm), width=2.5, shape="hv"),
            hovertemplate="%{x:,} evaluations<br>Best recorded: %{y:.3f}<extra>%{fullData.name}</extra>",
        ))
    style_figure(figure, dark)
    figure.update_layout(title="Search progress at recorded evaluation budgets")
    figure.update_xaxes(title="Complete-tour objective evaluations", rangemode="tozero")
    figure.update_yaxes(title="Best distance · coordinate units", rangemode="tozero")
    return figure


def convergence_figure(
    history: Sequence[dict[str, Any]], dark: bool = True
) -> go.Figure:
    """Plot the best-so-far and current population mean distances by generation."""
    figure = go.Figure()
    generations = [row["generation"] for row in history]
    figure.add_trace(go.Scatter(
        x=generations, y=[row["average_distance"] for row in history],
        name="Population mean", mode="lines",
        line=dict(color="#64748B", width=1.5, dash="dot"),
        hovertemplate="Generation %{x}<br>Mean: %{y:.3f}<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=generations, y=[row["best_distance"] for row in history],
        name="Best so far", mode="lines",
        line=dict(color="#22D3EE", width=2.5),
        hovertemplate="Generation %{x}<br>Best: %{y:.3f}<extra></extra>",
    ))
    style_figure(figure, dark)
    figure.update_layout(title="Evolution of route distance")
    figure.update_xaxes(title="Generation", rangemode="tozero")
    figure.update_yaxes(title="Distance · coordinate units", rangemode="tozero")
    return figure
