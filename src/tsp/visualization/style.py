"""A small shared chart design system."""

from __future__ import annotations

import plotly.graph_objects as go

COLORS = ["#818CF8", "#22D3EE", "#F59E0B", "#34D399", "#F472B6"]


def algorithm_color(algorithm: str) -> str:
    """Keep algorithm colors stable when exact results are absent at larger n."""
    if algorithm.startswith("Exact"):
        return "#F472B6"
    return {
        "Genetic Algorithm": "#818CF8", "Random Search": "#22D3EE",
        "Nearest Neighbor": "#F59E0B", "Nearest Neighbor + 2-opt": "#34D399",
        "2-opt (supplied route)": "#34D399", "Genetic Algorithm + 2-opt": "#34D399",
    }.get(algorithm, "#94A3B8")


def style_figure(
    figure: go.Figure, dark: bool = True, height: int = 370
) -> go.Figure:
    """Apply typography, spacing and readable grid colors consistently."""
    foreground = "#E2E8F0" if dark else "#0F172A"
    muted = "#94A3B8" if dark else "#64748B"
    grid = "rgba(148,163,184,0.12)" if dark else "#E2E8F0"
    figure.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color=foreground, size=12),
        height=height, margin=dict(l=22, r=22, t=48, b=35),
        title=dict(font=dict(size=16)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=11, color=muted)),
        hoverlabel=dict(bgcolor="#1E293B" if dark else "#FFFFFF"),
        colorway=COLORS,
    )
    figure.update_xaxes(gridcolor=grid, zeroline=False, tickfont=dict(color=muted))
    figure.update_yaxes(gridcolor=grid, zeroline=False, tickfont=dict(color=muted))
    return figure
