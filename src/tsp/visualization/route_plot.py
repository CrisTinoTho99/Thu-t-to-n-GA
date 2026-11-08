"""Interactive closed-route plots with a distinct depot."""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from tsp.models import Dataset
from tsp.validation import validate_route
from .style import style_figure


def route_figure(
    dataset: Dataset,
    route: Sequence[int] | None = None,
    title: str | None = None,
    dark: bool = True,
) -> go.Figure:
    """Render coordinates and an optional validated full closed tour.

    Plotly's modebar provides reset axes and PNG export. Labels on customer
    markers are visit order when a route is available, otherwise location IDs.
    """
    figure = go.Figure()
    order: dict[int, int] = {}
    if route is not None:
        validate_route(list(route), dataset)
        order = {idx: step for step, idx in enumerate(route[:-1])}
        figure.add_trace(go.Scatter(
            x=[dataset.locations[i].x for i in route],
            y=[dataset.locations[i].y for i in route],
            mode="lines", name="Closed delivery tour",
            line=dict(color="#22D3EE", width=2.5),
            hoverinfo="skip",
        ))
    customer_indices = dataset.customer_indices
    customers = [dataset.locations[i] for i in customer_indices]
    figure.add_trace(go.Scatter(
        x=[p.x for p in customers], y=[p.y for p in customers],
        text=[str(order[i]) if order else p.id
              for i, p in zip(customer_indices, customers)],
        customdata=[[p.id, p.name, order.get(i, "—")]
                    for i, p in zip(customer_indices, customers)],
        mode="markers+text", textposition="top center", name="Customers",
        textfont=dict(size=11, color="#A5B4FC" if dark else "#4F46E5"),
        marker=dict(size=11, color="#818CF8", line=dict(width=2,
                    color="#0B1120" if dark else "#FFFFFF")),
        hovertemplate=("<b>%{customdata[1]}</b><br>ID: %{customdata[0]}"
                       "<br>Visit: %{customdata[2]}"
                       "<br>x: %{x:.3f} · y: %{y:.3f}<extra></extra>"),
    ))
    depot = dataset.locations[dataset.depot_index]
    figure.add_trace(go.Scatter(
        x=[depot.x], y=[depot.y], mode="markers+text", name="Warehouse",
        text=["DEPOT"], textposition="bottom center",
        textfont=dict(color="#34D399", size=11),
        marker=dict(size=18, symbol="diamond", color="#34D399",
                    line=dict(width=2, color="#FFFFFF")),
        customdata=[[depot.id, depot.name]],
        hovertemplate=("<b>%{customdata[1]} · Warehouse</b>"
                       "<br>ID: %{customdata[0]}"
                       "<br>x: %{x:.3f} · y: %{y:.3f}<extra></extra>"),
    ))
    style_figure(figure, dark=dark, height=470)
    figure.update_layout(title=title or "Delivery network", dragmode="pan",
                         uirevision=f"{dataset.fingerprint}-{title}")
    figure.update_xaxes(title="x · coordinate units", constrain="domain")
    figure.update_yaxes(title="y · coordinate units", scaleanchor="x", scaleratio=1)
    return figure
