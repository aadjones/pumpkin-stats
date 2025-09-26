# modules/charts.py
from .constants import COLORS, LABELS  # COLORS is now used 100 % of the time


def _label(col: str) -> str:
    return LABELS.get(col.lower(), col.capitalize())


import plotly.express as px


def line_chart(df, column: str, color: str | None = None):
    color = COLORS.get(column.lower(), color or "#4682B4")  # auto-lookup
    fig = px.line(
        df,
        x=df.columns[0],
        y=column,
        markers=True,
        color_discrete_sequence=[color],
    )

    # Emphasize data points and de-emphasize trend lines
    fig.update_traces(
        # Make data points prominent
        marker=dict(size=12, line=dict(width=2, color="white")),
        # Make connecting lines dashed and subtle
        line=dict(dash="dash", width=2, color=color),
        opacity=0.8,  # Set opacity at trace level, not line level
        # Enhance hover for data points
        hovertemplate="<b>%{x}</b><br>%{y:$,.0f}<extra></extra>",
    )

    fig.update_layout(yaxis_title=_label(column))
    return fig


def pie_chart(df, names_col: str, values_col: str, title: str = ""):
    """Create a pie chart for category spending data."""
    # Filter out zero values for cleaner visualization
    df_filtered = df[df[values_col] > 0].copy()

    # Create color palette - use theme colors where possible
    colors = [
        "#DB6D72",  # Primary theme color
        "#4682B4",  # Steel Blue
        "#32CD32",  # Lime Green
        "#FFB347",  # Peach
        "#DDA0DD",  # Plum
        "#87CEEB",  # Sky Blue
        "#F0E68C",  # Khaki
        "#FFA07A",  # Light Salmon
        "#98FB98",  # Pale Green
        "#D3D3D3",  # Light Gray
    ]

    fig = px.pie(df_filtered, names=names_col, values=values_col, title=title, color_discrete_sequence=colors)

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Amount: $%{value:,.2f}<br>Percentage: %{percent}<extra></extra>",
    )

    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01),
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig
