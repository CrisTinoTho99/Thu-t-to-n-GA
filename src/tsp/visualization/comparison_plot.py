"""Algorithm comparison charts without inferred or synthetic results."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.graph_objects as go

from tsp.models import OptimizationResult
from tsp.evaluation.metrics import results_frame
from .style import algorithm_color, style_figure


def comparison_figure(
    results: Iterable[OptimizationResult] | pd.DataFrame,
    metric: str = "distance",
    dark: bool = True,
) -> go.Figure:
    """Compare distance, measured seconds, or evaluated solutions."""
    if metric not in {"distance", "runtime_seconds", "evaluations"}:
        raise ValueError("Unsupported comparison metric.")
    frame = results.copy() if isinstance(results, pd.DataFrame) else results_frame(results)
    titles = {"distance": "Route distance", "runtime_seconds": "Execution time",
              "evaluations": "Evaluated solutions"}
    units = {"distance": "Coordinate units", "runtime_seconds": "Seconds",
             "evaluations": "Objective evaluations"}
    figure = go.Figure(go.Bar(
        x=frame["algorithm"], y=frame[metric],
        marker=dict(color=[algorithm_color(str(name)) for name in frame["algorithm"]],
                    cornerradius=5),
        text=frame[metric], texttemplate="%{text:.3f}" if metric != "evaluations" else "%{text:.0f}",
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:.5g}<extra></extra>",
    ))
    style_figure(figure, dark)
    figure.update_layout(title=titles[metric], showlegend=False, bargap=0.38)
    figure.update_yaxes(title=units[metric], rangemode="tozero")
    figure.update_xaxes(tickangle=-12)
    return figure
