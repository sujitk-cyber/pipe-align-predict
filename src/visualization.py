"""
Interactive chart generation using Plotly for ILI growth analysis reports.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def depth_growth_histogram(growth_df: pd.DataFrame) -> str:
    """Histogram of depth growth rates coloured by feature type.

    Returns:
        Plotly figure as self-contained HTML div string.
    """
    if growth_df.empty or "depth_growth_pct_per_yr" not in growth_df.columns:
        return ""

    df = growth_df.dropna(subset=["depth_growth_pct_per_yr"]).copy()
    fig = px.histogram(
        df,
        x="depth_growth_pct_per_yr",
        color="feature_type" if "feature_type" in df.columns else None,
        nbins=40,
        title="Depth Growth Rate Distribution",
        labels={"depth_growth_pct_per_yr": "Depth Growth (%WT / yr)", "count": "Count"},
        barmode="overlay",
        opacity=0.75,
    )
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Depth Growth (%WT / yr)",
        yaxis_title="Count",
        height=400,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def worst_n_chart(growth_df: pd.DataFrame, n: int = 20) -> str:
    """Horizontal bar chart of worst-N anomalies by severity score.

    Returns:
        Plotly figure as self-contained HTML div string.
    """
    if growth_df.empty or "severity_score" not in growth_df.columns:
        return ""

    top = growth_df.head(n).copy()
    top["label"] = top.apply(
        lambda r: f"{r.get('feature_id_a', '?')} ({r.get('feature_type', '')})", axis=1
    )
    top = top.iloc[::-1]  # reverse for bottom-up bar order

    fig = px.bar(
        top,
        x="severity_score",
        y="label",
        orientation="h",
        title=f"Top-{n} Most Severe Anomalies",
        labels={"severity_score": "Severity Score", "label": "Anomaly"},
        color="severity_score",
        color_continuous_scale="YlOrRd",
    )
    fig.update_layout(
        template="plotly_white",
        height=max(350, n * 25),
        showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def growth_scatter(growth_df: pd.DataFrame) -> str:
    """Scatter plot of depth_A vs depth_B with 1:1 reference line.

    Returns:
        Plotly figure as self-contained HTML div string.
    """
    if growth_df.empty:
        return ""
    needed = ["depth_pct_a", "depth_pct_b"]
    if not all(c in growth_df.columns for c in needed):
        return ""

    df = growth_df.dropna(subset=needed).copy()
    if df.empty:
        return ""

    fig = px.scatter(
        df,
        x="depth_pct_a",
        y="depth_pct_b",
        color="feature_type" if "feature_type" in df.columns else None,
        hover_data=["feature_id_a", "depth_growth_pct_per_yr"] if "depth_growth_pct_per_yr" in df.columns else None,
        title="Depth: Run A vs Run B",
        labels={"depth_pct_a": "Depth % (Run A)", "depth_pct_b": "Depth % (Run B)"},
        opacity=0.7,
    )
    # 1:1 reference line
    mx = max(df["depth_pct_a"].max(), df["depth_pct_b"].max(), 1)
    fig.add_trace(go.Scatter(
        x=[0, mx], y=[0, mx],
        mode="lines", line=dict(dash="dash", color="grey"),
        showlegend=False, name="1:1",
    ))
    fig.update_layout(template="plotly_white", height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def segment_alignment_plot(segments: list[dict], residuals: pd.DataFrame) -> str:
    """Bar chart of per-segment stretch factors and residual scatter.

    Returns:
        Plotly figure as self-contained HTML div string.
    """
    if not segments:
        return ""

    seg_df = pd.DataFrame(segments)
    if "scale" not in seg_df.columns:
        return ""

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(len(seg_df))),
        y=seg_df["scale"],
        name="Scale (stretch factor)",
    ))
    fig.update_layout(
        title="Alignment Stretch Factors by Segment",
        xaxis_title="Segment",
        yaxis_title="Scale",
        template="plotly_white",
        height=350,
    )
    # Add 1.0 reference line
    fig.add_hline(y=1.0, line_dash="dash", line_color="grey", annotation_text="1.0")

    html = fig.to_html(full_html=False, include_plotlyjs=False)

    # Residuals scatter if available
    if residuals is not None and not residuals.empty and "residual_ft" in residuals.columns:
        fig2 = px.scatter(
            residuals,
            x="distance_a" if "distance_a" in residuals.columns else residuals.index,
            y="residual_ft",
            title="Alignment Residuals at Control Points",
            labels={"distance_a": "Distance (ft)", "residual_ft": "Residual (ft)"},
        )
        fig2.add_hline(y=0, line_dash="dash", line_color="grey")
        fig2.update_layout(template="plotly_white", height=300)
        html += fig2.to_html(full_html=False, include_plotlyjs=False)

    return html


def remaining_life_histogram(growth_df: pd.DataFrame) -> str:
    """Histogram of remaining life (years to critical) capped at 100 yr.

    Returns:
        Plotly figure as self-contained HTML div string.
    """
    if growth_df.empty or "remaining_life_yr" not in growth_df.columns:
        return ""

    df = growth_df.copy()
    life = pd.to_numeric(df["remaining_life_yr"], errors="coerce")
    life = life.replace([np.inf, -np.inf], np.nan).dropna()
    if life.empty:
        return ""

    life = life.clip(upper=100)
    fig = px.histogram(
        x=life,
        nbins=30,
        title="Remaining Life Distribution (capped at 100 yr)",
        labels={"x": "Remaining Life (years)", "count": "Count"},
    )
    fig.update_layout(template="plotly_white", height=350)
    return fig.to_html(full_html=False, include_plotlyjs=False)
