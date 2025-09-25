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
    fig.update_layout(yaxis_title=_label(column))
    return fig
