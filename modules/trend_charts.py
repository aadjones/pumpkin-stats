"""
Trend-specific chart visualizations.

Handles complex trend charts separate from basic chart components.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .constants import COLORS


def create_monthly_trends_chart(trend_df: pd.DataFrame) -> go.Figure:
    """Create multi-line trend chart showing spending, income, and net over time."""
    if trend_df.empty:
        return go.Figure()

    fig = go.Figure()

    # Add spending line
    fig.add_trace(
        go.Scatter(
            x=trend_df["month_name"],
            y=trend_df["spending"],
            mode="lines+markers",
            name="Spending",
            line=dict(color=COLORS.get("spending", "#DB6D72"), width=2, dash="dash"),
            marker=dict(size=12, line=dict(width=2, color="white")),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>$%{y:,.2f}<extra></extra>",
        )
    )

    # Add income line
    fig.add_trace(
        go.Scatter(
            x=trend_df["month_name"],
            y=trend_df["income"],
            mode="lines+markers",
            name="Income",
            line=dict(color=COLORS.get("income", "#32CD32"), width=2, dash="dash"),
            marker=dict(size=12, line=dict(width=2, color="white")),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>$%{y:,.2f}<extra></extra>",
        )
    )

    # Add horizontal line at zero for reference
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="12-Month Financial Trends",
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=450,
    )

    # Format y-axis to show dollars
    fig.update_layout(yaxis_tickformat="$,.0f")

    return fig


def create_category_trends_chart(category_df: pd.DataFrame) -> go.Figure:
    """Create stacked area chart showing top category spending trends."""
    if category_df.empty:
        return go.Figure()

    # Pivot data to have categories as columns
    pivot_df = category_df.pivot(index="month_name", columns="category", values="spending").fillna(0)

    # Preserve chronological order by reindexing with original month order
    chronological_months = category_df.sort_values("date")["month_name"].unique()
    pivot_df = pivot_df.reindex(chronological_months)

    # Create colors for categories - improved accessibility
    category_colors = [
        "#DB6D72",  # Theme red
        "#2E86AB",  # Blue
        "#A23B72",  # Purple
        "#F18F01",  # Orange
        "#C73E1D",  # Dark red
        "#6A994E",  # Green
        "#577590",  # Blue-gray
        "#F2CC8F",  # Light orange
        "#81B29A",  # Sage green
        "#E07A5F",  # Coral
    ]

    fig = go.Figure()

    # Add traces for each category
    for i, category in enumerate(pivot_df.columns):
        color = category_colors[i % len(category_colors)]

        fig.add_trace(
            go.Scatter(
                x=pivot_df.index,
                y=pivot_df[category],
                mode="lines",
                name=category,
                stackgroup="one",
                fillcolor=color,
                line=dict(width=0.5, color="white"),  # Add subtle borders
                fill="tonexty" if i > 0 else "tozeroy",  # Fill the area
                hoveron="fills",  # Enable hover on the filled area, not just the line
                hovertemplate=(
                    f"<b>{category}</b><br>" "%{x}<br>" f"This category: $%{{y:,.2f}}<br>" "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Spending Trends by Category",
        xaxis_title="Month",
        yaxis_title="Spending ($)",
        hovermode="closest",  # Show only the hovered category
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.01,
            itemclick="toggleothers",  # Click to isolate one category
            itemdoubleclick="toggle",  # Double-click to show/hide
        ),
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )

    # Format y-axis to show dollars
    fig.update_layout(yaxis_tickformat="$,.0f")

    return fig


def create_top_categories_chart(category_df: pd.DataFrame, top_n: int = 5) -> go.Figure:
    """Create line chart showing top N categories with prominent data points."""
    if category_df.empty:
        return go.Figure()

    # Get top categories by total spending
    category_totals = category_df.groupby("category")["spending"].sum().sort_values(ascending=False)
    top_categories = category_totals.head(top_n).index.tolist()

    # Filter to top categories
    filtered_df = category_df[category_df["category"].isin(top_categories)]

    if filtered_df.empty:
        return go.Figure()

    # Preserve chronological order by getting month order from original data
    chronological_months = filtered_df.sort_values("date")["month_name"].unique()

    fig = go.Figure()

    # Define colors for top categories
    colors = ["#DB6D72", "#4682B4", "#32CD32", "#FFB347", "#DDA0DD", "#87CEEB", "#F0E68C"]

    # Add line for each category
    for i, category in enumerate(top_categories):
        cat_data = filtered_df[filtered_df["category"] == category].sort_values("date")
        color = colors[i % len(colors)]

        fig.add_trace(
            go.Scatter(
                x=cat_data["month_name"],
                y=cat_data["spending"],
                mode="lines+markers",
                name=category,
                line=dict(color=color, width=2, dash="dash"),
                marker=dict(size=10, line=dict(width=2, color="white")),
                hovertemplate=f"<b>{category}</b><br>%{{x}}<br>${{y:,.0f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Top {top_n} Category Spending Trends",
        xaxis_title="Month",
        yaxis_title="Spending ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
        xaxis=dict(categoryorder="array", categoryarray=chronological_months),
    )

    # Format y-axis to show dollars
    fig.update_layout(yaxis_tickformat="$,.0f")

    return fig


def create_trend_summary_metrics(metrics: dict) -> go.Figure:
    """Create simple metric cards showing trend summary."""
    if not metrics:
        return go.Figure()

    # Create a simple text-based figure for key metrics
    fig = go.Figure()

    # This is a placeholder - in a real implementation you might use
    # Streamlit's metric components instead of trying to create this in Plotly
    fig.add_annotation(
        text="Trend metrics would be better displayed as Streamlit st.metric components",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        xanchor="center",
        yanchor="middle",
        showarrow=False,
        font=dict(size=16, color="gray"),
    )

    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=100,
        margin=dict(l=0, r=0, t=0, b=0),
    )

    return fig
